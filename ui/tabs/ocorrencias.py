import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from ui import settings
from ui.tabs.processing_base import ProcessingTab
from ui.widgets import DropZone, KpiTile, SectionCard
from ui.widgets.conflict_dialog import ConflictDialog
from ui.widgets.text_dialog import show_text_dialog


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

            # A chave do Gemini vem do servidor; buscar aqui (na thread do
            # worker) evita travar a UI quando o servidor está lento.
            if self.modo == "ia" and not self.api_key:
                from ui.server_config import fetch_gemini_key
                self.api_key = fetch_gemini_key()
                if not self.api_key:
                    self.log.emit("Não foi possível obter a chave do Gemini do servidor — "
                                  "a verificação por IA seguirá em fallback (V1+V2).")

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
                "nao_encontrados": result.get("nao_encontrados", []),
                "info_verif": info_verif,
            })
        except _Cancelled:
            self.finished.emit({"status": "cancelled", "duration": time.monotonic() - t0})
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}", traceback.format_exc())


class OcorrenciasTab(ProcessingTab):
    DEFAULT_CODIGOS = "FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13"

    TITLE = "Ocorrências"
    SUBTITLE = "Leia o PDF de jornada, reconcilie as varreduras e gere a planilha de saída."
    EMPTY_HINT = "Adicione o PDF e a planilha de pedido."

    def __init__(self, parent=None):
        self._pdf = None
        self._xlsx = None
        super().__init__(parent)

    # ---------- coluna esquerda ----------
    def _build_left(self, left):
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
        ajuda.setObjectName("helpText")
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

    # ---------- estado ----------
    def _is_ready(self):
        return self._pdf is not None and self._xlsx is not None

    def _set_inputs_enabled(self, enabled):
        self._dz_pdf.setEnabled(enabled)
        self._dz_xlsx.setEnabled(enabled)
        self._ed_codigos.setEnabled(enabled)
        for b in self._modo_group.buttons():
            b.setEnabled(enabled)

    def _modo_atual(self) -> str:
        btn = self._modo_group.checkedButton()
        return btn.property("modo") if btn else "unica"

    def _salvar_codigos(self):
        settings.save({"codigos_ocorrencias": self._ed_codigos.text()})

    def _restaurar_codigos(self):
        self._ed_codigos.setText(self.DEFAULT_CODIGOS)
        self._salvar_codigos()

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

    # ---------- execução ----------
    def _create_worker(self):
        codigos = [c.strip() for c in self._ed_codigos.text().split(",") if c.strip()]
        if not codigos:
            QMessageBox.warning(self, "Códigos", "Informe pelo menos um código de ocorrência.")
            return None
        modo = self._modo_atual()
        cfg = settings.load()
        gemini_model = cfg.get("gemini_model", "gemini-2.5-flash")

        default_dir = cfg.get("last_dir") or os.path.dirname(self._xlsx)
        suggested = os.path.join(default_dir, Path(self._xlsx).stem + "_out.xlsx")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar planilha como",
                                                 suggested, "Excel (*.xlsx)")
        if not output:
            return None
        settings.save({"last_dir": os.path.dirname(output)})

        worker = OcorrenciasWorker(self._pdf, self._xlsx, output, codigos,
                                   modo, "", gemini_model)
        msg = f"iniciando [{modo}] ({Path(self._pdf).name} → {Path(output).name})"
        return worker, msg

    def _connect_worker(self, worker):
        worker.conflitos_detectados.connect(self._on_conflitos)

    def _on_conflitos(self, conflitos):
        dlg = ConflictDialog(conflitos, self)
        dlg.exec()
        self._worker.fornecer_resolucao(dlg.resultado())

    def _render_result(self, info):
        iv = info.get("info_verif", {})
        matched = info.get("matched", 0)
        total = info.get("total_pdf", 0)
        dur = info.get("duration", 0.0)
        conflitos = iv.get("conflitos_resolvidos", 0)
        nao_enc = info.get("nao_encontrados", [])
        n_falta = len(nao_enc)
        if iv.get("ia_usada"):
            ia = "usada"
        elif iv.get("ia_fallback"):
            ia = "fallback"
        else:
            ia = "—"
        tile_falta = KpiTile(
            "Não localizados", str(n_falta),
            sub="clique para ver" if n_falta else "",
            accent="warn" if n_falta else None,
            clickable=bool(n_falta))
        if n_falta:
            tile_falta.clicked.connect(lambda: self._show_nao_encontrados(nao_enc))
        tiles = [
            KpiTile("Localizados", f"{matched}/{total}", accent="ok"),
            tile_falta,
            KpiTile("Conflitos", str(conflitos), accent="warn" if conflitos else None),
            KpiTile("Duração", f"{dur:.1f}s", accent="accent"),
            KpiTile("IA", ia),
        ]
        self._show_result_tiles(tiles, info)

    def _show_nao_encontrados(self, nao_enc):
        linhas = [f"{len(nao_enc)} pessoa(s) não localizada(s) na planilha:\n"]
        for item in nao_enc:
            linhas.append(f"RE {item['re']} — {item['nome']}\n    motivo: {item['motivo']}")
        show_text_dialog(self, "Não localizados", "\n".join(linhas))

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
                f"concluído em {duration:.1f}s — {info.get('matched',0)}/{info.get('total_pdf',0)} localizados{extra}",
                level="success")
            nao_enc = info.get("nao_encontrados", [])
            if nao_enc:
                self._log.append(
                    f"{len(nao_enc)} não localizado(s):", level="warning")
                for item in nao_enc:
                    self._log.append(
                        f"  RE {item['re']} — {item['nome']} ({item['motivo']})",
                        level="warning")
            self._render_result(info)
        elif status == "cancelled":
            self._log.append("cancelado", level="warning")
        self._log.set_progress(100 if status == "ok" else 0, visible=False)
        self._emit_history(info)

    def _history_entry(self, info):
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tipo": "ocorrencias",
            "inputs": [self._pdf, self._xlsx],
            "output": info.get("output_path"),
            "status": info.get("status", "error"),
            "duration_seconds": round(info.get("duration", 0.0), 2),
            "rows_processed": info.get("matched"),
            "nao_encontrados": [
                f"RE {x['re']} — {x['nome']} ({x['motivo']})"
                for x in info.get("nao_encontrados", [])
            ],
            "error": info.get("error"),
        }
