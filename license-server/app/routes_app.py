import csv
import io
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import history as history_module
from app import ref_codes
from app import users as users_module
from app.security import (
    current_user_id, get_or_create_csrf_token, require_user, verify_csrf_token,
)
from core.processador import ProcessadorOcorrencias

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _tutorial_seen(request: Request) -> bool:
    settings = request.app.state.settings
    user = users_module.get_user(settings.db_path, current_user_id(request))
    return bool(user["tutorial_seen"])


def _recentes(request: Request, kind: str) -> list[dict]:
    settings = request.app.state.settings
    entries = history_module.list_for_user(settings.db_path, current_user_id(request))
    return [e for e in entries if e["kind"] == kind][:5]


@router.get("/app/ocorrencias", response_class=HTMLResponse)
def ocorrencias(request: Request, _=Depends(require_user)):
    settings = request.app.state.settings
    builtin = [{"codigo": c,
                "descricao": ProcessadorOcorrencias.DESCRICOES.get(c, ""),
                "custom": False}
               for c in ProcessadorOcorrencias.TODOS_CODIGOS]
    custom = [{"codigo": r["codigo"], "descricao": r["descricao"], "custom": True}
              for r in ref_codes.list_occurrence_codes(settings.db_path)]
    return templates.TemplateResponse(request, "ocorrencias.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "ocorrencias",
        "tutorial_seen": _tutorial_seen(request),
        "codigos_disponiveis": builtin + custom,
        "recentes": _recentes(request, "ocorrencias"),
    })


@router.get("/app/vt-caixa", response_class=HTMLResponse)
def vt_caixa(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "vt_caixa.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "vt_caixa",
        "tutorial_seen": _tutorial_seen(request),
        "recentes": _recentes(request, "vt_caixa"),
    })


@router.get("/app/historico", response_class=HTMLResponse)
def historico(request: Request, q: str = "", status: str = "", _=Depends(require_user)):
    settings = request.app.state.settings
    entries = history_module.list_for_user(settings.db_path, current_user_id(request), q, status)
    return templates.TemplateResponse(request, "historico.html", {
        "entries": entries, "q": q, "status": status, "active": "historico",
        "csrf_token": get_or_create_csrf_token(request),
        "tutorial_seen": _tutorial_seen(request),
    })


@router.post("/app/tutorial/seen")
def tutorial_seen(request: Request, csrf_token: str = Form(""),
                  _=Depends(require_user)):
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        settings = request.app.state.settings
        users_module.mark_tutorial_seen(settings.db_path, current_user_id(request))
    return Response(status_code=204)


@router.get("/app/historico.csv")
def historico_csv(request: Request, q: str = "", status: str = "", _=Depends(require_user)):
    settings = request.app.state.settings
    entries = history_module.list_for_user(settings.db_path, current_user_id(request), q, status)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["data", "tipo", "status", "arquivos", "detalhes"])
    for e in entries:
        w.writerow([e["created_at"], e["kind"], e["status"],
                    "; ".join(e["input_names"]), json.dumps(e["counts"], ensure_ascii=False)])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=historico.csv"})
