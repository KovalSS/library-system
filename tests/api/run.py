"""Запуск сценаріїв проти mock API і перевірка відповідей за схемами OpenAPI.

    python tests/api/mock_server.py   # в одному терміналі
    python tests/api/run.py           # в іншому
    python tests/api/run.py --base http://127.0.0.1:4010 --report logs/api-scenarios-report.md
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from scenarios import SCENARIOS, TOKEN  # noqa: E402

SPEC_PATH = Path(__file__).resolve().parents[2] / "spec" / "openapi.yaml"
METHODS = ("get", "post", "put", "patch", "delete")


def deref(node, root):
    """Розгортає локальні $ref (у контракті немає циклічних посилань)."""
    if isinstance(node, dict):
        if "$ref" in node:
            target = root
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            return deref(target, root)
        return {k: deref(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [deref(v, root) for v in node]
    return node


def load_operations():
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    ops = {}
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                op = deref(item[method], spec)
                ops[op["operationId"]] = {"path": path, "method": method.upper(), "op": op}
    return ops


def path_matches(template, actual):
    pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
    return re.match(pattern, actual.split("?")[0]) is not None


def send(base, req):
    headers = {"Accept": req["accept"]}
    if req["auth"]:
        headers["Authorization"] = TOKEN
    data = None
    if req["body"] is not None:
        data = json.dumps(req["body"]).encode()
        headers["Content-Type"] = "application/json"
    if req["prefer"]:
        headers["Prefer"] = req["prefer"]
    request = urllib.request.Request(base + req["path"], data=data, headers=headers, method=req["method"])
    try:
        with urllib.request.urlopen(request) as res:
            return res.status, res.headers, res.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read().decode()


def run(s, operations, base):
    problems = []
    target = operations.get(s["op"])
    if target is None:
        return None, [f"operationId {s['op']} відсутній у контракті"]
    req = s["request"]
    if target["method"] != req["method"] or not path_matches(target["path"], req["path"]):
        problems.append(f"запит {req['method']} {req['path']} не збігається з {target['method']} {target['path']}")

    status, headers, raw = send(base, req)
    content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
    expect = s["expect"]
    if status != expect["status"]:
        problems.append(f"очікувався статус {expect['status']}, отримано {status}")

    # Відповідь має бути описана в контракті: статус, тип вмісту та схема.
    declared = target["op"]["responses"].get(str(status))
    if declared is None:
        problems.append(f"статус {status} не описаний у контракті для {s['op']}")
    elif raw:
        media = declared.get("content", {}).get(content_type)
        if media is None:
            problems.append(f"тип вмісту {content_type or '(порожній)'} не описаний для {s['op']} {status}")
        elif content_type == "application/json":
            validator = Draft202012Validator(media["schema"], format_checker=FormatChecker())
            for error in validator.iter_errors(json.loads(raw)):
                problems.append(f"тіло не відповідає схемі: {error.message}")
    if expect["content_type"] and content_type != expect["content_type"]:
        problems.append(f"очікувався Content-Type {expect['content_type']}, отримано {content_type}")
    for name in expect["headers"]:
        if name not in headers:
            problems.append(f"відсутній заголовок {name}")
    if expect["check"] and raw:
        body = json.loads(raw) if content_type == "application/json" else raw
        if not expect["check"](body):
            problems.append("перевірка змісту відповіді не пройдена")
    return status, problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:4010")
    parser.add_argument("--report")
    args = parser.parse_args()

    operations = load_operations()
    try:
        send(args.base, {"method": "GET", "path": "/genres", "body": None, "auth": True, "prefer": None, "accept": "application/json"})
    except urllib.error.URLError:
        print(f"Mock API недоступний на {args.base}. Запустіть: python tests/api/mock_server.py")
        return 2

    results = [(s, *run(s, operations, args.base)) for s in SCENARIOS]
    for s, status, problems in results:
        print(f"{'FAIL' if problems else 'ok  '} {s['id']}  {s['op']:<26} {status!s:<4} {s['title']}")
        for p in problems:
            print(f"       - {p}")

    def tally(kind):
        rows = [r for r in results if r[0]["kind"] == kind]
        return sum(1 for r in rows if not r[2]), len(rows)

    (pp, pt), (np_, nt) = tally("positive"), tally("negative")
    covered = {s["op"] for s, _, problems in results if not problems}
    uncovered = [op for op in operations if op not in covered]
    print(f"\nПозитивні: {pp}/{pt}; негативні: {np_}/{nt}")
    print(f"Операцій у контракті: {len(operations)}; охоплено успішними сценаріями: {len(covered)}")
    if uncovered:
        print("Без сценарію:", ", ".join(uncovered))

    if args.report:
        kind_ua = {"positive": "позитивний", "negative": "негативний"}
        lines = [
            "# Звіт про виконання сценаріїв проти mock API",
            "",
            "Контракт: `spec/openapi.yaml`; mock: `tests/api/mock_server.py`; сценарії: `tests/api/scenarios.py`; запуск: `python tests/api/run.py`.",
            "",
            "| ID | Тип | Операція | Статус | REQ-ID | BDD | Сценарій | Результат |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for s, status, problems in results:
            lines.append(
                f"| {s['id']} | {kind_ua[s['kind']]} | `{s['op']}` | {status} | {', '.join(s['req'])} "
                f"| {s['bdd'] or '—'} | {s['title']} | {'FAIL' if problems else 'OK'} |"
            )
        lines += [
            "",
            f"Позитивні: {pp}/{pt}; негативні: {np_}/{nt}.",
            f"Операцій у контракті: {len(operations)}; охоплено успішними сценаріями: {len(covered)}.",
            "Без сценарію: " + ", ".join(f"`{u}`" for u in uncovered) + "." if uncovered
            else "Усі операції охоплені хоча б одним сценарієм.",
            "",
        ]
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    return 1 if any(r[2] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
