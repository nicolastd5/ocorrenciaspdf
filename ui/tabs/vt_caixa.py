import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog

from ui import settings
from ui.tabs.processing_base import ProcessingTab
from ui.widgets import DropZone, KpiTile, SectionCard
from ui.widgets.text_dialog import show_text_dialog


# Resolvido sob demanda em VTCaixaWorker.run — pdfplumber/openpyxl/xlrd são
# pesados e só precisam carregar quando o usuário processa um arquivo.
# Testes podem injetar um fake atribuindo a este nome.
ProcessadorVTCaixa = None


def _resolver_processador():
    global ProcessadorVTCaixa
    if ProcessadorVTCaixa is None:
        from vt_caixa_processador import ProcessadorVTCaixa as _P
        ProcessadorVTCaixa = _P
    return ProcessadorVTCaixa


class _Cancelled(Exception):
    pass


class VTCaixaWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, fonte, xls, output, usar_ia, api_key, model):
        super().__init__()
        self.fonte, self.xls, self.output = fonte, xls, output
        self.usar_ia, self.api_key, self.model = usar_ia, api_key, model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        t0 = time.monotonic()
        try:
            proc = _resolver_processador()()

            def cb(pct, msg):
                if self._cancel:
                    raise _Cancelled()
                self.progress.emit(int(pct), msg)
                self.log.emit(msg)

            # Busca da chave aqui (thread do worker) para não travar a UI.
            if self.usar_ia and not self.api_key:
                from ui.server_config import fetch_gemini_key
                self.api_key = fetch_gemini_key()
                if not self.api_key:
                    self.log.emit("Não foi possível obter a chave do Gemini do servidor — "
                                  "processando sem verificação por IA.")
                    self.usar_ia = False

            result = proc.processar(self.fonte, self.xls, self.output,
                                    progress_cb=cb,
                                    usar_ia=self.usar_ia,
                                    api_key=self.api_key,
                                    model_id=self.model)
            self.finished.emit({
                "status": "ok",
                "output_path": self.output,
                "duration": time.monotonic() - t0,
                "total_ok": result.get("total_ok", 0),
                "total_pdf": result.get("total_pdf", 0),
                "total_fonte": result.get("total_fonte", result.get("total_pdf", 0)),
                "tipo_fonte": result.get("tipo_fonte", "PDF"),
                "nao_encontrados": list(result.get("nao_encontrados", [])),
                "avisos_csv": list(result.get("avisos_csv", [])),
                "alertas_ia": list(result.get("alertas_ia", [])),
            })
        except _Cancelled:
            self.finished.emit({"status": "cancelled", "duration": time.monotonic() - t0})
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}", traceback.format_exc())


