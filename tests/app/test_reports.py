"""G10: звіти та експорт у CSV (REQ-F-039...042, LS-25)."""
import csv
import io

import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


def csv_rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.text)))


def lend(api, librarian, edition, times):
    loans = []
    for _ in range(times):
        copy = api.copy(librarian, edition["id"])
        loans.append(api.issue(librarian, api.reader()[0]["id"], copy["id"]))
    return loans


# --- REQ-F-039: топ видань за період
def test_top_editions_sorted_by_loans_in_period(client, api, librarian, contract):
    popular = api.edition(librarian, title="Кобзар")
    rare = api.edition(librarian, title="Гайдамаки")
    lend(api, librarian, popular, 3)
    lend(api, librarian, rare, 1)

    r = client.get("/reports/top-editions", headers=librarian, params={"from": "2026-10-01", "to": "2026-10-31"})

    contract(r, "getTopEditionsReport")
    assert r.status_code == 200
    assert [(i["title"], i["loansCount"]) for i in r.json()["items"]] == [("Кобзар", 3), ("Гайдамаки", 1)]


def test_top_editions_counts_only_loans_inside_period(client, api, librarian, clock):
    edition = api.edition(librarian, title="Кобзар")
    lend(api, librarian, edition, 2)                    # 31.10.2026
    clock.advance(days=5)
    lend(api, librarian, edition, 1)                    # 05.11.2026

    r = client.get("/reports/top-editions", headers=librarian, params={"from": "2026-11-01", "to": "2026-11-30"})

    assert [(i["title"], i["loansCount"]) for i in r.json()["items"]] == [("Кобзар", 1)]


def test_top_editions_period_bounds_are_inclusive(client, api, librarian):
    edition = api.edition(librarian, title="Кобзар")
    lend(api, librarian, edition, 1)                    # рівно 31.10.2026

    r = client.get("/reports/top-editions", headers=librarian, params={"from": "2026-10-31", "to": "2026-10-31"})

    assert [i["loansCount"] for i in r.json()["items"]] == [1]


def test_top_editions_limit(client, api, librarian):
    for title in ("А", "Б", "В"):
        lend(api, librarian, api.edition(librarian, title=title), 1)

    r = client.get("/reports/top-editions", headers=librarian,
                   params={"from": "2026-10-01", "to": "2026-10-31", "limit": 2})

    assert len(r.json()["items"]) == 2


# --- REQ-F-040: читачі-боржники
def test_debtors_report_lists_overdue_and_unpaid_readers_only(client, api, librarian, clock, contract):
    overdue_reader, _ = api.reader()
    unpaid_reader, _ = api.reader()
    paid_reader, _ = api.reader()
    punctual_reader, _ = api.reader()
    edition, copies = api.stock(librarian, copies=4, price=300)
    api.issue(librarian, overdue_reader["id"], copies[0]["id"])            # не поверне
    late = api.issue(librarian, unpaid_reader["id"], copies[1]["id"])
    paid = api.issue(librarian, paid_reader["id"], copies[2]["id"])
    clock.advance(days=30 + 2)
    api.give_back(librarian, late["id"])                                   # повернув із запізненням, не сплатив
    api.give_back(librarian, paid["id"])
    client.post(f"/readers/{paid_reader['id']}/fine-payments", headers=librarian, json={"method": "cash"})
    api.issue(librarian, punctual_reader["id"], copies[3]["id"])           # ще не прострочено

    r = client.get("/reports/debtors", headers=librarian)

    contract(r, "getDebtorsReport")
    rows = {i["readerId"]: i for i in r.json()["items"]}
    assert rows.keys() == {overdue_reader["id"], unpaid_reader["id"]}
    assert (rows[overdue_reader["id"]]["overdueLoans"], rows[overdue_reader["id"]]["outstandingFine"]) == (1, 6)
    assert (rows[unpaid_reader["id"]]["overdueLoans"], rows[unpaid_reader["id"]]["outstandingFine"]) == (0, 6)
    assert rows[unpaid_reader["id"]]["email"] == unpaid_reader["email"]


