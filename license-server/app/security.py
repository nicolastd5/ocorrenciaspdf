import bcrypt
import hmac
import secrets
from typing import Optional

from fastapi import HTTPException, Request, status


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(session_token: Optional[str], form_token: Optional[str]) -> bool:
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)


def mask_key(key: Optional[str]) -> str:
    if not key or len(key) < 4:
        return "***"
    return f"{key[:4]}-***"


def is_authenticated(request: Request) -> bool:
    return request.session.get("admin_authenticated") is True


def require_admin(request: Request):
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token
