"""G1: каталог і фонд (REQ-F-001...008, LS-03)."""
import pytest

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


@pytest.fixture
def genre(api):
    return api.genre("Поезія")


def edition_body(genre_id, **fields):
    return {"author": "Тарас Шевченко", "title": "Кобзар", "year": 1840, "isbn": "9786171234501",
            "genreId": genre_id, "price": 300, "totalCopies": 5, **fields}


# --- REQ-F-001: реєстрація видання
def test_librarian_registers_edition_and_it_appears_in_catalog(client, librarian, genre, contract):
    r = client.post("/editions", headers=librarian, json=edition_body(genre["id"]))

    contract(r, "createEdition")
    assert r.status_code == 201
    created = r.json()
    assert created["genre"] == genre
    assert created["availableCopies"] == 0
    assert created["loansCount"] == 0

    r = client.get(f"/editions/{created['id']}", headers=librarian)
    contract(r, "getEdition")
    assert r.json() == created


@pytest.mark.parametrize("missing", ["author", "title", "year", "isbn", "genreId", "price", "totalCopies"])
def test_edition_without_required_field_is_not_saved(client, librarian, genre, missing, contract):
    body = edition_body(genre["id"])
    del body[missing]

    r = client.post("/editions", headers=librarian, json=body)

    contract(r, "createEdition")
    assert r.status_code == 400
    assert missing in {d["field"] for d in r.json()["details"]}


def test_edition_with_negative_price_is_rejected(client, librarian, genre):
    assert client.post("/editions", headers=librarian, json=edition_body(genre["id"], price=-1)).status_code == 400


def test_edition_with_unknown_genre_is_rejected(client, librarian):
    r = client.post("/editions", headers=librarian, json=edition_body(UNKNOWN_ID))

    assert r.status_code == 400
    assert "genreId" in {d["field"] for d in r.json()["details"]}


def test_only_librarian_registers_editions(client, api, genre):
    _, admin = api.create_admin()
    _, reader = api.reader()

    assert client.post("/editions", headers=admin, json=edition_body(genre["id"])).status_code == 403
    assert client.post("/editions", headers=reader, json=edition_body(genre["id"])).status_code == 403


def test_any_role_can_view_edition(client, api, librarian):
    edition = api.edition(librarian)
    _, reader = api.reader()

    assert client.get(f"/editions/{edition['id']}", headers=reader).status_code == 200


def test_unknown_edition_is_not_found(client, librarian, contract):
    r = client.get(f"/editions/{UNKNOWN_ID}", headers=librarian)

    contract(r, "getEdition")
    assert r.status_code == 404


# --- REQ-F-002: унікальність ISBN
def test_duplicate_isbn_is_rejected_and_not_saved(client, librarian, genre, contract):
    client.post("/editions", headers=librarian, json=edition_body(genre["id"], isbn="9786171234501"))

    r = client.post("/editions", headers=librarian, json=edition_body(genre["id"], isbn="9786171234501", title="Інше"))

    contract(r, "createEdition")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_isbn"


def test_changing_isbn_to_existing_one_is_rejected(client, api, librarian, contract):
    first = api.edition(librarian)
    second = api.edition(librarian)

    r = client.patch(f"/editions/{second['id']}", headers=librarian, json={"isbn": first["isbn"]})

    contract(r, "updateEdition")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_isbn"


def test_isbn10_ending_with_x_is_accepted(client, librarian, genre):
    r = client.post("/editions", headers=librarian, json=edition_body(genre["id"], isbn="080442957X"))

    assert r.status_code == 201


def test_malformed_isbn_is_rejected(client, librarian, genre):
    r = client.post("/editions", headers=librarian, json=edition_body(genre["id"], isbn="978-617-12"))

    assert r.status_code == 400


