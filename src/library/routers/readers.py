"""Читачі: самостійна реєстрація та підтвердження email (REQ-F-015...017)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from library import audit
from library.access import readable_reader
from library.db import Account, to_db
from library.deps import STAFF_ROLES, current_account, get_clock, get_hasher, get_session, require
from library.identity import duplicate_email, email_taken, invalid_token, issue_email_token, use_email_token
from library.schemas import ReaderRegistration, TokenBody, page_out, reader_out

router = APIRouter()


@router.post("/readers", status_code=201)
def register_reader(body: ReaderRegistration, request: Request, session: Session = Depends(get_session),
                    clock=Depends(get_clock), hasher=Depends(get_hasher)):
    """Реєструє нового читача в системі та надсилає лист підтвердження пошти (REQ-F-015, REQ-F-016)."""
    if email_taken(session, body.email):
        raise duplicate_email()
    reader = Account(email=body.email, full_name=body.fullName, role="reader", active=False,
                     password_hash=hasher(body.password), created_at=to_db(clock.now()),
                     phone=body.phone, birth_date=body.birthDate.isoformat())
    session.add(reader)
    audit.record(session, clock, reader, "reader.registered", "reader", reader)
    session.commit()
    issue_email_token(session, request.app.state.mailer, reader, "email_confirmation")
    return reader_out(reader)


@router.post("/email-confirmations")
def confirm_email(body: TokenBody, session: Session = Depends(get_session), clock=Depends(get_clock)):
    """Підтверджує адресу електронної пошти читача за одноразовим токеном (REQ-F-016)."""
    reader = use_email_token(session, body.token, "email_confirmation")
    # Поки лист чекав, email міг підтвердити інший акаунт (REQ-F-017).
    if email_taken(session, reader.email, except_id=reader.id):
        raise invalid_token()
    reader.active = True
    audit.record(session, clock, reader, "reader.email_confirmed", "reader", reader)
    session.commit()
    return reader_out(reader)


# --- персональні дані читачів лише для власника та персоналу (REQ-F-050)
@router.get("/readers")
def list_readers(q: str | None = Query(default=None, min_length=1, max_length=100),
                 page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                 session: Session = Depends(get_session), _=Depends(require(*STAFF_ROLES))):
    """Повертає список зареєстрованих читачів для бібліотекаря з пошуком (REQ-F-050)."""
    query = select(Account).where(Account.role == "reader")
    if q:
        pattern = f"%{q.casefold()}%"
        query = query.where(or_(func.casefold(Account.full_name).like(pattern),
                                func.casefold(Account.email).like(pattern)))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    readers = session.scalars(query.order_by(Account.full_name).offset((page - 1) * pageSize).limit(pageSize))
    return page_out([reader_out(r) for r in readers], page, pageSize, total)


@router.get("/readers/{reader_id}")
def get_reader(reader_id: str, session: Session = Depends(get_session), viewer: Account = Depends(current_account)):
    """Отримує профіль читача для власника кабінету або персоналу бібліотеки (REQ-F-050)."""
    return reader_out(readable_reader(session, viewer, reader_id))
