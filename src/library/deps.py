"""Залежності запиту: сесія БД, годинник, поточний користувач і перевірка ролі."""
from datetime import date
from functools import partial

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from library.circulation import expire_reservations
from library.db import AccessToken, Account, to_db
from library.errors import ApiError, forbidden, not_found
from library.security import hash_password

ADMIN_ROLES = ("admin", "chief_admin")
STAFF_ROLES = ("librarian", "admin", "chief_admin")


def get_session(request: Request):
    """Генератор сесії бази даних із автоматичним виконанням регламентних дій за часом."""
    with request.app.state.sessions() as session:
        # Дії за часом (автоскасування броні, щодобова копія) виконуються при зверненні, без фонового завдання.
        now = to_db(request.app.state.clock.now())
        request.app.state.backup.run_if_due(now)
        expire_reservations(session, now)
        yield session


def get_clock(request: Request):
    """Повертає інжектоване джерело часу (Clock) із стану застосунку."""
    return request.app.state.clock


def get_hasher(request: Request):
    """Хешування пароля з кількістю повторів, заданою при створенні застосунку."""
    return partial(hash_password, iterations=request.app.state.password_iterations)


def get_or_404(session: Session, model, object_id: str, matches=None):
    """Ресурс за ідентифікатором або 404; `matches` уточнює, що це саме потрібний ресурс (напр. читач)."""
    found = session.get(model, object_id)
    if found is None or (matches is not None and not matches(found)):
        raise not_found()
    return found


def today(clock) -> date:
    """Повертає поточну календарну дату в UTC з переданого годинника."""
    return to_db(clock.now()).date()


def current_account(request: Request, session: Session = Depends(get_session)) -> Account:
    """Автентифікує користувача за токеном Bearer із заголовка Authorization (REQ-F-047)."""
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
    """Фабрика залежностей FastAPI для перевірки наявності дозволеної ролі в користувача."""
    def check(account: Account = Depends(current_account)) -> Account:
        if account.role not in roles:
            raise forbidden()
        return account
    return check
