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
