import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import requests


logger = logging.getLogger("license_client")


class LicenseStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    OFFLINE_TOLERATED = "offline_tolerated"
    OFFLINE_EXPIRED = "offline_expired"
    NO_KEY = "no_key"


@dataclass
class ValidationResult:
    status: LicenseStatus
    reason: Optional[str] = None
    client_name: Optional[str] = None


DEFAULT_CONFIG_PATH = Path.home() / ".ocorrencias_config.json"


class LicenseClient:
    SERVER_URL = "https://nicolasapp.duckdns.org"
    OFFLINE_TOLERANCE_HOURS = 24
    TIMEOUT_SECONDS = 10
    APP_VERSION = "1.42"

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path

    def _read_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Config file inválido em %s — tratando como vazio", self.config_path)
            return {}

    def _write_config(self, data: dict) -> None:
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_saved_key(self) -> Optional[str]:
        return self._read_config().get("license_key")

    def save_key(self, key: str) -> None:
        cfg = self._read_config()
        cfg["license_key"] = key
        self._write_config(cfg)

    def clear_key(self) -> None:
        cfg = self._read_config()
        cfg.pop("license_key", None)
        cfg.pop("last_validated_at", None)
        self._write_config(cfg)

    def validate(self, key: Optional[str] = None) -> ValidationResult:
        if key is None:
            key = self.get_saved_key()
        if not key:
            return ValidationResult(status=LicenseStatus.NO_KEY)

        url = f"{self.SERVER_URL}/api/validate"
        payload = {"key": key, "app_version": self.APP_VERSION}

        try:
            resp = requests.post(url, json=payload, timeout=self.TIMEOUT_SECONDS)
        except requests.RequestException as e:
            logger.info("Erro de rede validando licença: %s", e)
            return self._offline_result()

        if resp.status_code != 200:
            logger.info("Servidor respondeu %d — tratando como offline", resp.status_code)
            return self._offline_result()

        try:
            data = resp.json()
        except ValueError:
            logger.info("Resposta do servidor não é JSON válido — tratando como offline")
            return self._offline_result()

        if data.get("valid") is True:
            self._update_last_validated()
            return ValidationResult(
                status=LicenseStatus.VALID,
                client_name=data.get("client_name"),
            )

        return ValidationResult(
            status=LicenseStatus.INVALID,
            reason=data.get("reason"),
        )

    def _update_last_validated(self) -> None:
        cfg = self._read_config()
        cfg["last_validated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._write_config(cfg)

    def _offline_result(self) -> ValidationResult:
        cfg = self._read_config()
        last_str = cfg.get("last_validated_at")
        if not last_str:
            return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
        try:
            last = datetime.fromisoformat(last_str)
        except ValueError:
            return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        if delta < timedelta(hours=self.OFFLINE_TOLERANCE_HOURS):
            return ValidationResult(status=LicenseStatus.OFFLINE_TOLERATED)
        return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
