"""Фабрика застосунку FastAPI.

Зовнішній інтерфейс визначає затверджений контракт `spec/openapi.yaml`;
маршрути додаються лише разом із тестами (TDD, SRS розд. 1.4).
"""
from pathlib import Path

from fastapi import FastAPI

DEFAULT_LOG_FILE = Path("var/log/library.log")


def create_app(log_file: Path = DEFAULT_LOG_FILE) -> FastAPI:
    app = FastAPI(title="Library System API", version="1.0.0")
    return app
