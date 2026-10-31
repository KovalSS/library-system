"""Обіг фонду: терміни, штрафи, бронювання й черга (REQ-F-018...031).

Усе, що залежить від часу (прострочення, штраф, автоскасування броні), обчислюється
на льоту від поточного моменту годинника, без фонового завдання (REQ-F-027).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library.db import Copy, Edition, Loan, Reservation
from library.notifications import notify_reservation_ready

TERM_WITH_QUEUE, TERM_WITHOUT_QUEUE = 14, 30          # REQ-F-019
RATE_WITH_QUEUE, RATE_WITHOUT_QUEUE = 5, 1            # REQ-F-027, % ціни за день
PICKUP_PERIOD = timedelta(days=2)                      # REQ-F-023, 025
CENT = Decimal("0.01")


# --- штраф (REQ-F-027...029)
@dataclass(frozen=True)
class FineState:
    overdue_days: int
    amount: Decimal
    compensated: bool


def fine_state(loan: Loan, today: date) -> FineState:
    """Прострочення рахується до повернення або до сьогодні; штраф не більший за ціну (REQ-F-028)."""
    end = loan.returned_on or today
    overdue = max(0, (end - loan.due_on).days)
    raw = loan.price * loan.fine_rate_percent * overdue / 100
    amount = min(loan.price, raw).quantize(CENT, rounding=ROUND_HALF_UP)
    return FineState(overdue, amount, compensated=loan.returned_on is None and raw >= loan.price)


def loan_status(loan: Loan, today: date) -> str:
    if loan.returned_on is not None:
        return "returned"
    return "compensated" if fine_state(loan, today).compensated else "active"


def outstanding(loan: Loan, today: date) -> Decimal:
    return fine_state(loan, today).amount - loan.fine_paid


# --- заборгованість читача: одне визначення для звіту REQ-F-040 і відмови у видачі REQ-F-051
@dataclass(frozen=True)
class Debt:
    overdue_loans: int
    unpaid: Decimal

    @property
    def exists(self) -> bool:
        return self.overdue_loans > 0 or self.unpaid > 0


def debt_of(loans, today: date) -> Debt:
    """Прострочені неповернуті видачі (зокрема компенсовані) та сума несплачених штрафів."""
    loans = list(loans)
    overdue = sum(1 for loan in loans if loan.returned_on is None and fine_state(loan, today).overdue_days > 0)
    return Debt(overdue, sum((outstanding(loan, today) for loan in loans), Decimal("0")))


def reader_debt(session: Session, reader_id: str, today: date) -> Debt:
    return debt_of(session.scalars(select(Loan).where(Loan.reader_id == reader_id)), today)


# --- правила видачі (REQ-F-018, 019, 023, 051)
@dataclass(frozen=True)
class Refusal:
    code: str
    message: str
    reason: str                     # для системного журналу (REQ-NF-005)


def loan_refusal(session: Session, reader_id: str, copy: Copy, today: date) -> Refusal | None:
    """Причина відмови у видачі або None. Заборгованість — першою: вона стосується читача, а не екземпляра."""
    debt = reader_debt(session, reader_id, today)
    if debt.exists:
        return Refusal("reader_has_debt", "У читача є прострочена видача або несплачений штраф.",
                       f"читач {reader_id}: прострочених видач {debt.overdue_loans}, несплачено {debt.unpaid} грн")
    if copy.status != "available":
        return Refusal("copy_not_available", "Екземпляр не в стані «доступний».",
                       f"екземпляр {copy.id}: стан {copy.status}")
    reservation = holding_reservation(session, copy.id)
    if reservation is not None and reservation.reader_id != reader_id:
        return Refusal("copy_not_available", "Екземпляр не в стані «доступний».",
                       f"екземпляр {copy.id}: утримується бронюванням іншого читача")
    return None


def new_loan(session: Session, reader_id: str, copy: Copy, today: date) -> Loan:
    """Термін і ставка визначаються чергою на момент видачі й далі не змінюються (REQ-F-019, 027)."""
    queue = has_queue(session, copy.edition_id, except_reader=reader_id)
    term = TERM_WITH_QUEUE if queue else TERM_WITHOUT_QUEUE
    return Loan(reader_id=reader_id, copy_id=copy.id, edition_id=copy.edition_id, issued_on=today,
                due_on=today + timedelta(days=term), term_days=term,
                fine_rate_percent=RATE_WITH_QUEUE if queue else RATE_WITHOUT_QUEUE,
                price=session.get(Edition, copy.edition_id).price)


# --- черга й утримання екземплярів (REQ-F-023...026)
def has_queue(session: Session, edition_id: str, except_reader: str | None = None) -> bool:
    query = select(Reservation).where(Reservation.edition_id == edition_id, Reservation.status == "queued")
    if except_reader:
        query = query.where(Reservation.reader_id != except_reader)
    return session.scalar(query.limit(1)) is not None


def holding_reservation(session: Session, copy_id: str) -> Reservation | None:
    return session.scalar(select(Reservation).where(Reservation.copy_id == copy_id, Reservation.status == "ready"))


def free_copy(session: Session, edition_id: str) -> Copy | None:
    """Доступний екземпляр, не утриманий бронюванням іншого читача."""
    held = select(Reservation.copy_id).where(Reservation.status == "ready", Reservation.copy_id.is_not(None))
    return session.scalar(select(Copy).where(Copy.edition_id == edition_id, Copy.status == "available",
                                             Copy.id.not_in(held)).order_by(Copy.inventory_number).limit(1))


def available_count(session: Session, edition_id: str) -> int:
    held = select(Reservation.copy_id).where(Reservation.status == "ready", Reservation.copy_id.is_not(None))
    return session.scalar(select(func.count()).where(Copy.edition_id == edition_id, Copy.status == "available",
                                                     Copy.id.not_in(held)))


def queue_position(session: Session, reservation: Reservation) -> int | None:
    if reservation.status != "queued":
        return None
    ahead = session.scalar(select(func.count()).where(Reservation.edition_id == reservation.edition_id,
                                                      Reservation.status == "queued",
                                                      Reservation.seq < reservation.seq))
    return ahead + 1


def offer_copy(session: Session, copy: Copy, moment: datetime) -> Reservation | None:
    """Звільнений екземпляр пропонується першому в черзі на 2 доби (REQ-F-026)."""
    first = session.scalar(select(Reservation).where(Reservation.edition_id == copy.edition_id,
                                                     Reservation.status == "queued")
                           .order_by(Reservation.seq).limit(1))
    if first is not None:
        first.status = "ready"
        first.copy_id = copy.id
        first.pickup_deadline = moment + PICKUP_PERIOD
        notify_reservation_ready(session, first)                  # REQ-F-036
    return first


def expire_reservations(session: Session, now: datetime) -> None:
    """Бронювання, не отримані за 2 доби, скасовуються автоматично (REQ-F-025).

    Відбувається при зверненні до даних; звільнений екземпляр переходить наступному в черзі
    з моменту скасування, тож ланцюжок може тягнутися кілька разів поспіль.
    """
    while True:
        overdue = session.scalar(select(Reservation).where(Reservation.status == "ready",
                                                           Reservation.pickup_deadline < now)
                                 .order_by(Reservation.pickup_deadline).limit(1))
        if overdue is None:
            break
        overdue.status = "expired"
        copy = session.get(Copy, overdue.copy_id)
        session.flush()
        offer_copy(session, copy, overdue.pickup_deadline)
        session.flush()
    session.commit()
