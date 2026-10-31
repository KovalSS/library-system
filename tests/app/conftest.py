import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from contract import assert_contract
from library.app import create_app
from library.infrastructure import ChiefAdmin

CHIEF = ChiefAdmin(email="chief@library.test", password="Chief-Pass-2026")


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    def now(self):
        return self.current

    def advance(self, **delta):
        self.current += timedelta(**delta)


class Outbox:
    """Підміна пошти: зберігає листи, щоб тест дістав токен із листа."""

    def __init__(self):
        self.messages = []

    def send(self, to, kind, token):
        self.messages.append({"to": to, "kind": kind, "token": token})

    def last(self, to, kind):
        found = [m for m in self.messages if m["to"] == to and m["kind"] == kind]
        assert found, f"листа {kind} для {to} немає"
        return found[-1]["token"]


@pytest.fixture
def log_file(tmp_path):
    return tmp_path / "library.log"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "library.db"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def outbox():
    return Outbox()


@pytest.fixture
def backup_dir(tmp_path):
    return tmp_path / "backups"


@pytest.fixture
def app(log_file, db_path, clock, outbox, backup_dir):
    return create_app(
        log_file=log_file,
        database_url=f"sqlite:///{db_path}",
        chief_admin=CHIEF,
        mailer=outbox,
        clock=clock,
        # Тести не захищають справжніх паролів: менше повторів хешування пришвидшує прогін у десятки разів.
        password_iterations=1_000,
        backup_dir=backup_dir,
    )


@pytest.fixture
def client(app):
    # Необроблені винятки мають перетворюватися на відповідь 500, а не падати в тесті.
    # Клієнт відкривається один раз на тест: без `with` він запускає новий цикл подій на кожен запит.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def read_log(log_file):
    """Записи системного журналу (JSON Lines). Порожній список, якщо файлу ще немає."""
    def read():
        if not log_file.exists():
            return []
        return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return read


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class Api:
    """Підготовка даних через публічний API (лише операції контракту)."""

    def __init__(self, client, outbox):
        self.client = client
        self.outbox = outbox
        self._counter = 0

    def unique(self, prefix):
        self._counter += 1
        return f"{prefix}{self._counter}"

    def login(self, email, password):
        r = self.client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()

    def token(self, email, password):
        return self.login(email, password)["accessToken"]

    @property
    def chief(self):
        return bearer(self.token(CHIEF.email, CHIEF.password))

    def create_admin(self, email=None, password="Adm1n-Pass-2026", full_name="Олена Коваль"):
        email = email or f"{self.unique('admin')}@library.test"
        r = self.client.post("/administrators", headers=self.chief,
                             json={"fullName": full_name, "email": email, "password": password})
        assert r.status_code == 201, r.text
        return r.json(), bearer(self.token(email, password))

    def create_librarian(self, email=None, password="L1brarian-Pass", full_name="Марія Гнатюк"):
        email = email or f"{self.unique('librarian')}@library.test"
        r = self.client.post("/librarians", headers=self.chief,
                             json={"fullName": full_name, "email": email, "password": password})
        assert r.status_code == 201, r.text
        return r.json(), bearer(self.token(email, password))

    def register(self, email=None, password="S3cret-pass", **fields):
        email = email or f"{self.unique('reader')}@example.com"
        body = {"fullName": "Іван Петренко", "email": email, "phone": "+380501234567",
                "birthDate": "1995-04-12", "password": password, **fields}
        return self.client.post("/readers", json=body)

    def reader(self, email=None, password="S3cret-pass"):
        """Зареєстрований і підтверджений читач: (профіль, заголовки авторизації)."""
        email = email or f"{self.unique('reader')}@example.com"
        r = self.register(email, password)
        assert r.status_code == 201, r.text
        token = self.outbox.last(email, "email_confirmation")
        r = self.client.post("/email-confirmations", json={"token": token})
        assert r.status_code == 200, r.text
        return r.json(), bearer(self.token(email, password))

    def genre(self, name=None):
        _, admin = self.create_admin()
        r = self.client.post("/genres", headers=admin, json={"name": name or self.unique("Жанр ")})
        assert r.status_code == 201, r.text
        return r.json()

    def edition(self, librarian, **fields):
        genre_id = fields.pop("genreId", None) or self.genre()["id"]
        body = {"author": "Тарас Шевченко", "title": "Кобзар", "year": 1840,
                "isbn": self.isbn(), "genreId": genre_id, "price": 300, "totalCopies": 5, **fields}
        r = self.client.post("/editions", headers=librarian, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def isbn(self):
        self._counter += 1
        return f"978617{self._counter:07d}"

    def copy(self, librarian, edition_id, **fields):
        body = {"inventoryNumber": self.unique("INV-"), "location": "Зал 1, стелаж 1", **fields}
        r = self.client.post(f"/editions/{edition_id}/copies", headers=librarian, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def stock(self, librarian, copies=1, price=300):
        """Видання з указаною ціною та кількістю доступних екземплярів: (видання, [екземпляри])."""
        edition = self.edition(librarian, price=price)
        return edition, [self.copy(librarian, edition["id"]) for _ in range(copies)]

    def issue(self, librarian, reader_id, copy_id):
        r = self.client.post("/loans", headers=librarian, json={"readerId": reader_id, "copyId": copy_id})
        assert r.status_code == 201, r.text
        return r.json()

    def give_back(self, librarian, loan_id):
        r = self.client.post(f"/loans/{loan_id}/return", headers=librarian)
        assert r.status_code == 200, r.text
        return r.json()

    def reserve(self, reader_headers, edition_id):
        r = self.client.post("/reservations", headers=reader_headers, json={"editionId": edition_id})
        assert r.status_code == 201, r.text
        return r.json()

    def reservations(self, reader, reader_headers):
        r = self.client.get(f"/readers/{reader['id']}/reservations", headers=reader_headers)
        assert r.status_code == 200, r.text
        return {x["id"]: x for x in r.json()["items"]}

    def loan(self, headers, loan_id):
        r = self.client.get(f"/loans/{loan_id}", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    def fines(self, reader, headers):
        r = self.client.get(f"/readers/{reader['id']}/fines", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def api(client, outbox):
    return Api(client, outbox)


@pytest.fixture
def contract():
    return assert_contract
