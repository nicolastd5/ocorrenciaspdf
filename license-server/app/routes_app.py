from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import get_or_create_csrf_token, require_user

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
def historico(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "historico.html", {
        "entries": [], "active": "historico",
    })
