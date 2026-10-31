"""Фабрика застосунку FastAPI.

Зовнішній інтерфейс визначає затверджений контракт `spec/openapi.yaml`;
маршрути додаються лише разом із тестами (TDD, SRS розд. 1.4).
"""
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from library.db import Account, make_session_factory, to_db
from library.errors import install_error_handlers
from library.infrastructure import ChiefAdmin, Clock, FileOutbox, Mailer, SystemClock
from library.logging_setup import LOGGER_NAME, configure_logging, request_id_var
from library.routers import accounts, auth, readers
from library.security import hash_password

DEFAULT_LOG_FILE = Path("var/log/library.log")
DEFAULT_DATABASE_URL = "sqlite:///var/library.db"

http_log = logging.getLogger(f"{LOGGER_NAME}.http")


def default_chief_admin() -> ChiefAdmin:
    # Значення для локальної розробки; у розгортанні задаються змінними середовища.
    return ChiefAdmin(
        email=os.environ.get("LIBRARY_CHIEF_EMAIL", "chief@library.local"),
        password=os.environ.get("LIBRARY_CHIEF_PASSWORD", "Chief-Pass-2026"),
    )


def seed_chief_admin(sessions, chief: ChiefAdmin, clock: Clock) -> None:
    """Єдиний попередньо створений головний адміністратор (REQ-F-009)."""
    with sessions() as session:
        if session.scalar(select(Account).where(Account.role == "chief_admin")) is None:
            session.add(Account(email=chief.email, full_name=chief.full_name, role="chief_admin",
                                password_hash=hash_password(chief.password), created_at=to_db(clock.now())))
            session.commit()


def create_app(
    log_file: Path = DEFAULT_LOG_FILE,
    database_url: str = DEFAULT_DATABASE_URL,
    chief_admin: ChiefAdmin | None = None,
    mailer: Mailer | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    configure_logging(log_file)
    app = FastAPI(title="Library System API", version="1.0.0")
    app.state.database_url = database_url
    app.state.chief_admin = chief_admin or default_chief_admin()
    app.state.mailer = mailer or FileOutbox(Path("var/mail/outbox.jsonl"))
    app.state.clock = clock or SystemClock()
    if database_url.startswith("sqlite:///"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    app.state.sessions = make_session_factory(database_url)
    seed_chief_admin(app.state.sessions, app.state.chief_admin, app.state.clock)

    install_error_handlers(app)
    for module in (auth, accounts, readers):
        app.include_router(module.router)

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
