import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QMutex, QWaitCondition, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from processador import ProcessadorOcorrencias
from ui import history, settings
from ui.widgets import DropZone, LogPanel, PrimaryButton, SectionCard
from ui.widgets.conflict_dialog import ConflictDialog


class _Cancelled(Exception):
    pass


class OcorrenciasWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    conflitos_detectados = Signal(list)
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, pdf_path, xlsx_path, output_path, codigos,
                 modo, api_key, gemini_model):
        super().__init__()
        self.pdf_path = pdf_path
        self.xlsx_path = xlsx_path
        self.output_path = output_path
        self.codigos = codigos
        self.modo = modo
        self.api_key = api_key
        self.gemini_model = gemini_model
        self._cancel = False
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._resolucao = None
        self._resolucao_pronta = False

    def cancel(self):
        self._cancel = True

    def fornecer_resolucao(self, escolhas):
        self._mutex.lock()
        self._resolucao = escolhas
        self._resolucao_pronta = True
        self._cond.wakeAll()
        self._mutex.unlock()

    def _esperar_resolucao(self):
        self._mutex.lock()
        while not self._resolucao_pronta:
            self._cond.wait(self._mutex)
        escolhas = self._resolucao
        self._mutex.unlock()
        return escolhas

    def run(self):
        t0 = time.monotonic()
        try:
            proc = ProcessadorOcorrencias()

            def cb(pct, msg):
                if self._cancel:
                    raise _Cancelled()
                self.progress.emit(int(pct), msg)
                self.log.emit(msg)

            info_verif = {"modo": self.modo, "ia_usada": False, "ia_fallback": False}
            dados_externos = None

            if self.modo in ("dupla", "ia"):
                cb(5, "Lendo PDF (varredura 1)...")
                v1 = proc.extrair_ocorrencias(self.pdf_path, self.codigos)
                cb(20, "Varredura 2 (texto/regex)...")
                v2 = proc.extrair_ocorrencias_texto(self.pdf_path, self.codigos)
                camadas = [v1] if not v2 else [v1, v2]

                if self.modo == "ia":
                    cb(35, "Verificando com IA (Gemini Vision)...")
                    v3 = proc.verificar_com_ia(self.pdf_path, self.codigos,
                                               self.api_key, self.gemini_model)
                    if v3 is not None:
                        camadas.append(v3)
                        info_verif["ia_usada"] = True
                    else:
                        info_verif["ia_fallback"] = True
                        self.log.emit("IA indisponível — seguindo com V1+V2 (fallback).")

                cb(45, "Reconciliando resultados...")
                rec = proc.reconciliar(camadas, self.codigos)
                concordantes = rec["concordantes"]
                conflitos = rec["conflitos"]

                if conflitos:
                    self.conflitos_detectados.emit(conflitos)
                    escolhas = self._esperar_resolucao()
                    if escolhas is None:
                        self.finished.emit({"status": "cancelled",
                                            "duration": time.monotonic() - t0})
                        return
                    for re_val, cod, val in escolhas:
                        if re_val not in concordantes:
                            nome = next((c.get(re_val, {}).get("nome", "")
                                         for c in camadas if re_val in c), "")
                            concordantes[re_val] = {"nome": nome, "ocorrencias": {}}
                        concordantes[re_val]["ocorrencias"][cod] = val

                dados_externos = concordantes
                info_verif["concordantes"] = len(concordantes)
                info_verif["conflitos_resolvidos"] = len(conflitos)

            result = proc.processar(self.pdf_path, self.xlsx_path, self.output_path,
                                    self.codigos, progress_cb=cb,
                                    dados_externos=dados_externos)
            self.finished.emit({
                "status": "ok",
                "output_path": self.output_path,
                "duration": time.monotonic() - t0,
                "matched": result.get("matched", 0),
                "total_pdf": result.get("total_pdf", 0),
                "info_verif": info_verif,
            })
        except _Cancelled:
            self.finished.emit({"status": "cancelled", "duration": time.monotonic() - t0})
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}", traceback.format_exc())


