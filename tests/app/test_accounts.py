"""G2: облікові записи адміністраторів і бібліотекарів (REQ-F-009...014, LS-04)."""
from conftest import CHIEF, bearer


# --- REQ-F-009: попередньо створений головний адміністратор
def test_chief_admin_can_log_in_right_after_deploy(client, contract):
    r = client.post("/auth/login", json={"email": CHIEF.email, "password": CHIEF.password})

    contract(r, "login")
    assert r.status_code == 200
    assert r.json()["role"] == "chief_admin"


# --- REQ-F-010: створення адміністратора нижчого рівня лише головним
def test_chief_creates_admin_who_can_log_in_immediately(client, api, contract):
    r = client.post("/administrators", headers=api.chief,
                    json={"fullName": "Олена Коваль", "email": "admin@library.test", "password": "Adm1n-Pass-2026"})

    contract(r, "createAdministrator")
    assert r.status_code == 201
    assert r.json()["role"] == "admin"
    assert r.json()["active"] is True
    assert api.login("admin@library.test", "Adm1n-Pass-2026")["role"] == "admin"


def test_admin_cannot_create_another_admin(client, api, contract):
    _, admin = api.create_admin()

    r = client.post("/administrators", headers=admin,
                    json={"fullName": "Хтось", "email": "other@library.test", "password": "Adm1n-Pass-2026"})

    contract(r, "createAdministrator")
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


def test_librarian_cannot_create_admin(client, api):
    _, librarian = api.create_librarian()

    r = client.post("/administrators", headers=librarian,
                    json={"fullName": "Хтось", "email": "other@library.test", "password": "Adm1n-Pass-2026"})

    assert r.status_code == 403


def test_creating_admin_without_token_is_unauthorized(client, contract):
    r = client.post("/administrators", json={"fullName": "Хтось", "email": "x@library.test", "password": "Adm1n-Pass-2026"})

    contract(r, "createAdministrator")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_invalid_token_is_unauthorized(client):
    r = client.get("/administrators", headers=bearer("not-a-real-token"))

    assert r.status_code == 401


def test_admin_with_duplicate_email_is_rejected(client, api, contract):
    api.create_admin(email="dup@library.test")

    r = client.post("/administrators", headers=api.chief,
                    json={"fullName": "Інша", "email": "dup@library.test", "password": "Adm1n-Pass-2026"})

    contract(r, "createAdministrator")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_email"


def test_admin_with_missing_fields_is_rejected_with_field_details(client, api, contract):
    r = client.post("/administrators", headers=api.chief, json={"email": "x@library.test"})

    contract(r, "createAdministrator")
    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"
    fields = {d["field"] for d in r.json()["details"]}
    assert {"fullName", "password"} <= fields


def test_admin_password_shorter_than_8_is_rejected(client, api):
    r = client.post("/administrators", headers=api.chief,
                    json={"fullName": "Олена", "email": "x@library.test", "password": "short"})

    assert r.status_code == 400


def test_chief_lists_lower_admins(client, api, contract):
    created, _ = api.create_admin()

    r = client.get("/administrators", headers=api.chief)

    contract(r, "listAdministrators")
    assert r.status_code == 200
    assert created["id"] in [a["id"] for a in r.json()]


def test_admin_cannot_list_admins(client, api):
    _, admin = api.create_admin()

    assert client.get("/administrators", headers=admin).status_code == 403


# --- REQ-F-011: акаунт головного адміністратора захищений
def test_chief_account_cannot_be_edited_even_by_chief(client, api, contract):
    chief_id = api.login(CHIEF.email, CHIEF.password)["userId"]

    r = client.patch(f"/administrators/{chief_id}", headers=api.chief, json={"fullName": "Інше ім'я"})

    contract(r, "updateAdministrator")
    assert r.status_code == 403
    assert r.json()["code"] == "protected_account"


def test_chief_account_cannot_be_deactivated(client, api):
    chief_id = api.login(CHIEF.email, CHIEF.password)["userId"]

    r = client.patch(f"/administrators/{chief_id}", headers=api.chief, json={"active": False})

    assert r.status_code == 403
    assert api.login(CHIEF.email, CHIEF.password)["role"] == "chief_admin"


def test_chief_account_cannot_be_edited_by_admin(client, api):
    chief_id = api.login(CHIEF.email, CHIEF.password)["userId"]
    _, admin = api.create_admin()

    r = client.patch(f"/administrators/{chief_id}", headers=admin, json={"fullName": "Інше"})

    assert r.status_code == 403


