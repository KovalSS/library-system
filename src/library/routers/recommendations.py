"""Прості рекомендації за авторами й жанрами раніше отриманих книг (REQ-F-032...034)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from library.access import readable_reader
from library.db import Account, Copy, Edition, Loan
from library.deps import current_account, get_session
from library.editions import present_edition

router = APIRouter()


def in_stock(session: Session, edition_id: str) -> bool:
    """«Наявне у фонді» — є хоча б один не списаний екземпляр, навіть якщо зараз виданий (REQ-F-034)."""
    return session.scalar(select(Copy.id).where(Copy.edition_id == edition_id, Copy.status != "written_off")
                          .limit(1)) is not None


def recommendation_reason(edition: Edition, authors: set[str], genres: set[str]) -> str | None:
    """Збіг за автором має пріоритет над збігом за жанром (REQ-F-032, 033)."""
    if edition.author in authors:
        return "same_author"
    if edition.genre_id in genres:
        return "same_genre"
    return None


@router.get("/readers/{reader_id}/recommendations")
def list_recommendations(reader_id: str, session: Session = Depends(get_session),
                         viewer: Account = Depends(current_account)):
    """Формує персональні рекомендації читачу на основі його попередніх видач (REQ-F-032...034, REQ-F-052).

    Рекомендуються наявні у фонді видання тих самих авторів чи жанрів, виключаючи
    вже раніше отримані читачем книги (REQ-F-052).
    """
    readable_reader(session, viewer, reader_id)
    read_ids = set(session.scalars(select(Loan.edition_id).where(Loan.reader_id == reader_id)))
    read = [session.get(Edition, edition_id) for edition_id in read_ids]
    authors, genres = {e.author for e in read}, {e.genre_id for e in read}
    recommendations = []
    for edition in session.scalars(select(Edition).order_by(Edition.title)):
        reason = recommendation_reason(edition, authors, genres)
        # REQ-F-052: видання, за яким у читача є будь-яка видача, не рекомендується.
        if reason and edition.id not in read_ids and in_stock(session, edition.id):
            recommendations.append({"reason": reason, "edition": present_edition(session, edition)})
    recommendations.sort(key=lambda r: r["reason"] != "same_author")
    return recommendations
