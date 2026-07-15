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


def test_form_ocorrencias_mostra_codigo_personalizado(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias Remuneradas", True)
    r = c.get("/app/ocorrencias")
    assert 'value="FR"' in r.text
    assert 'value="FA"' in r.text   # embutidos continuam


def test_paginas_incluem_app_js(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'src="/static/app.js"' in r.text
    assert 'class="dropzone"' in r.text
    assert 'data-tour="oc-pdf"' in r.text          # anchor preservado
    assert 'data-tour="oc-processar"' in r.text


def test_ocorrencias_mostra_requisitos_e_recentes(logged_client):
    c, db = logged_client
    from app import history
    from app import users as users_module
    uid = users_module.list_users(db)[0]["id"]
    history.add(db, uid, "j1", "ocorrencias", "sucesso", ["jornada.pdf"], {"matched": 3})
    history.add(db, uid, "j2", "vt_caixa", "sucesso", ["nautilus.pdf"], {"total_ok": 9})
    r = c.get("/app/ocorrencias")
    assert "Folha RE" in r.text and "MOTIVO" in r.text   # card de requisitos
    assert "jornada.pdf" in r.text                        # recente do tipo certo
    assert "nautilus.pdf" not in r.text                   # tipo errado não aparece


def test_historico_usa_chips(logged_client):
    c, db = logged_client
    from app import history
    from app import users as users_module
    uid = users_module.list_users(db)[0]["id"]
    history.add(db, uid, "j1", "ocorrencias", "erro", ["x.pdf"], {})
    r = c.get("/app/historico")
    assert 'class="chip chip-err"' in r.text


def test_base_inclui_tour_theme(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'href="/static/tour-theme.css"' in r.text


def test_tour_js_tem_welcome_e_requisitos():
    from pathlib import Path
    js = Path("app/static/tour.js").read_text(encoding="utf-8")
    assert "Fazer o tour" in js
    assert "Agora não" in js
    assert "Folha RE" in js          # conteúdo didático
    assert "MOTIVO" in js
