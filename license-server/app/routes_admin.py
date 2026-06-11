import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.keygen import generate_key
from app.licenses import (
    count_validations_since, create_license, get_by_id, last_validation_map,
    license_stats, list_all_licenses, list_recent_validations,
    list_validations_for_license, revoke_license, unrevoke_license,
)
from app.releases import (
    ReleaseError, delete_release_file, list_release_files, publish_release,
    read_version_info,
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


_GEMINI_KEY_FILE = Path(__file__).parent.parent / "gemini_key.txt"


def _fmt_size(n) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "—"


templates.env.filters["filesize"] = _fmt_size


def _read_gemini_key() -> str:
    if _GEMINI_KEY_FILE.exists():
        return _GEMINI_KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def _write_gemini_key(key: str) -> None:
    _GEMINI_KEY_FILE.write_text(key.strip(), encoding="utf-8")


def _delete_gemini_key() -> None:
    if _GEMINI_KEY_FILE.exists():
        _GEMINI_KEY_FILE.unlink()


@router.get("", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    settings = request.app.state.settings
    db = settings.db_path
    now = datetime.now(timezone.utc)
    stats = license_stats(db)
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "csrf_token": csrf,
            "stats": stats,
            "val_24h": count_validations_since(
                db, (now - timedelta(hours=24)).isoformat(timespec="seconds")),
            "val_7d": count_validations_since(
                db, (now - timedelta(days=7)).isoformat(timespec="seconds")),
            "recent": list_recent_validations(db, limit=12),
            "release": read_version_info(),
        },
    )


@router.get("/licenses", response_class=HTMLResponse)
async def licenses_view(request: Request, q: str = Query(""),
                        status_f: str = Query("", alias="status")):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    settings = request.app.state.settings
    licenses = list_all_licenses(settings.db_path)
    lastmap = last_validation_map(settings.db_path)

    busca = q.strip().lower()
    if busca:
        licenses = [l for l in licenses
                    if busca in l.client_name.lower() or busca in l.key.lower()]
    if status_f == "active":
        licenses = [l for l in licenses if not l.revoked]
    elif status_f == "revoked":
        licenses = [l for l in licenses if l.revoked]

    rows = [{"license": lic, "last": lastmap.get(lic.id)} for lic in licenses]
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "list.html",
        {"rows": rows, "csrf_token": csrf, "q": q, "status_f": status_f,
         "stats": license_stats(settings.db_path)},
    )


# ---------- releases (upload de versão nova direto pelo painel) ----------

def _render_releases(request, *, message=None, error=None, status_code=200):
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "releases.html",
        {"csrf_token": csrf, "release": read_version_info(),
         "files": list_release_files(), "message": message, "error": error},
        status_code=status_code,
    )


@router.get("/releases", response_class=HTMLResponse)
async def releases_get(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    return _render_releases(request)


@router.post("/releases/upload", response_class=HTMLResponse)
async def releases_upload(
    request: Request,
    csrf_token: str = Form(...),
    version: str = Form(...),
    keep_old: str = Form(""),
    file: UploadFile = File(...),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)
    try:
        info = publish_release(version, file.file, keep_old=bool(keep_old))
    except ReleaseError as e:
        return _render_releases(request, error=str(e))
    logger.info("release v%s publicado via painel por %s", info["version"],
                request.client.host if request.client else "?")
    return _render_releases(
        request,
        message=(f"Release v{info['version']} publicado — os clientes passam a "
                 f"receber a atualização imediatamente. SHA-256: {info['sha256'][:16]}…"))


@router.post("/releases/delete", response_class=HTMLResponse)
async def releases_delete(
    request: Request,
    csrf_token: str = Form(...),
    filename: str = Form(...),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)
    try:
        ok = delete_release_file(filename)
    except ReleaseError as e:
        return _render_releases(request, error=str(e))
    if ok:
        return _render_releases(request, message=f"{Path(filename).name} removido.")
    return _render_releases(request, error="Arquivo não encontrado.")


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


@router.get("/config", response_class=HTMLResponse)
async def config_get(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request, "config.html",
        {"csrf_token": csrf, "gemini_key": _read_gemini_key(), "message": None, "error": None},
    )


@router.post("/config")
async def config_post(
    request: Request,
    csrf_token: str = Form(...),
    gemini_key: str = Form(""),
    action: str = Form("save"),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)

    if action == "delete":
        _delete_gemini_key()
        msg = "API key removida."
    else:
        _write_gemini_key(gemini_key)
        msg = "API key salva com sucesso."

    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request, "config.html",
        {"csrf_token": csrf, "gemini_key": _read_gemini_key(), "message": msg, "error": None},
    )


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
