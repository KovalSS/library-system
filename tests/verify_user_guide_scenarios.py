"""Перевірка користувацької документації (`docs/user-guide.md`) проти фактичного API (Крок 10)."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from library.app import create_app
from library.infrastructure import ChiefAdmin


class SimpleClock:
    def __init__(self):
        from datetime import datetime, timezone
        self.dt = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    def now(self):
        return self.dt


class InMemoryOutbox:
    def __init__(self):
        self.messages = []

    def send(self, to, kind, token):
        self.messages.append({"to": to, "kind": kind, "token": token})


def run_user_guide_verification(tmp_path):
    clock = SimpleClock()
    outbox = InMemoryOutbox()
    chief = ChiefAdmin(email="chief@library.local", password="Chief-Pass-2026")

    app = create_app(
        log_file=tmp_path / "test.log",
        database_url=f"sqlite:///{tmp_path}/test.db",
        chief_admin=chief,
        mailer=outbox,
        clock=clock,
        password_iterations=1000,
        backup_dir=tmp_path / "backups",
    )

    client = TestClient(app)

    print("1. Сценарій 1: Реєстрація, активація та вхід читача...")
    r = client.post("/readers", json={
        "fullName": "Олена Коваленко",
        "email": "olena@example.ua",
        "phone": "+380501234567",
        "birthDate": "2000-05-14",
        "password": "SecurePassword123"
    })
    assert r.status_code == 201, r.text
    reader_id = r.json()["id"]

    # Лист з токеном
    token = outbox.messages[-1]["token"]
    r = client.post("/email-confirmations", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    # Вхід
    r = client.post("/auth/login", json={"email": "olena@example.ua", "password": "SecurePassword123"})
    assert r.status_code == 200, r.text
    reader_token = r.json()["accessToken"]
    reader_headers = {"Authorization": f"Bearer {reader_token}"}

    print("2. Сценарій: Створення персоналу головним адміном...")
    r = client.post("/auth/login", json={"email": "chief@library.local", "password": "Chief-Pass-2026"})
    chief_token = r.json()["accessToken"]
    chief_headers = {"Authorization": f"Bearer {chief_token}"}

    # Створення бібліотекаря
    r = client.post("/librarians", headers=chief_headers, json={
        "fullName": "Марія Іванівна",
        "email": "maria@library.local",
        "password": "LibrarianPass123"
    })
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": "maria@library.local", "password": "LibrarianPass123"})
    lib_token = r.json()["accessToken"]
    lib_headers = {"Authorization": f"Bearer {lib_token}"}

    print("3. Сценарій 2: Каталог та пошук літератури...")
    # Додаємо жанр і видання
    r = client.post("/genres", headers=chief_headers, json={"name": "Поезія"})
    genre_id = r.json()["id"]

    r = client.post("/editions", headers=lib_headers, json={
        "author": "Тарас Шевченко",
        "title": "Кобзар",
        "year": 2021,
        "isbn": "9789660100001",
        "genreId": genre_id,
        "price": 250.00,
        "totalCopies": 1
    })
    assert r.status_code == 201, r.text
    edition_id = r.json()["id"]

    r = client.post(f"/editions/{edition_id}/copies", headers=lib_headers, json={
        "inventoryNumber": "KBZ-001",
        "location": "Зал 1, стелаж 2",
        "status": "available"
    })
    copy_id = r.json()["id"]

    # Пошук
    r = client.get("/editions", headers=reader_headers, params={"title": "Кобзар", "availableOnly": True})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    print("4. Сценарій 3: Бронювання книги...")
    r = client.post("/reservations", headers=reader_headers, json={"editionId": edition_id})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "ready"

    print("5. Сценарій 4: Видача та повернення книги...")
    r = client.post("/loans", headers=lib_headers, json={"readerId": reader_id, "copyId": copy_id})
    assert r.status_code == 201, r.text
    loan_id = r.json()["id"]

    r = client.post(f"/loans/{loan_id}/return", headers=lib_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "returned"

    print("6. Сценарій 6: Сповіщення та рекомендації...")
    r = client.get(f"/readers/{reader_id}/notifications", headers=reader_headers)
    assert r.status_code == 200
    r = client.get(f"/readers/{reader_id}/recommendations", headers=reader_headers)
    assert r.status_code == 200

    print("7. Сценарій 7: Звіти та аудит-лог...")
    r = client.get("/reports/top-editions", headers=lib_headers, params={"from": "2026-01-01", "to": "2026-12-31"})
    assert r.status_code == 200
    r = client.get("/reports/debtors", headers=lib_headers)
    assert r.status_code == 200
    r = client.get("/audit-log-entries", headers=chief_headers)
    assert r.status_code == 200
    assert r.json()["total"] > 0

    print("Всі сценарії з docs/user-guide.md успішно відтворені та перевірені!")
    app.state.sessions.kw['bind'].dispose()
    import logging
    logging.shutdown()


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        run_user_guide_verification(Path(td))
