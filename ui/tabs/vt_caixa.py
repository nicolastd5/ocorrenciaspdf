import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QVBoxLayout, QWidget
)

from vt_caixa_processador import ProcessadorVTCaixa
from ui import settings
from ui.widgets import DropZone, LogPanel, PrimaryButton, SectionCard


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
            proc = ProcessadorVTCaixa()

            def cb(pct, msg):
                if self._cancel:
                    raise _Cancelled()
                self.progress.emit(int(pct), msg)
                self.log.emit(msg)

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


class VTCaixaTab(QWidget):
    processed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonte = None
        self._xls = None
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        card1 = SectionCard(1, "Fonte Nautilus (PDF ou Excel)", self)
        self._dz_fonte = DropZone("Arraste o arquivo ou clique para selecionar",
                                    (".pdf", ".xlsx", ".xls"))
        self._lbl_fonte = QLabel("nenhum arquivo selecionado")
        self._lbl_fonte.setStyleSheet("color: #8b949e;")
        self._dz_fonte.files_selected.connect(lambda p: self._set_fonte(p[0]))
        card1.add(self._dz_fonte); card1.add(self._lbl_fonte)
        layout.addWidget(card1)

        card2 = SectionCard(2, "Excel cadastral", self)
        self._dz_xls = DropZone("Arraste o .xls/.xlsx ou clique", (".xlsx", ".xls"))
        self._lbl_xls = QLabel("nenhum arquivo selecionado")
        self._lbl_xls.setStyleSheet("color: #8b949e;")
        self._dz_xls.files_selected.connect(lambda p: self._set_xls(p[0]))
        card2.add(self._dz_xls); card2.add(self._lbl_xls)
        layout.addWidget(card2)

        card3 = SectionCard(3, "Opções", self)
        self._chk_ia = QCheckBox("Usar IA (Gemini)")
        card3.add(self._chk_ia)
        layout.addWidget(card3)

        row = QHBoxLayout(); row.addStretch()
        self._btn = PrimaryButton("▶ Processar")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button)
        row.addWidget(self._btn)
        wrap = QWidget(); wrap.setLayout(row)
        layout.addWidget(wrap)

        self._log = LogPanel(self)
        layout.addWidget(self._log, stretch=1)

    def _set_fonte(self, p):
        self._fonte = p
        self._lbl_fonte.setText(os.path.basename(p))
        self._refresh()

    def _set_xls(self, p):
        self._xls = p
        self._lbl_xls.setText(os.path.basename(p))
        self._refresh()

    def _refresh(self):
        self._btn.setEnabled(self._fonte is not None and self._xls is not None and self._thread is None)

    def _on_button(self):
        if self._thread:
            self._worker.cancel()
            self._log.append("cancelando...", level="warning")
            return
        self._start()

    def _start(self):
        cfg = settings.load()
        suggested_dir = cfg.get("last_dir") or os.path.dirname(self._xls)
        suggested = os.path.join(suggested_dir, Path(self._xls).stem + "_vtcaixa.csv")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar CSV como", suggested, "CSV (*.csv)")
        if not output:
            return
        settings.save({"last_dir": os.path.dirname(output)})

        usar_ia = self._chk_ia.isChecked()
        api_key = ""
        if usar_ia:
            from ui.server_config import fetch_gemini_key
            api_key = fetch_gemini_key()
            if not api_key:
                QMessageBox.warning(
                    self, "API key",
                    "IA marcada, mas não foi possível obter a chave do Gemini do servidor. "
                    "Verifique sua conexão e se sua licença está ativa."
                )
                return
        model = cfg.get("gemini_model", "gemini-2.5-flash")

        self._log.clear()
        self._log.append(f"iniciando ({Path(self._fonte).name} + {Path(self._xls).name})")
        for w in (self._dz_fonte, self._dz_xls, self._chk_ia):
            w.setEnabled(False)
        self._btn.set_mode("warning"); self._btn.setText("Cancelar")

        self._thread = QThread(self)
        self._worker = VTCaixaWorker(self._fonte, self._xls, output, usar_ia, api_key, model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda pct, _m: self._log.set_progress(pct, True))
        self._worker.log.connect(lambda m: self._log.append(m))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()

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
            self._mostrar_janela_ia(alertas)

        self._log.set_progress(0, False)
        self._emit_history(info)

    def _model_atual(self):
        from ui import settings
        return settings.load().get("gemini_model", "gemini-2.5-flash")

    def _mostrar_janela_ia(self, alertas):
        from PySide6.QtWidgets import (
            QDialog, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Relatório de Verificação IA")
        dlg.resize(620, 440)
        lay = QVBoxLayout(dlg)
        txt = QPlainTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setObjectName("log")
        txt.setPlainText("\n".join(alertas))
        lay.addWidget(txt)
        row = QHBoxLayout(); row.addStretch()
        b = QPushButton("Fechar"); b.clicked.connect(dlg.accept)
        row.addWidget(b)
        lay.addLayout(row)
        dlg.exec()

    def _on_error(self, msg, tb):
        self._log.append(msg, level="error")
        self._log.append(tb, level="error")
        self._log.set_progress(0, False)
        self._emit_history({"status": "error", "error": msg, "duration": 0.0})

    def _cleanup(self):
        self._thread = None; self._worker = None
        for w in (self._dz_fonte, self._dz_xls, self._chk_ia):
            w.setEnabled(True)
        self._btn.set_mode("primary"); self._btn.setText("▶ Processar")
        self._refresh()

    def _emit_history(self, info):
        self.processed.emit({
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
        })
