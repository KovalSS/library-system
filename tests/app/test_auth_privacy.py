"""G4: автентифікація та конфіденційність (REQ-F-047, 048, 050; REQ-NF-003; LS-06)."""
from conftest import CHIEF


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- REQ-F-047: відновлення пароля через email
def test_password_reset_request_is_accepted_and_sends_letter(client, api, outbox, contract):
    api.reader("reader@example.com")

    r = client.post("/auth/password-reset-requests", json={"email": "reader@example.com"})

    contract(r, "requestPasswordReset")
    assert r.status_code == 202
    assert outbox.last("reader@example.com", "password_reset")


def test_password_reset_for_unknown_email_looks_the_same_and_sends_nothing(client, outbox):
    r = client.post("/auth/password-reset-requests", json={"email": "nobody@example.com"})

    assert r.status_code == 202
    assert not [m for m in outbox.messages if m["to"] == "nobody@example.com"]


def test_new_password_works_and_old_one_does_not(client, api, outbox, contract):
    api.reader("reader@example.com", "Old-pass-123")
    client.post("/auth/password-reset-requests", json={"email": "reader@example.com"})
    token = outbox.last("reader@example.com", "password_reset")

    r = client.post("/auth/password-resets", json={"token": token, "newPassword": "New-pass-456"})

    contract(r, "resetPassword")
    assert r.status_code == 204
    assert login(client, "reader@example.com", "New-pass-456").status_code == 200
    assert login(client, "reader@example.com", "Old-pass-123").status_code == 401


def test_password_reset_works_for_staff_accounts(client, api, outbox):
    api.create_librarian(email="lib@library.test", password="Old-pass-123")
    client.post("/auth/password-reset-requests", json={"email": "lib@library.test"})
    token = outbox.last("lib@library.test", "password_reset")

    client.post("/auth/password-resets", json={"token": token, "newPassword": "New-pass-456"})

    assert login(client, "lib@library.test", "New-pass-456").status_code == 200


def test_password_reset_with_unknown_token_is_rejected(client, contract):
    r = client.post("/auth/password-resets", json={"token": "no-such-token", "newPassword": "New-pass-456"})

    contract(r, "resetPassword")
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_token"


def test_password_reset_token_works_only_once(client, api, outbox):
    api.reader("reader@example.com")
    client.post("/auth/password-reset-requests", json={"email": "reader@example.com"})
    token = outbox.last("reader@example.com", "password_reset")
    client.post("/auth/password-resets", json={"token": token, "newPassword": "New-pass-456"})

    r = client.post("/auth/password-resets", json={"token": token, "newPassword": "Other-pass-789"})

    assert r.status_code == 400
    assert r.json()["code"] == "invalid_token"


def test_password_reset_with_short_password_is_rejected(client, api, outbox):
    api.reader("reader@example.com")
    client.post("/auth/password-reset-requests", json={"email": "reader@example.com"})
    token = outbox.last("reader@example.com", "password_reset")

    r = client.post("/auth/password-resets", json={"token": token, "newPassword": "short"})

    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"


# --- REQ-F-048: блокування на 15 хвилин після 5 поспіль невдалих спроб
def test_wrong_password_is_rejected(client, api, contract):
    api.reader("reader@example.com", "S3cret-pass")

    r = login(client, "reader@example.com", "wrong-pass")

    contract(r, "login")
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_unknown_email_gives_same_error_as_wrong_password(client):
    r = login(client, "nobody@example.com", "whatever-pass")

    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_four_failures_do_not_lock_account(client, api):
    api.reader("reader@example.com", "S3cret-pass")
    for _ in range(4):
        login(client, "reader@example.com", "wrong-pass")

    assert login(client, "reader@example.com", "S3cret-pass").status_code == 200


def test_after_five_failures_account_is_locked_even_for_correct_password(client, api, contract):
    api.reader("reader@example.com", "S3cret-pass")
    for _ in range(5):
        login(client, "reader@example.com", "wrong-pass")

    r = login(client, "reader@example.com", "S3cret-pass")

    contract(r, "login")
    assert r.status_code == 423
    assert r.json()["code"] == "account_locked"
    assert 0 < int(r.headers["Retry-After"]) <= 15 * 60


