"""G6: видача та повернення (REQ-F-018...021, BDD 8.1, LS-15). REQ-F-022 скасовано (LS-40)."""
import pytest

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


def copy_status(client, librarian, edition_id, copy_id):
    copies = client.get(f"/editions/{edition_id}/copies", headers=librarian).json()
    return next(c["status"] for c in copies if c["id"] == copy_id)


# --- BDD 8.1: успішна видача доступного екземпляра (REQ-F-018, 019)
def test_bdd_8_1_issue_available_copy_without_queue(client, api, librarian, contract):
    reader, reader_headers = api.reader()
    edition, [copy] = api.stock(librarian)

    r = client.post("/loans", headers=librarian, json={"readerId": reader["id"], "copyId": copy["id"]})

    contract(r, "createLoan")
    assert r.status_code == 201
    loan = r.json()
    assert loan["status"] == "active"
    assert loan["issuedAt"] == "2026-10-31"
    assert loan["termDays"] == 30
    assert loan["dueDate"] == "2026-11-30"
    assert loan["editionId"] == edition["id"]
    assert copy_status(client, librarian, edition["id"], copy["id"]) == "issued"
    history = client.get(f"/readers/{reader['id']}/loans", headers=reader_headers).json()["items"]
    assert [(h["id"], h["dueDate"]) for h in history] == [(loan["id"], "2026-11-30")]


# --- REQ-F-019: термін 14 днів, якщо на видання є черга
def test_term_is_14_days_when_edition_has_queue(client, api, librarian):
    edition, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, api.reader()[0]["id"], first["id"])
    api.issue(librarian, api.reader()[0]["id"], second["id"])
    api.reserve(api.reader()[1], edition["id"])           # усі видано -> черга
    third = api.copy(librarian, edition["id"])

    loan = api.issue(librarian, api.reader()[0]["id"], third["id"])

    assert loan["termDays"] == 14
    assert loan["dueDate"] == "2026-11-14"


def test_issued_copy_reduces_availability_and_counts_as_loan(client, api, librarian):
    edition, [copy, _] = api.stock(librarian, copies=2)

    api.issue(librarian, api.reader()[0]["id"], copy["id"])

    shown = client.get(f"/editions/{edition['id']}", headers=librarian).json()
    assert shown["availableCopies"] == 1
    assert shown["loansCount"] == 1


@pytest.mark.parametrize("state", ["damaged", "written_off"])
def test_unavailable_copy_cannot_be_issued(client, api, librarian, state, contract):
    reader, _ = api.reader()
    edition, [copy] = api.stock(librarian)
    if state == "damaged":
        client.patch(f"/copies/{copy['id']}", headers=librarian, json={"status": "damaged"})
    else:
        client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    r = client.post("/loans", headers=librarian, json={"readerId": reader["id"], "copyId": copy["id"]})

    contract(r, "createLoan")
    assert r.status_code == 409
    assert r.json()["code"] == "copy_not_available"


def test_issued_copy_cannot_be_issued_again(client, api, librarian):
    edition, [copy] = api.stock(librarian)
    api.issue(librarian, api.reader()[0]["id"], copy["id"])

    r = client.post("/loans", headers=librarian, json={"readerId": api.reader()[0]["id"], "copyId": copy["id"]})

    assert r.status_code == 409
    assert r.json()["code"] == "copy_not_available"


def test_loan_for_unknown_reader_or_copy_is_not_found(client, api, librarian, contract):
    reader, _ = api.reader()
    _, [copy] = api.stock(librarian)

    r = client.post("/loans", headers=librarian, json={"readerId": UNKNOWN_ID, "copyId": copy["id"]})
    contract(r, "createLoan")
    assert r.status_code == 404
    assert client.post("/loans", headers=librarian, json={"readerId": reader["id"], "copyId": UNKNOWN_ID}).status_code == 404
    # Той самий запит з наявними читачем і екземпляром проходить: 404 означає саме «не знайдено».
    assert client.post("/loans", headers=librarian, json={"readerId": reader["id"], "copyId": copy["id"]}).status_code == 201


def test_loan_to_staff_account_is_not_found(client, api, librarian):
    staff, _ = api.create_librarian()
    _, [copy] = api.stock(librarian)

    r = client.post("/loans", headers=librarian, json={"readerId": staff["id"], "copyId": copy["id"]})

    assert r.status_code == 404
    assert api.issue(librarian, api.reader()[0]["id"], copy["id"])["status"] == "active"


def test_only_librarian_issues_loans(client, api, librarian):
    reader, reader_headers = api.reader()
    _, [copy] = api.stock(librarian)
    _, admin = api.create_admin()
    body = {"readerId": reader["id"], "copyId": copy["id"]}

    assert client.post("/loans", headers=admin, json=body).status_code == 403
    assert client.post("/loans", headers=reader_headers, json=body).status_code == 403


