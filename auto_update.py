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


def _download_and_relaunch(filename: str, on_progress=None, on_status=None) -> None:
    url = f"{SERVER_URL}/api/download/{filename}"
    logger.info("Baixando atualização: %s", url)

    current_exe = Path(sys.executable)
    target_exe = current_exe.parent / filename
    tmp_dir = Path(tempfile.mkdtemp())
    new_exe = tmp_dir / filename

    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0) or 0)
            baixado = 0
            with open(new_exe, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    baixado += len(chunk)
                    if on_progress:
                        on_progress(baixado, total)
    except requests.RequestException as e:
        logger.warning("Falha ao baixar atualização: %s", e)
        if on_status:
            on_status("erro")
        return

    # Script bat robusto:
    # 1) espera o processo atual terminar (loop com timeout máximo)
    # 2) tenta mover o novo exe até 5 vezes (Defender pode estar escaneando)
    # 3) só faz start + del do antigo se o destino existir; senão mostra erro
    # 4) loga tudo num arquivo para diagnóstico
    bat = tmp_dir / "updater.bat"
    log_path = tmp_dir / "updater.log"
    pid = os.getpid()

    # Tenta apagar o exe antigo com retry — o Windows pode demorar alguns ms para
    # liberar o handle do exe que acabou de fechar (mesmo apos tasklist confirmar).
    delete_old_line = ""
    if target_exe.resolve() != current_exe.resolve():
        delete_old_line = (
            f'set /a dtries=0\n'
            f':del_retry\n'
            f'del /Q "{current_exe}" >> "{log_path}" 2>&1\n'
            f'if not exist "{current_exe}" goto del_ok\n'
            f'set /a dtries+=1\n'
            f'if %dtries% geq 5 (echo aviso: nao foi possivel apagar {current_exe} >> "{log_path}" & goto del_ok)\n'
            f'timeout /t 1 /nobreak >nul\n'
            f'goto del_retry\n'
            f':del_ok\n'
        )

    bat.write_text(
        f'@echo off\n'
        f'chcp 65001 >nul\n'
        f'echo [%date% %time%] updater iniciado, aguardando PID {pid} > "{log_path}"\n'
        f'set /a tries=0\n'
        f':wait\n'
        f'tasklist /FI "PID eq {pid}" 2>nul | find /I "{pid}" >nul\n'
        f'if errorlevel 1 goto done_wait\n'
        f'set /a tries+=1\n'
        f'if %tries% geq 60 (echo timeout aguardando processo >> "{log_path}" & goto done_wait)\n'
        f'timeout /t 1 /nobreak >nul\n'
        f'goto wait\n'
        f':done_wait\n'
        f'echo [%date% %time%] processo encerrado, movendo exe >> "{log_path}"\n'
        f'set /a mtries=0\n'
        f':move_retry\n'
        f'move /Y "{new_exe}" "{target_exe}" >> "{log_path}" 2>&1\n'
        f'if exist "{target_exe}" goto move_ok\n'
        f'set /a mtries+=1\n'
        f'if %mtries% geq 5 goto move_fail\n'
        f'timeout /t 2 /nobreak >nul\n'
        f'goto move_retry\n'
        f':move_fail\n'
        f'echo ERRO: nao foi possivel mover o exe para {target_exe} >> "{log_path}"\n'
        f'msg * "Falha ao atualizar Processador de Ocorrencias. Veja o log em {log_path}"\n'
        f'exit /b 1\n'
        f':move_ok\n'
        f'echo move OK >> "{log_path}"\n'
        f'{delete_old_line}'
        f'start "" "{target_exe}"\n'
        f'echo [%date% %time%] start emitido >> "{log_path}"\n',
        encoding="utf-8-sig",
    )

    logger.info("Relançando via updater.bat -> %s (log: %s)", target_exe, log_path)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=subprocess.CREATE_NO_WINDOW)
    if on_status:
        # Modo callback: a thread principal cuida de fechar a UI e encerrar o
        # processo após mostrar "reiniciando". sys.exit numa thread secundária
        # só encerraria a thread, não o processo.
        on_status("reiniciando")
        return
    sys.exit(0)


def check_and_update(on_progress=None, on_status=None) -> None:
    """Verifica e aplica atualização. Chame antes de abrir a janela principal.

    on_progress(baixado:int, total:int) e on_status(estado:str) são opcionais;
    sem eles, mantém o comportamento legado (download síncrono + sys.exit).
    """
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
        _download_and_relaunch(filename, on_progress=on_progress, on_status=on_status)
