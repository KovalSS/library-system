"""Генератор вичерпного API-довідника `docs/api-reference.md` з `spec/openapi.yaml`."""
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "api-reference.md"

ROLE_NAMES = {
    "public": "Публічний (без авторизації)",
    "reader": "Читач (`reader`)",
    "librarian": "Бібліотекар (`librarian`)",
    "admin": "Адміністратор (`admin`)",
    "chief_admin": "Головний адміністратор (`chief_admin`)",
}

SECTION_MAP = {
    "auth": "1. Автентифікація та сесії",
    "readers": "2. Управління читачами та реєстрація",
    "accounts": "3. Акаунти персоналу бібліотеки",
    "genres": "4. Довідник жанрів",
    "editions": "5. Каталог видань та пошук",
    "copies": "6. Облік фізичних екземплярів фонду",
    "loans": "7. Обіг фонду: видача та повернення",
    "reservations": "8. Онлайн-бронювання та черга",
    "fines": "9. Штрафи та облік оплат",
    "recommendations": "10. Персональні рекомендації",
    "notifications": "11. Внутрішні сповіщення читача",
    "reports": "12. Аналітичні звіти бібліотеки",
    "audit": "13. Аудит-лог дій користувачів",
}


def deref(node):
    if isinstance(node, dict) and "$ref" in node:
        target = SPEC
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return deref(target)
    return node


def classify(path: str) -> str:
    if path.startswith("/auth"):
        return "auth"
    if path in ("/readers", "/email-confirmations") or (path.startswith("/readers/{") and path.endswith("}")):
        return "readers"
    if path.startswith("/administrators") or path.startswith("/librarians"):
        return "accounts"
    if path.startswith("/genres"):
        return "genres"
    if path.startswith("/editions") and "/copies" not in path:
        return "editions"
    if "/copies" in path or path.startswith("/copies"):
        return "copies"
    if "/loans" in path:
        return "loans"
    if "/reservations" in path:
        return "reservations"
    if "/fines" in path or "/fine-payments" in path:
        return "fines"
    if "/recommendations" in path:
        return "recommendations"
    if "/notifications" in path:
        return "notifications"
    if path.startswith("/reports"):
        return "reports"
    if path.startswith("/audit"):
        return "audit"
    return "other"


