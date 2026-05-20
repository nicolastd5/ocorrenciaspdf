import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "licenses.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    import importlib
    import app.routes_admin
    import app.main
    # Reset cached password hash between test runs
    app.routes_admin._admin_password_hash = None
    # Reset rate limiter storage to avoid 429 accumulation between tests
    app.routes_admin.limiter._storage.reset()
    importlib.reload(app.main)
    return TestClient(app.main.app), db_path


def _login(client_obj):
    resp = client_obj.get("/admin/login")
    assert resp.status_code == 200
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    assert m, "csrf token não encontrado na página de login"
    csrf = m.group(1)
    resp = client_obj.post(
        "/admin/login",
        data={"csrf_token": csrf, "password": "test-password"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    return csrf


def _csrf_from(client_obj, path):
    resp = client_obj.get(path)
    assert resp.status_code == 200
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    assert m, f"csrf token não encontrado em {path}"
    return m.group(1)


def test_admin_index_requires_auth(client):
    c, _ = client
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/admin/login" in resp.headers["location"]


def test_login_with_correct_password_creates_session(client):
    c, _ = client
    _login(c)
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code == 200
    assert "Licenças" in resp.text


def test_login_with_wrong_password_shows_error(client):
    c, _ = client
    csrf = _csrf_from(c, "/admin/login")
    resp = c.post(
        "/admin/login",
        data={"csrf_token": csrf, "password": "senha-errada"},
    )
    assert resp.status_code == 200
    assert "Senha incorreta" in resp.text


def test_create_license_via_admin_form(client):
    c, db_path = client
    _login(c)
    csrf = _csrf_from(c, "/admin/new")
    resp = c.post(
        "/admin/new",
        data={"csrf_token": csrf, "client_name": "Cliente Novo", "notes": "primeiro"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    from app.licenses import list_all_licenses
    licenses = list_all_licenses(db_path)
    assert len(licenses) == 1
    assert licenses[0].client_name == "Cliente Novo"
    assert licenses[0].notes == "primeiro"


def test_revoke_license(client):
    c, db_path = client
    from app.licenses import create_license, get_by_id
    lic = create_license(db_path, key="REVO-FROM-ADMI-NTST", client_name="X", notes=None)
    _login(c)
    csrf = _csrf_from(c, f"/admin/{lic.id}")
    resp = c.post(
        f"/admin/{lic.id}/revoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert get_by_id(db_path, lic.id).revoked is True


def test_unrevoke_license(client):
    c, db_path = client
    from app.licenses import create_license, revoke_license, get_by_id
    lic = create_license(db_path, key="UNRE-VOKE-FROM-ADMI", client_name="Y", notes=None)
    revoke_license(db_path, lic.id)
    _login(c)
    csrf = _csrf_from(c, f"/admin/{lic.id}")
    resp = c.post(
        f"/admin/{lic.id}/unrevoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert get_by_id(db_path, lic.id).revoked is False


def test_revoke_without_csrf_is_rejected(client):
    c, db_path = client
    from app.licenses import create_license, get_by_id
    lic = create_license(db_path, key="NOCS-RFTO-KENT-EST1", client_name="Z", notes=None)
    _login(c)
    resp = c.post(
        f"/admin/{lic.id}/revoke",
        data={"csrf_token": "token-falso"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert get_by_id(db_path, lic.id).revoked is False


def test_logout_clears_session(client):
    c, _ = client
    _login(c)
    csrf = _csrf_from(c, "/admin")
    c.post("/admin/logout", data={"csrf_token": csrf}, follow_redirects=False)
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303)
