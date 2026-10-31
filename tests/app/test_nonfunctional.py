"""G13: нефункціональні вимоги (REQ-NF-001, 002, LS-28).

REQ-NF-004 (видача за ≤ 3 кроки інтерфейсу без навчання) стосується веб-інтерфейсу,
якого в цій роботі немає; API автоматичним тестом її довести не може. Вона
перевіряється людиною під час валідації (крок 7 лаби).
"""
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


# --- REQ-NF-001: типові операції ≤ 2 с при 10 одночасних користувачах
def test_typical_operations_take_under_2_seconds_with_10_concurrent_users(client, api, librarian):
    edition, copies = api.stock(librarian, copies=10)
    readers = [api.reader() for _ in range(10)]

    def session(i):
        reader, headers = readers[i]
        timings = []
        for method, path, kwargs in (
            ("get", "/editions", {"headers": headers, "params": {"author": "Шевченко"}}),          # пошук
            ("post", "/loans", {"headers": librarian,
                                "json": {"readerId": reader["id"], "copyId": copies[i]["id"]}}),  # видача
            ("get", f"/readers/{reader['id']}/loans", {"headers": headers}),                       # кабінет
        ):
            started = time.perf_counter()
            r = getattr(client, method)(path, **kwargs)
            timings.append(time.perf_counter() - started)
            assert r.status_code in (200, 201), r.text
        return timings

    with ThreadPoolExecutor(max_workers=10) as pool:
        slowest = max(t for timings in pool.map(session, range(10)) for t in timings)

    assert slowest < 2.0


# --- REQ-NF-002: автоматичне резервне копіювання не рідше разу на добу
def backups(backup_dir):
    return sorted(backup_dir.glob("*.db")) if backup_dir.exists() else []


def test_backup_is_made_automatically(client, api, backup_dir):
    api.reader("reader@example.com")

    assert len(backups(backup_dir)) == 1


def test_no_second_backup_within_a_day(client, api, clock, backup_dir):
    api.reader()
    clock.advance(hours=23)
    api.reader()

    assert len(backups(backup_dir)) == 1


def test_new_backup_after_a_day(client, api, clock, backup_dir):
    api.reader()
    clock.advance(hours=24, minutes=1)
    api.reader()

    assert len(backups(backup_dir)) == 2


def test_backup_can_be_restored_with_all_data(client, api, clock, backup_dir):
    api.reader("first@example.com")
    clock.advance(hours=24, minutes=1)
    api.reader("second@example.com")                    # перший запит після доби створює другу копію

    latest = backups(backup_dir)[-1]
    with sqlite3.connect(latest) as restored:
        emails = {row[0] for row in restored.execute("select email from accounts")}
    assert {"first@example.com"} <= emails


def test_backup_is_written_to_system_log(client, api, read_log):
    api.reader()

    assert any("резервн" in r["message"].lower() for r in read_log())
