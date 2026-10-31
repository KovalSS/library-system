"""Перевірка відповідей застосунку за затвердженим контрактом `spec/openapi.yaml`."""
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SPEC_PATH = Path(__file__).resolve().parents[2] / "spec" / "openapi.yaml"


def _deref(node, root):
    if isinstance(node, dict):
        if "$ref" in node:
            target = root
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            return _deref(target, root)
        return {k: _deref(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [_deref(v, root) for v in node]
    return node


def _load_operations():
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    spec = _deref(raw, raw)
    return {
        op["operationId"]: op
        for item in spec["paths"].values()
        for method, op in item.items()
        if method in ("get", "post", "put", "patch", "delete")
    }


OPERATIONS = _load_operations()


def assert_contract(response, operation_id):
    """Статус, тип вмісту й тіло відповіді описані в контракті для цієї операції."""
    op = OPERATIONS[operation_id]
    status = str(response.status_code)
    assert status in op["responses"], f"{operation_id}: статус {status} не описаний у контракті ({response.text})"
    content = op["responses"][status].get("content")
    if not content:
        assert not response.content, f"{operation_id} {status}: контракт не передбачає тіла"
        return
    content_type = response.headers.get("content-type", "").split(";")[0]
    assert content_type in content, f"{operation_id} {status}: тип {content_type} не описаний"
    if content_type == "application/json":
        validator = Draft202012Validator(content[content_type]["schema"], format_checker=FormatChecker())
        errors = [e.message for e in validator.iter_errors(response.json())]
        assert not errors, f"{operation_id} {status}: тіло не відповідає схемі: {errors}"
