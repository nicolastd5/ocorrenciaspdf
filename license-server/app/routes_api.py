import logging
import re
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.licenses import get_by_key, log_validation
from app.security import mask_key


router = APIRouter(prefix="/api")
logger = logging.getLogger("license-server.api")
limiter = Limiter(key_func=get_remote_address)

KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class ValidateBody(BaseModel):
    key: str
    app_version: Optional[str] = None


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/validate")
@limiter.limit("60/minute")
async def validate(request: Request) -> dict:
    try:
        raw = await request.json()
        body = ValidateBody(**raw)
    except (ValidationError, ValueError, TypeError):
        logger.info("validate: body inválido de %s", _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if not KEY_PATTERN.match(body.key):
        logger.info("validate: formato inválido %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    settings = request.app.state.settings
    lic = get_by_key(settings.db_path, body.key)
    if lic is None:
        logger.info("validate: not_found %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if lic.revoked:
        logger.info("validate: revoked %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "revoked"}

    log_validation(
        settings.db_path,
        license_id=lic.id,
        ip=_client_ip(request),
        app_version=body.app_version,
    )
    logger.info("validate: OK %s de %s", mask_key(body.key), _client_ip(request))
    return {"valid": True, "client_name": lic.client_name}


class ConfigBody(BaseModel):
    key: str


@router.post("/config")
@limiter.limit("30/minute")
async def get_config(request: Request) -> dict:
    try:
        raw = await request.json()
        body = ConfigBody(**raw)
    except (ValidationError, ValueError, TypeError):
        return {"error": "invalid_request"}

    if not KEY_PATTERN.match(body.key):
        return {"error": "invalid_key"}

    settings = request.app.state.settings
    lic = get_by_key(settings.db_path, body.key)
    if lic is None or lic.revoked:
        return {"error": "invalid_key"}

    from pathlib import Path as _Path
    key_file = _Path(__file__).parent.parent / "gemini_key.txt"
    gemini_key = key_file.read_text(encoding="utf-8").strip() if key_file.exists() else settings.gemini_api_key
    return {"gemini_api_key": gemini_key}
