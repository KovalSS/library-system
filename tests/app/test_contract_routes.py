"""Верифікація контракту: реалізація має рівно ті операції, що затверджено в `spec/openapi.yaml`.

Страховка для рефакторингу (крок 3 лаби): перейменування чи перенесення маршрутів
не повинно непомітно додати, прибрати чи змінити операцію API.
"""
import re

import yaml

from contract import SPEC_PATH

METHODS = ("get", "post", "put", "patch", "delete")


def operations(spec):
    """Множина (метод, шлях) з опису OpenAPI; імена параметрів шляху не важливі."""
    return {(method.upper(), re.sub(r"\{[^}]+\}", "{}", path))
            for path, item in spec["paths"].items() for method in item if method in METHODS}


def contract_operations():
    return operations(yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")))


def implemented_operations(app):
    # Опис, який FastAPI будує з реально підключених маршрутів.
    return operations(app.openapi())


def test_implemented_operations_are_found(app):
    # Захист від «порожнього» проходження: якщо маршрути не знайдено, решта тестів нічого не доводить.
    assert len(implemented_operations(app)) >= 38


def test_every_contract_operation_is_implemented(app):
    missing = contract_operations() - implemented_operations(app)

    assert not missing, f"операції контракту без реалізації: {sorted(missing)}"


def test_no_operation_outside_contract(app):
    extra = implemented_operations(app) - contract_operations()

    assert not extra, f"операції поза контрактом: {sorted(extra)}"
