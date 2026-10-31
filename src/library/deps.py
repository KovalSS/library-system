"""Залежності запиту: сесія БД, годинник, поточний користувач і перевірка ролі."""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from library.db import AccessToken, Account
from library.errors import ApiError, forbidden

ADMIN_ROLES = ("admin", "chief_admin")
STAFF_ROLES = ("librarian", "admin", "chief_admin")


def get_session(request: Request):
    with request.app.state.sessions() as session:
        yield session


def get_clock(request: Request):
    return request.app.state.clock


def current_account(request: Request, session: Session = Depends(get_session)) -> Account:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme != "Bearer" or not token:
        raise ApiError(401, "unauthorized", "Потрібна автентифікація.")
    found = session.get(AccessToken, token)
    account = session.get(Account, found.account_id) if found else None
    # Токен деактивованого акаунта перестає діяти (REQ-F-012, 014).
    if account is None or not account.active:
        raise ApiError(401, "unauthorized", "Потрібна автентифікація.")
    return account


def require(*roles: str):
    def check(account: Account = Depends(current_account)) -> Account:
        if account.role not in roles:
            raise forbidden()
        return account
    return check
