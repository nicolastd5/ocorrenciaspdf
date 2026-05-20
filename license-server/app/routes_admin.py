import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.keygen import generate_key
from app.licenses import (
    create_license, get_by_id, list_all_licenses,
    list_validations_for_license, revoke_license, unrevoke_license,
)
from app.security import (
    get_or_create_csrf_token, is_authenticated,
    verify_csrf_token, verify_password, hash_password,
)


router = APIRouter(prefix="/admin")
logger = logging.getLogger("license-server.admin")
limiter = Limiter(key_func=get_remote_address)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_BRT = timezone(timedelta(hours=-3))

def _fmt_brasilia(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BRT).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["brasilia"] = _fmt_brasilia

_admin_password_hash: str | None = None


def _get_admin_hash(request: Request) -> str:
    global _admin_password_hash
    if _admin_password_hash is None:
        _admin_password_hash = hash_password(request.app.state.settings.admin_password)
    return _admin_password_hash


def _check_csrf(request: Request, form_token: str) -> None:
    session_token = request.session.get("csrf_token")
    if not verify_csrf_token(session_token, form_token):
        raise HTTPException(status_code=400, detail="csrf_invalid")


def _require_auth_or_redirect(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return None


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": csrf, "error": None},
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login_post(
    request: Request,
    csrf_token: str = Form(...),
    password: str = Form(...),
):
    _check_csrf(request, csrf_token)
    admin_hash = _get_admin_hash(request)
    if not verify_password(password, admin_hash):
        logger.info("login: senha incorreta de %s", request.client.host if request.client else "?")
        return templates.TemplateResponse(
            request,
            "login.html",
            {"csrf_token": csrf_token, "error": "Senha incorreta"},
        )
    request.session["admin_authenticated"] = True
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    _check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse)
async def list_view(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    settings = request.app.state.settings
    licenses = list_all_licenses(settings.db_path)
    rows = []
    for lic in licenses:
        validations = list_validations_for_license(settings.db_path, lic.id)
        last = validations[0].validated_at if validations else None
        rows.append({"license": lic, "last_validation": last})
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "list.html",
        {"rows": rows, "csrf_token": csrf, "message": None},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_get(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(request, "new.html", {"csrf_token": csrf})


@router.post("/new")
async def new_post(
    request: Request,
    csrf_token: str = Form(...),
    client_name: str = Form(...),
    notes: str = Form(""),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)
    settings = request.app.state.settings
    key = generate_key()
    create_license(settings.db_path, key=key, client_name=client_name.strip(), notes=notes.strip() or None)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{license_id}", response_class=HTMLResponse)
async def detail_view(request: Request, license_id: int):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    settings = request.app.state.settings
    lic = get_by_id(settings.db_path, license_id)
    if lic is None:
        raise HTTPException(status_code=404)
    validations = list_validations_for_license(settings.db_path, license_id)
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {"license": lic, "validations": validations, "csrf_token": csrf},
    )


@router.post("/{license_id}/revoke")
async def revoke_post(request: Request, license_id: int, csrf_token: str = Form(...)):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)
    settings = request.app.state.settings
    revoke_license(settings.db_path, license_id)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{license_id}/unrevoke")
async def unrevoke_post(request: Request, license_id: int, csrf_token: str = Form(...)):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)
    settings = request.app.state.settings
    unrevoke_license(settings.db_path, license_id)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)