class VTCaixaTab(ProcessingTab):
    TITLE = "VT-Caixa"
    SUBTITLE = "Processe a fonte Nautilus contra o Excel cadastral e gere o CSV de benefícios."
    EMPTY_HINT = "Adicione a fonte Nautilus e o Excel cadastral."

    def __init__(self, parent=None):
        self._fonte = None
        self._xls = None
        super().__init__(parent)

    # ---------- coluna esquerda ----------
    def _build_left(self, left):
        self._card1 = SectionCard(1, "Fonte Nautilus (PDF ou Excel)", self)
        self._dz_fonte = DropZone("Arraste a fonte Nautilus", (".pdf", ".xlsx", ".xls"))
        self._dz_fonte.files_selected.connect(lambda p: self._set_fonte(p[0]))
        self._dz_fonte.removed.connect(self._on_fonte_removed)
        self._card1.add(self._dz_fonte)
        left.addWidget(self._card1)

        self._card2 = SectionCard(2, "Excel cadastral", self)
        self._dz_xls = DropZone("Arraste o .xls/.xlsx cadastral", (".xlsx", ".xls"))
        self._dz_xls.files_selected.connect(lambda p: self._set_xls(p[0]))
        self._dz_xls.removed.connect(self._on_xls_removed)
        self._card2.add(self._dz_xls)
        left.addWidget(self._card2)

        card3 = SectionCard(3, "Opções", self, optional=True)
        self._chk_ia = QCheckBox("Usar IA (Gemini)")
        card3.add(self._chk_ia)
        left.addWidget(card3)

    # ---------- estado ----------
    def _is_ready(self):
        return self._fonte is not None and self._xls is not None

    def _set_inputs_enabled(self, enabled):
        for w in (self._dz_fonte, self._dz_xls, self._chk_ia):
            w.setEnabled(enabled)

    def _set_fonte(self, p):
        self._fonte = p
        self._dz_fonte.show_file(p)
        self._card1.set_done(True)
        self._refresh_state()

    def _on_fonte_removed(self):
        self._fonte = None
        self._card1.set_done(False)
        self._refresh_state()

    def _set_xls(self, p):
        self._xls = p
        self._dz_xls.show_file(p)
        self._card2.set_done(True)
        self._refresh_state()

    def _on_xls_removed(self):
        self._xls = None
        self._card2.set_done(False)
        self._refresh_state()

    # ---------- execução ----------
    def _create_worker(self):
        cfg = settings.load()
        suggested_dir = cfg.get("last_dir") or os.path.dirname(self._xls)
        suggested = os.path.join(suggested_dir, Path(self._xls).stem + "_vtcaixa.csv")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar CSV como", suggested, "CSV (*.csv)")
        if not output:
            return None
        settings.save({"last_dir": os.path.dirname(output)})

        usar_ia = self._chk_ia.isChecked()
        model = cfg.get("gemini_model", "gemini-2.5-flash")
        worker = VTCaixaWorker(self._fonte, self._xls, output, usar_ia, "", model)
        msg = f"iniciando ({Path(self._fonte).name} + {Path(self._xls).name})"
        return worker, msg

    def _render_result(self, info):
        ok = info.get("total_ok", 0)
        total = info.get("total_fonte", info.get("total_pdf", 0))
        dur = info.get("duration", 0.0)
        nao_enc = info.get("nao_encontrados", [])
        tile_sem_match = KpiTile("Sem match", str(len(nao_enc)),
                                 accent="warn" if nao_enc else None,
                                 clickable=bool(nao_enc))
        if nao_enc:
            tile_sem_match.setToolTip("Clique para ver as matrículas sem correspondência")
            tile_sem_match.clicked.connect(
                lambda itens=list(nao_enc): show_text_dialog(
                    self, "Matrículas sem correspondência",
                    "\n".join(f"• {x}" for x in itens)))
        tiles = [
            KpiTile("Processados", str(ok), accent="ok"),
            KpiTile("Na fonte", str(total), accent="accent"),
            tile_sem_match,
            KpiTile("Duração", f"{dur:.1f}s"),
        ]
        self._show_result_tiles(tiles, info)

    def _on_finished(self, info):
        s = info.get("status", "ok")
        if s != "ok":
            self._log.append("cancelado", level="warning")
            self._log.set_progress(0, False)
            self._emit_history(info)
            return

        ok = info.get("total_ok", 0)
        total = info.get("total_fonte", info.get("total_pdf", 0))
        tipo_fonte = info.get("tipo_fonte", "PDF")
        nao_enc = info.get("nao_encontrados", [])
        avisos_csv = info.get("avisos_csv", [])
        alertas = info.get("alertas_ia", [])

        self._log.append("─" * 40)
        self._log.append(f"{ok} registro(s) processado(s) com sucesso.", level="success")
        self._log.append(f"Total na fonte ({tipo_fonte}): {total}")

        if nao_enc:
            self._log.append(f"{len(nao_enc)} matrícula(s) sem correspondência no Excel:", level="warning")
            for item in nao_enc:
                self._log.append(f"   • {item}", level="warning")
        else:
            self._log.append("Todas as matrículas foram encontradas no Excel.", level="success")

        self._log.append(f"CSV salvo em: {info.get('output_path')}")

        if avisos_csv:
            self._log.append(
                f"{len(avisos_csv)} campo(s) com caracteres fora do latin-1 (substituídos por ?):",
                level="warning")
            for av in avisos_csv:
                self._log.append(f"   • {av}", level="warning")

        if alertas:
            self._log.append(f"Relatório IA ({self._model_atual()}):")
            for linha in alertas:
                ll = linha.lower()
                eh_negacao = "nenhuma" in ll or "tudo ok" in ll or "sem inconsist" in ll
                nivel = "error" if (not eh_negacao and any(
                    k in ll for k in ("erro", "inconsistência", "alerta", "vazio", "zerado"))) else "info"
                self._log.append(f"   {linha}", level=nivel)
            show_text_dialog(self, "Relatório de Verificação IA", "\n".join(alertas))

        self._render_result(info)
        self._log.set_progress(0, False)
        self._emit_history(info)

    def _model_atual(self):
        return settings.load().get("gemini_model", "gemini-2.5-flash")

    def _history_entry(self, info):
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tipo": "vt_caixa",
            "inputs": [self._fonte, self._xls],
            "output": info.get("output_path"),
            "status": info.get("status", "error"),
            "duration_seconds": round(info.get("duration", 0.0), 2),
            "rows_processed": info.get("total_ok"),
            "error": info.get("error"),
            "nao_encontrados": info.get("nao_encontrados", []),
            "avisos_csv": info.get("avisos_csv", []),
            "alertas_ia": info.get("alertas_ia", []),
        }
