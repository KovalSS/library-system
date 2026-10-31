"""Системний журнал: REQ-NF-005 і вимога лаб. №5 логувати всі дії системи.

Критерій прийняття REQ-NF-005: кожна необроблена помилка породжує рівно один
запис ERROR з часовою міткою, джерелом і контекстом; запис потрапляє у файл.
"""
from datetime import datetime

REQUIRED_FIELDS = {"timestamp", "level", "source", "message", "requestId"}


def test_every_request_is_written_to_log_file(client, read_log):
    client.get("/no-such-path")

    records = [r for r in read_log() if r.get("level") == "INFO"]
    assert len(records) == 1
    assert "GET /no-such-path" in records[0]["message"]
    assert "404" in records[0]["message"]


def test_log_record_has_timestamp_level_source_and_request_id(client, read_log):
    client.get("/no-such-path")

    record = read_log()[0]
    assert REQUIRED_FIELDS <= record.keys()
    datetime.fromisoformat(record["timestamp"])
    assert record["source"]
    assert record["requestId"]


def test_each_request_gets_its_own_request_id(client, read_log):
    client.get("/no-such-path")
    client.get("/no-such-path")

    ids = [r["requestId"] for r in read_log()]
    assert len(ids) == 2
    assert ids[0] != ids[1]


def test_unhandled_exception_produces_exactly_one_error_record(app, client, read_log):
    @app.get("/test-only/boom")
    def boom():
        raise RuntimeError("boom")

    response = client.get("/test-only/boom")

    assert response.status_code == 500
    errors = [r for r in read_log() if r["level"] == "ERROR"]
    assert len(errors) == 1
    assert errors[0]["source"]
    assert "RuntimeError: boom" in errors[0]["stack"]


def test_error_response_request_id_matches_log_record(app, client, read_log):
    @app.get("/test-only/boom")
    def boom():
        raise RuntimeError("boom")

    response = client.get("/test-only/boom")

    error = next(r for r in read_log() if r["level"] == "ERROR")
    assert response.json()["requestId"] == error["requestId"]
