import pytest

from app import ref_codes, users
from app.db import init_db


def _create_users(db_path):
    """Cria usuários com id=1 e id=2 para satisfazer as FKs dos testes."""
    users.create_user(db_path, "test1@test.com", "Test1", "s3nh4forte")
    users.create_user(db_path, "test2@test.com", "Test2", "s3nh4forte")


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "t.db")
    init_db(p)
    _create_users(p)
    return p


def test_add_e_list_beneficio(db):
    rid = ref_codes.add_benefit_code(db, 1, "nova linha", "11,50", "12345")
    lst = ref_codes.list_benefit_codes(db)
    assert len(lst) == 1
    assert lst[0]["id"] == rid
    assert lst[0]["operadora"] == "NOVA LINHA"   # normalizado p/ uppercase
    assert lst[0]["valor_unitario"] == "11,50"
    assert lst[0]["codigo"] == "12345"


def test_valor_vazio_vira_none(db):
    ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    assert ref_codes.list_benefit_codes(db)[0]["valor_unitario"] is None
    assert ref_codes.benefit_tuples(db) == [("OPX", None, "111")]


def test_beneficio_campos_obrigatorios(db):
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 1, "", "1", "111")
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 1, "OP", "1", "")


def test_beneficio_duplicata(db):
    ref_codes.add_benefit_code(db, 1, "OPX", "11,50", "111")
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 2, "opx", "11,50", "222")
    # mesmo nome com valor diferente é permitido (como SPTRANS embutido)
    ref_codes.add_benefit_code(db, 1, "OPX", "22,00", "222")


def test_delete_beneficio(db):
    rid = ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    ref_codes.delete_benefit_code(db, rid)
    assert ref_codes.list_benefit_codes(db) == []


def test_add_list_delete_depart(db):
    rid = ref_codes.add_depart_sub(db, 1, "DEPTO ORIGINAL", "SUBSTITUTO")
    assert ref_codes.depart_dict(db) == {"DEPTO ORIGINAL": "SUBSTITUTO"}
    with pytest.raises(ValueError):
        ref_codes.add_depart_sub(db, 2, "DEPTO ORIGINAL", "OUTRO")
    with pytest.raises(ValueError):
        ref_codes.add_depart_sub(db, 1, "", "X")
    ref_codes.delete_depart_sub(db, rid)
    assert ref_codes.list_depart_subs(db) == []
