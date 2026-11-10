"""Схема бази даних (SQLite через SQLAlchemy). Внутрішня модель, не частина контракту."""
import uuid
from datetime import date, datetime, timezone

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def new_id() -> str:
    """Генерує новий унікальний UUID v4 у вигляді рядка."""
    return str(uuid.uuid4())


def to_db(moment: datetime) -> datetime:
    """Нормалізує часову мітку до UTC без інформації про пояс (naive UTC).

    SQLite зберігає дату/час без таймзони, тому всі моменти приводяться до UTC
    і позбавляються tzinfo перед збереженням.

    Args:
        moment: Вихідний об'єкт datetime (з таймзоною або без).

    Returns:
        datetime в UTC без tzinfo.
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Базовий декларативний клас SQLAlchemy для всіх таблиць моделі."""
    pass


class Account(Base):
    """Обліковий запис будь-якої ролі: reader, librarian, admin, chief_admin."""
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime]
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(default=None)
    # Поля читача
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    birth_date: Mapped[str | None] = mapped_column(String(10), default=None)


class AccessToken(Base):
    """Токен сесії користувача для автентифікації за схемою Bearer (REQ-F-047)."""
    __tablename__ = "access_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))


class EmailToken(Base):
    """Одноразові токени з листів: підтвердження email і скидання пароля (REQ-F-016, REQ-F-048)."""
    __tablename__ = "email_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    kind: Mapped[str] = mapped_column(String(30))
    used: Mapped[bool] = mapped_column(default=False)


class Genre(Base):
    """Довідник літературних жанрів для класифікації видань (REQ-F-007, 008)."""
    __tablename__ = "genres"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))


class Edition(Base):
    """Бібліографічний запис видання в каталозі (REQ-F-001...003)."""
    __tablename__ = "editions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    author: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int]
    isbn: Mapped[str] = mapped_column(String(13), unique=True)
    genre_id: Mapped[str] = mapped_column(ForeignKey("genres.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_copies: Mapped[int]


class Copy(Base):
    """Фізичний екземпляр видання з інвентарним номером і станом (REQ-F-004...006)."""
    __tablename__ = "copies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    edition_id: Mapped[str] = mapped_column(ForeignKey("editions.id"))
    inventory_number: Mapped[str] = mapped_column(String(50), unique=True)
    location: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="available")


class Loan(Base):
    """Видача екземпляра читачу. Штраф і статус «компенсовано» обчислюються на льоту (REQ-F-027, 029)."""
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reader_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    copy_id: Mapped[str] = mapped_column(ForeignKey("copies.id"))
    edition_id: Mapped[str] = mapped_column(ForeignKey("editions.id"), index=True)
    issued_on: Mapped[date]
    due_on: Mapped[date]
    term_days: Mapped[int]
    fine_rate_percent: Mapped[int]
    # Ціна фіксується при видачі разом зі ставкою: подальша зміна ціни видання не змінює штраф.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    returned_on: Mapped[date | None] = mapped_column(default=None)
    fine_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))


class Reservation(Base):
    """Бронювання (`ready`, утримує екземпляр) або місце в черзі (`queued`)."""
    __tablename__ = "reservations"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id)
    reader_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    edition_id: Mapped[str] = mapped_column(ForeignKey("editions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    copy_id: Mapped[str | None] = mapped_column(ForeignKey("copies.id"), default=None)
    pickup_deadline: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime]


class FinePayment(Base):
    """Факт сплати нарахованого штрафу читачем через бібліотекаря (REQ-F-030, 031)."""
    __tablename__ = "fine_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reader_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    method: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    paid_at: Mapped[datetime]


class Notification(Base):
    """Внутрішнє сповіщення читача (REQ-F-035...038). `key` не дає створити ту саму подію двічі."""
    __tablename__ = "notifications"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), unique=True)
    reader_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(300))
    loan_id: Mapped[str | None] = mapped_column(String(36), default=None)
    reservation_id: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime]


class AuditEntry(Base):
    """Аудит-лог значущих дій користувачів (REQ-F-049), окремо від системного журналу."""
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(50))
    object_type: Mapped[str] = mapped_column(String(30))
    object_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(index=True)


def make_session_factory(database_url: str):
    """Створює фабрику сесій SQLAlchemy з оптимізованими налаштуваннями SQLite.

    Вмикає перевірку зовнішніх ключів (PRAGMA foreign_keys=ON), режим WAL
    (PRAGMA journal_mode=WAL) та реєструє детерміновану функцію `casefold`
    для підтримки нечутливого до регістру пошуку кирилицею.

    Args:
        database_url: Рядок підключення до БД (наприклад, 'sqlite:///var/library.db').

    Returns:
        Об'єкт sessionmaker для створення сесій бази даних.
    """
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        # WAL: читання не блокує запис, збереження не чекає повного запису на диск після кожної транзакції.
        # База лишається цілісною при збої; раптове вимкнення живлення може втратити останні секунди записів
        # (прийнятно: щодобове резервне копіювання, SLA не встановлюється — REQ-NF-002).
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        # Вбудована lower() SQLite змінює лише латиницю; casefold() Python — будь-яку абетку, зокрема кирилицю.
        connection.create_function("casefold", 1, lambda text: text.casefold() if text else text, deterministic=True)

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
