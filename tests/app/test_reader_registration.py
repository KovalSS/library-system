"""G3: самостійна реєстрація читача (REQ-F-015...017, BDD 8.4, LS-05)."""


# --- REQ-F-015: реєстрація створює неактивний акаунт
def test_registration_creates_inactive_reader(api, contract):
    r = api.register("reader@example.com")

    contract(r, "registerReader")
    assert r.status_code == 201
    assert r.json()["status"] == "pending_confirmation"
    assert r.json()["email"] == "reader@example.com"


def test_registration_sends_confirmation_link(api, outbox):
    api.register("reader@example.com")

    assert outbox.last("reader@example.com", "email_confirmation")


def test_unconfirmed_reader_cannot_log_in(client, api, contract):
    api.register("reader@example.com", "S3cret-pass")

    r = client.post("/auth/login", json={"email": "reader@example.com", "password": "S3cret-pass"})

    contract(r, "login")
    assert r.status_code == 403
    assert r.json()["code"] == "account_inactive"


def test_registration_response_never_contains_password(api):
    r = api.register("reader@example.com", "S3cret-pass")

    assert r.status_code == 201
    assert "password" not in r.json()
    assert "S3cret-pass" not in r.text


def test_registration_without_required_fields_is_rejected(client, contract):
    r = client.post("/readers", json={"email": "reader@example.com"})

    contract(r, "registerReader")
    assert r.status_code == 400
    fields = {d["field"] for d in r.json()["details"]}
    assert {"fullName", "phone", "birthDate", "password"} <= fields


def test_registration_with_invalid_email_is_rejected(api):
    assert api.register("not-an-email").status_code == 400


def test_registration_with_short_password_is_rejected(api):
    assert api.register("reader@example.com", "short").status_code == 400


def test_registration_with_invalid_phone_is_rejected(api):
    assert api.register("reader@example.com", phone="abc").status_code == 400


# --- REQ-F-016: підтвердження email
def test_confirmation_activates_reader_and_allows_login(client, api, outbox, contract):
    api.register("reader@example.com", "S3cret-pass")
    token = outbox.last("reader@example.com", "email_confirmation")

    r = client.post("/email-confirmations", json={"token": token})

    contract(r, "confirmReaderEmail")
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert api.login("reader@example.com", "S3cret-pass")["role"] == "reader"


def test_confirmation_with_unknown_token_is_rejected(client, contract):
    r = client.post("/email-confirmations", json={"token": "no-such-token"})

    contract(r, "confirmReaderEmail")
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_token"


def test_confirmation_without_token_is_rejected(client):
    r = client.post("/email-confirmations", json={})

    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"


# --- REQ-F-017: унікальність email підтвердженого акаунта
def test_registration_with_email_of_confirmed_reader_is_rejected(api, contract):
    api.reader("taken@example.com")

    r = api.register("taken@example.com")

    contract(r, "registerReader")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_email"


def test_registration_with_email_of_unconfirmed_reader_is_allowed(api):
    # Критерій REQ-F-017 забороняє лише email, що вже використовується підтвердженим акаунтом.
    api.register("pending@example.com")

    assert api.register("pending@example.com").status_code == 201

