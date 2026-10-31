"""G12: сповіщення читача (REQ-F-035...038, LS-27). Термін повернення видачі від 31.10.2026 — 30.11.2026."""
from datetime import datetime, timezone

import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


@pytest.fixture
def loan(api, librarian):
    reader, headers = api.reader()
    _, [copy] = api.stock(librarian, price=300)
    loan = api.issue(librarian, reader["id"], copy["id"])
    assert loan["dueDate"] == "2026-11-30"
    return {"reader": reader, "headers": headers, "loan": loan}


def set_date(clock, day):
    clock.current = datetime.fromisoformat(day).replace(hour=10, tzinfo=timezone.utc)


def notifications(client, reader, headers, kind=None):
    r = client.get(f"/readers/{reader['id']}/notifications", headers=headers, params={"pageSize": 100})
    assert r.status_code == 200, r.text
    return [n for n in r.json()["items"] if kind is None or n["type"] == kind]


# --- REQ-F-035: наближення терміну (за 1–2 дні)
def test_no_due_soon_notice_three_days_before_due_date(client, clock, loan):
    set_date(clock, "2026-11-27")

    assert notifications(client, loan["reader"], loan["headers"], "due_soon") == []


def test_due_soon_notice_appears_two_days_before_and_is_not_repeated(client, clock, loan, contract):
    set_date(clock, "2026-11-28")
    r = client.get(f"/readers/{loan['reader']['id']}/notifications", headers=loan["headers"])
    contract(r, "listReaderNotifications")
    [notice] = [n for n in r.json()["items"] if n["type"] == "due_soon"]
    assert notice["loanId"] == loan["loan"]["id"]

    set_date(clock, "2026-11-29")
    assert len(notifications(client, loan["reader"], loan["headers"], "due_soon")) == 1


def test_returned_loan_gets_no_due_or_overdue_notices(client, api, librarian, clock, loan):
    api.give_back(librarian, loan["loan"]["id"])

    set_date(clock, "2026-12-03")

    assert notifications(client, loan["reader"], loan["headers"]) == []


# --- REQ-F-037: прострочення й кожне нарахування штрафу
def test_overdue_notice_appears_on_first_overdue_day(client, clock, loan):
    set_date(clock, "2026-12-01")

    [notice] = notifications(client, loan["reader"], loan["headers"], "overdue_fine")
    assert notice["loanId"] == loan["loan"]["id"]


def test_one_notice_for_each_day_of_fine(client, clock, loan):
    set_date(clock, "2026-12-03")

    assert len(notifications(client, loan["reader"], loan["headers"], "overdue_fine")) == 3


# --- REQ-F-036: бронювання доступне для отримання
def test_notice_when_reserved_copy_becomes_ready_with_pickup_deadline(client, api, librarian, clock):
    edition, [copy] = api.stock(librarian)
    first = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    reader, headers = api.reader()
    reservation = api.reserve(headers, edition["id"])               # черга
    clock.advance(days=3)
    api.give_back(librarian, first["id"])                           # 03.11 — копія для читача до 05.11

    [notice] = notifications(client, reader, headers, "reservation_ready")
    assert notice["reservationId"] == reservation["id"]
    assert "05.11.2026" in notice["message"]


# --- REQ-F-038: повний список у хронологічному порядку
def test_notifications_are_listed_newest_first(client, clock, loan):
    set_date(clock, "2026-12-02")

    items = notifications(client, loan["reader"], loan["headers"])

    assert [n["type"] for n in items] == ["overdue_fine", "overdue_fine", "due_soon"]
    assert [n["createdAt"] for n in items] == sorted((n["createdAt"] for n in items), reverse=True)


def test_reader_cannot_see_another_readers_notifications(client, api, loan, contract):
    _, stranger = api.reader()

    r = client.get(f"/readers/{loan['reader']['id']}/notifications", headers=stranger)

    contract(r, "listReaderNotifications")
    assert r.status_code == 403


def test_notifications_reject_invalid_page_size(client, loan):
    r = client.get(f"/readers/{loan['reader']['id']}/notifications", headers=loan["headers"],
                   params={"pageSize": 1000})

    assert r.status_code == 400
