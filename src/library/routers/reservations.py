"""Бронювання та черга (REQ-F-023...026)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.circulation import PICKUP_PERIOD, free_copy, queue_position
from library.db import Account, Edition, Reservation, to_db
from library.deps import current_account, get_clock, get_session, require
from library.errors import not_found
from library.notifications import notify_reservation_ready
from library.routers.readers import readable_reader
from library.schemas import ReservationCreate, ReservationStatus, iso, page_out

router = APIRouter()


def reservation_out(session: Session, reservation: Reservation) -> dict:
    return {"id": reservation.id, "readerId": reservation.reader_id, "editionId": reservation.edition_id,
            "status": reservation.status, "queuePosition": queue_position(session, reservation),
            "pickupDeadline": iso(reservation.pickup_deadline) if reservation.pickup_deadline else None,
            "createdAt": iso(reservation.created_at)}


@router.post("/reservations", status_code=201)
def create_reservation(body: ReservationCreate, session: Session = Depends(get_session), clock=Depends(get_clock),
                       reader: Account = Depends(require("reader"))):
    edition = session.get(Edition, str(body.editionId))
    if edition is None:
        raise not_found()
    now = to_db(clock.now())
    reservation = Reservation(reader_id=reader.id, edition_id=edition.id, created_at=now, status="queued")
    copy = free_copy(session, edition.id)
    if copy is not None:                                       # REQ-F-023: доступне — утримується 2 доби
        reservation.status = "ready"
        reservation.copy_id = copy.id
        reservation.pickup_deadline = now + PICKUP_PERIOD
    session.add(reservation)                                   # інакше REQ-F-024: черга
    if reservation.status == "ready":
        session.flush()
        notify_reservation_ready(session, reservation)
    session.commit()
    audit.record(session, clock, reader, f"reservation.{reservation.status}", "reservation", reservation.id)
    return reservation_out(session, reservation)


@router.get("/readers/{reader_id}/reservations")
def list_reader_reservations(reader_id: str, status: ReservationStatus | None = None,
                             page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                             session: Session = Depends(get_session), viewer: Account = Depends(current_account)):
    readable_reader(session, viewer, reader_id)
    query = select(Reservation).where(Reservation.reader_id == reader_id)
    if status:
        query = query.where(Reservation.status == status)
    reservations = session.scalars(query.order_by(Reservation.seq)).all()
    chunk = reservations[(page - 1) * pageSize: page * pageSize]
    return page_out([reservation_out(session, r) for r in chunk], page, pageSize, len(reservations))
