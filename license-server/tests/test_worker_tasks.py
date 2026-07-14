import pytest
from openpyxl import Workbook

from app import jobs, users, worker_tasks
from app.db import init_db


def _create_user(db_path):
    try:
        return users.create_user(db_path, "test@test.com", "Test", "s3nh4forte")
    except ValueError:
        pass


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    _create_user(db)
    return db, str(tmp_path / "data")


def _make_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Folha RE", "Nome", "MOTIVO"])
    ws.append(["12345", "ANA", ""])
    wb.save(path)


def _setup_job(db, data_dir, params=None):
    p = {"codigos": ["FA", "AT"],
         "pdf_name": "jornada.pdf", "xlsx_name": "pedido.xlsx",
         "orig_pdf": "jornada.pdf", "orig_xlsx": "pedido.xlsx"}
    p.update(params or {})
    jid = jobs.create_job(db, 1, "ocorrencias", p)
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "jornada.pdf").write_bytes(b"%PDF-fake")
    _make_xlsx(d / "in" / "pedido.xlsx")
    return jid


def test_processar_sem_dias_mes():
    import inspect
    from core.processador import ProcessadorOcorrencias
    sig = inspect.signature(ProcessadorOcorrencias.processar)
    assert "dias_mes" not in sig.parameters
    assert "colunas_qt_sel" not in sig.parameters


def test_sem_conflito_gera_done(env, monkeypatch):
    db, data_dir = env
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert j["result"]["matched"] == 1
    assert (jobs.job_dir(data_dir, jid) / "out" / "resultado.xlsx").exists()


def test_com_conflito_aguarda_revisao_e_finaliza(env, monkeypatch):
    db, data_dir = env
    v1 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 2}}}
    v2 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 3}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: v1)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: v2)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "awaiting_review"
    assert j["result"]["conflitos"][0]["codigo"] == "AT"

    res = worker_tasks.finalizar_ocorrencias(db, data_dir, jid, {"12345|AT": 3})
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert res["matched"] == 1
    assert (jobs.job_dir(data_dir, jid) / "out" / "resultado.xlsx").exists()


def test_erro_marca_job(env, monkeypatch):
    db, data_dir = env

    def boom(self, p, c):
        raise ValueError("PDF ilegível")
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias", boom)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "error" and "PDF ilegível" in j["error"]


def test_vt_caixa_done(env, monkeypatch):
    db, data_dir = env
    resultado = {"total_pdf": 5, "total_fonte": 5, "tipo_fonte": "PDF",
                 "total_ok": 4, "nao_encontrados": [{"codigo": "999"}],
                 "avisos_csv": []}

    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None,
                       codigos_extras=None, depart_extras=None):
        from pathlib import Path
        Path(output_path).write_text("CNPJ;CEP\n", encoding="latin-1")
        return resultado

    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    jid = jobs.create_job(db, 1, "vt_caixa", {
        "fonte_name": "fonte.pdf", "cadastral_name": "cadastral.xlsx",
        "orig_fonte": "nautilus.pdf", "orig_cadastral": "cad.xlsx"})
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "fonte.pdf").write_bytes(b"%PDF")
    (d / "in" / "cadastral.xlsx").write_bytes(b"xx")
    worker_tasks.run_vt_caixa(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert j["result"]["total_ok"] == 4
    assert j["result"]["output_name"] == "beneficios.csv"
    assert (d / "out" / "beneficios.csv").exists()


def test_vt_caixa_injeta_personalizados(env, monkeypatch):
    db, data_dir = env
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "OP CUSTOM", "", "777")
    ref_codes.add_depart_sub(db, 1, "DEP A", "DEP B")

    capturado = {}

    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None,
                       codigos_extras=None, depart_extras=None):
        from pathlib import Path
        capturado["codigos"] = codigos_extras
        capturado["depart"] = depart_extras
        Path(output_path).write_text("CNPJ\n", encoding="latin-1")
        return {"total_pdf": 1, "total_fonte": 1, "tipo_fonte": "PDF",
                "total_ok": 1, "nao_encontrados": [], "avisos_csv": []}

    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    jid = jobs.create_job(db, 1, "vt_caixa", {
        "fonte_name": "fonte.pdf", "cadastral_name": "cadastral.xlsx"})
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "fonte.pdf").write_bytes(b"%PDF")
    (d / "in" / "cadastral.xlsx").write_bytes(b"xx")
    worker_tasks.run_vt_caixa(db, data_dir, jid)

    assert jobs.get_job(db, jid)["status"] == "done"
    assert capturado["codigos"] == [("OP CUSTOM", None, "777")]
    assert capturado["depart"] == {"DEP A": "DEP B"}
