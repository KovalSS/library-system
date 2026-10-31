"""Каталог і фонд: жанри, видання, екземпляри, пошук (REQ-F-001...008, 043...046)."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library import audit
from library.circulation import available_count
from library.db import Account, Copy, Edition, Genre, Loan
from library.deps import ADMIN_ROLES, STAFF_ROLES, current_account, get_clock, get_or_404, get_session, require
from library.errors import ApiError, validation_failed
from library.schemas import (CopyInput, CopyUpdate, EditionInput, EditionUpdate, GenreInput, copy_out,
                             edition_out, genre_out, page_out)

router = APIRouter()

# Стани, які встановлює система (видача, списання), а не ручна зміна (REQ-F-006).
SYSTEM_MANAGED_STATES = ("issued", "written_off")


# --- REQ-F-003: довідник жанрів
@router.get("/genres")
def list_genres(session: Session = Depends(get_session), _: Account = Depends(current_account)):
    return [genre_out(g) for g in session.scalars(select(Genre).order_by(Genre.name))]


@router.post("/genres", status_code=201)
def create_genre(body: GenreInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                 actor: Account = Depends(require(*ADMIN_ROLES))):
    genre = Genre(name=body.name)
    session.add(genre)
    audit.record(session, clock, actor, "genre.created", "genre", genre)
    session.commit()
    return genre_out(genre)


@router.patch("/genres/{genre_id}")
def update_genre(genre_id: str, body: GenreInput, session: Session = Depends(get_session),
                 clock=Depends(get_clock), actor: Account = Depends(require(*ADMIN_ROLES))):
    genre = get_or_404(session, Genre, genre_id)
    genre.name = body.name
    audit.record(session, clock, actor, "genre.updated", "genre", genre)
    session.commit()
    return genre_out(genre)


# --- REQ-F-001, 002, 008: видання
def loans_count(session: Session, edition_id: str) -> int:
    return session.scalar(select(func.count()).where(Loan.edition_id == edition_id))


def present_edition(session: Session, edition: Edition) -> dict:
    return edition_out(edition, session.get(Genre, edition.genre_id), available_count(session, edition.id),
                       loans_count(session, edition.id))


def existing_genre(session: Session, genre_id: str) -> None:
    # Контракт не має 404 для createEdition: невідомий жанр — помилка вхідних даних.
    if session.get(Genre, genre_id) is None:
        raise validation_failed("genreId", "Жанр не знайдено в довіднику.")


def ensure_isbn_free(session: Session, isbn: str, except_id: str | None = None) -> None:
    other = session.scalar(select(Edition).where(Edition.isbn == isbn))
    if other is not None and other.id != except_id:
        raise ApiError(409, "duplicate_isbn", "Видання з таким ISBN уже є в каталозі.")


# --- REQ-F-043...046: пошук і фільтрація, доступні всім ролям
SORT_KEYS = {
    "title": lambda e: e["title"],
    "year": lambda e: e["year"],
    "popularity": lambda e: e["loansCount"],          # кількість видач за весь час (REQ-F-045)
}


@router.get("/editions")
def search_editions(author: str | None = Query(default=None, min_length=1, max_length=200),
                    title: str | None = Query(default=None, min_length=1, max_length=300),
                    genreId: UUID | None = None,
                    year: int | None = Query(default=None, ge=1000, le=2100),
                    availableOnly: bool = False,
                    sort: Literal["title", "year", "popularity"] = "title",
                    order: Literal["asc", "desc"] = "asc",
                    page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                    session: Session = Depends(get_session), _: Account = Depends(current_account)):
    # Усі задані фільтри застосовуються одночасно — перетин умов (REQ-F-043).
    query = select(Edition)
    if author:
        query = query.where(Edition.author.contains(author))
    if title:
        query = query.where(Edition.title.contains(title))
    if genreId:
        query = query.where(Edition.genre_id == str(genreId))
    if year:
        query = query.where(Edition.year == year)
    found = [present_edition(session, e) for e in session.scalars(query)]
    if availableOnly:
        found = [e for e in found if e["availableCopies"] > 0]          # REQ-F-044
    found.sort(key=SORT_KEYS[sort], reverse=order == "desc")
    return page_out(found[(page - 1) * pageSize: page * pageSize], page, pageSize, len(found))


@router.post("/editions", status_code=201)
def create_edition(body: EditionInput, session: Session = Depends(get_session), clock=Depends(get_clock),
                   actor: Account = Depends(require("librarian"))):
    existing_genre(session, body.genreId)
    ensure_isbn_free(session, body.isbn)
    edition = Edition(author=body.author, title=body.title, year=body.year, isbn=body.isbn,
                      genre_id=body.genreId, price=body.price, total_copies=body.totalCopies)
    session.add(edition)
    audit.record(session, clock, actor, "edition.created", "edition", edition)
    session.commit()
    return present_edition(session, edition)


@router.get("/editions/{edition_id}")
def get_edition(edition_id: str, session: Session = Depends(get_session), _: Account = Depends(current_account)):
    return present_edition(session, get_or_404(session, Edition, edition_id))


@router.patch("/editions/{edition_id}")
def update_edition(edition_id: str, body: EditionUpdate, session: Session = Depends(get_session),
                   clock=Depends(get_clock), actor: Account = Depends(require("librarian"))):
    edition = get_or_404(session, Edition, edition_id)
    if body.genreId is not None:
        existing_genre(session, body.genreId)
        edition.genre_id = body.genreId
    if body.isbn is not None:
        ensure_isbn_free(session, body.isbn, except_id=edition.id)
        edition.isbn = body.isbn
    for field, column in (("author", "author"), ("title", "title"), ("year", "year"),
                          ("price", "price"), ("totalCopies", "total_copies")):
        value = getattr(body, field)
        if value is not None:
            setattr(edition, column, value)
    audit.record(session, clock, actor, "edition.updated", "edition", edition)
    session.commit()
    return present_edition(session, edition)


# --- REQ-F-004...007: екземпляри
@router.get("/editions/{edition_id}/copies")
def list_copies(edition_id: str, session: Session = Depends(get_session), _=Depends(require(*STAFF_ROLES))):
    get_or_404(session, Edition, edition_id)
    copies = session.scalars(select(Copy).where(Copy.edition_id == edition_id).order_by(Copy.inventory_number))
    return [copy_out(c) for c in copies]


@router.post("/editions/{edition_id}/copies", status_code=201)
def create_copy(edition_id: str, body: CopyInput, session: Session = Depends(get_session),
                clock=Depends(get_clock), actor: Account = Depends(require("librarian"))):
    get_or_404(session, Edition, edition_id)
    if session.scalar(select(Copy).where(Copy.inventory_number == body.inventoryNumber)) is not None:
        raise ApiError(409, "duplicate_inventory_number", "Екземпляр із таким інвентарним номером уже існує.")
    copy = Copy(edition_id=edition_id, inventory_number=body.inventoryNumber, location=body.location,
                status=body.status)
    session.add(copy)
    audit.record(session, clock, actor, "copy.created", "copy", copy)
    session.commit()
    return copy_out(copy)


def copy_state_conflict() -> ApiError:
    return ApiError(409, "copy_state_conflict", "Екземпляр виданий або списаний, зміна неможлива.")


@router.patch("/copies/{copy_id}")
def update_copy(copy_id: str, body: CopyUpdate, session: Session = Depends(get_session),
                clock=Depends(get_clock), actor: Account = Depends(require("librarian"))):
    copy = get_or_404(session, Copy, copy_id)
    if body.status is not None:
        if copy.status in SYSTEM_MANAGED_STATES:
            raise copy_state_conflict()
        copy.status = body.status
    if body.location is not None:
        copy.location = body.location
    audit.record(session, clock, actor, "copy.updated", "copy", copy)
    session.commit()
    return copy_out(copy)


@router.post("/copies/{copy_id}/write-off")
def write_off_copy(copy_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
                   actor: Account = Depends(require("librarian"))):
    copy = get_or_404(session, Copy, copy_id)
    if copy.status in SYSTEM_MANAGED_STATES:
        raise copy_state_conflict()
    copy.status = "written_off"
    audit.record(session, clock, actor, "copy.written_off", "copy", copy)
    session.commit()
    return copy_out(copy)