# --- REQ-F-003: довідник жанрів
def test_admin_adds_genre_and_librarian_sees_it(client, api, contract):
    _, admin = api.create_admin()
    _, librarian = api.create_librarian()

    r = client.post("/genres", headers=admin, json={"name": "Історичний роман"})
    contract(r, "createGenre")
    assert r.status_code == 201

    r = client.get("/genres", headers=librarian)
    contract(r, "listGenres")
    assert "Історичний роман" in [g["name"] for g in r.json()]


def test_admin_renames_genre_and_change_is_visible_immediately(client, api, librarian, genre, contract):
    edition = api.edition(librarian, genreId=genre["id"])
    _, admin = api.create_admin()

    r = client.patch(f"/genres/{genre['id']}", headers=admin, json={"name": "Поезія і поеми"})

    contract(r, "updateGenre")
    assert r.status_code == 200
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["genre"]["name"] == "Поезія і поеми"


def test_librarian_cannot_manage_genres(client, librarian, genre):
    assert client.post("/genres", headers=librarian, json={"name": "Новий"}).status_code == 403
    assert client.patch(f"/genres/{genre['id']}", headers=librarian, json={"name": "Новий"}).status_code == 403


def test_genre_with_empty_name_is_rejected(client, api):
    _, admin = api.create_admin()

    assert client.post("/genres", headers=admin, json={"name": ""}).status_code == 400


def test_renaming_unknown_genre_is_not_found(client, api):
    _, admin = api.create_admin()

    assert client.patch(f"/genres/{UNKNOWN_ID}", headers=admin, json={"name": "X"}).status_code == 404


# --- REQ-F-004: додавання екземпляра
def test_added_copy_appears_in_edition_copies_as_available(client, api, librarian, contract):
    edition = api.edition(librarian)

    r = client.post(f"/editions/{edition['id']}/copies", headers=librarian,
                    json={"inventoryNumber": "INV-000123", "location": "Зал 2, стелаж 4"})

    contract(r, "createCopy")
    assert r.status_code == 201
    assert r.json()["status"] == "available"
    assert r.json()["location"] == "Зал 2, стелаж 4"

    r = client.get(f"/editions/{edition['id']}/copies", headers=librarian)
    contract(r, "listCopies")
    assert [c["inventoryNumber"] for c in r.json()] == ["INV-000123"]


def test_available_copy_increases_edition_availability(client, api, librarian):
    edition = api.edition(librarian)
    api.copy(librarian, edition["id"])

    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 1


def test_copy_can_start_as_damaged(client, api, librarian):
    edition = api.edition(librarian)

    copy = api.copy(librarian, edition["id"], status="damaged")

    assert copy["status"] == "damaged"
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 0


def test_copy_cannot_start_as_issued(client, api, librarian):
    edition = api.edition(librarian)

    r = client.post(f"/editions/{edition['id']}/copies", headers=librarian,
                    json={"inventoryNumber": "INV-1", "location": "Зал 1", "status": "issued"})

    assert r.status_code == 400


def test_copy_for_unknown_edition_is_not_found(client, librarian, contract):
    r = client.post(f"/editions/{UNKNOWN_ID}/copies", headers=librarian,
                    json={"inventoryNumber": "INV-1", "location": "Зал 1"})

    contract(r, "createCopy")
    assert r.status_code == 404


def test_reader_cannot_see_inventory(client, api, librarian):
    edition = api.edition(librarian)
    _, reader = api.reader()

    assert client.get(f"/editions/{edition['id']}/copies", headers=reader).status_code == 403


# --- REQ-F-005: унікальність інвентарного номера
def test_duplicate_inventory_number_is_rejected_across_catalog(client, api, librarian, contract):
    first = api.edition(librarian)
    second = api.edition(librarian)
    api.copy(librarian, first["id"], inventoryNumber="INV-000123")

    r = client.post(f"/editions/{second['id']}/copies", headers=librarian,
                    json={"inventoryNumber": "INV-000123", "location": "Зал 1"})

    contract(r, "createCopy")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_inventory_number"
    assert client.get(f"/editions/{second['id']}/copies", headers=librarian).json() == []


