"""Облікові записи адміністраторів і бібліотекарів (REQ-F-009...014)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.db import Account, to_db
from library.deps import ADMIN_ROLES, get_clock, get_session, require
from library.errors import ApiError, not_found
from library.schemas import AccountInput, AccountUpdate, account_out
from library.security import hash_password

router = APIRouter()


def email_taken(session: Session, email: str, except_id: str | None = None) -> bool:
    """Email зайнятий будь-яким акаунтом персоналу або підтвердженим читачем (REQ-F-017)."""
    for account in session.scalars(select(Account).where(Account.email == email)):
        if account.id != except_id and (account.role != "reader" or account.active):
            return True
    return False


def duplicate_email() -> ApiError:
    return ApiError(409, "duplicate_email", "Цей email уже використовується.")


def create_staff(session: Session, clock, actor: Account, body: AccountInput, role: str) -> Account:
    if email_taken(session, body.email):
        raise duplicate_email()
    account = Account(email=body.email, full_name=body.fullName, role=role,
                      password_hash=hash_password(body.password), created_at=to_db(clock.now()))
    session.add(account)
    session.commit()
    audit.record(session, clock, actor, "account.created", role, account.id)
    return account


def update_staff(session: Session, clock, actor: Account, account: Account, body: AccountUpdate) -> Account:
    if body.email is not None and body.email != account.email:
        if email_taken(session, body.email, except_id=account.id):
            raise duplicate_email()
        account.email = body.email
    if body.fullName is not None:
        account.full_name = body.fullName
    if body.active is not None:
        account.active = body.active
    session.commit()
    audit.record(session, clock, actor, "account.deactivated" if body.active is False else "account.updated",
                 account.role, account.id)
    return account


# --- адміністратори нижчого рівня: лише головний адміністратор
@router.get("/administrators")
def list_administrators(session: Session = Depends(get_session), _=Depends(require("chief_admin"))):
    return [account_out(a) for a in session.scalars(select(Account).where(Account.role == "admin"))]


@router.post("/administrators", status_code=201)
def create_administrator(body: AccountInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                         actor: Account = Depends(require("chief_admin"))):
    return account_out(create_staff(session, clock, actor, body, "admin"))


@router.patch("/administrators/{administrator_id}")
def update_administrator(administrator_id: str, body: AccountUpdate, session: Session = Depends(get_session),
                         clock=Depends(get_clock), actor: Account = Depends(require("chief_admin"))):
    account = session.get(Account, administrator_id)
    if account is not None and account.role == "chief_admin":
        raise ApiError(403, "protected_account", "Акаунт головного адміністратора змінювати заборонено.")
    if account is None or account.role != "admin":
        raise not_found()
    return account_out(update_staff(session, clock, actor, account, body))


# --- бібліотекарі: адміністратори
@router.get("/librarians")
def list_librarians(session: Session = Depends(get_session), _=Depends(require(*ADMIN_ROLES))):
    return [account_out(a) for a in session.scalars(select(Account).where(Account.role == "librarian"))]


@router.post("/librarians", status_code=201)
def create_librarian(body: AccountInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                     actor: Account = Depends(require(*ADMIN_ROLES))):
    return account_out(create_staff(session, clock, actor, body, "librarian"))


@router.patch("/librarians/{librarian_id}")
def update_librarian(librarian_id: str, body: AccountUpdate, session: Session = Depends(get_session),
                     clock=Depends(get_clock), actor: Account = Depends(require(*ADMIN_ROLES))):
    account = session.get(Account, librarian_id)
    if account is None or account.role != "librarian":
        raise not_found()
    return account_out(update_staff(session, clock, actor, account, body))
