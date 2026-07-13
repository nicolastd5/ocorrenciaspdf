import os
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from app import users
from app.db import init_db


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    from app.db import init_db
    db_path = str(tmp_path / "test_licenses.db")
    init_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def set_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "licenses.db"))


# ── Fixtures compartilhadas para testes de rota ──────────────────────────────

@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a fresh TestClient for each test, with a clean DB."""
    db_path = str(tmp_path / "licenses.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    import importlib
    import app.routes_admin
    import app.main
    app.routes_admin._admin_password_hash = None
    app.routes_admin.limiter._storage.reset()
    importlib.reload(app.main)
    return TestClient(app.main.app), db_path


@pytest.fixture
def db_path(client):
    """Convenience: return db_path from the client fixture."""
    _, db = client
    return db


@pytest.fixture
def login_user(client):
    """Create user ana@ex.com + login, return (TestClient, csrf_token)."""
    c, db = client
    users.create_user(db, "ana@ex.com", "Ana", "s3nh4forte")
    r = c.get("/login")
    assert r.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/login", data={"email": "ana@ex.com", "password": "s3nh4forte",
                               "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    return c, token


@pytest.fixture
def user_csrf(login_user):
    """Just return the csrf token from login_user."""
    return login_user[1]


@pytest.fixture
def logged_client(client):
    """Create user, log in, return TestClient with active session."""
    c, db = client
    from app import users
    users.create_user(db, "ana@ex.com", "Ana", "s3nh4forte")
    r = c.get("/login")
    assert r.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/login", data={"email": "ana@ex.com", "password": "s3nh4forte",
                               "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    return c, db


@pytest.fixture
def admin_client(client, monkeypatch):
    """Log into admin and return dict with 'client' and 'csrf'."""
    c = client[0] if isinstance(client, tuple) else client
    # Login as admin
    r = c.get("/admin/login")
    assert r.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/admin/login", data={"csrf_token": token, "password": "test-password"},
               follow_redirects=False)
    assert r.status_code in (302, 303)
    # Get fresh CSRF from dashboard
    r = c.get("/admin")
    assert r.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    return {"client": c, "csrf": token}
