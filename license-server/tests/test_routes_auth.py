import re

from app import users


def test_login_ok_redireciona_para_app(client, db_path):
    c = client[0] if isinstance(client, tuple) else client
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = c.get("/login")
    assert r.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/login", data={"email": "ana@ex.com", "password": "s3nh4forte",
                               "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/ocorrencias"


def test_login_senha_errada(client, db_path):
    c = client[0] if isinstance(client, tuple) else client
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = c.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/login", data={"email": "ana@ex.com", "password": "x",
                               "csrf_token": token})
    assert r.status_code == 200
    assert "inválid" in r.text.lower()


def test_area_do_app_exige_login(client):
    c = client[0] if isinstance(client, tuple) else client
    r = c.get("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_logout(client, db_path, login_user):
    c = client[0] if isinstance(client, tuple) else client
    r = c.get("/logout", follow_redirects=False)
    assert r.status_code == 303
    r = c.get("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303
