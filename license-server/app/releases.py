"""Publicação de releases do app pelo painel admin.

Substitui o passo de upload do deploy.py: recebe o exe, calcula o SHA-256
durante a gravação e atualiza o version.json atomicamente — o /api/version
passa a anunciar a versão nova na hora.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("license-server.releases")

_BASE = Path(__file__).parent.parent
VERSION_FILE = _BASE / "version.json"
EXE_DIR = _BASE / "releases"

_VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")
_EXE_PREFIX = "ProcessadorOcorrencias-v"
MAX_SIZE = 300 * 1024 * 1024  # 300 MB


class ReleaseError(ValueError):
    """Erro de validação no publish — mensagem é exibida no painel."""


def read_version_info(version_file: Path = None) -> dict:
    vf = version_file or VERSION_FILE
    info = {"version": None, "filename": None, "sha256": None,
            "size": None, "published_at": None}
    if not vf.exists():
        return info
    try:
        data = json.loads(vf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return info
    info.update({k: data.get(k) for k in info})
    return info


def list_release_files(exe_dir: Path = None) -> list[dict]:
    d = exe_dir or EXE_DIR
    if not d.is_dir():
        return []
    files = []
    for p in sorted(d.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True):
        st = p.stat()
        files.append({
            "name": p.name,
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                             .isoformat(timespec="seconds"),
        })
    return files


def publish_release(version: str, stream, *, keep_old: bool = False,
                    version_file: Path = None, exe_dir: Path = None) -> dict:
    """Grava o exe vindo de `stream`, valida e publica no version.json.

    Levanta ReleaseError para entradas inválidas (versão, vazio, grande demais).
    """
    vf = version_file or VERSION_FILE
    d = exe_dir or EXE_DIR

    version = (version or "").strip()
    if not _VERSION_RE.match(version):
        raise ReleaseError("Versão inválida — use o formato 1.66 ou 1.66.1.")

    filename = f"{_EXE_PREFIX}{version}.exe"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (filename + ".part")

    h = hashlib.sha256()
    total = 0
    try:
        with open(tmp, "wb") as f:
            while True:
                chunk = stream.read(1048576)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SIZE:
                    raise ReleaseError("Arquivo maior que 300 MB — upload recusado.")
                h.update(chunk)
                f.write(chunk)
        if total == 0:
            raise ReleaseError("Arquivo vazio — selecione o .exe gerado pelo PyInstaller.")
        os.replace(tmp, d / filename)
    finally:
        if tmp.exists():
            tmp.unlink()

    info = {
        "version": version,
        "filename": filename,
        "sha256": h.hexdigest(),
        "size": total,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    vtmp = vf.with_suffix(".json.tmp")
    vtmp.write_text(json.dumps(info), encoding="utf-8")
    os.replace(vtmp, vf)

    if not keep_old:
        for p in d.glob(f"{_EXE_PREFIX}*.exe"):
            if p.name != filename:
                try:
                    p.unlink()
                    logger.info("release antigo removido: %s", p.name)
                except OSError:
                    logger.warning("não foi possível remover %s", p.name)

    logger.info("release publicado: v%s (%s, %d bytes, sha256=%s)",
                version, filename, total, info["sha256"])
    return info


def delete_release_file(filename: str, *, version_file: Path = None,
                        exe_dir: Path = None) -> bool:
    """Remove um exe antigo. Recusa remover o release atualmente publicado."""
    d = exe_dir or EXE_DIR
    safe = Path(filename).name
    current = read_version_info(version_file).get("filename")
    if safe == current:
        raise ReleaseError("Este é o release publicado — envie outra versão antes de removê-lo.")
    p = d / safe
    if p.suffix.lower() != ".exe" or not p.is_file():
        return False
    p.unlink()
    logger.info("release removido manualmente: %s", safe)
    return True
