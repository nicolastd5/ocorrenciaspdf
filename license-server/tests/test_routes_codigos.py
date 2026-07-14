import re


def _c(client):
    return client[0] if isinstance(client, tuple) else client


def _csrf(c, path="/app/codigos"):
    r = c.get(path)
    assert r.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)


def test_pagina_exige_login(client):
    c = _c(client)
    r = c.get("/app/codigos", follow_redirects=False)
    assert r.status_code == 303


def test_pagina_mostra_embutidos_e_personalizados(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "MINHA OPERADORA", "", "424242")
    r = c.get("/app/codigos")
    assert r.status_code == 200
    assert "SPTRANS" in r.text            # embutido
    assert "MINHA OPERADORA" in r.text    # personalizado
    assert "424242" in r.text


def test_adicionar_beneficio(logged_client):
    c, db = logged_client
    token = _csrf(c)
    r = c.post("/app/codigos/beneficio", data={
        "operadora": "Nova Op", "valor_unitario": "", "codigo": "9999",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "NOVA OP" in r.text
    from app import ref_codes
    assert ref_codes.benefit_tuples(db) == [("NOVA OP", None, "9999")]


def test_adicionar_beneficio_duplicado_mostra_erro(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    token = _csrf(c)
    r = c.post("/app/codigos/beneficio", data={
        "operadora": "OPX", "valor_unitario": "", "codigo": "222",
        "csrf_token": token,
    })
    assert r.status_code == 400
    assert "Já existe" in r.text
    assert len(ref_codes.list_benefit_codes(db)) == 1


def test_excluir_beneficio(logged_client):
    c, db = logged_client
    from app import ref_codes
    rid = ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    token = _csrf(c)
    r = c.post(f"/app/codigos/beneficio/{rid}/excluir",
               data={"csrf_token": token})
    assert r.status_code == 200
    assert ref_codes.list_benefit_codes(db) == []


def test_adicionar_e_excluir_departamento(logged_client):
    c, db = logged_client
    token = _csrf(c)
    r = c.post("/app/codigos/departamento", data={
        "original": "DEP X", "substituto": "DEP Y", "csrf_token": token,
    })
    assert r.status_code == 200
    assert "DEP Y" in r.text
    from app import ref_codes
    subs = ref_codes.list_depart_subs(db)
    assert len(subs) == 1
    token = _csrf(c)
    r = c.post(f"/app/codigos/departamento/{subs[0]['id']}/excluir",
               data={"csrf_token": token})
    assert r.status_code == 200
    assert ref_codes.list_depart_subs(db) == []


def test_post_sem_login(client):
    c = _c(client)
    r = c.post("/app/codigos/beneficio", data={"operadora": "X", "codigo": "1"},
               follow_redirects=False)
    assert r.status_code == 303
