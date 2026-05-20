import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from license_client import LicenseClient, LicenseStatus, ValidationResult


def test_status_enum_has_expected_values():
    assert LicenseStatus.VALID.value == "valid"
    assert LicenseStatus.INVALID.value == "invalid"
    assert LicenseStatus.OFFLINE_TOLERATED.value == "offline_tolerated"
    assert LicenseStatus.OFFLINE_EXPIRED.value == "offline_expired"
    assert LicenseStatus.NO_KEY.value == "no_key"


def test_validation_result_has_status_reason_client_name():
    r = ValidationResult(status=LicenseStatus.VALID, reason=None, client_name="Foo")
    assert r.status == LicenseStatus.VALID
    assert r.reason is None
    assert r.client_name == "Foo"


def test_validate_no_key_when_config_missing(tmp_path):
    config_path = tmp_path / "config.json"
    client = LicenseClient(config_path=config_path)
    result = client.validate()
    assert result.status == LicenseStatus.NO_KEY


from unittest.mock import patch, MagicMock


def _make_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


def test_validate_with_valid_key_returns_valid(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake_response = _make_response(200, {"valid": True, "client_name": "Fulano"})
    with patch("license_client.requests.post", return_value=fake_response) as mock_post:
        result = client.validate()
    assert result.status == LicenseStatus.VALID
    assert result.client_name == "Fulano"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "/api/validate" in call_args[0][0]
    assert call_args[1]["json"]["key"] == "ABCD-EFGH-IJKL-MNOP"


def test_validate_with_valid_key_updates_last_validated_at(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake_response = _make_response(200, {"valid": True, "client_name": "Fulano"})
    with patch("license_client.requests.post", return_value=fake_response):
        client.validate()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert "last_validated_at" in saved
    datetime.fromisoformat(saved["last_validated_at"])


def test_validate_returns_invalid_with_reason_not_found(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "not_found"})
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.INVALID
    assert result.reason == "not_found"


def test_validate_returns_invalid_with_reason_revoked(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "revoked"})
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.INVALID
    assert result.reason == "revoked"


def test_validate_invalid_does_not_clear_saved_key(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "revoked"})
    with patch("license_client.requests.post", return_value=fake):
        client.validate()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved.get("license_key") == "ABCD-EFGH-IJKL-MNOP"


def _config_with(license_key, last_validated_at):
    return {"license_key": license_key, "last_validated_at": last_validated_at}


def test_validate_offline_recent_validation_returns_tolerated(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED


def test_validate_offline_old_validation_returns_expired(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", old)), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_no_prior_validation_returns_expired(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.Timeout()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_corrupt_timestamp_returns_expired(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP", "last_validated_at": "lixo"}),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_non_200_response_uses_offline_path(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(503, None)
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED


def test_validate_offline_invalid_json_uses_offline_path(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.json.side_effect = ValueError("invalid json")
    with patch("license_client.requests.post", return_value=bad_resp):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED


def test_validate_corrupt_config_is_treated_as_no_key(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ não é json válido", encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    result = client.validate()
    assert result.status == LicenseStatus.NO_KEY
