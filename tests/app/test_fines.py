"""G8: штрафи (REQ-F-027...031, BDD 8.2 і 8.5, LS-17). Висока ціна відмови: точні суми."""
import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


def loan_with_queue(api, librarian, price):
    """Видача, оформлена, коли на видання була черга: 14 днів, 5% на день (REQ-F-019, 027)."""
    edition, [first, second] = api.stock(librarian, copies=2, price=price)
    api.issue(librarian, api.reader()[0]["id"], first["id"])
    api.issue(librarian, api.reader()[0]["id"], second["id"])
    api.reserve(api.reader()[1], edition["id"])
    reader, headers = api.reader()
    loan = api.issue(librarian, reader["id"], api.copy(librarian, edition["id"])["id"])
    assert (loan["termDays"], loan["fineRatePercent"]) == (14, 5)
    return reader, headers, loan


def loan_without_queue(api, librarian, price):
    """Видача без черги: 30 днів, 1% на день."""
    edition, [copy] = api.stock(librarian, price=price)
    reader, headers = api.reader()
    loan = api.issue(librarian, reader["id"], copy["id"])
    assert (loan["termDays"], loan["fineRatePercent"]) == (30, 1)
    return reader, headers, loan, edition


# --- BDD 8.2: повернення з простроченням (REQ-F-020, 027, 030, 031)
def test_bdd_8_2_return_after_3_overdue_days_charges_45(client, api, librarian, clock, contract):
    reader, headers, loan = loan_with_queue(api, librarian, price=300)
    clock.advance(days=14 + 3)

    r = client.post(f"/loans/{loan['id']}/return", headers=librarian)

    contract(r, "returnLoan")
    assert r.json()["overdueDays"] == 3
    assert r.json()["fineAmount"] == 45          # 5% x 3 дні x 300 грн
    fines = api.fines(reader, headers)
    assert fines["totalOutstanding"] == 45
    assert [(i["loanId"], i["outstandingAmount"]) for i in fines["items"]] == [(loan["id"], 45)]


# --- REQ-F-027: ставка фіксується при видачі, штраф на льоту
def test_fine_without_queue_is_1_percent_per_day(api, librarian, clock):
    _, _, loan, _ = loan_without_queue(api, librarian, price=300)
    clock.advance(days=30 + 10)

    assert api.loan(librarian, loan["id"])["fineAmount"] == 30       # 1% x 10 x 300


def test_fine_is_calculated_on_the_fly_from_current_date(api, librarian, clock):
    _, _, loan = loan_with_queue(api, librarian, price=300)

    clock.advance(days=14)
    assert (api.loan(librarian, loan["id"])["overdueDays"], api.loan(librarian, loan["id"])["fineAmount"]) == (0, 0)
    clock.advance(days=1)
    assert api.loan(librarian, loan["id"])["fineAmount"] == 15
    clock.advance(days=3)
    assert api.loan(librarian, loan["id"])["fineAmount"] == 60


def test_rate_stays_as_fixed_at_issue_when_queue_appears_later(api, librarian, clock):
    _, _, loan, edition = loan_without_queue(api, librarian, price=300)
    api.reserve(api.reader()[1], edition["id"])          # черга з'явилась після видачі
    clock.advance(days=30 + 2)

    shown = api.loan(librarian, loan["id"])
    assert shown["fineRatePercent"] == 1
    assert shown["fineAmount"] == 6


def test_return_on_due_date_has_no_fine(api, librarian, clock):
    _, _, loan, _ = loan_without_queue(api, librarian, price=300)
    clock.advance(days=30)

    assert api.give_back(librarian, loan["id"])["fineAmount"] == 0


def test_fine_stops_growing_after_return(api, librarian, clock):
    _, _, loan = loan_with_queue(api, librarian, price=300)
    clock.advance(days=14 + 3)
    api.give_back(librarian, loan["id"])

    clock.advance(days=10)

    assert api.loan(librarian, loan["id"])["fineAmount"] == 45


def test_fine_with_fractional_amount_is_exact(api, librarian, clock):
    _, _, loan, _ = loan_without_queue(api, librarian, price=199.99)
    clock.advance(days=30 + 3)

    assert api.loan(librarian, loan["id"])["fineAmount"] == pytest.approx(6.00, abs=0.01)   # 1% x 3 x 199.99


# --- REQ-F-028: межа 100% ціни
def test_fine_never_exceeds_book_price(api, librarian, clock):
    _, _, loan = loan_with_queue(api, librarian, price=200)
    clock.advance(days=14 + 25)                          # 5% x 25 = 125%

    assert api.loan(librarian, loan["id"])["fineAmount"] == 200


# --- BDD 8.5, REQ-F-029: вичерпання ліміту штрафу
def test_one_day_before_limit_loan_is_still_active(api, librarian, clock):
    _, _, loan = loan_with_queue(api, librarian, price=200)
    clock.advance(days=14 + 19)

    shown = api.loan(librarian, loan["id"])
    assert (shown["status"], shown["fineAmount"]) == ("active", 190)


def test_bdd_8_5_fine_reaches_limit_and_loan_is_compensated(client, api, librarian, clock, contract):
    _, _, loan = loan_with_queue(api, librarian, price=200)
    clock.advance(days=14 + 20)                          # 5% x 20 = 100%

    r = client.get(f"/loans/{loan['id']}", headers=librarian)

    contract(r, "getLoan")
    assert r.json()["fineAmount"] == 200
    assert r.json()["status"] == "compensated"
    clock.advance(days=10)
    assert api.loan(librarian, loan["id"])["fineAmount"] == 200


