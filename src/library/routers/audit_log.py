"""Перегляд аудит-логу адміністраторами (REQ-F-049)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from library.db import AuditEntry, to_db
from library.deps import ADMIN_ROLES, get_session, require
from library.schemas import iso, page_out

router = APIRouter()


@router.get("/audit-log-entries")
def list_audit_log_entries(actorId: str | None = None,
                           from_: datetime | None = Query(default=None, alias="from"),
                           to: datetime | None = None,
                           page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
                           session: Session = Depends(get_session), _=Depends(require(*ADMIN_ROLES))):
    query = select(AuditEntry)
    if actorId:
        query = query.where(AuditEntry.actor_id == actorId)
    if from_:
        query = query.where(AuditEntry.occurred_at >= to_db(from_))
    if to:
        query = query.where(AuditEntry.occurred_at <= to_db(to))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    entries = session.scalars(query.order_by(AuditEntry.occurred_at.desc())
                              .offset((page - 1) * pageSize).limit(pageSize))
    return page_out([{"id": e.id, "actorId": e.actor_id, "actorRole": e.actor_role, "action": e.action,
                      "objectType": e.object_type, "objectId": e.object_id, "occurredAt": iso(e.occurred_at)}
                     for e in entries], page, pageSize, total)