def main():
    lines = [
        "# Довідник REST API Бібліотечної системи",
        "",
        "Цей документ є повним технічним довідником реалізованого REST API "
        "(контракт `spec/openapi.yaml`, версія 1.0.0). Він описує всі 38 операцій API, "
        "їхні параметри, авторизаційні вимоги (RBAC), формати відповідей та зв'язок "
        "із вимогами SRS (`spec/srs.md`).",
        "",
        "## Загальні конвенції взаємодії",
        "",
        "* **Базовий URI:** `http://127.0.0.1:8000` (локально) або відносний `/` при роботі через зворотний проксі.",
        "* **Інтерактивна документація (Swagger UI):** доступна за адресою `http://127.0.0.1:8000/docs`.",
        "* **Формат обміну даними:** `application/json; charset=utf-8` (для аналітичних звітів підтримується `text/csv`).",
        "* **Автентифікація:** передача Bearer токена в HTTP-заголовку `Authorization: Bearer <token>`.",
        "* **Ідентифікатори:** валідні рядки UUID v4 (36 символів).",
        "* **Часові мітки:** формат ISO 8601 UTC (наприклад, `2026-10-31T12:00:00Z`).",
        "* **Грошові суми:** десяткові числа в гривнях (UAH), заокруглення до копійок.",
        "* **Єдина модель помилки (`Error`):**",
        "  ```json",
        "  {",
        '    "code": "reader_has_debt",',
        '    "message": "У читача є прострочена видача або несплачений штраф.",',
        '    "requestId": "req-9b87f2e1a4c0"',
        "  }",
        "  ```",
        "",
        "---",
        "",
        "## Зміст",
        "",
    ]

    grouped = {k: [] for k in SECTION_MAP}
    for path, methods in SPEC.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                cat = classify(path)
                grouped[cat].append((method.upper(), path, op))

    for cat_key, cat_title in SECTION_MAP.items():
        anchor = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁіІїЇєЄґҐ]+", "-", cat_title.lower()).strip("-")
        lines.append(f"- [{cat_title}](#{anchor})")

    lines.append("")
    lines.append("---")
    lines.append("")

    for cat_key, cat_title in SECTION_MAP.items():
        ops = grouped[cat_key]
        if not ops:
            continue
        lines.append(f"## {cat_title}")
        lines.append("")

        for method, path, op in ops:
            op_id = op.get("operationId", "")
            summary = op.get("summary", "")
            desc = op.get("description", "")
            reqs = op.get("x-req-ids", [])
            roles = op.get("x-roles", [])
            params = op.get("parameters", [])
            body = op.get("requestBody", {})
            responses = op.get("responses", {})

            lines.append(f"### `{method} {path}`")
            lines.append(f"**ID операції:** `{op_id}`  ")
            lines.append(f"**Короткий опис:** {summary}  ")
            lines.append(f"**Вимоги SRS:** {', '.join(f'`{r}`' for r in reqs) if reqs else '—'}  ")
            roles_str = ", ".join(ROLE_NAMES.get(r, r) for r in roles) if roles else "Будь-яка"
            lines.append(f"**Дозволені ролі (RBAC):** {roles_str}  ")
            lines.append("")
            if desc:
                lines.append(f"> {desc}")
                lines.append("")

            # Параметри
            if params:
                lines.append("#### Параметри запиту:")
                lines.append("| Назва | Розташування | Тип | Обов'язковий | Опис |")
                lines.append("|---|---|---|---|---|")
                for p_raw in params:
                    p = deref(p_raw)
                    name = p.get("name", "")
                    in_ = p.get("in", "")
                    schema = p.get("schema", {})
                    ptype = schema.get("type", "string")
                    pfmt = schema.get("format", "")
                    req = "Так" if p.get("required") else "Ні"
                    pdesc = p.get("description", "—")
                    t_str = f"{ptype} ({pfmt})" if pfmt else ptype
                    lines.append(f"| `{name}` | `{in_}` | `{t_str}` | {req} | {pdesc} |")
                lines.append("")

            # Тіло запиту
            if body:
                body_deref = deref(body)
                content = body_deref.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                lines.append("#### Тіло запиту (`application/json`):")
                if "$ref" in schema:
                    ref_name = schema["$ref"].split("/")[-1]
                    lines.append(f"Схема: `{ref_name}`")
                elif schema.get("type"):
                    lines.append(f"Тип: `{schema.get('type')}`")
                lines.append("")

            # Відповіді
            lines.append("#### Коди відповідей:")
            lines.append("| Код | Опис | Схема відповіді |")
            lines.append("|---|---|---|")
            for code, resp_raw in sorted(responses.items()):
                resp = deref(resp_raw)
                r_desc = resp.get("description", "").strip() or "Успішно"
                r_content = resp.get("content", {})
                r_schema = "—"
                if "application/json" in r_content:
                    s_raw = r_content["application/json"].get("schema", {})
                    if "$ref" in s_raw:
                        r_schema = f"`{s_raw['$ref'].split('/')[-1]}`"
                    elif s_raw.get("type") == "array":
                        item_ref = s_raw.get("items", {}).get("$ref", "")
                        r_schema = f"Масив `{item_ref.split('/')[-1]}`" if item_ref else "Масив"
                    else:
                        r_schema = f"`{s_raw.get('type', 'object')}`"
                elif "text/csv" in r_content:
                    r_schema = "`text/csv`"
                lines.append(f"| `{code}` | {r_desc} | {r_schema} |")
            lines.append("")
            lines.append("---")
            lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {OUT} successfully!")


if __name__ == "__main__":
    main()