def test_loan_with_invalid_body_is_rejected(client, librarian, contract):
    r = client.post("/loans", headers=librarian, json={"readerId": "abc"})

    contract(r, "createLoan")
    assert r.status_code == 400


# --- REQ-F-020: повернення
def test_return_makes_copy_available_again(client, api, librarian, clock, contract):
    edition, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    clock.advance(days=10)

    r = client.post(f"/loans/{loan['id']}/return", headers=librarian)

    contract(r, "returnLoan")
    assert r.status_code == 200
    assert r.json()["status"] == "returned"
    assert r.json()["returnedAt"] == "2026-11-10"
    assert r.json()["fineAmount"] == 0
    assert copy_status(client, librarian, edition["id"], copy["id"]) == "available"


def test_returned_loan_cannot_be_returned_again(client, api, librarian, contract):
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    api.give_back(librarian, loan["id"])

    r = client.post(f"/loans/{loan['id']}/return", headers=librarian)

    contract(r, "returnLoan")
    assert r.status_code == 409
    assert r.json()["code"] == "loan_already_closed"


def test_returning_unknown_loan_is_not_found(client, api, librarian):
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])

    assert client.post(f"/loans/{UNKNOWN_ID}/return", headers=librarian).status_code == 404
    assert client.post(f"/loans/{loan['id']}/return", headers=librarian).status_code == 200


def test_only_librarian_registers_return(client, api, librarian):
    _, [copy] = api.stock(librarian)
    reader, reader_headers = api.reader()
    loan = api.issue(librarian, reader["id"], copy["id"])

    assert client.post(f"/loans/{loan['id']}/return", headers=reader_headers).status_code == 403


# --- REQ-F-021: історія видач у кабінеті
def test_history_contains_past_and_current_loans_with_dates(client, api, librarian, clock, contract):
    reader, reader_headers = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    returned = api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=3)
    api.give_back(librarian, returned["id"])
    current = api.issue(librarian, reader["id"], second["id"])

    r = client.get(f"/readers/{reader['id']}/loans", headers=reader_headers)

    contract(r, "listReaderLoans")
    by_id = {x["id"]: x for x in r.json()["items"]}
    assert by_id.keys() == {returned["id"], current["id"]}
    assert by_id[returned["id"]]["returnedAt"] == "2026-11-03"
    assert by_id[current["id"]]["status"] == "active"
    assert r.json()["total"] == 2


def test_history_can_be_filtered_by_status(client, api, librarian):
    reader, reader_headers = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.give_back(librarian, api.issue(librarian, reader["id"], first["id"])["id"])
    current = api.issue(librarian, reader["id"], second["id"])

    r = client.get(f"/readers/{reader['id']}/loans", headers=reader_headers, params={"status": "active"})

    assert [x["id"] for x in r.json()["items"]] == [current["id"]]


def test_reader_cannot_see_another_readers_loans(client, api, librarian, contract):
    other, _ = api.reader()
    _, reader_headers = api.reader()

    r = client.get(f"/readers/{other['id']}/loans", headers=reader_headers)

    contract(r, "listReaderLoans")
    assert r.status_code == 403


def test_reader_cannot_open_another_readers_loan(client, api, librarian, contract):
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    _, stranger = api.reader()

    r = client.get(f"/loans/{loan['id']}", headers=stranger)

    contract(r, "getLoan")
    assert r.status_code == 403


def test_reader_opens_own_loan_card(client, api, librarian, contract):
    reader, reader_headers = api.reader()
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, reader["id"], copy["id"])

    r = client.get(f"/loans/{loan['id']}", headers=reader_headers)

    contract(r, "getLoan")
    assert r.json()["id"] == loan["id"]


def test_unknown_loan_is_not_found(client, api, librarian, contract):
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])

    r = client.get(f"/loans/{UNKNOWN_ID}", headers=librarian)

    contract(r, "getLoan")
    assert r.status_code == 404
    assert client.get(f"/loans/{loan['id']}", headers=librarian).status_code == 200


# --- REQ-F-049, REQ-NF-005: видача — критична операція
def test_loan_and_return_are_audited(client, api, librarian):
    _, [copy] = api.stock(librarian)
    loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
    api.give_back(librarian, loan["id"])

    entries = client.get("/audit-log-entries", headers=api.chief, params={"pageSize": 100}).json()["items"]
    assert len([e for e in entries if e.get("objectId") == loan["id"]]) == 2


def test_refused_loan_is_written_to_system_log(client, api, librarian, read_log):
    _, [copy] = api.stock(librarian)
    client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    client.post("/loans", headers=librarian, json={"readerId": api.reader()[0]["id"], "copyId": copy["id"]})

    assert any(r["level"] == "WARNING" and copy["id"] in r["message"] for r in read_log())
