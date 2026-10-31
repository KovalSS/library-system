"""Читачі: самостійна реєстрація та підтвердження email (REQ-F-015...017)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from library import audit
from library.db import Account, EmailToken, to_db
from library.deps import STAFF_ROLES, current_account, get_clock, get_hasher, get_or_404, get_session, require
from library.errors import ApiError, forbidden
from library.routers.accounts import duplicate_email, email_taken
from library.schemas import ReaderRegistration, TokenBody, page_out, reader_out
from library.security import new_token

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
                    clock=Depends(get_clock), hasher=Depends(get_hasher)):
    if email_taken(session, body.email):
        raise duplicate_email()
    reader = Account(email=body.email, full_name=body.fullName, role="reader", active=False,
                     password_hash=hasher(body.password), created_at=to_db(clock.now()),
                     phone=body.phone, birth_date=body.birthDate.isoformat())
    session.add(reader)
    session.commit()
    audit.record(session, clock, reader, "reader.registered", "reader", reader.id)
    issue_email_token(session, request, reader, "email_confirmation")
    return reader_out(reader)


@router.post("/email-confirmations")
def confirm_email(body: TokenBody, session: Session = Depends(get_session), clock=Depends(get_clock)):
    reader = use_email_token(session, body.token, "email_confirmation")
    # Поки лист чекав, email міг підтвердити інший акаунт (REQ-F-017).
    if email_taken(session, reader.email, except_id=reader.id):
        raise invalid_token()
    reader.active = True
    session.commit()
    audit.record(session, clock, reader, "reader.email_confirmed", "reader", reader.id)
    return reader_out(reader)


# --- персональні дані читачів лише для власника та персоналу (REQ-F-050)
@router.get("/readers")
def list_readers(q: str | None = Query(default=None, min_length=1, max_length=100),
                 page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                 session: Session = Depends(get_session), _=Depends(require(*STAFF_ROLES))):
    query = select(Account).where(Account.role == "reader")
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Account.full_name).like(pattern), func.lower(Account.email).like(pattern)))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    readers = session.scalars(query.order_by(Account.full_name).offset((page - 1) * pageSize).limit(pageSize))
    return page_out([reader_out(r) for r in readers], page, pageSize, total)


def readable_reader(session: Session, viewer: Account, reader_id: str) -> Account:
    """Читач бачить лише себе (про чужі акаунти навіть не дізнається, чи вони існують)."""
    if viewer.role == "reader" and viewer.id != reader_id:
        raise forbidden()
    return get_or_404(session, Account, reader_id, lambda a: a.role == "reader")


@router.get("/readers/{reader_id}")
def get_reader(reader_id: str, session: Session = Depends(get_session), viewer: Account = Depends(current_account)):
    return reader_out(readable_reader(session, viewer, reader_id))
