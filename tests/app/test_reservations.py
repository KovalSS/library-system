"""G7: бронювання та черга (REQ-F-023...026, BDD 8.3, LS-16)."""
import pytest

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


def busy_edition(api, librarian):
    """Видання з одним екземпляром, який уже видано: (видання, видача)."""
    edition, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    return edition, loan


# --- BDD 8.3, REQ-F-023: бронювання вільного видання
def test_bdd_8_3_reserving_available_edition_holds_copy_for_2_days(client, api, librarian, contract):
    reader, reader_headers = api.reader()
    edition, _ = api.stock(librarian)

    r = client.post("/reservations", headers=reader_headers, json={"editionId": edition["id"]})

    contract(r, "createReservation")
    assert r.status_code == 201
    reservation = r.json()
    assert reservation["status"] == "ready"
    assert reservation["pickupDeadline"].startswith("2026-11-02T10:00")
    assert reservation["queuePosition"] is None
    assert reservation["id"] in api.reservations(reader, reader_headers)


def test_held_copy_is_not_available_to_others(client, api, librarian):
    edition, [copy] = api.stock(librarian)
    api.reserve(api.reader()[1], edition["id"])

    r = client.post("/loans", headers=librarian, json={"readerId": api.reader()[0]["id"], "copyId": copy["id"]})

    assert r.status_code == 409
    assert r.json()["code"] == "copy_not_available"
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 0


def test_issuing_held_copy_to_its_reader_fulfils_reservation(client, api, librarian):
    reader, reader_headers = api.reader()
    edition, [copy] = api.stock(librarian)
    reservation = api.reserve(reader_headers, edition["id"])

    api.issue(librarian, reader["id"], copy["id"])

    assert api.reservations(reader, reader_headers)[reservation["id"]]["status"] == "fulfilled"


# --- BDD 8.3, REQ-F-024: постановка в чергу на зайняте видання
def test_bdd_8_3_reserving_busy_edition_puts_reader_in_queue(client, api, librarian, contract):
    edition, _ = busy_edition(api, librarian)
    reader, reader_headers = api.reader()

    r = client.post("/reservations", headers=reader_headers, json={"editionId": edition["id"]})

    contract(r, "createReservation")
    assert r.status_code == 201
    assert r.json()["status"] == "queued"
    assert r.json()["queuePosition"] == 1
    assert r.json()["pickupDeadline"] is None


def test_queue_positions_follow_reservation_order(api, librarian):
    edition, _ = busy_edition(api, librarian)
    first = api.reserve(api.reader()[1], edition["id"])
    second = api.reserve(api.reader()[1], edition["id"])

    assert first["queuePosition"] == 1
    assert second["queuePosition"] == 2


def test_reader_sees_queue_position_in_cabinet(client, api, librarian, contract):
    edition, _ = busy_edition(api, librarian)
    api.reserve(api.reader()[1], edition["id"])
    reader, reader_headers = api.reader()
    mine = api.reserve(reader_headers, edition["id"])

    r = client.get(f"/readers/{reader['id']}/reservations", headers=reader_headers)

    contract(r, "listReaderReservations")
    assert [(x["id"], x["queuePosition"]) for x in r.json()["items"]] == [(mine["id"], 2)]


def test_reservation_of_unknown_edition_is_not_found(client, api, librarian, contract):
    _, reader_headers = api.reader()
    edition, _ = api.stock(librarian)

    r = client.post("/reservations", headers=reader_headers, json={"editionId": UNKNOWN_ID})

    contract(r, "createReservation")
    assert r.status_code == 404
    assert client.post("/reservations", headers=reader_headers, json={"editionId": edition["id"]}).status_code == 201


def test_only_readers_reserve(client, api, librarian):
    edition, _ = api.stock(librarian)

    assert client.post("/reservations", headers=librarian, json={"editionId": edition["id"]}).status_code == 403


