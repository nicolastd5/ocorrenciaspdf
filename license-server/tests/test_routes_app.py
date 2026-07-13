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