def test_accounts_cannot_be_deleted(client, api):
    created, _ = api.create_admin()

    r = client.delete(f"/administrators/{created['id']}", headers=api.chief)

    assert r.status_code == 405


# --- REQ-F-012: редагування й деактивація адміністратора головним
def test_chief_edits_admin(client, api, contract):
    created, _ = api.create_admin()

    r = client.patch(f"/administrators/{created['id']}", headers=api.chief, json={"fullName": "Олена Петрівна"})

    contract(r, "updateAdministrator")
    assert r.status_code == 200
    assert r.json()["fullName"] == "Олена Петрівна"


def test_deactivated_admin_cannot_log_in(client, api, contract):
    created, _ = api.create_admin(email="gone@library.test", password="Adm1n-Pass-2026")

    r = client.patch(f"/administrators/{created['id']}", headers=api.chief, json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    r = client.post("/auth/login", json={"email": "gone@library.test", "password": "Adm1n-Pass-2026"})
    contract(r, "login")
    assert r.status_code == 403
    assert r.json()["code"] == "account_inactive"


def test_deactivated_admin_token_stops_working(client, api):
    created, admin = api.create_admin()
    client.patch(f"/administrators/{created['id']}", headers=api.chief, json={"active": False})

    assert client.get("/librarians", headers=admin).status_code in (401, 403)


def test_admin_cannot_edit_another_admin(client, api):
    other, _ = api.create_admin()
    _, admin = api.create_admin()

    r = client.patch(f"/administrators/{other['id']}", headers=admin, json={"fullName": "Інше"})

    assert r.status_code == 403


def test_editing_unknown_admin_is_not_found(client, api, contract):
    r = client.patch("/administrators/00000000-0000-4000-8000-000000000000", headers=api.chief, json={"fullName": "X"})

    contract(r, "updateAdministrator")
    assert r.status_code == 404


def test_admin_update_with_empty_body_is_rejected(client, api):
    created, _ = api.create_admin()

    r = client.patch(f"/administrators/{created['id']}", headers=api.chief, json={})

    assert r.status_code == 400


# --- REQ-F-013: створення бібліотекаря адміністратором
def test_admin_creates_librarian_who_can_log_in(client, api, contract):
    _, admin = api.create_admin()

    r = client.post("/librarians", headers=admin,
                    json={"fullName": "Марія Гнатюк", "email": "lib@library.test", "password": "L1brarian-Pass"})

    contract(r, "createLibrarian")
    assert r.status_code == 201
    assert r.json()["role"] == "librarian"
    assert api.login("lib@library.test", "L1brarian-Pass")["role"] == "librarian"


def test_librarian_cannot_create_librarian(client, api):
    _, librarian = api.create_librarian()

    r = client.post("/librarians", headers=librarian,
                    json={"fullName": "Інша", "email": "lib2@library.test", "password": "L1brarian-Pass"})

    assert r.status_code == 403


def test_admin_lists_librarians(client, api, contract):
    created, _ = api.create_librarian()
    _, admin = api.create_admin()

    r = client.get("/librarians", headers=admin)

    contract(r, "listLibrarians")
    assert created["id"] in [a["id"] for a in r.json()]


# --- REQ-F-014: редагування й деактивація бібліотекаря адміністратором
def test_admin_edits_librarian(client, api, contract):
    created, _ = api.create_librarian()
    _, admin = api.create_admin()

    r = client.patch(f"/librarians/{created['id']}", headers=admin, json={"fullName": "Марія Іванівна"})

    contract(r, "updateLibrarian")
    assert r.status_code == 200
    assert r.json()["fullName"] == "Марія Іванівна"


def test_deactivated_librarian_cannot_log_in(client, api):
    created, _ = api.create_librarian(email="lib-off@library.test", password="L1brarian-Pass")
    _, admin = api.create_admin()

    client.patch(f"/librarians/{created['id']}", headers=admin, json={"active": False})

    r = client.post("/auth/login", json={"email": "lib-off@library.test", "password": "L1brarian-Pass"})
    assert r.status_code == 403
    assert r.json()["code"] == "account_inactive"


def test_editing_unknown_librarian_is_not_found(client, api):
    _, admin = api.create_admin()

    r = client.patch("/librarians/00000000-0000-4000-8000-000000000000", headers=admin, json={"fullName": "X"})

    assert r.status_code == 404
