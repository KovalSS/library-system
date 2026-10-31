"""Схеми вводу й перетворення моделей на відповіді за контрактом `spec/openapi.yaml`."""
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


def iso(moment) -> str:
    return moment.isoformat().replace("+00:00", "Z") if moment.tzinfo else moment.isoformat() + "Z"


def account_out(account: Account) -> dict:
    return {"id": account.id, "fullName": account.full_name, "email": account.email,
            "role": account.role, "active": account.active, "createdAt": iso(account.created_at)}


Role = Literal["reader", "librarian", "admin", "chief_admin"]
