"""
Verifica se há uma versão nova no servidor e, se houver, baixa e relança o exe.
Só tem efeito quando rodando como executável PyInstaller (sys.frozen).
"""

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("auto_update")

SERVER_URL = "https://nicolasapp.duckdns.org"
TIMEOUT = 10


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


def _current_version() -> str:
    from license_client import LicenseClient
    return LicenseClient.APP_VERSION


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _fetch_latest() -> Optional[dict]:
    try:
        resp = requests.get(f"{SERVER_URL}/api/version", timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        logger.debug("Erro ao verificar versão: %s", e)
    return None


def _download_and_relaunch(filename: str) -> None:
    url = f"{SERVER_URL}/api/download/{filename}"
    logger.info("Baixando atualização: %s", url)

    current_exe = Path(sys.executable)
    tmp_dir = Path(tempfile.mkdtemp())
    new_exe = tmp_dir / filename

    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(new_exe, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
    except requests.RequestException as e:
        logger.warning("Falha ao baixar atualização: %s", e)
        return

    # Script bat que aguarda o processo atual fechar, copia o novo exe e relança
    bat = tmp_dir / "updater.bat"
    bat.write_text(
        f'@echo off\n'
        f':wait\n'
        f'tasklist /FI "PID eq {os.getpid()}" 2>nul | find /I "{os.getpid()}" >nul\n'
        f'if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)\n'
        f'copy /Y "{new_exe}" "{current_exe}" >nul\n'
        f'start "" "{current_exe}"\n'
        f'del "%~f0"\n',
        encoding="utf-8",
    )

    logger.info("Relançando via updater.bat")
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)


def check_and_update() -> None:
    """Verifica e aplica atualização. Chame antes de abrir a janela principal."""
    if not _is_frozen():
        logger.debug("Não é executável — auto-update ignorado")
        return

    latest = _fetch_latest()
    if not latest:
        return

    latest_ver = latest.get("version", "0.0")
    filename = latest.get("filename")

    if not filename:
        return

    current = _current_version()
    if _parse_version(latest_ver) > _parse_version(current):
        logger.info("Atualização disponível: %s → %s", current, latest_ver)
        _download_and_relaunch(filename)
