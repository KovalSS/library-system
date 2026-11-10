"""Перевірка відповідності API-документації (`docs/api-reference.md`) фактичному коду та контракту (Крок 9)."""
import re
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fastapi.openapi.utils import get_openapi
from library.app import create_app
DOC_PATH = ROOT / "docs" / "api-reference.md"
SPEC_PATH = ROOT / "spec" / "openapi.yaml"

doc_text = DOC_PATH.read_text(encoding="utf-8")
spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
app = create_app()

# Отримуємо всі операції з docs/api-reference.md
doc_operations = re.findall(r"### `(GET|POST|PUT|PATCH|DELETE) ([^`]+)`\s*\n\*\*ID операції:\*\* `([^`]+)`", doc_text)

print(f"Знайдено операцій у документації docs/api-reference.md: {len(doc_operations)}")
assert len(doc_operations) == 38, f"Очікувалось 38 операцій у довіднику, знайдено {len(doc_operations)}"

# Отримуємо маршрути, які FastAPI будує з коду
api_spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
app_routes = set()
for path, item in api_spec.get("paths", {}).items():
    for method in item:
        if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            norm = re.sub(r"\{[^}]+\}", "{}", path)
            app_routes.add((method.upper(), norm))

errors = []
for method, path, op_id in doc_operations:
    norm_path = re.sub(r"\{[^}]+\}", "{}", path)
    if (method, norm_path) not in app_routes:
        errors.append(f"Маршрут із документації {method} {path} ({op_id}) відсутній у коді FastAPI!")

    # Перевірка наявності в OpenAPI
    spec_op = spec.get("paths", {}).get(path, {}).get(method.lower())
    if not spec_op:
        errors.append(f"Маршрут {method} {path} відсутній у spec/openapi.yaml!")
    elif spec_op.get("operationId") != op_id:
        errors.append(f"Невідповідність operationId: doc={op_id}, spec={spec_op.get('operationId')}")

if errors:
    print("Знайдено помилки невідповідності документації коду:")
    for err in errors:
        print("  -", err)
    sys.exit(1)
else:
    print("Усі 38 операцій з документації повністю відповідають фактичному коду та контракту!")
