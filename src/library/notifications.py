"""Внутрішні сповіщення читача (REQ-F-035...037).

Сповіщення про термін і прострочення створюються на льоту при зверненні до списку,
з датою самої події (як і штраф, без фонового завдання). Сповіщення про бронювання
створюється в момент, коли екземпляр стає доступним для отримання.
"""
import math
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from library.db import Edition, Loan, Notification, Reservation

DUE_SOON_DAYS = 2                                     # REQ-F-035: за 1–2 дні до терміну


def notify(session: Session, key: str, reader_id: str, kind: str, message: str, created_at: datetime,
           loan_id: str | None = None, reservation_id: str | None = None) -> None:
    """Ідемпотентно створює сповіщення для читача, якщо ключ ще не існує."""
    if session.scalar(select(Notification.seq).where(Notification.key == key)) is None:
        session.add(Notification(key=key, reader_id=reader_id, type=kind, message=message, created_at=created_at,
                                 loan_id=loan_id, reservation_id=reservation_id))


def start_of(day: date) -> datetime:
    """Перетворює календарну дату на початок доби (00:00:00)."""
    return datetime.combine(day, time())


def notify_reservation_ready(session: Session, reservation: Reservation) -> None:
    """REQ-F-036: бронювання доступне для отримання — повідомити строк."""
    title = session.get(Edition, reservation.edition_id).title
    deadline = reservation.pickup_deadline
    notify(session, f"ready:{reservation.id}:{deadline.isoformat()}", reservation.reader_id, "reservation_ready",
           f"Видання «{title}» доступне для отримання до {deadline:%d.%m.%Y}.", deadline - timedelta(days=2),
           reservation_id=reservation.id)


def sync_loan_notifications(session: Session, reader_id: str, on: date) -> None:
    """Генерує та оновлює сповіщення про наближення терміну та прострочення (REQ-F-035, REQ-F-037)."""
    for loan in session.scalars(select(Loan).where(Loan.reader_id == reader_id)):
        title = session.get(Edition, loan.edition_id).title
        last_day = min(on, loan.returned_on) if loan.returned_on else on

        soon = loan.due_on - timedelta(days=DUE_SOON_DAYS)
        if soon <= last_day and (loan.returned_on is None or loan.returned_on > soon):
            notify(session, f"due_soon:{loan.id}", reader_id, "due_soon",
                   f"Термін повернення книги «{title}» спливає {loan.due_on:%d.%m.%Y}.", start_of(soon),
                   loan_id=loan.id)

        # REQ-F-037: перший день прострочення і кожне подальше нарахування — до межі штрафу (REQ-F-028).
        charged_days = min((last_day - loan.due_on).days, math.ceil(100 / loan.fine_rate_percent))
        for day_number in range(1, charged_days + 1):
            day = loan.due_on + timedelta(days=day_number)
            fine = min(loan.price, loan.price * loan.fine_rate_percent * day_number / 100)
            notify(session, f"overdue:{loan.id}:{day_number}", reader_id, "overdue_fine",
                   f"Книгу «{title}» не повернуто вчасно: {day:%d.%m.%Y} нараховано штраф, разом {fine:.2f} грн.",
                   start_of(day), loan_id=loan.id)
    session.commit()
