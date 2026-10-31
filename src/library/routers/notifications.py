"""Список сповіщень читача у хронологічному порядку від найновіших (REQ-F-038)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library.access import readable_reader
from library.db import Account, Notification
from library.deps import current_account, get_clock, get_session, today
from library.notifications import sync_loan_notifications
from library.schemas import iso, page_out

router = APIRouter()


def notification_out(n: Notification) -> dict:
    out = {"id": n.id, "readerId": n.reader_id, "type": n.type, "message": n.message, "createdAt": iso(n.created_at)}
    if n.loan_id:
        out["loanId"] = n.loan_id
    if n.reservation_id:
        out["reservationId"] = n.reservation_id
    return out


@router.get("/readers/{reader_id}/notifications")
def list_notifications(reader_id: str, page: int = Query(default=1, ge=1),
                       pageSize: int = Query(default=20, ge=1, le=100),
                       session: Session = Depends(get_session), clock=Depends(get_clock),
                       viewer: Account = Depends(current_account)):
    readable_reader(session, viewer, reader_id)
    sync_loan_notifications(session, reader_id, today(clock))
    query = select(Notification).where(Notification.reader_id == reader_id)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(query.order_by(Notification.created_at.desc(), Notification.seq.desc())
                            .offset((page - 1) * pageSize).limit(pageSize))
    return page_out([notification_out(n) for n in items], page, pageSize, total)
