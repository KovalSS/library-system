"""Каталог і фонд: жанри, видання, екземпляри (REQ-F-001...008)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library.db import Account, Copy, Edition, Genre
from library.deps import ADMIN_ROLES, STAFF_ROLES, current_account, get_session, require
from library.errors import ApiError, not_found, validation_failed
from library.schemas import (CopyInput, CopyUpdate, EditionInput, EditionUpdate, GenreInput, copy_out,
                             edition_out, genre_out)

router = APIRouter()

# Стани, які встановлює система (видача, списання), а не ручна зміна (REQ-F-006).
SYSTEM_MANAGED_STATES = ("issued", "written_off")


# --- REQ-F-003: довідник жанрів
@router.get("/genres")
def list_genres(session: Session = Depends(get_session), _: Account = Depends(current_account)):
    return [genre_out(g) for g in session.scalars(select(Genre).order_by(Genre.name))]


@router.post("/genres", status_code=201)
def create_genre(body: GenreInput, session: Session = Depends(get_session), _=Depends(require(*ADMIN_ROLES))):
    genre = Genre(name=body.name)
    session.add(genre)
    session.commit()
    return genre_out(genre)


@router.patch("/genres/{genre_id}")
def update_genre(genre_id: str, body: GenreInput, session: Session = Depends(get_session),
                 _=Depends(require(*ADMIN_ROLES))):
    genre = session.get(Genre, genre_id)
    if genre is None:
        raise not_found()
    genre.name = body.name
    session.commit()
    return genre_out(genre)


# --- REQ-F-001, 002, 008: видання
def available_copies(session: Session, edition_id: str) -> int:
    return session.scalar(select(func.count()).where(Copy.edition_id == edition_id, Copy.status == "available"))


def present_edition(session: Session, edition: Edition) -> dict:
    return edition_out(edition, session.get(Genre, edition.genre_id), available_copies(session, edition.id), loans=0)


def existing_genre(session: Session, genre_id: str) -> None:
    # Контракт не має 404 для createEdition: невідомий жанр — помилка вхідних даних.
    if session.get(Genre, genre_id) is None:
        raise validation_failed("genreId", "Жанр не знайдено в довіднику.")


def ensure_isbn_free(session: Session, isbn: str, except_id: str | None = None) -> None:
    other = session.scalar(select(Edition).where(Edition.isbn == isbn))
    if other is not None and other.id != except_id:
        raise ApiError(409, "duplicate_isbn", "Видання з таким ISBN уже є в каталозі.")


def get_edition_or_404(session: Session, edition_id: str) -> Edition:
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise not_found()
    return edition


@router.post("/editions", status_code=201)
def create_edition(body: EditionInput, session: Session = Depends(get_session), _=Depends(require("librarian"))):
    existing_genre(session, body.genreId)
    ensure_isbn_free(session, body.isbn)
    edition = Edition(author=body.author, title=body.title, year=body.year, isbn=body.isbn,
                      genre_id=body.genreId, price=body.price, total_copies=body.totalCopies)
    session.add(edition)
    session.commit()
    return present_edition(session, edition)


@router.get("/editions/{edition_id}")
def get_edition(edition_id: str, session: Session = Depends(get_session), _: Account = Depends(current_account)):
    return present_edition(session, get_edition_or_404(session, edition_id))


@router.patch("/editions/{edition_id}")
def update_edition(edition_id: str, body: EditionUpdate, session: Session = Depends(get_session),
                   _=Depends(require("librarian"))):
    edition = get_edition_or_404(session, edition_id)
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
    session.commit()
    return present_edition(session, edition)


# --- REQ-F-004...007: екземпляри
@router.get("/editions/{edition_id}/copies")
def list_copies(edition_id: str, session: Session = Depends(get_session), _=Depends(require(*STAFF_ROLES))):
    get_edition_or_404(session, edition_id)
    copies = session.scalars(select(Copy).where(Copy.edition_id == edition_id).order_by(Copy.inventory_number))
    return [copy_out(c) for c in copies]


@router.post("/editions/{edition_id}/copies", status_code=201)
def create_copy(edition_id: str, body: CopyInput, session: Session = Depends(get_session),
                _=Depends(require("librarian"))):
    get_edition_or_404(session, edition_id)
    if session.scalar(select(Copy).where(Copy.inventory_number == body.inventoryNumber)) is not None:
        raise ApiError(409, "duplicate_inventory_number", "Екземпляр із таким інвентарним номером уже існує.")
    copy = Copy(edition_id=edition_id, inventory_number=body.inventoryNumber, location=body.location,
                status=body.status)
    session.add(copy)
    session.commit()
    return copy_out(copy)


def get_copy_or_404(session: Session, copy_id: str) -> Copy:
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise not_found()
    return copy


def copy_state_conflict() -> ApiError:
    return ApiError(409, "copy_state_conflict", "Екземпляр виданий або списаний, зміна неможлива.")


@router.patch("/copies/{copy_id}")
def update_copy(copy_id: str, body: CopyUpdate, session: Session = Depends(get_session),
                _=Depends(require("librarian"))):
    copy = get_copy_or_404(session, copy_id)
    if body.status is not None:
        if copy.status in SYSTEM_MANAGED_STATES:
            raise copy_state_conflict()
        copy.status = body.status
    if body.location is not None:
        copy.location = body.location
    session.commit()
    return copy_out(copy)


@router.post("/copies/{copy_id}/write-off")
def write_off_copy(copy_id: str, session: Session = Depends(get_session), _=Depends(require("librarian"))):
    copy = get_copy_or_404(session, copy_id)
    if copy.status in SYSTEM_MANAGED_STATES:
        raise copy_state_conflict()
    copy.status = "written_off"
    session.commit()
    return copy_out(copy)
