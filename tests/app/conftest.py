import json

import pytest
from fastapi.testclient import TestClient

from library.app import create_app


@pytest.fixture
def log_file(tmp_path):
    return tmp_path / "library.log"


@pytest.fixture
def app(log_file):
    return create_app(log_file=log_file)


@pytest.fixture
def client(app):
    # Необроблені винятки мають перетворюватися на відповідь 500, а не падати в тесті.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def read_log(log_file):
    """Записи системного журналу (JSON Lines). Порожній список, якщо файлу ще немає."""
    def read():
        if not log_file.exists():
            return []
        return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return read
