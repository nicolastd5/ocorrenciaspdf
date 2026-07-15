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


# ── Ocorrência ──

def test_add_e_list_ocorrencia(db):
    rid = ref_codes.add_occurrence_code(db, 1, "fr", "Férias Remuneradas", True)
    lst = ref_codes.list_occurrence_codes(db)
    assert len(lst) == 1
    assert lst[0]["id"] == rid
    assert lst[0]["codigo"] == "FR"          # normalizado p/ uppercase
    assert lst[0]["descricao"] == "Férias Remuneradas"
    assert lst[0]["com_quantidade"] == 1


def test_ocorrencia_validacoes(db):
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "", "desc", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "ABCDE", "desc", True)   # > 4 chars
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "FR", "", True)          # sem descrição


def test_ocorrencia_duplicata_personalizado(db):
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 2, "fr", "Outra", False)


def test_ocorrencia_duplicata_embutido(db):
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "FA", "Faltas de novo", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "at", "Atestado 2", True)


def test_occurrence_config_e_delete(db):
    ref_codes.add_occurrence_code(db, 1, "ZZ", "Zeta", True)
    rid = ref_codes.add_occurrence_code(db, 1, "BB", "Beta", False)
    assert ref_codes.occurrence_config(db) == [
        {"codigo": "BB", "com_quantidade": False},
        {"codigo": "ZZ", "com_quantidade": True},
    ]
    ref_codes.delete_occurrence_code(db, rid)
    assert ref_codes.occurrence_config(db) == [{"codigo": "ZZ", "com_quantidade": True}]
