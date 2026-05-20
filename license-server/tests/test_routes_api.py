import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "licenses.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    import importlib
    import app.main
    importlib.reload(app.main)
    # Reset limiter storage so rate-limit counts don't bleed across tests
    import app.routes_api
    app.routes_api.limiter.reset()
    return TestClient(app.main.app), db_path


def test_validate_unknown_key_returns_valid_false(client):
    c, _ = client
    resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "not_found"}


def test_validate_active_key_returns_valid_true(client):
    c, db_path = client
    from app.licenses import create_license
    create_license(db_path, key="VALI-DKEY-VALI-DKEY", client_name="Fulano", notes=None)
    resp = c.post("/api/validate", json={"key": "VALI-DKEY-VALI-DKEY", "app_version": "1.34"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["client_name"] == "Fulano"


def test_validate_revoked_key_returns_revoked(client):
    c, db_path = client
    from app.licenses import create_license, revoke_license
    lic = create_license(db_path, key="REVO-KEDK-REVO-KEDK", client_name="X", notes=None)
    revoke_license(db_path, lic.id)
    resp = c.post("/api/validate", json={"key": "REVO-KEDK-REVO-KEDK", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "revoked"}


def test_validate_invalid_format_returns_not_found(client):
    c, _ = client
    resp = c.post("/api/validate", json={"key": "formato-errado", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "not_found"}


def test_validate_logs_successful_validation(client):
    c, db_path = client
    from app.licenses import create_license, list_validations_for_license
    lic = create_license(db_path, key="LOGM-EVAL-LOGM-EVAL", client_name="Y", notes=None)
    c.post("/api/validate", json={"key": "LOGM-EVAL-LOGM-EVAL", "app_version": "1.34"})
    entries = list_validations_for_license(db_path, lic.id)
    assert len(entries) == 1
    assert entries[0].app_version == "1.34"


def test_validate_does_not_log_failed_validation(client):
    c, db_path = client
    from app.licenses import create_license, list_validations_for_license, revoke_license
    lic = create_license(db_path, key="REVO-LOGM-REVO-LOGM", client_name="Z", notes=None)
    revoke_license(db_path, lic.id)
    c.post("/api/validate", json={"key": "REVO-LOGM-REVO-LOGM", "app_version": "1.34"})
    entries = list_validations_for_license(db_path, lic.id)
    assert len(entries) == 0


def test_validate_malformed_body_returns_not_found(client):
    c, _ = client
    resp = c.post("/api/validate", json={"foo": "bar"})
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json() == {"valid": False, "reason": "not_found"}


def test_validate_rate_limit_blocks_after_60_per_minute(client):
    c, _ = client
    for _ in range(60):
        resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "x"})
        assert resp.status_code == 200
    resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "x"})
    assert resp.status_code == 429