def test_lock_ends_after_15_minutes(client, api, clock):
    api.reader("reader@example.com", "S3cret-pass")
    for _ in range(5):
        login(client, "reader@example.com", "wrong-pass")

    clock.advance(minutes=14, seconds=59)
    assert login(client, "reader@example.com", "S3cret-pass").status_code == 423
    clock.advance(seconds=1)
    assert login(client, "reader@example.com", "S3cret-pass").status_code == 200


def test_successful_login_resets_failure_counter(client, api):
    api.reader("reader@example.com", "S3cret-pass")
    for _ in range(4):
        login(client, "reader@example.com", "wrong-pass")
    login(client, "reader@example.com", "S3cret-pass")
    for _ in range(4):
        login(client, "reader@example.com", "wrong-pass")

    assert login(client, "reader@example.com", "S3cret-pass").status_code == 200


def test_lock_applies_to_staff_accounts(client, api):
    api.create_librarian(email="lib@library.test", password="L1brarian-Pass")
    for _ in range(5):
        login(client, "lib@library.test", "wrong-pass")

    assert login(client, "lib@library.test", "L1brarian-Pass").status_code == 423


def test_login_with_invalid_body_is_rejected(client, contract):
    r = client.post("/auth/login", json={"email": "reader@example.com"})

    contract(r, "login")
    assert r.status_code == 400


# --- REQ-F-050: персональні дані читача лише для власника та персоналу
def test_reader_data_requires_authentication(client, api, contract):
    reader, _ = api.reader()

    r = client.get(f"/readers/{reader['id']}")

    contract(r, "getReader")
    assert r.status_code == 401


def test_reader_sees_own_data(client, api, contract):
    reader, headers = api.reader()

    r = client.get(f"/readers/{reader['id']}", headers=headers)

    contract(r, "getReader")
    assert r.status_code == 200
    assert r.json()["email"] == reader["email"]


def test_reader_cannot_see_another_readers_data(client, api, contract):
    other, _ = api.reader()
    _, headers = api.reader()

    r = client.get(f"/readers/{other['id']}", headers=headers)

    contract(r, "getReader")
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


def test_librarian_and_admin_see_reader_data(client, api):
    reader, _ = api.reader()
    _, librarian = api.create_librarian()
    _, admin = api.create_admin()

    assert client.get(f"/readers/{reader['id']}", headers=librarian).status_code == 200
    assert client.get(f"/readers/{reader['id']}", headers=admin).status_code == 200


def test_unknown_reader_is_not_found(client, api, contract):
    _, librarian = api.create_librarian()

    r = client.get("/readers/00000000-0000-4000-8000-000000000000", headers=librarian)

    contract(r, "getReader")
    assert r.status_code == 404


def test_malformed_reader_id_is_not_found(client, api):
    _, librarian = api.create_librarian()

    assert client.get("/readers/abc", headers=librarian).status_code == 404


def test_librarian_searches_readers(client, api, contract):
    reader, _ = api.reader()
    _, librarian = api.create_librarian()

    r = client.get("/readers", headers=librarian, params={"q": reader["email"]})

    contract(r, "listReaders")
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["items"]] == [reader["id"]]


def test_reader_cannot_list_readers(client, api, contract):
    _, headers = api.reader()

    r = client.get("/readers", headers=headers)

    contract(r, "listReaders")
    assert r.status_code == 403


def test_reader_list_rejects_invalid_page(client, api, contract):
    _, librarian = api.create_librarian()

    r = client.get("/readers", headers=librarian, params={"page": 0})

    contract(r, "listReaders")
    assert r.status_code == 400


# --- REQ-NF-003: паролі лише в хешованому вигляді
def test_passwords_are_not_stored_in_plain_text(api, db_path):
    api.reader("reader@example.com", "Plain-Text-Secret-1")
    api.create_librarian(email="lib@library.test", password="Plain-Text-Secret-2")

    raw = db_path.read_bytes()
    assert b"Plain-Text-Secret-1" not in raw
    assert b"Plain-Text-Secret-2" not in raw
    assert CHIEF.password.encode() not in raw


def test_api_responses_never_expose_passwords(client, api):
    reader, headers = api.reader("reader@example.com", "S3cret-pass")
    _, librarian = api.create_librarian()

    for r in (client.get(f"/readers/{reader['id']}", headers=headers),
              client.get("/librarians", headers=api.chief),
              client.get("/readers", headers=librarian)):
        assert r.status_code == 200
        assert "password" not in r.text.lower()
