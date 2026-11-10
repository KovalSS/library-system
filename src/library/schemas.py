"""Схеми вводу й перетворення моделей на відповіді за контрактом `spec/openapi.yaml`."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from uuid import UUID

from library.db import Account, Copy, Edition, Genre

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
ISBN = r"^(?:[0-9]{9}[0-9X]|[0-9]{13})$"


class NonEmptyPatch(BaseModel):
    """PATCH-тіло має містити хоча б одне поле (`minProperties: 1` у контракті)."""

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Потрібне хоча б одне поле.")
        return self


class LoginRequest(BaseModel):
    """Схема вхідних даних для запиту входу в систему (/auth/login)."""
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=1)


class AccountInput(BaseModel):
    """Схема створення облікового запису персоналу (/administrators, /librarians)."""
    fullName: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=8, max_length=128)


class AccountUpdate(NonEmptyPatch):
    """Схема часткового оновлення облікового запису персоналу."""
    fullName: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, pattern=EMAIL)
    active: bool | None = None


class ReaderRegistration(BaseModel):
    """Схема даних для самостійної реєстрації читача (/readers)."""
    fullName: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL)
    phone: str = Field(pattern=r"^\+?[0-9]{10,15}$")
    birthDate: date
    password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    """Схема запиту на скидання пароля за адресою email."""
    email: str = Field(pattern=EMAIL)


class PasswordReset(BaseModel):
    """Схема встановлення нового пароля за одноразовим токеном."""
    token: str = Field(min_length=1)
    newPassword: str = Field(min_length=8, max_length=128)


class TokenBody(BaseModel):
    """Схема для передачі токена підтвердження пошти."""
    token: str = Field(min_length=1)


class GenreInput(BaseModel):
    """Схема створення чи оновлення літературного жанру."""
    name: str = Field(min_length=1, max_length=100)


class EditionInput(BaseModel):
    """Схема додавання нового бібліографічного видання до каталогу."""
    author: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    year: int = Field(ge=1000, le=2100)
    isbn: str = Field(pattern=ISBN)
    genreId: str
    price: Decimal = Field(ge=0)
    totalCopies: int = Field(ge=0)


class EditionUpdate(NonEmptyPatch):
    """Схема часткового оновлення полів видання."""
    author: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1000, le=2100)
    isbn: str | None = Field(default=None, pattern=ISBN)
    genreId: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    totalCopies: int | None = Field(default=None, ge=0)


class CopyInput(BaseModel):
    """Схема реєстрації нового фізичного екземпляра книги."""
    inventoryNumber: str = Field(min_length=1, max_length=50)
    location: str = Field(min_length=1, max_length=200)
    status: Literal["available", "damaged"] = "available"


class CopyUpdate(NonEmptyPatch):
    """Схема редагування розташування або статусу екземпляра."""
    location: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["available", "damaged"] | None = None


class LoanCreate(BaseModel):
    """Схема оформлення нової видачі книги читачу."""
    readerId: UUID
    copyId: UUID


class ReservationCreate(BaseModel):
    """Схема оформлення нового бронювання на видання."""
    editionId: UUID


class FinePaymentCreate(BaseModel):
    """Схема реєстрації оплати штрафу читачем."""
    method: Literal["cash", "card"]


LoanStatus = Literal["active", "returned", "compensated"]
ReservationStatus = Literal["ready", "queued", "fulfilled", "expired"]


def money(amount: Decimal) -> int | float:
    """Форматує десяткову грошову суму як ціле число або число з плаваючою крапкою для JSON."""
    return int(amount) if amount == int(amount) else float(amount)


def genre_out(genre: Genre) -> dict:
    """Перетворює модель Genre на словник схеми `Genre`."""
    return {"id": genre.id, "name": genre.name}


def edition_out(edition: Edition, genre: Genre, available: int, loans: int) -> dict:
    """Перетворює модель Edition на словник схеми `Edition` з додатковими лічильниками."""
    return {"id": edition.id, "author": edition.author, "title": edition.title, "year": edition.year,
            "isbn": edition.isbn, "genre": genre_out(genre), "price": money(edition.price),
            "totalCopies": edition.total_copies, "availableCopies": available, "loansCount": loans}


def copy_out(copy: Copy) -> dict:
    """Перетворює модель Copy на словник схеми `Copy`."""
    return {"id": copy.id, "editionId": copy.edition_id, "inventoryNumber": copy.inventory_number,
            "location": copy.location, "status": copy.status}


def iso(moment) -> str:
    """Форматує дату/час у стандартизований ISO 8601 рядок з суфіксом 'Z'."""
    return moment.isoformat().replace("+00:00", "Z") if moment.tzinfo else moment.isoformat() + "Z"


def account_out(account: Account) -> dict:
    """Перетворює обліковий запис співробітника на словник схеми `Account`."""
    return {"id": account.id, "fullName": account.full_name, "email": account.email,
            "role": account.role, "active": account.active, "createdAt": iso(account.created_at)}


def page_out(items: list, page: int, page_size: int, total: int) -> dict:
    """Формує стандартизовану пагіновану відповідь із метаданими."""
    return {"items": items, "page": page, "pageSize": page_size, "total": total}


def reader_out(account: Account) -> dict:
    """Перетворює акаунт читача на словник схеми `Reader`."""
    return {"id": account.id, "fullName": account.full_name, "email": account.email, "phone": account.phone,
            "birthDate": account.birth_date, "status": "active" if account.active else "pending_confirmation",
            "registeredAt": iso(account.created_at)}


Role = Literal["reader", "librarian", "admin", "chief_admin"]
