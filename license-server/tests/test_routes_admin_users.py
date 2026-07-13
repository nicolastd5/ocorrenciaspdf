from app import users


def test_lista_usuarios(admin_client, db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "x12345678")
    r = admin_client["client"].get("/admin/users")
    assert r.status_code == 200
    assert "ana@ex.com" in r.text


def test_criar_usuario(admin_client, db_path):
    r = admin_client["client"].post("/admin/users/new", data={
        "email": "novo@ex.com", "name": "Novo", "password": "s3nh4forte",
        "csrf_token": admin_client["csrf"],
    }, follow_redirects=False)
    assert r.status_code == 303
    assert users.authenticate(db_path, "novo@ex.com", "s3nh4forte")


def test_desativar_usuario(admin_client, db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = admin_client["client"].post(f"/admin/users/{uid}/toggle", data={
        "csrf_token": admin_client["csrf"],
    }, follow_redirects=False)
    assert r.status_code == 303
    assert users.authenticate(db_path, "ana@ex.com", "s3nh4forte") is None


def test_users_exige_admin(client):
    c = client[0] if isinstance(client, tuple) else client
    r = c.get("/admin/users", follow_redirects=False)
    assert r.status_code == 303
