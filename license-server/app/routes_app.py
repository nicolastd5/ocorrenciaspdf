import csv
import io
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import history as history_module
from app.security import current_user_id, get_or_create_csrf_token, require_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/app/ocorrencias", response_class=HTMLResponse)
def ocorrencias(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "ocorrencias.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "ocorrencias",
    })


@router.get("/app/vt-caixa", response_class=HTMLResponse)
def vt_caixa(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "vt_caixa.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "vt_caixa",
    })


@router.get("/app/codigos", response_class=HTMLResponse)
def codigos(request: Request, _=Depends(require_user)):
    from core.vt_caixa_processador import ProcessadorVTCaixa
    cod_rows = [(op, valor or "qualquer", cod)
                for op, valor, cod in ProcessadorVTCaixa._CODIGOS_BENEFICIO]
    return templates.TemplateResponse(request, "codigos.html", {
        "cod_rows": cod_rows, "depart_map": ProcessadorVTCaixa._DEPART_MAP,
        "active": "codigos",
    })


@router.get("/app/historico", response_class=HTMLResponse)
def historico(request: Request, q: str = "", status: str = "", _=Depends(require_user)):
    settings = request.app.state.settings
    entries = history_module.list_for_user(settings.db_path, current_user_id(request), q, status)
    return templates.TemplateResponse(request, "historico.html", {
        "entries": entries, "q": q, "status": status, "active": "historico",
    })


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
