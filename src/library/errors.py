"""Єдина модель помилки API (`Error` у контракті) та відображення винятків на неї."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from library.logging_setup import request_id_var


class ApiError(Exception):
    """Базовий виняток бізнес-логіки та контракту API.

    Відображається на відповідь зі схемою `Error` у контракті OpenAPI.

    Attributes:
        status: HTTP статус-код відповіді (наприклад, 400, 403, 404, 409).
        code: Машиночитний код помилки (наприклад, 'reader_has_debt').
        message: Людиночитне повідомлення про помилку українською мовою.
        details: Опціональний список деталей валідації полів.
        headers: Опціональні HTTP-заголовки (наприклад, WWW-Authenticate).
    """

    def __init__(self, status: int, code: str, message: str, details=None, headers=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def not_found() -> ApiError:
    """Створює стандартну помилку 404 Not Found."""
    return ApiError(404, "not_found", "Ресурс не знайдено.")


def forbidden() -> ApiError:
    """Створює стандартну помилку 403 Forbidden (недостатньо прав)."""
    return ApiError(403, "forbidden", "Недостатньо прав для цієї дії.")


def validation_failed(field: str, issue: str) -> ApiError:
    """Створює помилку 400 Validation Failed для конкретного поля запиту."""
    return ApiError(400, "validation_failed", "Запит містить некоректні дані.", [{"field": field, "issue": issue}])


def error_response(status, code, message, details=None, headers=None):
    """Формує стандартизований JSONResponse відповідно до схеми `Error` контракту."""
    body = {"code": code, "message": message, "requestId": request_id_var.get()}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content=body, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    """Реєструє глобальні обробники винятків для застосунку FastAPI."""
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def request_invalid(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        # Некоректний ідентифікатор у шляху означає, що такого ресурсу немає (адендум A14).
        if any(e["loc"][0] == "path" for e in errors):
            return error_response(404, "not_found", "Ресурс не знайдено.")
        details = [{"field": _field_name(e["loc"]), "issue": e["msg"]} for e in errors]
        return error_response(400, "validation_failed", "Запит містить некоректні дані.", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return error_response(404, "not_found", "Ресурс не знайдено.")
        body = {"message": exc.detail, "requestId": request_id_var.get()}
        return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))


def _field_name(loc) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query")]
    return ".".join(parts) or "body"