class OcorrenciasTab(QWidget):
    DEFAULT_CODIGOS = "FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13"
    processed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf = None
        self._xlsx = None
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        card_pdf = SectionCard(1, "PDF de jornada", self)
        self._dz_pdf = DropZone("Arraste o PDF ou clique para selecionar", (".pdf",))
        self._lbl_pdf = QLabel("nenhum arquivo selecionado", self)
        self._lbl_pdf.setStyleSheet("color: #8b949e;")
        self._dz_pdf.files_selected.connect(self._on_pdf_selected)
        card_pdf.add(self._dz_pdf); card_pdf.add(self._lbl_pdf)
        layout.addWidget(card_pdf)

        card_xlsx = SectionCard(2, "Planilha de pedido", self)
        self._dz_xlsx = DropZone("Arraste o .xlsx ou clique para selecionar", (".xlsx",))
        self._lbl_xlsx = QLabel("nenhum arquivo selecionado", self)
        self._lbl_xlsx.setStyleSheet("color: #8b949e;")
        self._dz_xlsx.files_selected.connect(self._on_xlsx_selected)
        card_xlsx.add(self._dz_xlsx); card_xlsx.add(self._lbl_xlsx)
        layout.addWidget(card_xlsx)

        card_opt = SectionCard(3, "Opções", self)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Códigos:"))
        self._ed_codigos = QLineEdit(settings.load().get("codigos_ocorrencias", self.DEFAULT_CODIGOS))
        self._ed_codigos.editingFinished.connect(self._salvar_codigos)
        row1.addWidget(self._ed_codigos)
        wrap1 = QWidget(); wrap1.setLayout(row1)
        card_opt.add(wrap1)
        ajuda = QLabel(
            "Digite os códigos de ocorrência que devem ser buscados, separados por vírgula "
            "(ex.: FA, AT, 14). Os códigos ficam salvos para a próxima vez. Para restaurar o "
            "padrão, use o botão abaixo."
        )
        ajuda.setWordWrap(True)
        ajuda.setStyleSheet("color: #8b949e; font-size: 9pt;")
        card_opt.add(ajuda)
        btn_padrao = QPushButton("Restaurar códigos padrão")
        btn_padrao.clicked.connect(self._restaurar_codigos)
        card_opt.add(btn_padrao)
        self._modo_group = QButtonGroup(self)
        modos = [("unica", "Varredura única"),
                 ("dupla", "Dupla varredura (V1 tabelas + V2 texto)"),
                 ("ia", "Dupla + IA (Gemini)")]
        modo_row = QVBoxLayout()
        modo_row.addWidget(QLabel("Verificação:"))
        for i, (val, label) in enumerate(modos):
            rb = QRadioButton(label)
            rb.setProperty("modo", val)
            if val == "unica":
                rb.setChecked(True)
            self._modo_group.addButton(rb, i)
            modo_row.addWidget(rb)
        wrap_modo = QWidget(); wrap_modo.setLayout(modo_row)
        card_opt.add(wrap_modo)
        layout.addWidget(card_opt)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        self._btn = PrimaryButton("▶ Processar")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button_clicked)
        btn_row.addWidget(self._btn)
        btn_wrap = QWidget(); btn_wrap.setLayout(btn_row)
        layout.addWidget(btn_wrap)

        self._log = LogPanel(self)
        layout.addWidget(self._log, stretch=1)

    def _modo_atual(self) -> str:
        btn = self._modo_group.checkedButton()
        return btn.property("modo") if btn else "unica"

    def _salvar_codigos(self):
        settings.save({"codigos_ocorrencias": self._ed_codigos.text()})

    def _restaurar_codigos(self):
        self._ed_codigos.setText(self.DEFAULT_CODIGOS)
        self._salvar_codigos()

    def _refresh_state(self):
        self._btn.setEnabled(self._pdf is not None and self._xlsx is not None and self._thread is None)

    def _on_pdf_selected(self, paths):
        self._pdf = paths[0]; self._lbl_pdf.setText(os.path.basename(self._pdf)); self._refresh_state()

    def _on_xlsx_selected(self, paths):
        self._xlsx = paths[0]; self._lbl_xlsx.setText(os.path.basename(self._xlsx)); self._refresh_state()

    def _on_button_clicked(self):
        if self._thread is not None:
            self._worker.cancel()
            self._log.append("cancelando...", level="warning")
            return
        self._start()

    def _start(self):
        codigos = [c.strip() for c in self._ed_codigos.text().split(",") if c.strip()]
        if not codigos:
            QMessageBox.warning(self, "Códigos", "Informe pelo menos um código de ocorrência.")
            return
        modo = self._modo_atual()
        cfg = settings.load()
        gemini_model = cfg.get("gemini_model", "gemini-2.5-flash")
        api_key = ""
        if modo == "ia":
            from ui.server_config import fetch_gemini_key
            api_key = fetch_gemini_key()
            if not api_key:
                QMessageBox.warning(
                    self, "API key",
                    "Modo 'Dupla + IA' precisa da chave do Gemini, que é obtida do servidor. "
                    "Verifique sua conexão e se sua licença está ativa."
                )
                return

        default_dir = cfg.get("last_dir") or os.path.dirname(self._xlsx)
        suggested = os.path.join(default_dir, Path(self._xlsx).stem + "_out.xlsx")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar planilha como",
                                                 suggested, "Excel (*.xlsx)")
        if not output:
            return
        settings.save({"last_dir": os.path.dirname(output)})

        self._log.clear()
        self._log.append(f"iniciando [{modo}] ({Path(self._pdf).name} → {Path(output).name})")
        self._dz_pdf.setEnabled(False); self._dz_xlsx.setEnabled(False)
        self._ed_codigos.setEnabled(False)
        for b in self._modo_group.buttons():
            b.setEnabled(False)
        self._btn.set_mode("warning"); self._btn.setText("Cancelar")

        self._thread = QThread(self)
        self._worker = OcorrenciasWorker(self._pdf, self._xlsx, output, codigos,
                                         modo, api_key, gemini_model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(lambda m: self._log.append(m))
        self._worker.conflitos_detectados.connect(self._on_conflitos)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_progress(self, pct, msg):
        self._log.set_progress(pct, visible=True)

    def _on_conflitos(self, conflitos):
        dlg = ConflictDialog(conflitos, self)
        dlg.exec()
        self._worker.fornecer_resolucao(dlg.resultado())

    def _on_finished(self, info):
        status = info.get("status", "ok")
        duration = info.get("duration", 0.0)
        if status == "ok":
            iv = info.get("info_verif", {})
            extra = ""
            if iv.get("ia_fallback"):
                extra = " (IA em fallback)"
            elif iv.get("ia_usada"):
                extra = " (IA usada)"
            self._log.append(
                f"concluído em {duration:.1f}s — {info.get('matched',0)}/{info.get('total_pdf',0)} matches{extra}",
                level="success")
        elif status == "cancelled":
            self._log.append("cancelado", level="warning")
        self._log.set_progress(100 if status == "ok" else 0, visible=False)
        self._emit_history(info)

    def _on_error(self, msg, tb):
        self._log.append(msg, level="error")
        self._log.append(tb, level="error")
        self._log.set_progress(0, visible=False)
        self._emit_history({"status": "error", "error": msg, "duration": 0.0})

    def _cleanup_thread(self):
        self._thread = None; self._worker = None
        self._dz_pdf.setEnabled(True); self._dz_xlsx.setEnabled(True)
        self._ed_codigos.setEnabled(True)
        for b in self._modo_group.buttons():
            b.setEnabled(True)
        self._btn.set_mode("primary"); self._btn.setText("▶ Processar")
        self._refresh_state()

    def _emit_history(self, info):
        self.processed.emit({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tipo": "ocorrencias",
            "inputs": [self._pdf, self._xlsx],
            "output": info.get("output_path"),
            "status": info.get("status", "error"),
            "duration_seconds": round(info.get("duration", 0.0), 2),
            "rows_processed": info.get("matched"),
            "error": info.get("error"),
        })
