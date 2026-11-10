"""Оновлює матрицю простежуваності `plan/traceability.md`: додає вимоги адендумів і колонки
«Реалізація» та «Тести», згенеровані з коду. Ланцюжок SRS (розд. 1.4):
вимога → критерій прийняття → тест → реалізація.

    python tests/update_traceability.py

Запуск ідемпотентний: перші сім колонок зберігаються, останні дві перераховуються.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8")
from verify_requirements import requirements_by_test  # noqa: E402

MATRIX = ROOT / "plan" / "traceability.md"
# Вимоги адендумів лаб. №5: тікети LS-41…50 не мають GitHub Issues (`plan/issue-map.md`).
ADDED = {
    "REQ-F-051": ("A1", "LS-42", "LS-43", "LS-44", "LS-45, LS-37", "`createLoan`"),
    "REQ-F-052": ("A2", "LS-47", "LS-48", "LS-49", "LS-50, LS-37", "`listReaderRecommendations`"),
}

DOC_SECTIONS = {
    "G1": "[api-reference.md](docs/api-reference.md#4-довідник-жанрів), [user-guide.md](docs/user-guide.md#3-сценарій-2-пошук-літератури-в-електронному-каталозі)",
    "G2": "[api-reference.md](docs/api-reference.md#3-акаунти-персоналу-бібліотеки), [user-guide.md](docs/user-guide.md#8-сценарій-7-адміністрування-та-аналітичні-звіти)",
    "G3": "[api-reference.md](docs/api-reference.md#2-управління-читачами-та-реєстрація), [user-guide.md](docs/user-guide.md#2-сценарій-1-реєстрація-активація-та-вхід-читача)",
    "G4": "[api-reference.md](docs/api-reference.md#1-автентифікація-та-сесії), [user-guide.md](docs/user-guide.md#2-сценарій-1-реєстрація-активація-та-вхід-читача)",
    "G5": "[api-reference.md](docs/api-reference.md#13-аудит-лог-дій-користувачів), [user-guide.md](docs/user-guide.md#8-сценарій-7-адміністрування-та-аналітичні-звіти)",
    "G6": "[api-reference.md](docs/api-reference.md#7-обіг-фонду-видача-та-повернення), [user-guide.md](docs/user-guide.md#5-сценарій-4-видача-та-повернення-книги-робота-бібліотекаря)",
    "G7": "[api-reference.md](docs/api-reference.md#8-онлайн-бронювання-та-черга), [user-guide.md](docs/user-guide.md#4-сценарій-3-бронювання-та-черга-очікування)",
    "G8": "[api-reference.md](docs/api-reference.md#9-штрафи-та-облік-оплат), [user-guide.md](docs/user-guide.md#6-сценарій-5-штрафи-за-прострочення-та-їх-оплата)",
    "G9": "[api-reference.md](docs/api-reference.md#5-каталог-видань-та-пошук), [user-guide.md](docs/user-guide.md#3-сценарій-2-пошук-літератури-в-електронному-каталозі)",
    "G10": "[api-reference.md](docs/api-reference.md#12-аналітичні-звіти-бібліотеки), [user-guide.md](docs/user-guide.md#8-сценарій-7-адміністрування-та-аналітичні-звіти)",
    "G11": "[api-reference.md](docs/api-reference.md#10-персональні-рекомендації), [user-guide.md](docs/user-guide.md#7-сценарій-6-кабінет-читача--сповіщення-та-рекомендації)",
    "G12": "[api-reference.md](docs/api-reference.md#11-внутрішні-сповіщення-читача), [user-guide.md](docs/user-guide.md#7-сценарій-6-кабінет-читача--сповіщення-та-рекомендації)",
    "G13": "[stack.md](docs/stack.md), [README.md](README.md), [coding-convention.md](docs/coding-convention.md)",
    "A1": "[api-reference.md](docs/api-reference.md#7-обіг-фонду-видача-та-повернення), [user-guide.md](docs/user-guide.md#5-сценарій-4-видача-та-повернення-книги-робота-бібліотекаря)",
    "A2": "[api-reference.md](docs/api-reference.md#10-персональні-рекомендації), [user-guide.md](docs/user-guide.md#7-сценарій-6-кабінет-читача--сповіщення-та-рекомендації)",
}
# Вимоги без власної операції API або з логікою поза маршрутом — місце реалізації вказано явно.
EXTRA_IMPLEMENTATION = {
    "REQ-F-009": ["app.py"], "REQ-F-025": ["circulation.py"], "REQ-F-026": ["circulation.py"],
    "REQ-F-027": ["circulation.py"], "REQ-F-028": ["circulation.py"], "REQ-F-029": ["circulation.py"],
    "REQ-F-035": ["notifications.py"], "REQ-F-036": ["notifications.py"], "REQ-F-037": ["notifications.py"],
    "REQ-F-048": ["routers/auth.py"], "REQ-F-051": ["circulation.py"], "REQ-F-049": ["audit.py"],
    "REQ-NF-001": ["app.py (журнал запитів)"], "REQ-NF-002": ["backup.py"], "REQ-NF-003": ["security.py"],
    "REQ-NF-005": ["logging_setup.py", "app.py"],
}
NO_AUTOMATED_TEST = {"REQ-F-022": "скасовано (LS-40)", "REQ-NF-004": "перевіряє людина (`logs/validation.md`)"}


def operation_modules() -> dict[str, str]:
    """operationId контракту → файл маршруту, у якому реалізовано (метод, шлях)."""
    spec = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
    by_route = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in ("get", "post", "put", "patch", "delete"):
                by_route[(method, re.sub(r"\{[^}]+\}", "{}", path))] = op["operationId"]
    found = {}
    for source in sorted((ROOT / "src" / "library" / "routers").glob("*.py")):
        for method, path in re.findall(r'@router\.(get|post|put|patch|delete)\("([^"]+)"', source.read_text(encoding="utf-8")):
            operation = by_route.get((method, re.sub(r"\{[^}]+\}", "{}", path)))
            if operation:
                found[operation] = f"routers/{source.name}"
    return found, by_route.values()


def main():
    modules, _ = operation_modules()
    spec = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
    ops_of = defaultdict(list)
    for item in spec["paths"].values():
        for method, op in item.items():
            if method in ("get", "post", "put", "patch", "delete"):
                for req in op["x-req-ids"]:
                    ops_of[req].append(op["operationId"])
    tests_of = defaultdict(set)
    for test, reqs in requirements_by_test().items():
        for req in reqs:
            tests_of[req].add(test.split("::")[0] + ".py")

    lines = MATRIX.read_text(encoding="utf-8").split("\n")
    header_at = next(i for i, l in enumerate(lines) if l.startswith("| ID вимоги |"))
    rows, tail = [], []
    for line in lines[header_at + 2:]:
        if line.startswith("| **REQ-"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")][:7])
        elif rows:
            tail.append(line)
    present = {r[0].strip("*") for r in rows}
    for req, (group, test, gate, feature, verification, operation) in ADDED.items():
        if req not in present:
            rows.append([f"**{req}**", group, test, gate, feature, verification, operation])
    rows.sort(key=lambda r: (r[0].strip("*").startswith("REQ-NF"), r[0]))

    out = []
    for row in rows:
        req = row[0].strip("*")
        group = row[1].strip()
        impl = sorted({modules[o] for o in ops_of.get(req, []) if o in modules} | set(EXTRA_IMPLEMENTATION.get(req, [])))
        if req in NO_AUTOMATED_TEST and not impl:
            impl_cell = "— (не реалізується)" if req == "REQ-F-022" else "— (веб-інтерфейсу немає)"
        else:
            impl_cell = ", ".join(f"`{m}`" for m in impl) or "—"
        test_cell = ", ".join(f"`{t}`" for t in sorted(tests_of.get(req, []))) or NO_AUTOMATED_TEST.get(req, "—")
        doc_cell = DOC_SECTIONS.get(group, "—")
        out.append("| " + " | ".join(row[:6] + [row[6], impl_cell, test_cell, doc_cell]) + " |")

    head = lines[:header_at]
    text = "\n".join(head) + "\n| ID вимоги | Група | Test | Gate | Feature | Verification | API operation | Реалізація | Тести | Документація |\n"
    text += "|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(out) + "\n" + "\n".join(tail).rstrip("\n") + "\n"
    MATRIX.write_text(text, encoding="utf-8")
    print(f"Оновлено {MATRIX.relative_to(ROOT)}: {len(out)} вимог")


if __name__ == "__main__":
    main()
