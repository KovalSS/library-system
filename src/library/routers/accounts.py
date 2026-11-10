"""Облікові записи адміністраторів і бібліотекарів (REQ-F-009...014)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.db import Account, to_db
from library.deps import ADMIN_ROLES, get_clock, get_hasher, get_or_404, get_session, require
from library.errors import ApiError, not_found
from library.identity import duplicate_email, email_taken
from library.schemas import AccountInput, AccountUpdate, account_out

router = APIRouter()


def create_staff(session: Session, clock, hasher, actor: Account, body: AccountInput, role: str) -> Account:
    """Створює обліковий запис співробітника (адміністратора або бібліотекаря) із записом в аудит."""
    if email_taken(session, body.email):
        raise duplicate_email()
    account = Account(email=body.email, full_name=body.fullName, role=role,
                      password_hash=hasher(body.password), created_at=to_db(clock.now()))
    session.add(account)
    audit.record(session, clock, actor, "account.created", role, account)
    session.commit()
    return account


def update_staff(session: Session, clock, actor: Account, account: Account, body: AccountUpdate) -> Account:
    """Оновлює дані або статус активності акаунта персоналу із фіксацією в аудит-лозі."""
    if body.email is not None and body.email != account.email:
        if email_taken(session, body.email, except_id=account.id):
            raise duplicate_email()
        account.email = body.email
    if body.fullName is not None:
        account.full_name = body.fullName
    if body.active is not None:
        account.active = body.active
    audit.record(session, clock, actor, "account.deactivated" if body.active is False else "account.updated",
                 account.role, account)
    session.commit()
    return account


# --- адміністратори нижчого рівня: лише головний адміністратор
@router.get("/administrators")
def list_administrators(session: Session = Depends(get_session), _=Depends(require("chief_admin"))):
    """Отримує список облікових записів адміністраторів нижчого рівня (REQ-F-010)."""
    return [account_out(a) for a in session.scalars(select(Account).where(Account.role == "admin"))]


@router.post("/administrators", status_code=201)
def create_administrator(body: AccountInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                         hasher=Depends(get_hasher), actor: Account = Depends(require("chief_admin"))):
    """Створює новий обліковий запис адміністратора головним адміністратором (REQ-F-010)."""
    return account_out(create_staff(session, clock, hasher, actor, body, "admin"))


@router.patch("/administrators/{administrator_id}")
def update_administrator(administrator_id: str, body: AccountUpdate, session: Session = Depends(get_session),
                         clock=Depends(get_clock), actor: Account = Depends(require("chief_admin"))):
    """Оновлює дані або деактивує обліковий запис адміністратора (REQ-F-011, REQ-F-012)."""
    account = session.get(Account, administrator_id)
    if account is not None and account.role == "chief_admin":
        raise ApiError(403, "protected_account", "Акаунт головного адміністратора змінювати заборонено.")
    if account is None or account.role != "admin":
        raise not_found()
    return account_out(update_staff(session, clock, actor, account, body))


# --- бібліотекарі: адміністратори
@router.get("/librarians")
def list_librarians(session: Session = Depends(get_session), _=Depends(require(*ADMIN_ROLES))):
    """Отримує список облікових записів бібліотекарів (REQ-F-013)."""
    return [account_out(a) for a in session.scalars(select(Account).where(Account.role == "librarian"))]


@router.post("/librarians", status_code=201)
def create_librarian(body: AccountInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                     hasher=Depends(get_hasher), actor: Account = Depends(require(*ADMIN_ROLES))):
    """Створює новий обліковий запис бібліотекаря адміністратором (REQ-F-013)."""
    return account_out(create_staff(session, clock, hasher, actor, body, "librarian"))


@router.patch("/librarians/{librarian_id}")
def update_librarian(librarian_id: str, body: AccountUpdate, session: Session = Depends(get_session),
                     clock=Depends(get_clock), actor: Account = Depends(require(*ADMIN_ROLES))):
    """Оновлює дані або деактивує обліковий запис бібліотекаря (REQ-F-014)."""
    account = get_or_404(session, Account, librarian_id, lambda a: a.role == "librarian")
    return account_out(update_staff(session, clock, actor, account, body))