# --- REQ-F-006: зміна стану екземпляра
def test_damaged_copy_is_no_longer_available(client, api, librarian, contract):
    edition = api.edition(librarian)
    copy = api.copy(librarian, edition["id"])

    r = client.patch(f"/copies/{copy['id']}", headers=librarian, json={"status": "damaged"})

    contract(r, "updateCopy")
    assert r.status_code == 200
    assert r.json()["status"] == "damaged"
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 0


def test_repaired_copy_becomes_available_again(client, api, librarian):
    edition = api.edition(librarian)
    copy = api.copy(librarian, edition["id"], status="damaged")

    client.patch(f"/copies/{copy['id']}", headers=librarian, json={"status": "available"})

    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 1


def test_copy_location_can_be_changed(client, api, librarian):
    copy = api.copy(librarian, api.edition(librarian)["id"])

    r = client.patch(f"/copies/{copy['id']}", headers=librarian, json={"location": "Зал 3"})

    assert r.json()["location"] == "Зал 3"


@pytest.mark.parametrize("status", ["issued", "written_off", "lost"])
def test_status_cannot_be_set_manually_to_system_values(client, api, librarian, status):
    copy = api.copy(librarian, api.edition(librarian)["id"])

    assert client.patch(f"/copies/{copy['id']}", headers=librarian, json={"status": status}).status_code == 400


def test_written_off_copy_status_cannot_be_changed(client, api, librarian, contract):
    copy = api.copy(librarian, api.edition(librarian)["id"])
    client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    r = client.patch(f"/copies/{copy['id']}", headers=librarian, json={"status": "available"})

    contract(r, "updateCopy")
    assert r.status_code == 409
    assert r.json()["code"] == "copy_state_conflict"


def test_updating_unknown_copy_is_not_found(client, librarian):
    assert client.patch(f"/copies/{UNKNOWN_ID}", headers=librarian, json={"status": "damaged"}).status_code == 404


# --- REQ-F-007: списання зі збереженням історії
def test_written_off_copy_stays_in_history_but_is_not_available(client, api, librarian, contract):
    edition = api.edition(librarian)
    copy = api.copy(librarian, edition["id"])

    r = client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    contract(r, "writeOffCopy")
    assert r.status_code == 200
    assert r.json()["status"] == "written_off"
    copies = client.get(f"/editions/{edition['id']}/copies", headers=librarian).json()
    assert [c["status"] for c in copies] == ["written_off"]
    assert client.get(f"/editions/{edition['id']}", headers=librarian).json()["availableCopies"] == 0


def test_copy_cannot_be_written_off_twice(client, api, librarian, contract):
    copy = api.copy(librarian, api.edition(librarian)["id"])
    client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    r = client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    contract(r, "writeOffCopy")
    assert r.status_code == 409
    assert r.json()["code"] == "copy_state_conflict"


def test_only_librarian_writes_off(client, api, librarian):
    copy = api.copy(librarian, api.edition(librarian)["id"])
    _, admin = api.create_admin()

    assert client.post(f"/copies/{copy['id']}/write-off", headers=admin).status_code == 403


# --- REQ-F-008: редагування видання
def test_edited_edition_is_shown_updated_immediately(client, api, librarian, contract):
    edition = api.edition(librarian)

    r = client.patch(f"/editions/{edition['id']}", headers=librarian, json={"price": 320, "title": "Кобзар (повне)"})

    contract(r, "updateEdition")
    assert r.status_code == 200
    shown = client.get(f"/editions/{edition['id']}", headers=librarian).json()
    assert shown["price"] == 320
    assert shown["title"] == "Кобзар (повне)"
    assert shown["isbn"] == edition["isbn"]


def test_edition_update_with_empty_body_is_rejected(client, api, librarian):
    edition = api.edition(librarian)

    assert client.patch(f"/editions/{edition['id']}", headers=librarian, json={}).status_code == 400


def test_updating_unknown_edition_is_not_found(client, librarian):
    assert client.patch(f"/editions/{UNKNOWN_ID}", headers=librarian, json={"price": 1}).status_code == 404
