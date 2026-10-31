"""Схеми вводу й перетворення моделей на відповіді за контрактом `spec/openapi.yaml`."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from library.db import Account

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class NonEmptyPatch(BaseModel):
    """PATCH-тіло має містити хоча б одне поле (`minProperties: 1` у контракті)."""

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Потрібне хоча б одне поле.")
        return self


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=1)


class AccountInput(BaseModel):
    fullName: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=8, max_length=128)


class AccountUpdate(NonEmptyPatch):
    fullName: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, pattern=EMAIL)
    active: bool | None = None


class ReaderRegistration(BaseModel):
    fullName: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL)
    phone: str = Field(pattern=r"^\+?[0-9]{10,15}$")
    birthDate: date
    password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str = Field(pattern=EMAIL)


class PasswordReset(BaseModel):
    token: str = Field(min_length=1)
    newPassword: str = Field(min_length=8, max_length=128)


class TokenBody(BaseModel):
    token: str = Field(min_length=1)


def iso(moment) -> str:
    return moment.isoformat().replace("+00:00", "Z") if moment.tzinfo else moment.isoformat() + "Z"


def account_out(account: Account) -> dict:
    return {"id": account.id, "fullName": account.full_name, "email": account.email,
            "role": account.role, "active": account.active, "createdAt": iso(account.created_at)}


def page_out(items: list, page: int, page_size: int, total: int) -> dict:
    return {"items": items, "page": page, "pageSize": page_size, "total": total}


def reader_out(account: Account) -> dict:
    return {"id": account.id, "fullName": account.full_name, "email": account.email, "phone": account.phone,
            "birthDate": account.birth_date, "status": "active" if account.active else "pending_confirmation",
            "registeredAt": iso(account.created_at)}


Role = Literal["reader", "librarian", "admin", "chief_admin"]
