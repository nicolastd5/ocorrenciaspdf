import pytest
from app import users
from app.db import init_db


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
    return p


def test_create_e_authenticate(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    u = users.authenticate(db_path, "ana@ex.com", "s3nh4forte")
    assert u is not None and u["id"] == uid and u["name"] == "Ana"


def test_senha_errada_e_inexistente(db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    assert users.authenticate(db_path, "ana@ex.com", "errada") is None
    assert users.authenticate(db_path, "nao@existe.com", "x") is None


def test_email_duplicado(db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    with pytest.raises(ValueError):
        users.create_user(db_path, "ana@ex.com", "Ana 2", "outra")


def test_usuario_inativo_nao_autentica(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    users.set_active(db_path, uid, False)
    assert users.authenticate(db_path, "ana@ex.com", "s3nh4forte") is None


def test_set_password(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "antiga")
    users.set_password(db_path, uid, "nova")
    assert users.authenticate(db_path, "ana@ex.com", "antiga") is None
    assert users.authenticate(db_path, "ana@ex.com", "nova") is not None