def test_reservation_with_invalid_body_is_rejected(client, api):
    _, reader_headers = api.reader()

    assert client.post("/reservations", headers=reader_headers, json={"editionId": "abc"}).status_code == 400


def test_reader_cannot_see_another_readers_reservations(client, api):
    other, _ = api.reader()
    _, reader_headers = api.reader()

    assert client.get(f"/readers/{other['id']}/reservations", headers=reader_headers).status_code == 403


def test_reservations_can_be_filtered_by_status_and_reject_unknown_status(client, api, librarian):
    reader, reader_headers = api.reader()
    free, _ = api.stock(librarian)
    busy, _ = busy_edition(api, librarian)
    api.reserve(reader_headers, free["id"])
    queued = api.reserve(reader_headers, busy["id"])

    r = client.get(f"/readers/{reader['id']}/reservations", headers=reader_headers, params={"status": "queued"})
    assert [x["id"] for x in r.json()["items"]] == [queued["id"]]
    r = client.get(f"/readers/{reader['id']}/reservations", headers=reader_headers, params={"status": "cancelled"})
    assert r.status_code == 400


# --- REQ-F-025: автоматичне скасування, якщо не отримано за 2 дні
def test_reservation_is_still_held_just_before_2_days(api, librarian, clock):
    reader, reader_headers = api.reader()
    edition, _ = api.stock(librarian)
    reservation = api.reserve(reader_headers, edition["id"])

    clock.advance(days=1, hours=23, minutes=59)

    assert api.reservations(reader, reader_headers)[reservation["id"]]["status"] == "ready"


def test_reservation_expires_after_2_days_and_copy_is_free_again(client, api, librarian, clock):
    reader, reader_headers = api.reader()
    edition, [copy] = api.stock(librarian)
    reservation = api.reserve(reader_headers, edition["id"])

    clock.advance(days=2, minutes=1)

    assert api.reservations(reader, reader_headers)[reservation["id"]]["status"] == "expired"
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 1
    assert api.issue(librarian, api.reader()[0]["id"], copy["id"])["status"] == "active"


# --- REQ-F-026: перехід до наступного в черзі
def test_returned_copy_is_offered_to_first_in_queue(api, librarian, clock):
    edition, loan = busy_edition(api, librarian)
    first, first_headers = api.reader()
    second, second_headers = api.reader()
    first_reservation = api.reserve(first_headers, edition["id"])
    second_reservation = api.reserve(second_headers, edition["id"])
    clock.advance(days=5)

    api.give_back(librarian, loan["id"])

    offered = api.reservations(first, first_headers)[first_reservation["id"]]
    assert offered["status"] == "ready"
    assert offered["pickupDeadline"].startswith("2026-11-07T10:00")
    assert api.reservations(second, second_headers)[second_reservation["id"]]["queuePosition"] == 1


def test_returned_copy_offered_to_queue_cannot_be_issued_to_others(client, api, librarian):
    edition, loan = busy_edition(api, librarian)
    api.reserve(api.reader()[1], edition["id"])
    api.give_back(librarian, loan["id"])

    r = client.post("/loans", headers=librarian, json={"readerId": api.reader()[0]["id"], "copyId": loan["copyId"]})

    assert r.status_code == 409


def test_expired_reservation_passes_copy_to_next_in_queue(api, librarian, clock):
    edition, loan = busy_edition(api, librarian)
    first, first_headers = api.reader()
    second, second_headers = api.reader()
    first_reservation = api.reserve(first_headers, edition["id"])
    second_reservation = api.reserve(second_headers, edition["id"])
    api.give_back(librarian, loan["id"])          # копія -> першому в черзі

    clock.advance(days=2, minutes=1)              # перший не прийшов

    assert api.reservations(first, first_headers)[first_reservation["id"]]["status"] == "expired"
    offered = api.reservations(second, second_headers)[second_reservation["id"]]
    assert offered["status"] == "ready"
    assert offered["pickupDeadline"].startswith("2026-11-04T10:0")
