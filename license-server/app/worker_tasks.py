"""Funções executadas pelo worker RQ. Recebem apenas tipos serializáveis."""
import logging

from app import history, jobs, ref_codes
from core.processador import ProcessadorOcorrencias
from core.vt_caixa_processador import ProcessadorVTCaixa

logger = logging.getLogger("worker")


def _progress_cb(db_path, job_id):
    def cb(pct, msg):
        jobs.set_progress(db_path, job_id, pct, msg)
    return cb


def _registrar_historico(db_path, job_id, status_hist, counts):
    job = jobs.get_job(db_path, job_id)
    if not job:
        return
    params = job["params"]
    # Use original filenames if available, else internal names
    nomes = [
        params.get("orig_pdf", params.get("pdf_name", "")),
        params.get("orig_xlsx", params.get("xlsx_name", "")),
    ]
    nomes += [
        params.get("orig_fonte", params.get("fonte_name", "")),
        params.get("orig_cadastral", params.get("cadastral_name", "")),
    ]
    history.add(db_path, job["user_id"], job_id, job["kind"], status_hist,
                [n for n in nomes if n], counts)


def run_ocorrencias(db_path: str, data_dir: str, job_id: str) -> None:
    try:
        job = jobs.get_job(db_path, job_id)
        params = job["params"]
        d = jobs.job_dir(data_dir, job_id)
        pdf = str(d / "in" / params["pdf_name"])
        codigos = params["codigos"]

        jobs.set_status(db_path, job_id, "running")
        cb = _progress_cb(db_path, job_id)

        p = ProcessadorOcorrencias()
        cb(10, "Lendo PDF (1ª varredura)...")
        v1 = p.extrair_ocorrencias(pdf, codigos)
        cb(30, "Lendo PDF (2ª varredura)...")
        v2 = p.extrair_ocorrencias_texto(pdf, codigos)
        rec = p.reconciliar([v1, v2], codigos)

        if rec["conflitos"]:
            jobs.set_progress(db_path, job_id, 45,
                              f"{len(rec['conflitos'])} divergência(s) aguardando revisão")
            jobs.set_status(db_path, job_id, "awaiting_review", result=rec)
            return

        result = _processar_final(db_path, data_dir, job_id, rec["concordantes"])
        jobs.set_status(db_path, job_id, "done", result=result)
        _registrar_historico(db_path, job_id, "sucesso", {
            "matched": result["matched"],
            "nao_encontrados": len(result["nao_encontrados"]),
        })
    except Exception as e:
        logger.exception("job %s falhou", job_id)
        jobs.set_status(db_path, job_id, "error", error=str(e))
        _registrar_historico(db_path, job_id, "erro", {})


def finalizar_ocorrencias(db_path: str, data_dir: str, job_id: str,
                          resolucoes: dict) -> dict:
    job = jobs.get_job(db_path, job_id)
    rec = job["result"]
    dados = {re_val: dict(info) for re_val, info in rec["concordantes"].items()}
    for c in rec["conflitos"]:
        chave = f"{c['re']}|{c['codigo']}"
        valor = int(resolucoes.get(chave, c["sugestao"]))
        entry = dados.setdefault(c["re"], {"nome": c["nome"], "ocorrencias": {}})
        if valor > 0:
            entry["ocorrencias"][c["codigo"]] = valor
    result = _processar_final(db_path, data_dir, job_id, dados)
    jobs.set_status(db_path, job_id, "done", result=result)
    _registrar_historico(db_path, job_id, "sucesso", {
        "matched": result["matched"],
        "nao_encontrados": len(result["nao_encontrados"]),
    })
    return result


def _processar_final(db_path: str, data_dir: str, job_id: str, dados: dict) -> dict:
    job = jobs.get_job(db_path, job_id)
    params = job["params"]
    d = jobs.job_dir(data_dir, job_id)
    out = d / "out" / "resultado.xlsx"
    p = ProcessadorOcorrencias()
    result = p.processar(
        pdf_path=None,
        xlsx_path=str(d / "in" / params["xlsx_name"]),
        output_path=str(out),
        codigos=params["codigos"],
        progress_cb=_progress_cb(db_path, job_id),
        dados_externos=dados,
        config_extras=ref_codes.occurrence_config(db_path),
    )
    result["output_name"] = "resultado.xlsx"
    return result


def run_vt_caixa(db_path: str, data_dir: str, job_id: str) -> None:
    try:
        job = jobs.get_job(db_path, job_id)
        params = job["params"]
        d = jobs.job_dir(data_dir, job_id)
        jobs.set_status(db_path, job_id, "running")
        p = ProcessadorVTCaixa()
        result = p.processar(
            fonte_path=str(d / "in" / params["fonte_name"]),
            xls_path=str(d / "in" / params["cadastral_name"]),
            output_path=str(d / "out" / "beneficios.csv"),
            progress_cb=_progress_cb(db_path, job_id),
            codigos_extras=ref_codes.benefit_tuples(db_path),
            depart_extras=ref_codes.depart_dict(db_path),
        )
        result["output_name"] = "beneficios.csv"
        jobs.set_status(db_path, job_id, "done", result=result)
        _registrar_historico(db_path, job_id, "sucesso", {
            "total_fonte": result["total_fonte"],
            "total_ok": result["total_ok"],
            "nao_encontrados": len(result["nao_encontrados"]),
        })
    except Exception as e:
        logger.exception("job %s falhou", job_id)
        jobs.set_status(db_path, job_id, "error", error=str(e))
        _registrar_historico(db_path, job_id, "erro", {})
