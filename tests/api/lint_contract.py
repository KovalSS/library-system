"""Автоматична валідація контракту (лише Python): структура OpenAPI + правила API-GATE.

    python tests/api/lint_contract.py

1. openapi-spec-validator: відповідність специфікації стандарту OpenAPI 3.1.
2. Правила проєкту (критерії API-GATE 1, 4, 5):
   * кожна операція має operationId (унікальний), summary, description, x-req-ids
     (формат REQ-F-NNN / REQ-NF-NNN, ID існує в SRS), x-roles і відповідь 4xx;
   * відповіді помилок посилаються на єдину схему Error;
   * усі приклади (example/examples) відповідають своїм схемам;
   * кожна вимога SRS, окрім відомих винятків, має операцію.
"""
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
METHODS = ("get", "post", "put", "patch", "delete")
ROLES = {"public", "reader", "librarian", "admin", "chief_admin"}
# Вимоги без операції API (обґрунтування - docs/api-design.md, розд. 1).
NOT_AN_OPERATION = {"REQ-F-022", "REQ-NF-001", "REQ-NF-002", "REQ-NF-005"}

raw = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
validate(raw)
print("openapi-spec-validator: специфікація відповідає OpenAPI", raw["openapi"])

srs = (ROOT / "spec" / "srs.md").read_text(encoding="utf-8")
known = set(re.findall(r"\*\*(REQ-(?:F|NF)-\d{3})\*\*", srs))
errors = []


def resolve(node):
    if isinstance(node, dict) and "$ref" in node:
        target = raw
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return resolve(target)
    return node


def deref(node):
    if isinstance(node, dict):
        if "$ref" in node:
            return deref(resolve(node))
        return {k: deref(v) for k, v in node.items()}
    if isinstance(node, list):
        return [deref(v) for v in node]
    return node


def check_examples(media, where):
    schema = media.get("schema")
    if schema is None:
        return
    validator = Draft202012Validator(deref(schema), format_checker=FormatChecker())
    examples = []
    if "example" in media:
        examples.append(("example", media["example"]))
    for key, ex in media.get("examples", {}).items():
        examples.append((f"examples.{key}", ex.get("value")))
    for label, value in examples:
        for err in validator.iter_errors(value):
            errors.append(f"{where} {label}: {err.message}")


# --- загальні відомості
if not raw["info"].get("contact"):
    errors.append("info: немає contact")

# --- відповіді помилок посилаються на Error
for name, resp in raw["components"]["responses"].items():
    schema = resp.get("content", {}).get("application/json", {}).get("schema", {})
    if schema.get("$ref") != "#/components/schemas/Error":
        errors.append(f"components.responses.{name}: має посилатися на схему Error")

# --- операції
seen_ids, covered = set(), set()
for path, item in raw["paths"].items():
    for method in METHODS:
        op = item.get(method)
        if not op:
            continue
        name = f"{method.upper()} {path}"
        op_id = op.get("operationId")
        if not op_id:
            errors.append(f"{name}: немає operationId")
        elif op_id in seen_ids:
            errors.append(f"{name}: operationId {op_id} повторюється")
        seen_ids.add(op_id)
        for field in ("summary", "description"):
            if not op.get(field):
                errors.append(f"{name}: немає {field}")
        reqs = op.get("x-req-ids") or []
        if not reqs:
            errors.append(f"{name}: немає x-req-ids")
        for req in reqs:
            if not re.fullmatch(r"REQ-(F|NF)-\d{3}", req):
                errors.append(f"{name}: некоректний формат {req}")
            elif req not in known:
                errors.append(f"{name}: {req} відсутня в SRS")
            covered.add(req)
        roles = op.get("x-roles") or []
        if not roles or set(roles) - ROLES:
            errors.append(f"{name}: x-roles порожні або містять невідому роль")
        if not any(code in op["responses"] for code in ("400", "401", "404")):
            errors.append(f"{name}: немає жодної відповіді 4xx")
        for code, resp in op["responses"].items():
            for ctype, media in resolve(resp).get("content", {}).items():
                check_examples(media, f"{name} {code} {ctype}")
        media = resolve(op.get("requestBody", {})).get("content", {}).get("application/json")
        if media:
            check_examples(media, f"{name} requestBody")

missing = sorted(known - covered - NOT_AN_OPERATION)
if missing:
    errors.append("вимоги без операції API: " + ", ".join(missing))

if errors:
    print("\n".join(f"ПОМИЛКА: {e}" for e in errors))
    sys.exit(1)
print(f"Правила проєкту виконано. Операцій: {len(seen_ids)}; "
      f"вимог SRS, пов'язаних з операціями: {len(covered)}; винятків: {len(NOT_AN_OPERATION)}")
