import io
import re as _re

from openpyxl import Workbook


def _c(client):
    return client[0] if isinstance(client, tuple) else client


def _upload(logged_client, pdf_name="jornada.pdf", xlsx_bytes=None):
    c = _c(logged_client)
    # Get CSRF from the ocorrencias page
    r = c.get("/app/ocorrencias")
    assert r.status_code == 200
    token = _re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)

    if xlsx_bytes is None:
        wb = Workbook()
        ws = wb.active
        ws.append(["Folha RE", "Nome", "MOTIVO"])
        ws.append(["12345", "ANA", ""])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()
    return c.post("/app/ocorrencias", data={
        "codigos": ["FA", "AT"], "csrf_token": token,
    }, files={
        "pdf": (pdf_name, b"%PDF-fake", "application/pdf"),
        "xlsx": ("pedido.xlsx", xlsx_bytes,
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }, follow_redirects=False)


def test_upload_cria_job_e_redireciona(logged_client, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/app/jobs/")


def test_upload_extensao_invalida(logged_client):
    r = _upload(logged_client, pdf_name="jornada.txt")
    assert r.status_code == 400


def test_upload_sem_login(client):
    c = _c(client)
    r = c.post("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303


def test_pagina_do_job_e_fragmento(logged_client, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client)
    job_url = r.headers["location"]
    c = _c(logged_client)
    r = c.get(job_url)
    assert r.status_code == 200
    r = c.get(job_url + "/fragment")
    assert r.status_code == 200
    # fake queue is synchronous: job is already done
    assert "download" in r.text.lower()
    assert "every 1s" not in r.text


def test_download_do_resultado(logged_client, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client)
    c = _c(logged_client)
    r = c.get(r.headers["location"] + "/download")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert len(r.content) > 1000  # xlsx real


def test_upload_vt_caixa(logged_client, monkeypatch):
    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None,
                       codigos_extras=None, depart_extras=None):
        from pathlib import Path
        Path(output_path).write_text("CNPJ\n", encoding="latin-1")
        return {"total_pdf": 1, "total_fonte": 1, "tipo_fonte": "PDF",
                "total_ok": 1, "nao_encontrados": [], "avisos_csv": []}
    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    c = _c(logged_client)
    r = c.get("/app/vt-caixa")
    assert r.status_code == 200
    token = _re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = c.post("/app/vt-caixa", data={"csrf_token": token}, files={
        "fonte": ("nautilus.pdf", b"%PDF", "application/pdf"),
        "cadastral": ("cad.xlsx", b"xx", "application/octet-stream"),
    }, follow_redirects=False)
    assert r.status_code == 303
    job_url = r.headers["location"]
    r = c.get(job_url + "/download")
    assert r.status_code == 200
    assert "vt-caixa" in r.headers["content-disposition"]
