"""Адендум REQ-F-051: відмова у видачі читачу із заборгованістю (LS-42).

Джерело: `spec/addendum-loan-refusal-for-debtors.md` (AC-1...AC-7), SRS BDD 8.6,
контракт `createLoan` → `409 reader_has_debt`.
"""
import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


def try_loan(client, librarian, reader_id, copy_id):
    return client.post("/loans", headers=librarian, json={"readerId": reader_id, "copyId": copy_id})


def copy_status(client, librarian, copy):
    copies = client.get(f"/editions/{copy['editionId']}/copies", headers=librarian).json()
    return next(c["status"] for c in copies if c["id"] == copy["id"])


def refused_for_debt(response):
    return response.status_code == 409 and response.json()["code"] == "reader_has_debt"


# --- AC-1: прострочена неповернута видача
def test_reader_with_overdue_unreturned_loan_is_refused(client, api, librarian, clock, contract):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 1)

    r = try_loan(client, librarian, reader["id"], second["id"])

    contract(r, "createLoan")
    assert refused_for_debt(r)
    assert copy_status(client, librarian, second) == "available"
    history = client.get(f"/readers/{reader['id']}/loans", headers=librarian).json()
    assert history["total"] == 1


# --- AC-2: повернув із запізненням, штраф не сплачено
def test_reader_with_unpaid_fine_is_refused(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    loan = api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 2)
    api.give_back(librarian, loan["id"])

    assert refused_for_debt(try_loan(client, librarian, reader["id"], second["id"]))


# --- AC-3: компенсована видача з несплаченим штрафом
def test_reader_with_unpaid_compensated_loan_is_refused(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    loan = api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 100)
    assert api.loan(librarian, loan["id"])["status"] == "compensated"

    assert refused_for_debt(try_loan(client, librarian, reader["id"], second["id"]))


# --- AC-4: після оплати й без прострочених видач — дозволено
def test_reader_who_paid_and_returned_everything_can_borrow_again(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    loan = api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 2)
    api.give_back(librarian, loan["id"])
    client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "cash"})

    assert try_loan(client, librarian, reader["id"], second["id"]).status_code == 201


def test_paying_the_fine_is_not_enough_while_overdue_book_is_kept(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 2)
    client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "cash"})

    assert refused_for_debt(try_loan(client, librarian, reader["id"], second["id"]))


# --- AC-5: поточна непрострочена видача — не борг
def test_reader_with_current_loan_can_borrow_more(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=10)

    assert try_loan(client, librarian, reader["id"], second["id"]).status_code == 201


def test_due_date_itself_is_not_yet_overdue(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30)                                  # день терміну повернення

    assert try_loan(client, librarian, reader["id"], second["id"]).status_code == 201


# --- AC-6: відмова — у системному журналі
def test_refusal_is_written_to_system_log(client, api, librarian, clock, read_log):
    reader, _ = api.reader()
    _, [first, second] = api.stock(librarian, copies=2)
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 1)

    try_loan(client, librarian, reader["id"], second["id"])

    assert any(r["level"] == "WARNING" and reader["id"] in r["message"] for r in read_log())


# --- AC-7: заборгованість перевіряється раніше за доступність екземпляра
def test_debt_is_reported_even_when_copy_is_unavailable(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [first, damaged] = api.stock(librarian, copies=2)
    client.patch(f"/copies/{damaged['id']}", headers=librarian, json={"status": "damaged"})
    api.issue(librarian, reader["id"], first["id"])
    clock.advance(days=30 + 1)

    assert refused_for_debt(try_loan(client, librarian, reader["id"], damaged["id"]))


# --- одне визначення боржника для звіту REQ-F-040 і відмови REQ-F-051
def test_refused_readers_are_exactly_the_debtors_report(client, api, librarian, clock):
    overdue, unpaid, paid, punctual = (api.reader()[0] for _ in range(4))
    edition, copies = api.stock(librarian, copies=8)
    api.issue(librarian, overdue["id"], copies[0]["id"])
    late = api.issue(librarian, unpaid["id"], copies[1]["id"])
    settled = api.issue(librarian, paid["id"], copies[2]["id"])
    clock.advance(days=30 + 2)
    api.give_back(librarian, late["id"])
    api.give_back(librarian, settled["id"])
    client.post(f"/readers/{paid['id']}/fine-payments", headers=librarian, json={"method": "cash"})
    api.issue(librarian, punctual["id"], copies[3]["id"])

    debtors = {d["readerId"] for d in client.get("/reports/debtors", headers=librarian).json()["items"]}
    refused = {reader["id"] for reader, copy in zip((overdue, unpaid, paid, punctual), copies[4:])
               if refused_for_debt(try_loan(client, librarian, reader["id"], copy["id"]))}

    assert refused == debtors == {overdue["id"], unpaid["id"]}


# --- BDD 8.6: відмова, оплата, повторна видача
def test_bdd_8_6_refused_then_paid_then_issued(client, api, librarian, clock, contract):
    edition, [first, second, kobzar] = api.stock(librarian, copies=3, price=300)
    api.issue(librarian, api.reader()[0]["id"], first["id"])
    api.issue(librarian, api.reader()[0]["id"], second["id"])
    api.reserve(api.reader()[1], edition["id"])                          # черга: 14 днів, 5%
    ivan, _ = api.reader()
    third = api.copy(librarian, edition["id"])
    late = api.issue(librarian, ivan["id"], third["id"])
    clock.advance(days=14 + 3)
    api.give_back(librarian, late["id"])                                  # штраф 5% x 3 x 300 = 45

    r = try_loan(client, librarian, ivan["id"], kobzar["id"])
    contract(r, "createLoan")
    assert refused_for_debt(r)
    assert copy_status(client, librarian, kobzar) == "available"

    payment = client.post(f"/readers/{ivan['id']}/fine-payments", headers=librarian, json={"method": "cash"})
    assert payment.json()["amount"] == 45

    assert try_loan(client, librarian, ivan["id"], kobzar["id"]).status_code == 201
