import pytest
from app.licenses import create_license, get_by_key
from app.models import License

def test_create_license_returns_license_with_id(temp_db):
    lic = create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="Cliente A", notes="anotação")
    assert isinstance(lic, License)
    assert lic.id > 0
    assert lic.key == "ABCD-EFGH-IJKL-MNOP"
    assert lic.client_name == "Cliente A"
    assert lic.notes == "anotação"
    assert lic.revoked is False
    assert lic.created_at
    assert lic.revoked_at is None

def test_create_license_duplicate_key_raises(temp_db):
    create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="A", notes=None)
    with pytest.raises(Exception):
        create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="B", notes=None)

from app.licenses import revoke_license, unrevoke_license, list_all_licenses

def test_revoke_marks_license_as_revoked(temp_db):
    lic = create_license(temp_db, key="AAAA-BBBB-CCCC-DDDD", client_name="X", notes=None)
    revoke_license(temp_db, lic.id)
    updated = get_by_key(temp_db, "AAAA-BBBB-CCCC-DDDD")
    assert updated.revoked is True
    assert updated.revoked_at is not None

def test_unrevoke_clears_revoked_flag(temp_db):
    lic = create_license(temp_db, key="EEEE-FFFF-GGGG-HHHH", client_name="Y", notes=None)
    revoke_license(temp_db, lic.id)
    unrevoke_license(temp_db, lic.id)
    updated = get_by_key(temp_db, "EEEE-FFFF-GGGG-HHHH")
    assert updated.revoked is False
    assert updated.revoked_at is None

def test_list_all_returns_all_licenses_ordered_by_created_at_desc(temp_db):
    create_license(temp_db, key="1111-1111-1111-1111", client_name="A", notes=None)
    create_license(temp_db, key="2222-2222-2222-2222", client_name="B", notes=None)
    all_licenses = list_all_licenses(temp_db)
    assert len(all_licenses) == 2
    assert all_licenses[0].key == "2222-2222-2222-2222"
    assert all_licenses[1].key == "1111-1111-1111-1111"

from app.licenses import (
    license_stats, last_validation_map, list_recent_validations,
    count_validations_since,
)


def test_license_stats_conta_total_ativas_revogadas(temp_db):
    a = create_license(temp_db, key="STAT-0001-STAT-0001", client_name="A", notes=None)
    create_license(temp_db, key="STAT-0002-STAT-0002", client_name="B", notes=None)
    revoke_license(temp_db, a.id)
    stats = license_stats(temp_db)
    assert stats == {"total": 2, "active": 1, "revoked": 1}


def test_last_validation_map_retorna_ultima_por_licenca(temp_db):
    from app.licenses import log_validation
    lic = create_license(temp_db, key="LAST-0001-LAST-0001", client_name="C", notes=None)
    log_validation(temp_db, license_id=lic.id, ip="1.1.1.1", app_version="1.60")
    log_validation(temp_db, license_id=lic.id, ip="2.2.2.2", app_version="1.65")
    m = last_validation_map(temp_db)
    assert lic.id in m
    assert m[lic.id]["app_version"] == "1.65"
    assert m[lic.id]["validated_at"]


def test_list_recent_validations_junta_nome_do_cliente(temp_db):
    from app.licenses import log_validation
    lic = create_license(temp_db, key="RECE-0001-RECE-0001", client_name="Empresa Z", notes=None)
    log_validation(temp_db, license_id=lic.id, ip="9.9.9.9", app_version="1.65")
    recentes = list_recent_validations(temp_db, limit=5)
    assert len(recentes) == 1
    assert recentes[0]["client_name"] == "Empresa Z"
    assert recentes[0]["ip"] == "9.9.9.9"


def test_count_validations_since(temp_db):
    from app.licenses import log_validation
    lic = create_license(temp_db, key="CNT0-0001-CNT0-0001", client_name="D", notes=None)
    log_validation(temp_db, license_id=lic.id, ip="1.1.1.1", app_version="1.65")
    assert count_validations_since(temp_db, "2000-01-01T00:00:00+00:00") == 1
    assert count_validations_since(temp_db, "2999-01-01T00:00:00+00:00") == 0


from app.licenses import log_validation, list_validations_for_license

def test_log_validation_creates_entry(temp_db):
    lic = create_license(temp_db, key="LOGT-EST1-LOGT-EST1", client_name="L", notes=None)
    log_validation(temp_db, license_id=lic.id, ip="192.168.0.1", app_version="1.34")
    entries = list_validations_for_license(temp_db, lic.id)
    assert len(entries) == 1
    assert entries[0].license_id == lic.id
    assert entries[0].ip == "192.168.0.1"
    assert entries[0].app_version == "1.34"
    assert entries[0].validated_at
