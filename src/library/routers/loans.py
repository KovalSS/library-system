"""Видача та повернення (REQ-F-018...021); картка видачі зі штрафом на льоту (REQ-F-027...029)."""
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.circulation import (RATE_WITH_QUEUE, RATE_WITHOUT_QUEUE, TERM_WITH_QUEUE, TERM_WITHOUT_QUEUE,
                                 fine_state, has_queue, holding_reservation, loan_status, offer_copy)
from library.db import Account, Copy, Edition, Loan, to_db
from library.deps import current_account, get_clock, get_or_404, get_session, require, today
from library.errors import ApiError, forbidden
from library.logging_setup import LOGGER_NAME
from library.routers.readers import readable_reader
from library.schemas import LoanCreate, LoanStatus, money, page_out

router = APIRouter()
loans_log = logging.getLogger(f"{LOGGER_NAME}.loans")


def loan_out(loan: Loan, on: date) -> dict:
    fine = fine_state(loan, on)
    return {"id": loan.id, "readerId": loan.reader_id, "copyId": loan.copy_id, "editionId": loan.edition_id,
            "issuedAt": loan.issued_on.isoformat(), "dueDate": loan.due_on.isoformat(), "termDays": loan.term_days,
            "status": loan_status(loan, on), "returnedAt": loan.returned_on.isoformat() if loan.returned_on else None,
            "overdueDays": fine.overdue_days, "fineRatePercent": loan.fine_rate_percent,
            "fineAmount": money(fine.amount), "finePaidAmount": money(loan.fine_paid)}


def copy_not_available(copy_id: str, reason: str) -> ApiError:
    # Помилки критичних операцій потрапляють у системний журнал (REQ-NF-005).
    loans_log.warning("Відмова у видачі екземпляра %s: %s", copy_id, reason)
    return ApiError(409, "copy_not_available", "Екземпляр не в стані «доступний».")


@router.post("/loans", status_code=201)
def create_loan(body: LoanCreate, session: Session = Depends(get_session), clock=Depends(get_clock),
                actor: Account = Depends(require("librarian"))):
    reader = get_or_404(session, Account, str(body.readerId), lambda a: a.role == "reader")
    copy = get_or_404(session, Copy, str(body.copyId))
    if copy.status != "available":
        raise copy_not_available(copy.id, f"стан {copy.status}")
    reservation = holding_reservation(session, copy.id)
    if reservation is not None and reservation.reader_id != reader.id:
        raise copy_not_available(copy.id, "утримується бронюванням іншого читача")

    queue = has_queue(session, copy.edition_id, except_reader=reader.id)       # REQ-F-019, 027
    term = TERM_WITH_QUEUE if queue else TERM_WITHOUT_QUEUE
    issued_on = today(clock)
    loan = Loan(reader_id=reader.id, copy_id=copy.id, edition_id=copy.edition_id, issued_on=issued_on,
                due_on=date.fromordinal(issued_on.toordinal() + term), term_days=term,
                fine_rate_percent=RATE_WITH_QUEUE if queue else RATE_WITHOUT_QUEUE,
                price=session.get(Edition, copy.edition_id).price)
    copy.status = "issued"
    if reservation is not None:
        reservation.status = "fulfilled"
    session.add(loan)
    audit.record(session, clock, actor, "loan.created", "loan", loan)
    session.commit()
    return loan_out(loan, issued_on)


@router.get("/loans/{loan_id}")
def get_loan(loan_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
             viewer: Account = Depends(current_account)):
    loan = get_or_404(session, Loan, loan_id)
    if viewer.role == "reader" and loan.reader_id != viewer.id:
        raise forbidden()
    return loan_out(loan, today(clock))


@router.post("/loans/{loan_id}/return")
def return_loan(loan_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
                actor: Account = Depends(require("librarian"))):
    loan = get_or_404(session, Loan, loan_id)
    on = today(clock)
    if loan_status(loan, on) != "active":
        loans_log.warning("Відмова у поверненні видачі %s: стан %s", loan.id, loan_status(loan, on))
        raise ApiError(409, "loan_already_closed", "Видача вже закрита.")
    loan.returned_on = on
    copy = session.get(Copy, loan.copy_id)
    copy.status = "available"
    session.flush()
    offer_copy(session, copy, to_db(clock.now()))                              # REQ-F-026
    audit.record(session, clock, actor, "loan.returned", "loan", loan)
    session.commit()
    return loan_out(loan, on)


@router.get("/readers/{reader_id}/loans")
def list_reader_loans(reader_id: str, status: LoanStatus | None = None,
                      page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                      session: Session = Depends(get_session), clock=Depends(get_clock),
                      viewer: Account = Depends(current_account)):
    readable_reader(session, viewer, reader_id)
    on = today(clock)
    loans = [loan for loan in session.scalars(select(Loan).where(Loan.reader_id == reader_id)
                                              .order_by(Loan.issued_on.desc()))
             if status is None or loan_status(loan, on) == status]
    chunk = loans[(page - 1) * pageSize: page * pageSize]
    return page_out([loan_out(loan, on) for loan in chunk], page, pageSize, len(loans))
