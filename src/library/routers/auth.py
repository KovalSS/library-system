"""Автентифікація: вхід, блокування після невдалих спроб (REQ-F-048)."""
import logging
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.db import AccessToken, Account, to_db
from library.deps import get_clock, get_hasher, get_session
from library.errors import ApiError
from library.logging_setup import LOGGER_NAME
from library.routers.readers import issue_email_token, use_email_token
from library.schemas import LoginRequest, PasswordReset, PasswordResetRequest
from library.security import new_token, verify_password

MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=15)

router = APIRouter()
auth_log = logging.getLogger(f"{LOGGER_NAME}.auth")


def find_login_account(session: Session, email: str) -> Account | None:
    """Акаунт для входу за email; підтверджений має перевагу над непідтвердженими дублями."""
    candidates = session.scalars(select(Account).where(Account.email == email)).all()
    return next((a for a in candidates if a.active), candidates[0] if candidates else None)


def invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Невірний email або пароль.")


@router.post("/auth/login")
def login(body: LoginRequest, session: Session = Depends(get_session), clock=Depends(get_clock)):
    now = to_db(clock.now())
    account = find_login_account(session, body.email)
    if account is None:
        auth_log.warning("Невдалий вхід: невідомий email %s", body.email)
        raise invalid_credentials()

    if account.locked_until and account.locked_until > now:
        retry_after = math.ceil((account.locked_until - now).total_seconds())
        auth_log.warning("Вхід у заблокований акаунт %s", body.email)
        raise ApiError(423, "account_locked", "Акаунт тимчасово заблоковано на 15 хвилин.",
                       headers={"Retry-After": str(retry_after)})

    if not verify_password(body.password, account.password_hash):
        account.failed_logins += 1
        if account.failed_logins >= MAX_FAILED_LOGINS:
            account.locked_until = now + LOCK_DURATION
            account.failed_logins = 0
            auth_log.warning("Акаунт %s заблоковано після %d невдалих спроб", body.email, MAX_FAILED_LOGINS)
        else:
            auth_log.warning("Невдалий вхід: невірний пароль для %s", body.email)
        session.commit()
        raise invalid_credentials()

    if not account.active:
        auth_log.warning("Вхід у неактивний акаунт %s", body.email)
        raise ApiError(403, "account_inactive", "Акаунт неактивний.")

    account.failed_logins = 0
    token = new_token()
    session.add(AccessToken(token=token, account_id=account.id))
    session.commit()
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": 3600,
            "userId": account.id, "role": account.role}


@router.post("/auth/password-reset-requests", status_code=202)
def request_password_reset(body: PasswordResetRequest, request: Request, session: Session = Depends(get_session)):
    # Відповідь однакова незалежно від того, чи існує акаунт (адендум A5).
    account = find_login_account(session, body.email)
    if account is not None:
        issue_email_token(session, request, account, "password_reset")
    return Response(status_code=202)


@router.post("/auth/password-resets", status_code=204)
def reset_password(body: PasswordReset, session: Session = Depends(get_session), clock=Depends(get_clock),
                   hasher=Depends(get_hasher)):
    account = use_email_token(session, body.token, "password_reset")
    account.password_hash = hasher(body.newPassword)
    session.commit()
    audit.record(session, clock, account, "account.password_reset", account.role, account.id)
    auth_log.info("Пароль змінено за посиланням з листа для акаунта %s", account.id)
    return Response(status_code=204)
