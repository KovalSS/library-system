"""Видача та повернення (REQ-F-018...021); картка видачі зі штрафом на льоту (REQ-F-027...029)."""
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.access import readable_reader
from library.circulation import fine_state, holding_reservation, loan_refusal, loan_status, new_loan, offer_copy
from library.db import Account, Copy, Loan, to_db
from library.deps import current_account, get_clock, get_or_404, get_session, require, today
from library.errors import ApiError, forbidden
from library.logging_setup import LOGGER_NAME
from library.schemas import LoanCreate, LoanStatus, money, page_out

router = APIRouter()
loans_log = logging.getLogger(f"{LOGGER_NAME}.loans")


def loan_out(loan: Loan, on: date) -> dict:
    """Формує словник картки видачі з динамічно розрахованим штрафом та статусом."""
    fine = fine_state(loan, on)
    return {"id": loan.id, "readerId": loan.reader_id, "copyId": loan.copy_id, "editionId": loan.edition_id,
            "issuedAt": loan.issued_on.isoformat(), "dueDate": loan.due_on.isoformat(), "termDays": loan.term_days,
            "status": loan_status(loan, on), "returnedAt": loan.returned_on.isoformat() if loan.returned_on else None,
            "overdueDays": fine.overdue_days, "fineRatePercent": loan.fine_rate_percent,
            "fineAmount": money(fine.amount), "finePaidAmount": money(loan.fine_paid)}


@router.post("/loans", status_code=201)
def create_loan(body: LoanCreate, session: Session = Depends(get_session), clock=Depends(get_clock),
                actor: Account = Depends(require("librarian"))):
    """Оформлює видачу екземпляра читачу бібліотекарем (REQ-F-018, REQ-F-051).

    Перевіряє доступність книги та відсутність заборгованості в читача.
    """
    reader = get_or_404(session, Account, str(body.readerId), lambda a: a.role == "reader")
    copy = get_or_404(session, Copy, str(body.copyId))
    on = today(clock)                       # одна дата на весь запит: і для перевірки боргу, і для видачі
    refusal = loan_refusal(session, reader.id, copy, on)
    if refusal is not None:
        # Відмови критичних операцій потрапляють у системний журнал (REQ-NF-005).
        loans_log.warning("Відмова у видачі: %s", refusal.reason)
        raise ApiError(409, refusal.code, refusal.message)

    loan = new_loan(session, reader.id, copy, on)
    copy.status = "issued"
    reservation = holding_reservation(session, copy.id)
    if reservation is not None:                                    # утримуваний для цього читача (B2)
        reservation.status = "fulfilled"
    session.add(loan)
    audit.record(session, clock, actor, "loan.created", "loan", loan)
    session.commit()
    return loan_out(loan, on)


@router.get("/loans/{loan_id}")
def get_loan(loan_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
             viewer: Account = Depends(current_account)):
    """Повертає детальну картку видачі за її ідентифікатором (REQ-F-020)."""
    loan = get_or_404(session, Loan, loan_id)
    if viewer.role == "reader" and loan.reader_id != viewer.id:
        raise forbidden()
    return loan_out(loan, today(clock))


@router.post("/loans/{loan_id}/return")
def return_loan(loan_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
                actor: Account = Depends(require("librarian"))):
    """Реєструє повернення книги, звільняє екземпляр або пропонує його черзі (REQ-F-021, REQ-F-026)."""
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
    """Повертає пагінований список видач читача з можливістю фільтрації за статусом (REQ-F-020)."""
    readable_reader(session, viewer, reader_id)
    on = today(clock)
    loans = [loan for loan in session.scalars(select(Loan).where(Loan.reader_id == reader_id)
                                              .order_by(Loan.issued_on.desc()))
             if status is None or loan_status(loan, on) == status]
    chunk = loans[(page - 1) * pageSize: page * pageSize]
    return page_out([loan_out(loan, on) for loan in chunk], page, pageSize, len(loans))
