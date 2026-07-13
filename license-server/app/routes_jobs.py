from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import jobs, worker_tasks
from app.security import current_user_id, get_or_create_csrf_token, require_user, verify_csrf_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MAX_UPLOAD = 50 * 1024 * 1024


def _erro(request, template, msg, status_code=400):
    return templates.TemplateResponse(request, template, {
        "csrf_token": get_or_create_csrf_token(request), "error": msg,
        "active": template.split(".")[0],
    }, status_code=status_code)


def _salvar_upload(up: UploadFile, destino: Path) -> Optional[str]:
    """Salva o arquivo; retorna mensagem de erro ou None."""
    data = up.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        return "Arquivo excede 50 MB."
    destino.write_bytes(data)
    return None


def _job_do_usuario(request: Request, job_id: str) -> dict:
    settings = request.app.state.settings
    job = jobs.get_job(settings.db_path, job_id)
    if not job or job["user_id"] != current_user_id(request):
        raise HTTPException(status_code=404)
    return job


# ── Ocorrências ──────────────────────────────────────────────────────

@router.post("/app/ocorrencias")
def ocorrencias_submit(request: Request,
                       pdf: UploadFile = File(...),
                       xlsx: UploadFile = File(...),
                       codigos: list[str] = Form(...),
                       dias_mes: Optional[int] = Form(None),
                       colunas_qt: Optional[list[str]] = Form(None),
                       csrf_token: str = Form(...),
                       _=Depends(require_user)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/app/ocorrencias", status_code=303)
    if not pdf.filename.lower().endswith(".pdf"):
        return _erro(request, "ocorrencias.html", "O arquivo de jornada deve ser PDF.")
    if not xlsx.filename.lower().endswith((".xlsx", ".xls")):
        return _erro(request, "ocorrencias.html", "A planilha de pedido deve ser Excel.")
    if not codigos:
        return _erro(request, "ocorrencias.html", "Selecione ao menos um código.")

    settings = request.app.state.settings
    uid = current_user_id(request)
    params = {
        "codigos": codigos, "dias_mes": dias_mes,
        "colunas_qt_sel": colunas_qt,
        "pdf_name": "jornada.pdf", "xlsx_name": "pedido.xlsx",
        "orig_pdf": pdf.filename, "orig_xlsx": xlsx.filename,
    }
    job_id = jobs.create_job(settings.db_path, uid, "ocorrencias", params)
    d = jobs.job_dir(settings.data_dir, job_id)
    for up, nome in ((pdf, "jornada.pdf"), (xlsx, "pedido.xlsx")):
        err = _salvar_upload(up, d / "in" / nome)
        if err:
            return _erro(request, "ocorrencias.html", err)
    jobs.enqueue_ocorrencias(request.app.state.queue, settings.db_path,
                             settings.data_dir, job_id)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)


# ── VT-Caixa ─────────────────────────────────────────────────────────

@router.post("/app/vt-caixa")
def vt_caixa_submit(request: Request,
                    fonte: UploadFile = File(...),
                    cadastral: UploadFile = File(...),
                    csrf_token: str = Form(...),
                    _=Depends(require_user)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/app/vt-caixa", status_code=303)
    if not fonte.filename.lower().endswith((".pdf", ".xlsx", ".xls")):
        return _erro(request, "vt_caixa.html", "A fonte deve ser PDF ou Excel.")
    if not cadastral.filename.lower().endswith((".xlsx", ".xls")):
        return _erro(request, "vt_caixa.html", "O cadastral deve ser Excel.")

    ext_fonte = "." + fonte.filename.rsplit(".", 1)[1].lower()
    ext_cad = "." + cadastral.filename.rsplit(".", 1)[1].lower()
    settings = request.app.state.settings
    params = {
        "fonte_name": f"fonte{ext_fonte}", "cadastral_name": f"cadastral{ext_cad}",
        "orig_fonte": fonte.filename, "orig_cadastral": cadastral.filename,
    }
    job_id = jobs.create_job(settings.db_path, current_user_id(request), "vt_caixa", params)
    d = jobs.job_dir(settings.data_dir, job_id)
    for up, nome in ((fonte, params["fonte_name"]), (cadastral, params["cadastral_name"])):
        err = _salvar_upload(up, d / "in" / nome)
        if err:
            return _erro(request, "vt_caixa.html", err)
    jobs.enqueue_vt_caixa(request.app.state.queue, settings.db_path,
                          settings.data_dir, job_id)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)


# ── Job pages ────────────────────────────────────────────────────────

@router.get("/app/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    return templates.TemplateResponse(request, "job.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
        "active": job["kind"],
    })


@router.get("/app/jobs/{job_id}/fragment", response_class=HTMLResponse)
def job_fragment(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    return templates.TemplateResponse(request, "job_fragment.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
    })


# ── Conflicts ────────────────────────────────────────────────────────

@router.get("/app/jobs/{job_id}/conflitos", response_class=HTMLResponse)
def conflitos_page(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "awaiting_review":
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "conflitos.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
        "active": "ocorrencias",
    })


@router.post("/app/jobs/{job_id}/conflitos")
async def conflitos_submit(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "awaiting_review":
        raise HTTPException(status_code=404)
    form = await request.form()
    if not verify_csrf_token(request.session.get("csrf_token"), form.get("csrf_token")):
        return RedirectResponse(f"/app/jobs/{job_id}/conflitos", status_code=303)
    resolucoes = {k[4:]: v for k, v in form.items() if k.startswith("res_")}
    settings = request.app.state.settings
    worker_tasks.finalizar_ocorrencias(settings.db_path, settings.data_dir,
                                       job_id, resolucoes)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)


# ── Download ─────────────────────────────────────────────────────────

@router.get("/app/jobs/{job_id}/download")
def job_download(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "done" or not job["result"]:
        raise HTTPException(status_code=404)
    settings = request.app.state.settings
    path = jobs.job_dir(settings.data_dir, job_id) / "out" / job["result"]["output_name"]
    if not path.exists():
        raise HTTPException(status_code=404)
    ext = path.suffix
    prefixo = "ocorrencias" if job["kind"] == "ocorrencias" else "vt-caixa"
    return FileResponse(path, filename=f"{prefixo}-{job_id[:8]}{ext}",
                        media_type="application/octet-stream")
