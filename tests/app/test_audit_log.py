"""G5: аудит-лог значущих дій (REQ-F-049) і журналювання невдалих входів (REQ-NF-005), LS-07."""
from datetime import timedelta


def entries(client, headers, **params):
    r = client.get("/audit-log-entries", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


# --- REQ-F-049: хто, що саме, коли
def test_edition_registration_is_audited_with_actor_and_time(client, api, clock, contract):
    librarian_account, librarian = api.create_librarian()
    edition = api.edition(librarian)
    _, admin = api.create_admin()

    r = client.get("/audit-log-entries", headers=admin, params={"actorId": librarian_account["id"]})

    contract(r, "listAuditLogEntries")
    entry = next(e for e in r.json()["items"] if e.get("objectId") == edition["id"])
    assert entry["actorRole"] == "librarian"
    assert entry["action"]
    assert entry["occurredAt"].startswith(clock.now().strftime("%Y-%m-%dT%H:%M"))


def test_account_creation_is_audited(client, api):
    librarian_account, _ = api.create_librarian()

    chief_entries = entries(client, api.chief)
    assert any(e.get("objectId") == librarian_account["id"] and e["actorRole"] == "chief_admin" for e in chief_entries)


def test_copy_write_off_is_audited(client, api):
    _, librarian = api.create_librarian()
    copy = api.copy(librarian, api.edition(librarian)["id"])
    before = [e for e in entries(client, api.chief) if e.get("objectId") == copy["id"]]

    client.post(f"/copies/{copy['id']}/write-off", headers=librarian)

    after = [e for e in entries(client, api.chief) if e.get("objectId") == copy["id"]]
    assert len(after) == len(before) + 1


def test_audit_log_is_filtered_by_period(client, api, clock):
    _, librarian = api.create_librarian()
    clock.advance(days=1)
    edition = api.edition(librarian)

    since = (clock.now() - timedelta(minutes=1)).isoformat()
    recent = entries(client, api.chief, **{"from": since})

    assert any(e.get("objectId") == edition["id"] for e in recent)
    assert all(e["occurredAt"] >= since[:16] for e in recent)


def test_only_admins_see_audit_log(client, api, contract):
    _, librarian = api.create_librarian()
    _, reader = api.reader()

    r = client.get("/audit-log-entries", headers=librarian)
    contract(r, "listAuditLogEntries")
    assert r.status_code == 403
    assert client.get("/audit-log-entries", headers=reader).status_code == 403


def test_audit_log_rejects_invalid_filter(client, api, contract):
    r = client.get("/audit-log-entries", headers=api.chief, params={"from": "yesterday"})

    contract(r, "listAuditLogEntries")
    assert r.status_code == 400


# --- REQ-NF-005: невдалі спроби автентифікації потрапляють у системний журнал
def test_failed_login_is_written_to_system_log_without_password(client, api, read_log):
    api.reader("reader@example.com", "S3cret-pass")

    client.post("/auth/login", json={"email": "reader@example.com", "password": "Wrong-Secret-1"})

    warnings = [r for r in read_log() if r["level"] == "WARNING"]
    assert any("reader@example.com" in w["message"] for w in warnings)
    assert all("Wrong-Secret-1" not in w["message"] for w in read_log())
