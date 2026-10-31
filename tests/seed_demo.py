"""Демо-дані для валідації людиною (крок 7 лаби): видачі з минулими датами.

    python tests/seed_demo.py --reset

Заповнює `var/library.db` через ті самі операції API, що й користувачі, але з годинником,
відмотаним на 40 днів, — щоб одразу існували прострочені видачі й несплачені штрафи.
Ручного втручання в базу немає. `--reset` видаляє наявну локальну базу `var/library.db`.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from library.app import DEFAULT_DATABASE_URL, create_app, default_chief_admin  # noqa: E402

DB = ROOT / "var" / "library.db"
PASSWORD = "S3cret-pass"


class MovableClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


class Letters:
    def __init__(self):
        self.tokens = {}

    def send(self, to, kind, token):
        self.tokens[(to, kind)] = token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="видалити наявну локальну базу var/library.db")
    args = parser.parse_args()
    existing = [p for p in DB.parent.glob(DB.name + "*")]
    if existing and not args.reset:
        sys.exit("База var/library.db уже існує. Запустіть з --reset, щоб створити демо-дані з нуля.")
    for path in existing:
        path.unlink()

    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    clock, letters = MovableClock(today - timedelta(days=40)), Letters()
    chief = default_chief_admin()
    app = create_app(database_url=DEFAULT_DATABASE_URL, chief_admin=chief, mailer=letters, clock=clock)

    with TestClient(app) as client:
        def call(method, path, token=None, **kwargs):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            r = client.request(method, path, headers=headers, **kwargs)
            assert r.status_code < 300, f"{method} {path}: {r.status_code} {r.text}"
            return r.json() if r.content else None

        def login(email, password):
            return call("POST", "/auth/login", json={"email": email, "password": password})["accessToken"]

        chief_t = login(chief.email, chief.password)
        call("POST", "/administrators", chief_t, json={"fullName": "Олена Коваль", "email": "admin@library.local",
                                                       "password": "Adm1n-Pass-2026"})
        call("POST", "/librarians", chief_t, json={"fullName": "Марія Гнатюк", "email": "lib@library.local",
                                                   "password": "L1brarian-Pass"})
        admin_t, lib_t = login("admin@library.local", "Adm1n-Pass-2026"), login("lib@library.local", "L1brarian-Pass")

        genres = {name: call("POST", "/genres", admin_t, json={"name": name})["id"]
                  for name in ("Поезія", "Повість", "Драма")}
        copies = {}
        for i, (author, title, year, genre, count) in enumerate((
                ("Тарас Шевченко", "Кобзар", 1840, "Поезія", 2),
                ("Тарас Шевченко", "Гайдамаки", 1841, "Поезія", 1),
                ("Леся Українка", "Лісова пісня", 1911, "Драма", 2),
                ("Іван Франко", "Захар Беркут", 1883, "Повість", 2),
                ("Михайло Коцюбинський", "Тіні забутих предків", 1911, "Повість", 1)), start=1):
            edition = call("POST", "/editions", lib_t, json={
                "author": author, "title": title, "year": year, "isbn": f"978617000{i:04d}",
                "genreId": genres[genre], "price": 300, "totalCopies": count})
            copies[title] = [call("POST", f"/editions/{edition['id']}/copies", lib_t,
                                  json={"inventoryNumber": f"INV-{i:02d}-{n}", "location": f"Зал {i}"})["id"]
                             for n in range(1, count + 1)]

        readers = {}
        for name, email in (("Іван Петренко", "ivan@example.com"), ("Петро Бойко", "petro@example.com"),
                            ("Ольга Шевчук", "olha@example.com")):
            reader = call("POST", "/readers", json={"fullName": name, "email": email, "phone": "+380501234567",
                                                    "birthDate": "1995-04-12", "password": PASSWORD})
            call("POST", "/email-confirmations", json={"token": letters.tokens[(email, "email_confirmation")]})
            readers[email] = reader["id"]

        # 40 днів тому: Іван і Петро беруть книги на 30 днів
        call("POST", "/loans", lib_t, json={"readerId": readers["ivan@example.com"], "copyId": copies["Захар Беркут"][0]})
        petro_loan = call("POST", "/loans", lib_t, json={"readerId": readers["petro@example.com"],
                                                         "copyId": copies["Тіні забутих предків"][0]})
        # 5 днів тому: Петро повертає із запізненням на 5 днів і не сплачує штраф
        clock.moment = today - timedelta(days=5)
        call("POST", f"/loans/{petro_loan['id']}/return", lib_t)
        # 3 дні тому: Ольга бере книгу; термін ще не минув
        clock.moment = today - timedelta(days=3)
        call("POST", "/loans", lib_t, json={"readerId": readers["olha@example.com"], "copyId": copies["Лісова пісня"][0]})

    letters_file = ROOT / "var" / "mail" / "outbox.jsonl"
    letters_file.parent.mkdir(parents=True, exist_ok=True)
    letters_file.write_text("".join(json.dumps({"to": to, "kind": kind, "token": token}, ensure_ascii=False) + "\n"
                                    for (to, kind), token in letters.tokens.items()), encoding="utf-8")
    print("Демо-дані створено у var/library.db. Облікові записи (пароль читачів: S3cret-pass):")
    print(f"  головний адміністратор  {chief.email} / {chief.password}")
    print("  адміністратор           admin@library.local / Adm1n-Pass-2026")
    print("  бібліотекар             lib@library.local / L1brarian-Pass")
    print("  ivan@example.com   — боржник: «Захар Беркут» прострочено на 10 днів, штраф 30 грн")
    print("  petro@example.com  — повернув на 5 днів пізніше, несплачений штраф 15 грн")
    print("  olha@example.com   — поточна видача без прострочення, боргу немає")
    print("Ідентифікатори читачів і екземплярів:")
    for email, reader_id in readers.items():
        print(f"  {email:20} {reader_id}")
    for title, ids in copies.items():
        print(f"  {title:22} {', '.join(ids)}")


if __name__ == "__main__":
    main()
