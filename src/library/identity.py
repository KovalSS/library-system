"""Облікові записи: унікальність email (REQ-F-017) і одноразові токени з листів (REQ-F-016, 047)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from library.db import Account, EmailToken
from library.errors import ApiError
from library.security import new_token


def email_taken(session: Session, email: str, except_id: str | None = None) -> bool:
    """Email зайнятий будь-яким акаунтом персоналу або підтвердженим читачем (REQ-F-017)."""
    for account in session.scalars(select(Account).where(Account.email == email)):
        if account.id != except_id and (account.role != "reader" or account.active):
            return True
    return False


def duplicate_email() -> ApiError:
    return ApiError(409, "duplicate_email", "Цей email уже використовується.")


def invalid_token() -> ApiError:
    return ApiError(400, "invalid_token", "Посилання недійсне або прострочене.")


def issue_email_token(session: Session, mailer, account: Account, kind: str) -> None:
    token = new_token()
    session.add(EmailToken(token=token, account_id=account.id, kind=kind))
    session.commit()
    mailer.send(account.email, kind, token)


def use_email_token(session: Session, token: str, kind: str) -> Account:
    found = session.get(EmailToken, token)
    if found is None or found.kind != kind or found.used:
        raise invalid_token()
    found.used = True
    return session.get(Account, found.account_id)
