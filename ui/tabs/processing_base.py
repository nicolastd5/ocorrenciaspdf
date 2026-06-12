"""Esqueleto comum das telas de processamento (Ocorrências e VT-Caixa).

Concentra o que era duplicado nas duas abas: página rolável com cabeçalho,
split esquerda (passos) / direita (painel Execução com botão, resumo e log),
fiação de QThread+worker, troca Processar↔Cancelar, prompt/resultado no
resumo e emissão do histórico.

Subclasses definem:
  TITLE / SUBTITLE / EMPTY_HINT — textos da página e do prompt
  _build_left(layout)          — cards da coluna esquerda
  _is_ready() -> bool          — pré-condições para habilitar Processar
  _set_inputs_enabled(bool)    — trava/destrava entradas durante execução
  _create_worker()             — retorna (worker, msg_inicial) ou None p/ abortar
  _connect_worker(worker)      — sinais específicos (opcional)
  _on_finished(info)           — tratamento do resultado
  _history_entry(info) -> dict — entrada de histórico
"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from ui import icons
from ui.utils import open_path
from ui.widgets import LogPanel, Panel, PrimaryButton


class ProcessingTab(QWidget):
    processed = Signal(dict)

    TITLE = ""
    SUBTITLE = ""
    READY_TEXT = "Pronto para processar"
    EMPTY_TEXT = "Selecione os arquivos"
    READY_HINT = "Clique em Processar para iniciar."
    EMPTY_HINT = ""

    def __init__(self, parent=None):
        super().__init__(parent)
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
        layout.setSpacing(18)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.addWidget(self._page_head(self.TITLE, self.SUBTITLE))

        # ---- workspace em duas colunas ----
        split = QHBoxLayout(); split.setSpacing(20)

        left = QVBoxLayout(); left.setSpacing(16)
        self._build_left(left)
        left.addStretch()
        left_wrap = QWidget(); left_wrap.setLayout(left)
        left_wrap.setStyleSheet("background: transparent;")
        split.addWidget(left_wrap, stretch=5)

        # coluna direita: execução (resumo/KPIs + log)
        self._panel = Panel("Execução", self)
        self._panel.setMinimumWidth(380)
        self._btn = PrimaryButton("Processar")
        self._btn.setIcon(icons.icon("play", "#ffffff", 14))
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button_clicked)
        self._panel.add_header_widget(self._btn)

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

    # ---------- hooks (subclasses) ----------
    def _build_left(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def _is_ready(self) -> bool:
        raise NotImplementedError

    def _set_inputs_enabled(self, enabled: bool) -> None:
        raise NotImplementedError

    def _create_worker(self):
        raise NotImplementedError

    def _connect_worker(self, worker) -> None:
        pass

    def _on_finished(self, info: dict) -> None:
        raise NotImplementedError

    def _history_entry(self, info: dict) -> dict:
        raise NotImplementedError

    # ---------- cabeçalho ----------
    @staticmethod
    def _page_head(title, sub):
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
        icon = icons.IconLabel("check" if ready else "play",
                               "ok_text" if ready else "fg_dim", 28)
        icon.setAlignment(Qt.AlignCenter)
        bl.addWidget(icon)
        t = QLabel(self.READY_TEXT if ready else self.EMPTY_TEXT)
        t.setObjectName("promptTitle")
        t.setAlignment(Qt.AlignCenter)
        bl.addWidget(t)
        s = QLabel(self.READY_HINT if ready else self.EMPTY_HINT)
        s.setObjectName("promptSub")
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        # Labels com wordWrap subestimam a própria altura em layouts
        # aninhados; reserva 2 linhas para o hint não ser cortado.
        s.setMinimumHeight(s.fontMetrics().lineSpacing() * 2 + 4)
        bl.addWidget(s)
        self._summary_lay.addWidget(box)

    def _show_result_tiles(self, tiles: list, info: dict):
        """Mostra a grade de KPIs do resultado + atalhos para abrir a saída."""
        self._showing_result = True
        self._clear_summary()
        grid = QGridLayout(); grid.setSpacing(10)
        for i, tile in enumerate(tiles):
            grid.addWidget(tile, i // 2, i % 2)
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;"); wrap.setLayout(grid)
        self._summary_lay.addWidget(wrap)

        out = info.get("output_path")
        if out and Path(out).is_file():
            row = QHBoxLayout(); row.setSpacing(8)
            b_open = QPushButton("Abrir saída")
            b_open.clicked.connect(lambda _=False, p=out: open_path(p))
            b_dir = QPushButton("Abrir pasta")
            b_dir.clicked.connect(lambda _=False, p=os.path.dirname(out): open_path(p))
            row.addWidget(b_open); row.addWidget(b_dir); row.addStretch()
            w = QWidget(); w.setStyleSheet("background: transparent;"); w.setLayout(row)
            self._summary_lay.addWidget(w)

    # ---------- estado / execução ----------
    def _refresh_state(self):
        ready = self._is_ready()
        self._btn.setEnabled(ready and self._thread is None)
        if self._thread is None and not self._showing_result:
            self._render_prompt(ready=ready)

    def _on_button_clicked(self):
        if self._thread is not None:
            self._worker.cancel()
            self._log.append("cancelando...", level="warning")
            return
        self._start()

    def _start(self):
        created = self._create_worker()
        if created is None:
            return
        worker, start_msg = created

        self._showing_result = False
        self._render_prompt(ready=True)
        self._log.clear()
        if start_msg:
            self._log.append(start_msg)
        self._set_inputs_enabled(False)
        self._btn.set_mode("warning")
        self._btn.setText("Cancelar")
        self._btn.setIcon(icons.icon("x", "#ffffff", 14))

        self._thread = QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._log.append)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.finished.connect(self._thread.quit)
        worker.error.connect(self._thread.quit)
        self._connect_worker(worker)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_progress(self, pct, _msg):
        self._log.set_progress(pct, visible=True)

    def _on_error(self, msg, tb):
        self._log.append(msg, level="error")
        self._log.append(tb, level="error")
        self._log.set_progress(0, visible=False)
        self._emit_history({"status": "error", "error": msg, "duration": 0.0})

    def _cleanup_thread(self):
        self._thread = None; self._worker = None
        self._set_inputs_enabled(True)
        self._btn.set_mode("primary")
        self._btn.setText("Processar")
        self._btn.setIcon(icons.icon("play", "#ffffff", 14))
        self._refresh_state()

    def _emit_history(self, info: dict):
        self.processed.emit(self._history_entry(info))