def test_limit_with_1_percent_rate_is_reached_after_100_days(api, librarian, clock):
    _, _, loan, _ = loan_without_queue(api, librarian, price=300)
    clock.advance(days=30 + 100)

    shown = api.loan(librarian, loan["id"])
    assert (shown["status"], shown["fineAmount"]) == ("compensated", 300)


def test_compensated_loan_cannot_be_returned(client, api, librarian, clock):
    _, _, loan = loan_with_queue(api, librarian, price=200)
    clock.advance(days=14 + 20)

    r = client.post(f"/loans/{loan['id']}/return", headers=librarian)

    assert r.status_code == 409
    assert r.json()["code"] == "loan_already_closed"


def test_compensated_status_is_shown_in_reader_history(client, api, librarian, clock):
    reader, headers, loan = loan_with_queue(api, librarian, price=200)
    clock.advance(days=14 + 20)

    history = client.get(f"/readers/{reader['id']}/loans", headers=headers, params={"status": "compensated"}).json()

    assert [x["id"] for x in history["items"]] == [loan["id"]]


# --- REQ-F-030: оплата повної суми бібліотекарем
@pytest.mark.parametrize("method", ["cash", "card"])
def test_payment_clears_whole_debt(client, api, librarian, clock, method, contract):
    reader, headers, loan = loan_with_queue(api, librarian, price=300)
    clock.advance(days=14 + 3)
    api.give_back(librarian, loan["id"])

    r = client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": method})

    contract(r, "payReaderFines")
    assert r.status_code == 201
    assert (r.json()["amount"], r.json()["method"]) == (45, method)
    assert api.fines(reader, headers)["totalOutstanding"] == 0
    assert api.loan(librarian, loan["id"])["finePaidAmount"] == 45


def test_payment_covers_fines_of_all_loans(client, api, librarian, clock):
    reader, headers = api.reader()
    _, [a, b] = api.stock(librarian, copies=2, price=300)
    api.issue(librarian, reader["id"], a["id"])
    api.issue(librarian, reader["id"], b["id"])
    clock.advance(days=30 + 2)

    assert api.fines(reader, headers)["totalOutstanding"] == 12             # 2 x (1% x 2 x 300)
    r = client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "cash"})
    assert r.json()["amount"] == 12
    assert api.fines(reader, headers)["totalOutstanding"] == 0


def test_payment_without_debt_is_rejected(client, api, librarian, contract):
    reader, _ = api.reader()

    r = client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "cash"})

    contract(r, "payReaderFines")
    assert r.status_code == 409
    assert r.json()["code"] == "no_outstanding_fine"


def test_payment_with_unknown_method_is_rejected(client, api, librarian):
    reader, _ = api.reader()

    r = client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "partial"})

    assert r.status_code == 400


def test_only_librarian_registers_payment(client, api, librarian, clock):
    reader, headers, loan = loan_with_queue(api, librarian, price=300)
    clock.advance(days=14 + 3)
    _, admin = api.create_admin()

    assert client.post(f"/readers/{reader['id']}/fine-payments", headers=headers, json={"method": "cash"}).status_code == 403
    assert client.post(f"/readers/{reader['id']}/fine-payments", headers=admin, json={"method": "cash"}).status_code == 403


def test_payment_for_unknown_reader_is_not_found(client, api, librarian):
    reader, _ = api.reader()

    r = client.post("/readers/00000000-0000-4000-8000-000000000000/fine-payments", headers=librarian,
                    json={"method": "cash"})

    assert r.status_code == 404
    # Наявний читач без боргу дає 409, а не 404: маршрут існує, а 404 стосується саме читача.
    assert client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian,
                       json={"method": "cash"}).status_code == 409


def test_payment_is_audited(client, api, librarian, clock):
    reader, _, loan = loan_with_queue(api, librarian, price=300)
    clock.advance(days=14 + 3)
    payment = client.post(f"/readers/{reader['id']}/fine-payments", headers=librarian, json={"method": "cash"}).json()

    entries = client.get("/audit-log-entries", headers=api.chief, params={"pageSize": 100}).json()["items"]
    assert any(e.get("objectId") == payment["id"] for e in entries)


# --- REQ-F-031: поточні штрафи в кабінеті
def test_reader_without_fines_sees_zero(client, api, contract):
    reader, headers = api.reader()

    r = client.get(f"/readers/{reader['id']}/fines", headers=headers)

    contract(r, "getReaderFines")
    assert r.json()["totalOutstanding"] == 0
    assert r.json()["items"] == []


def test_cabinet_shows_growing_fine_of_unreturned_loan(api, librarian, clock):
    reader, headers, _ = loan_with_queue(api, librarian, price=300)

    clock.advance(days=14 + 2)
    assert api.fines(reader, headers)["totalOutstanding"] == 30
    clock.advance(days=1)
    assert api.fines(reader, headers)["totalOutstanding"] == 45


def test_reader_cannot_see_another_readers_fines(client, api, contract):
    other, _ = api.reader()
    _, headers = api.reader()

    r = client.get(f"/readers/{other['id']}/fines", headers=headers)

    contract(r, "getReaderFines")
    assert r.status_code == 403
