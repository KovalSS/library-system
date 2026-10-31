"""Фабрика застосунку FastAPI.

Зовнішній інтерфейс визначає затверджений контракт `spec/openapi.yaml`;
маршрути додаються лише разом із тестами (TDD, SRS розд. 1.4).
"""
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from library.logging_setup import LOGGER_NAME, configure_logging, request_id_var

DEFAULT_LOG_FILE = Path("var/log/library.log")

http_log = logging.getLogger(f"{LOGGER_NAME}.http")


def create_app(log_file: Path = DEFAULT_LOG_FILE) -> FastAPI:
    configure_logging(log_file)
    app = FastAPI(title="Library System API", version="1.0.0")

    @app.middleware("http")
    async def log_every_request(request: Request, call_next):
        token = request_id_var.set(f"req-{uuid.uuid4().hex[:12]}")
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                http_log.exception("Необроблена помилка: %s %s", request.method, request.url.path)
                response = JSONResponse(
                    status_code=500,
                    content={"message": "Внутрішня помилка сервера.", "requestId": request_id_var.get()},
                )
            elapsed_ms = (time.perf_counter() - started) * 1000
            http_log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
            return response
        finally:
            request_id_var.reset(token)

    return app
