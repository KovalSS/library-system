"""Доступ до персональних даних читача (REQ-F-050)."""
from sqlalchemy.orm import Session

from library.db import Account
from library.deps import get_or_404
from library.errors import forbidden


def readable_reader(session: Session, viewer: Account, reader_id: str) -> Account:
    """Читач бачить лише себе (про чужі акаунти навіть не дізнається, чи вони існують); персонал — усіх."""
    if viewer.role == "reader" and viewer.id != reader_id:
        raise forbidden()
    return get_or_404(session, Account, reader_id, lambda a: a.role == "reader")
