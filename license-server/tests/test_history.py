import pytest
from app import history, users
from app.db import init_db


def _create_users(db_path):
    try:
        users.create_user(db_path, "u1@test.com", "User 1", "s3nh4forte")
    except ValueError:
        pass
    try:
        users.create_user(db_path, "u2@test.com", "User 2", "s3nh4forte")
    except ValueError:
        pass


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "t.db")
    init_db(p)
    _create_users(p)
    return p


def test_add_e_list(db_path):
    history.add(db_path, 1, "job1", "ocorrencias", "sucesso",
                ["jornada.pdf", "pedido.xlsx"], {"matched": 10})
    history.add(db_path, 2, "job2", "vt_caixa", "erro", ["nautilus.pdf"], {})
    lst = history.list_for_user(db_path, 1)
    assert len(lst) == 1
    assert lst[0]["counts"]["matched"] == 10


def test_filtros(db_path):
    history.add(db_path, 1, "j1", "ocorrencias", "sucesso", ["marco.pdf"], {})
    history.add(db_path, 1, "j2", "ocorrencias", "erro", ["abril.pdf"], {})
    assert len(history.list_for_user(db_path, 1, q="marco")) == 1
    assert len(history.list_for_user(db_path, 1, status="erro")) == 1
