"""Представлення видання з похідними величинами: доступні екземпляри й популярність."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library.circulation import available_count
from library.db import Edition, Genre, Loan
from library.schemas import edition_out


def loans_count(session: Session, edition_id: str) -> int:
    """Кількість видач за весь час — популярність видання (REQ-F-045)."""
    return session.scalar(select(func.count()).where(Loan.edition_id == edition_id))


def present_edition(session: Session, edition: Edition) -> dict:
    return edition_out(edition, session.get(Genre, edition.genre_id), available_count(session, edition.id),
                       loans_count(session, edition.id))
