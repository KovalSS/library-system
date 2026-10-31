"""Запис значущих дій в аудит-лог (REQ-F-049): хто, що саме, з яким об'єктом, коли."""
from sqlalchemy.orm import Session

from library.db import Account, AuditEntry, to_db


def record(session: Session, clock, actor: Account, action: str, object_type: str, target) -> None:
    """Додає запис до поточної транзакції: дія і її аудит зберігаються одним `commit` або не зберігаються зовсім."""
    session.flush()                  # ідентифікатор нового об'єкта з'являється після flush
    session.add(AuditEntry(actor_id=actor.id, actor_role=actor.role, action=action, object_type=object_type,
                           object_id=target.id, occurred_at=to_db(clock.now())))
