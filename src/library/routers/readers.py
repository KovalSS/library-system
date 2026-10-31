"""Читачі: самостійна реєстрація та підтвердження email (REQ-F-015...017)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from library.db import Account, EmailToken, to_db
from library.deps import get_clock, get_session
from library.errors import ApiError
from library.routers.accounts import duplicate_email, email_taken
from library.schemas import ReaderRegistration, TokenBody, reader_out
from library.security import hash_password, new_token

router = APIRouter()


def invalid_token() -> ApiError:
    return ApiError(400, "invalid_token", "Посилання недійсне або прострочене.")


def issue_email_token(session: Session, request: Request, account: Account, kind: str) -> None:
    token = new_token()
    session.add(EmailToken(token=token, account_id=account.id, kind=kind))
    session.commit()
    request.app.state.mailer.send(account.email, kind, token)


def use_email_token(session: Session, token: str, kind: str) -> Account:
    found = session.get(EmailToken, token)
    if found is None or found.kind != kind or found.used:
        raise invalid_token()
    found.used = True
    return session.get(Account, found.account_id)


@router.post("/readers", status_code=201)
def register_reader(body: ReaderRegistration, request: Request, session: Session = Depends(get_session),
                    clock=Depends(get_clock)):
    if email_taken(session, body.email):
        raise duplicate_email()
    reader = Account(email=body.email, full_name=body.fullName, role="reader", active=False,
                     password_hash=hash_password(body.password), created_at=to_db(clock.now()),
                     phone=body.phone, birth_date=body.birthDate.isoformat())
    session.add(reader)
    session.commit()
    issue_email_token(session, request, reader, "email_confirmation")
    return reader_out(reader)


@router.post("/email-confirmations")
def confirm_email(body: TokenBody, session: Session = Depends(get_session)):
    reader = use_email_token(session, body.token, "email_confirmation")
    # Поки лист чекав, email міг підтвердити інший акаунт (REQ-F-017).
    if email_taken(session, reader.email, except_id=reader.id):
        raise invalid_token()
    reader.active = True
    session.commit()
    return reader_out(reader)
