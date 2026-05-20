import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/api")
logger = logging.getLogger("license-server.update")

# Esses caminhos ficam no diretório raiz do servidor no VPS
_BASE = Path(__file__).parent.parent
VERSION_FILE = _BASE / "version.json"
EXE_DIR = _BASE / "releases"


@router.get("/version")
async def get_version() -> dict:
    if not VERSION_FILE.exists():
        return {"version": "0.0", "filename": None}
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        return {"version": data.get("version", "0.0"), "filename": data.get("filename")}
    except (json.JSONDecodeError, OSError):
        return {"version": "0.0", "filename": None}


@router.get("/download/{filename}")
async def download(filename: str) -> FileResponse:
    # Impede path traversal
    safe = Path(filename).name
    exe_path = EXE_DIR / safe
    if not exe_path.exists() or exe_path.suffix.lower() != ".exe":
        return JSONResponse(status_code=404, content={"error": "not_found"})
    logger.info("Download solicitado: %s", safe)
    return FileResponse(
        path=str(exe_path),
        filename=safe,
        media_type="application/octet-stream",
    )