# --- REQ-F-041: завантаженість бібліотеки
def test_library_load_counts_loans_and_returns_in_period(client, api, librarian, clock, contract):
    edition, copies = api.stock(librarian, copies=3)
    loans = [api.issue(librarian, api.reader()[0]["id"], c["id"]) for c in copies]   # 3 видачі 31.10
    clock.advance(days=2)
    api.give_back(librarian, loans[0]["id"])                                          # 1 повернення 02.11

    r = client.get("/reports/library-load", headers=librarian, params={"from": "2026-10-01", "to": "2026-10-31"})
    contract(r, "getLibraryLoadReport")
    assert (r.json()["issuedCount"], r.json()["returnedCount"]) == (3, 0)

    r = client.get("/reports/library-load", headers=librarian, params={"from": "2026-11-01", "to": "2026-11-30"})
    assert (r.json()["issuedCount"], r.json()["returnedCount"]) == (0, 1)


# --- REQ-F-042: експорт у CSV з тими самими даними
def test_top_editions_csv_has_same_data_as_json(client, api, librarian):
    lend(api, librarian, api.edition(librarian, title="Кобзар"), 2)
    lend(api, librarian, api.edition(librarian, title="Гайдамаки"), 1)
    params = {"from": "2026-10-01", "to": "2026-10-31"}

    as_json = client.get("/reports/top-editions", headers=librarian, params=params).json()["items"]
    rows = csv_rows(client.get("/reports/top-editions", headers={**librarian, "Accept": "text/csv"}, params=params))

    assert [(r["title"], int(r["loansCount"])) for r in rows] == [(i["title"], i["loansCount"]) for i in as_json]
    assert {r["editionId"] for r in rows} == {i["editionId"] for i in as_json}


def test_debtors_csv_has_same_data_as_json(client, api, librarian, clock):
    reader, _ = api.reader()
    _, [copy] = api.stock(librarian, price=300)
    api.issue(librarian, reader["id"], copy["id"])
    clock.advance(days=30 + 2)

    as_json = client.get("/reports/debtors", headers=librarian).json()["items"]
    rows = csv_rows(client.get("/reports/debtors", headers={**librarian, "Accept": "text/csv"}))

    assert [(r["readerId"], r["fullName"], int(r["overdueLoans"]), float(r["outstandingFine"])) for r in rows] == \
           [(i["readerId"], i["fullName"], i["overdueLoans"], i["outstandingFine"]) for i in as_json]


def test_library_load_csv_has_same_data_as_json(client, api, librarian):
    _, [copy] = api.stock(librarian)
    api.issue(librarian, api.reader()[0]["id"], copy["id"])
    params = {"from": "2026-10-01", "to": "2026-10-31"}

    as_json = client.get("/reports/library-load", headers=librarian, params=params).json()
    [row] = csv_rows(client.get("/reports/library-load", headers={**librarian, "Accept": "text/csv"}, params=params))

    assert (int(row["issuedCount"]), int(row["returnedCount"])) == (as_json["issuedCount"], as_json["returnedCount"])


# --- доступ і валідація
def test_reports_are_for_staff_only(client, api, librarian):
    _, reader = api.reader()
    _, admin = api.create_admin()

    assert client.get("/reports/debtors", headers=reader).status_code == 403
    assert client.get("/reports/debtors", headers=admin).status_code == 200
    assert client.get("/reports/debtors", headers=librarian).status_code == 200


@pytest.mark.parametrize("path", ["/reports/top-editions", "/reports/library-load"])
def test_period_is_required(client, librarian, path):
    r = client.get(path, headers=librarian)

    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"


@pytest.mark.parametrize("path", ["/reports/top-editions", "/reports/library-load"])
def test_period_with_from_after_to_is_rejected(client, librarian, path):
    r = client.get(path, headers=librarian, params={"from": "2026-11-30", "to": "2026-11-01"})

    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"
