import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QMutex, QWaitCondition, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget
)

from ui import history, settings
from ui.widgets import DropZone, KpiStrip, KpiTile, LogPanel, Panel, PrimaryButton, SectionCard
from ui.widgets.conflict_dialog import ConflictDialog


# Resolvido sob demanda em OcorrenciasWorker.run — pdfplumber/openpyxl são
# pesados e só precisam carregar quando o usuário processa um arquivo.
# Testes podem injetar um fake atribuindo a este nome.
ProcessadorOcorrencias = None


def _resolver_processador():
    global ProcessadorOcorrencias
    if ProcessadorOcorrencias is None:
        from processador import ProcessadorOcorrencias as _P
        ProcessadorOcorrencias = _P
    return ProcessadorOcorrencias


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
            proc = _resolver_processador()()

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
        self._showing_result = False

        # ---- raiz rolável ----
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll.setWidget(page)

        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 22, 24)

        layout.addWidget(self._page_head(
            "Ocorrências",
            "Leia o PDF de jornada, reconcilie as varreduras e gere a planilha de saída."
        ))

        # ---- workspace em duas colunas ----
        split = QHBoxLayout(); split.setSpacing(16)

        # coluna esquerda: passos
        left = QVBoxLayout(); left.setSpacing(14)

        self._card_pdf = SectionCard(1, "PDF de jornada", self)
        self._dz_pdf = DropZone("Arraste o PDF de jornada", (".pdf",))
        self._dz_pdf.files_selected.connect(self._on_pdf_selected)
        self._dz_pdf.removed.connect(self._on_pdf_removed)
        self._card_pdf.add(self._dz_pdf)
        left.addWidget(self._card_pdf)

        self._card_xlsx = SectionCard(2, "Planilha de pedido", self)
        self._dz_xlsx = DropZone("Arraste o .xlsx do pedido", (".xlsx",))
        self._dz_xlsx.files_selected.connect(self._on_xlsx_selected)
        self._dz_xlsx.removed.connect(self._on_xlsx_removed)
        self._card_xlsx.add(self._dz_xlsx)
        left.addWidget(self._card_xlsx)

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
        left.addWidget(card_opt)
        left.addStretch()

        left_wrap = QWidget(); left_wrap.setLayout(left)
        left_wrap.setStyleSheet("background: transparent;")
        split.addWidget(left_wrap, stretch=5)

        # coluna direita: execução (resumo/KPIs + log)
        self._panel = Panel("Execução", self)
        self._btn = PrimaryButton("▶ Processar")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button_clicked)
        self._panel.add_header_widget(self._btn)

        # área de resumo que troca entre "pronto" e KPIs de resultado
        self._summary = QWidget()
        self._summary.setStyleSheet("background: transparent;")
        self._summary_lay = QVBoxLayout(self._summary)
        self._summary_lay.setContentsMargins(0, 0, 0, 0)
        self._summary_lay.setSpacing(12)
        self._panel.add(self._summary)
        self._render_prompt()

        self._log = LogPanel(self)
        self._panel.add(self._log, stretch=1)
        split.addWidget(self._panel, stretch=4)

        layout.addLayout(split)

    # ---------- cabeçalho ----------
    def _page_head(self, title, sub):
        w = QWidget(); w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(3)
        t = QLabel(title); t.setObjectName("pageTitle")
        s = QLabel(sub); s.setObjectName("pageSub"); s.setWordWrap(True)
        lay.addWidget(t); lay.addWidget(s)
        return w

    # ---------- resumo da coluna direita ----------
    def _clear_summary(self):
        while self._summary_lay.count():
            item = self._summary_lay.takeAt(0)
            wid = item.widget()
            if wid is not None:
                wid.deleteLater()

    def _render_prompt(self, ready: bool = False):
        self._showing_result = False
        self._clear_summary()
        box = QWidget(); box.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(box); bl.setAlignment(Qt.AlignCenter); bl.setSpacing(8)
        bl.setContentsMargins(0, 18, 0, 18)
        icon = QLabel("✓" if ready else "▶")
        icon.setAlignment(Qt.AlignCenter)
        cor = "#3fb950" if ready else "#8b949e"
        icon.setStyleSheet(f"color: {cor}; font-size: 22pt; background: transparent;")
        bl.addWidget(icon)
        t = QLabel("Pronto para processar" if ready else "Selecione os arquivos")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color: #f0f6fc; font-weight: 500; background: transparent;")
        bl.addWidget(t)
        s = QLabel("Clique em Processar para iniciar." if ready
                   else "Adicione o PDF de jornada e a planilha de pedido.")
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet("color: #8b949e; font-size: 9pt; background: transparent;")
        s.setWordWrap(True)
        bl.addWidget(s)
        self._summary_lay.addWidget(box)

    def _render_result(self, info):
        self._showing_result = True
        self._clear_summary()
        iv = info.get("info_verif", {})
        matched = info.get("matched", 0)
        total = info.get("total_pdf", 0)
        dur = info.get("duration", 0.0)
        conflitos = iv.get("conflitos_resolvidos", 0)
        if iv.get("ia_usada"):
            ia = "usada"
        elif iv.get("ia_fallback"):
            ia = "fallback"
        else:
            ia = "—"

        grid = QGridLayout(); grid.setSpacing(10)
        tiles = [
            KpiTile("Matches", f"{matched}/{total}", accent="ok"),
            KpiTile("Conflitos", str(conflitos), accent="warn" if conflitos else None),
            KpiTile("Duração", f"{dur:.1f}s", accent="accent"),
            KpiTile("IA", ia),
        ]
        for i, tile in enumerate(tiles):
            grid.addWidget(tile, i // 2, i % 2)
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;"); wrap.setLayout(grid)
        self._summary_lay.addWidget(wrap)

    def _modo_atual(self) -> str:
        btn = self._modo_group.checkedButton()
        return btn.property("modo") if btn else "unica"

    def _salvar_codigos(self):
        settings.save({"codigos_ocorrencias": self._ed_codigos.text()})

    def _restaurar_codigos(self):
        self._ed_codigos.setText(self.DEFAULT_CODIGOS)
        self._salvar_codigos()

    def _refresh_state(self):
        ready = self._pdf is not None and self._xlsx is not None
        self._btn.setEnabled(ready and self._thread is None)
        if self._thread is None and not self._showing_result:
            self._render_prompt(ready=ready)

    def _on_pdf_selected(self, paths):
        self._pdf = paths[0]
        self._dz_pdf.show_file(self._pdf)
        self._card_pdf.set_done(True)
        self._refresh_state()

    def _on_pdf_removed(self):
        self._pdf = None
        self._card_pdf.set_done(False)
        self._refresh_state()

    def _on_xlsx_selected(self, paths):
        self._xlsx = paths[0]
        self._dz_xlsx.show_file(self._xlsx)
        self._card_xlsx.set_done(True)
        self._refresh_state()

    def _on_xlsx_removed(self):
        self._xlsx = None
        self._card_xlsx.set_done(False)
        self._refresh_state()

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

        self._showing_result = False
        self._render_prompt(ready=True)
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
            self._render_result(info)
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
