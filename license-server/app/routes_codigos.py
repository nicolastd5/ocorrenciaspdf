from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import ref_codes
from app import users as users_module
from app.security import (
    current_user_id, get_or_create_csrf_token, require_user, verify_csrf_token,
)
from core.vt_caixa_processador import ProcessadorVTCaixa

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _ctx_beneficio(request: Request, db_path: str, error: str | None = None) -> dict:
    builtin = [{"operadora": op, "valor_unitario": valor, "codigo": cod, "id": None}
               for op, valor, cod in ProcessadorVTCaixa._CODIGOS_BENEFICIO]
    return {
        "beneficio_rows": builtin + ref_codes.list_benefit_codes(db_path),
        "csrf_token": get_or_create_csrf_token(request),
        "beneficio_error": error,
    }


def _ctx_depart(request: Request, db_path: str, error: str | None = None) -> dict:
    builtin = [{"original": o, "substituto": s, "id": None}
               for o, s in ProcessadorVTCaixa._DEPART_MAP.items()]
    return {
        "depart_rows": builtin + ref_codes.list_depart_subs(db_path),
        "csrf_token": get_or_create_csrf_token(request),
        "depart_error": error,
    }


@router.get("/app/codigos", response_class=HTMLResponse)
def codigos_page(request: Request, _=Depends(require_user)):
    db = request.app.state.settings.db_path
    user = users_module.get_user(db, current_user_id(request))
    ctx = {**_ctx_beneficio(request, db), **_ctx_depart(request, db),
           "active": "codigos", "tutorial_seen": bool(user["tutorial_seen"])}
    return templates.TemplateResponse(request, "codigos.html", ctx)


@router.post("/app/codigos/beneficio", response_class=HTMLResponse)
def beneficio_add(request: Request, operadora: str = Form(""),
                  valor_unitario: str = Form(""), codigo: str = Form(""),
                  csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    error, status_code = None, 200
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        error, status_code = "Sessão expirada — recarregue a página.", 400
    else:
        try:
            ref_codes.add_benefit_code(db, current_user_id(request),
                                       operadora, valor_unitario, codigo)
        except ValueError as e:
            error, status_code = str(e), 400
    return templates.TemplateResponse(
        request, "codigos_beneficio_fragment.html",
        _ctx_beneficio(request, db, error), status_code=status_code)


@router.post("/app/codigos/beneficio/{code_id}/excluir", response_class=HTMLResponse)
def beneficio_delete(request: Request, code_id: int,
                     csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        ref_codes.delete_benefit_code(db, code_id)
    return templates.TemplateResponse(
        request, "codigos_beneficio_fragment.html", _ctx_beneficio(request, db))


@router.post("/app/codigos/departamento", response_class=HTMLResponse)
def depart_add(request: Request, original: str = Form(""),
               substituto: str = Form(""), csrf_token: str = Form(""),
               _=Depends(require_user)):
    db = request.app.state.settings.db_path
    error, status_code = None, 200
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        error, status_code = "Sessão expirada — recarregue a página.", 400
    else:
        try:
            ref_codes.add_depart_sub(db, current_user_id(request),
                                     original, substituto)
        except ValueError as e:
            error, status_code = str(e), 400
    return templates.TemplateResponse(
        request, "codigos_depart_fragment.html",
        _ctx_depart(request, db, error), status_code=status_code)


@router.post("/app/codigos/departamento/{sub_id}/excluir", response_class=HTMLResponse)
def depart_delete(request: Request, sub_id: int,
                  csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        ref_codes.delete_depart_sub(db, sub_id)
    return templates.TemplateResponse(
        request, "codigos_depart_fragment.html", _ctx_depart(request, db))
