import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "licenses.db"))
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    import importlib
    import app.main
    importlib.reload(app.main)
    import app.routes_update as ru
    return TestClient(app.main.app), ru, tmp_path


def test_version_inclui_sha256_quando_presente(client, monkeypatch):
    c, ru, tmp_path = client
    version_file = tmp_path / "version.json"
    version_file.write_text(json.dumps({
        "version": "9.99",
        "filename": "ProcessadorOcorrencias-v9.99.exe",
        "sha256": "abc123",
    }), encoding="utf-8")
    monkeypatch.setattr(ru, "VERSION_FILE", version_file)

    resp = c.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "9.99"
    assert body["sha256"] == "abc123"


def test_version_sem_sha256_retorna_none(client, monkeypatch):
    c, ru, tmp_path = client
    version_file = tmp_path / "version.json"
    version_file.write_text(json.dumps({
        "version": "9.99",
        "filename": "ProcessadorOcorrencias-v9.99.exe",
    }), encoding="utf-8")
    monkeypatch.setattr(ru, "VERSION_FILE", version_file)

    resp = c.get("/api/version")
    assert resp.status_code == 200
    assert resp.json()["sha256"] is None
