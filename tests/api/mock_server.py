"""Mock API, що працює виключно за OpenAPI-специфікацією (без бізнес-логіки).

    python tests/api/mock_server.py [--port 4010] [--spec spec/openapi.yaml]

Це не реалізація системи: сервер не зберігає стан і нічого не обчислює. Він
лише відтворює контракт, як це роблять mock-інструменти на кшталт Prism:

* знаходить операцію за методом і шляхом (шаблони `/loans/{loanId}`);
* перевіряє автентифікацію (`security`) -> 401;
* перевіряє параметри запиту/шляху та тіло за схемою -> 400;
* повертає приклад із контракту: найменшу 2xx-відповідь або ту, яку просить
  заголовок `Prefer: code=NNN`; `Prefer: example=ключ` вибирає іменований приклад;
* підтримує узгодження вмісту за `Accept` (JSON / CSV);
* додає заголовки, оголошені у відповіді (напр., `Retry-After`).
"""
import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
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


class Contract:
    def __init__(self, path):
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self.spec = deref(raw, raw)
        self.routes = []  # (regex, template, method, operation, path-level parameters)
        for template, item in self.spec["paths"].items():
            regex = re.compile("^" + re.sub(r"\{[^}]+\}", "([^/]+)", template) + "$")
            for method in METHODS:
                if method in item:
                    self.routes.append((regex, template, method.upper(), item[method], item.get("parameters", [])))

    def find(self, method, path):
        known_path = False
        for regex, template, m, op, shared in self.routes:
            match = regex.match(path)
            if match:
                known_path = True
                if m == method:
                    names = re.findall(r"\{([^}]+)\}", template)
                    return op, shared, dict(zip(names, match.groups())), True
        return None, None, None, known_path


def coerce(value, schema):
    """Рядок query/path -> значення типу зі схеми, щоб перевірити його схемою."""
    kind = schema.get("type")
    try:
        if kind == "integer":
            return int(value)
        if kind == "number":
            return float(value)
        if kind == "boolean":
            if value in ("true", "false"):
                return value == "true"
            return value
    except ValueError:
        return value
    return value


def check_value(value, schema, name, where, problems):
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for err in validator.iter_errors(value):
        problems.append(f"{where} {name}: {err.message}")


def validate_request(op, shared, path_values, query, body_bytes, content_type):
    problems = []
    params = {(p["in"], p["name"]): p for p in shared}
    params.update({(p["in"], p["name"]): p for p in op.get("parameters", [])})
    for (where, name), p in params.items():
        schema = p.get("schema", {})
        if where == "path":
            check_value(coerce(path_values[name], schema), schema, name, "path", problems)
        elif where == "query":
            if name in query:
                check_value(coerce(query[name][0], schema), schema, name, "query", problems)
            elif p.get("required"):
                problems.append(f"query {name}: обов'язковий параметр відсутній")
    body = op.get("requestBody")
    if body:
        schema = body.get("content", {}).get("application/json", {}).get("schema")
        if not body_bytes:
            if body.get("required"):
                problems.append("body: обов'язкове тіло відсутнє")
        elif schema is not None:
            if "application/json" not in (content_type or ""):
                problems.append("body: очікується Content-Type application/json")
            else:
                try:
                    check_value(json.loads(body_bytes), schema, "", "body", problems)
                except json.JSONDecodeError:
                    problems.append("body: некоректний JSON")
    return problems


def pick_media(content, accept):
    """Вибір типу вмісту відповіді за заголовком Accept."""
    wanted = [a.split(";")[0].strip() for a in (accept or "*/*").split(",")]
    for w in wanted:
        if w in content:
            return w
    if any(w in ("*/*", "application/*") for w in wanted) or not wanted:
        return "application/json" if "application/json" in content else next(iter(content))
    return None


def pick_example(media, name):
    if name and "examples" in media:
        return media["examples"].get(name, {}).get("value")
    if "example" in media:
        return media["example"]
    if "examples" in media:
        return next(iter(media["examples"].values()))["value"]
    return None


def error_status(op, status):
    return str(status) if str(status) in op["responses"] else None


class Handler(BaseHTTPRequestHandler):
    contract = None

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")

    def reply(self, status, op, response, example_name=None):
        content = response.get("content", {})
        body, ctype = b"", None
        if content and status != 204:
            ctype = pick_media(content, self.headers.get("Accept"))
            if ctype is None:
                status, body = 406, b""
            else:
                example = pick_example(content[ctype], example_name)
                body = (example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)).encode()
        self.send_response(status)
        if ctype and body:
            self.send_header("Content-Type", ctype)
        for name, header in response.get("headers", {}).items():
            self.send_header(name, "900" if header.get("schema", {}).get("type") == "integer" else "demo")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def handle_any(self):
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        op, shared, path_values, known = self.contract.find(self.command, url.path)
        if op is None:
            self.send_response(405 if known else 404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        security = op.get("security", self.contract.spec.get("security", []))
        if security and not (self.headers.get("Authorization") or "").startswith("Bearer "):
            response = op["responses"].get("401")
            return self.reply(401, op, response or {})

        problems = validate_request(op, shared, path_values, parse_qs(url.query), raw, self.headers.get("Content-Type"))
        if problems and error_status(op, 400):
            self.send_header_violations(problems)
            return self.reply(400, op, op["responses"]["400"])

        prefer = dict(re.findall(r"(\w+)=([^,;\s]+)", self.headers.get("Prefer", "")))
        if "code" in prefer:
            if prefer["code"] not in op["responses"]:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = prefer["code"]
        else:
            code = min(c for c in op["responses"] if c.startswith("2"))
        self.reply(int(code), op, op["responses"][code], prefer.get("example"))

    def send_header_violations(self, problems):
        # Деталі порушень показуються лише в журналі сервера .
        sys.stderr.write("  порушення запиту: " + "; ".join(problems) + "\n")

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4010)
    parser.add_argument("--spec", default=str(ROOT / "spec" / "openapi.yaml"))
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    Handler.contract = Contract(args.spec)
    print(f"Mock API за {args.spec}: http://127.0.0.1:{args.port} (операцій: {len(Handler.contract.routes)})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
