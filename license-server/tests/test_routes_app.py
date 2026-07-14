import pytest


def _c(client):
    return client[0] if isinstance(client, tuple) else client


@pytest.mark.parametrize("path", ["/app/ocorrencias", "/app/vt-caixa",
                                  "/app/codigos", "/app/historico"])
def test_paginas_exigem_login(client, path):
    c = _c(client)
    r = c.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


@pytest.mark.parametrize("path", ["/app/ocorrencias", "/app/vt-caixa",
                                  "/app/codigos", "/app/historico"])
def test_paginas_carregam_logado(logged_client, path):
    c = _c(logged_client)
    r = c.get(path)
    assert r.status_code == 200


def test_raiz_redireciona(logged_client):
    c = _c(logged_client)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/ocorrencias"


def _csrf_de(c, path="/app/ocorrencias"):
    import re
    r = c.get(path)
    return re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)


def test_tutorial_seen_endpoint(logged_client):
    c, db = logged_client
    token = _csrf_de(c)
    r = c.post("/app/tutorial/seen", data={"csrf_token": token})
    assert r.status_code == 204
    from app import users as users_module
    lst = users_module.list_users(db)
    assert lst[0]["tutorial_seen"] == 1


def test_tutorial_seen_exige_login(client):
    c = _c(client)
    r = c.post("/app/tutorial/seen", follow_redirects=False)
    assert r.status_code == 303


def test_base_inclui_tour(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'src="/static/tour.js"' in r.text
    assert 'src="/static/driver.js.iife.js"' in r.text
    assert "window.TOUR" in r.text
    assert '"seen": false' in r.text.replace("'", '"') or "seen: false" in r.text
    assert 'data-tour="nav-ocorrencias"' in r.text
    assert 'data-tour="btn-tutorial"' in r.text


def test_tour_seen_true_apos_marcar(logged_client):
    c, _ = logged_client
    token = _csrf_de(c)
    c.post("/app/tutorial/seen", data={"csrf_token": token})
    r = c.get("/app/ocorrencias")
    assert "seen: true" in r.text
