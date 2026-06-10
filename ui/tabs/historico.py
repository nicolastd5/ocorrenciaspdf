import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMenu, QMessageBox, QPushButton,
    QTableView, QVBoxLayout, QWidget
)

from ui import history
from ui.widgets import KpiStrip, KpiTile


COLUMNS = ["Data/hora", "Tipo", "Entrada", "Saída", "Status", "Duração"]


class _HistoryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = history.load()

    def reload(self):
        self.beginResetModel()
        self._rows = history.load()
        self.endResetModel()

    def entry_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[-(row + 1)]  # mais recente primeiro
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entry_at(index.row())
        if entry is None:
            return None
        col = index.column()
        if role == Qt.DisplayRole:
            inputs = ", ".join(os.path.basename(p) for p in entry.get("inputs", []) if p)
            return {
                0: (entry.get("timestamp", "") or "").replace("T", " "),
                1: entry.get("tipo", ""),
                2: inputs,
                3: os.path.basename(entry.get("output") or ""),
                4: entry.get("status", ""),
                5: f'{entry.get("duration_seconds", 0)}s',
            }.get(col)
        if role == Qt.ForegroundRole and col == 4:
            s = entry.get("status")
            return {
                "ok": QColor("#1f883d"),
                "error": QColor("#cf222e"),
                "cancelled": QColor("#9a6700"),
            }.get(s)
        return None


class HistoricoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = _HistoryModel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 22, 24)
        layout.setSpacing(16)

        head = QVBoxLayout(); head.setSpacing(3)
        t = QLabel("Histórico"); t.setObjectName("pageTitle")
        s = QLabel("Processamentos recentes. Clique duas vezes para abrir a saída.")
        s.setObjectName("pageSub")
        head.addWidget(t); head.addWidget(s)
        head_wrap = QWidget(); head_wrap.setStyleSheet("background: transparent;"); head_wrap.setLayout(head)
        layout.addWidget(head_wrap)

        # faixa de estatísticas
        self._strip = KpiStrip(self)
        self._k_total = KpiTile("Processamentos", "0", accent="accent")
        self._k_ok = KpiTile("Concluídos", "0", accent="ok")
        self._k_taxa = KpiTile("Taxa de sucesso", "—")
        self._k_ultima = KpiTile("Última execução", "—")
        for k in (self._k_total, self._k_ok, self._k_taxa, self._k_ultima):
            self._strip.add(k)
        layout.addWidget(self._strip)

        bar = QHBoxLayout()
        bar.addStretch()
        self._btn_reload = QPushButton("Atualizar")
        self._btn_clear = QPushButton("Limpar histórico")
        self._btn_reload.clicked.connect(self.refresh)
        self._btn_clear.clicked.connect(self._on_clear)
        bar.addWidget(self._btn_reload); bar.addWidget(self._btn_clear)
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;"); wrap.setLayout(bar)
        layout.addWidget(wrap)

        self._view = QTableView(self)
        self._view.setModel(self._model)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._view.verticalHeader().setVisible(False)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.setEditTriggers(QTableView.NoEditTriggers)
        self._view.doubleClicked.connect(self._open_output)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._view, stretch=1)
        self._update_stats()

    def refresh(self):
        self._model.reload()
        self._update_stats()

    def _update_stats(self):
        rows = history.load()
        total = len(rows)
        ok = sum(1 for r in rows if r.get("status") == "ok")
        taxa = f"{round(ok / total * 100)}%" if total else "—"
        ultima = "—"
        if rows:
            ts = rows[-1].get("timestamp", "") or ""
            ultima = ts.replace("T", " ")[5:16] if len(ts) >= 16 else ts.replace("T", " ")
        self._k_total.set_value(str(total))
        self._k_ok.set_value(str(ok))
        self._k_taxa.set_value(taxa)
        self._k_ultima.set_value(ultima)

    def _on_clear(self):
        if QMessageBox.question(self, "Limpar histórico",
                                "Tem certeza? Esta ação não pode ser desfeita.") == QMessageBox.Yes:
            history.clear()
            self.refresh()

    def _open_output(self, index):
        entry = self._model.entry_at(index.row())
        if not entry:
            return
        out = entry.get("output")
        if out and Path(out).is_file():
            self._open_path(out)

    def _show_context_menu(self, pos):
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            return
        entry = self._model.entry_at(idx.row())
        if entry is None:
            return
        menu = QMenu(self)
        a_open = QAction("Abrir saída", self)
        a_folder = QAction("Abrir pasta da saída", self)
        a_remove = QAction("Remover do histórico", self)
        a_open.triggered.connect(lambda: self._open_output(idx))
        a_folder.triggered.connect(lambda: self._open_folder(entry.get("output")))
        a_remove.triggered.connect(lambda: self._remove(idx.row()))
        menu.addAction(a_open); menu.addAction(a_folder)
        # Detalhes (não-encontrados / avisos / alertas IA) — só quando houver
        if entry.get("nao_encontrados") or entry.get("avisos_csv") or entry.get("alertas_ia"):
            a_det = QAction("Ver detalhes", self)
            a_det.triggered.connect(lambda: self._ver_detalhes(entry))
            menu.addAction(a_det)
        menu.addSeparator(); menu.addAction(a_remove)
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _ver_detalhes(self, entry):
        from PySide6.QtWidgets import (
            QDialog, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout
        )
        linhas = []
        nao_enc = entry.get("nao_encontrados") or []
        avisos = entry.get("avisos_csv") or []
        alertas = entry.get("alertas_ia") or []
        if nao_enc:
            linhas.append(f"Matrículas sem correspondência ({len(nao_enc)}):")
            linhas += [f"  • {x}" for x in nao_enc]
            linhas.append("")
        if avisos:
            linhas.append(f"Avisos de CSV ({len(avisos)}):")
            linhas += [f"  • {x}" for x in avisos]
            linhas.append("")
        if alertas:
            linhas.append("Relatório IA:")
            linhas += [f"  {x}" for x in alertas]
        dlg = QDialog(self)
        dlg.setWindowTitle("Detalhes do processamento")
        dlg.resize(620, 440)
        lay = QVBoxLayout(dlg)
        txt = QPlainTextEdit(dlg); txt.setReadOnly(True); txt.setObjectName("log")
        txt.setPlainText("\n".join(linhas))
        lay.addWidget(txt)
        row = QHBoxLayout(); row.addStretch()
        b = QPushButton("Fechar"); b.clicked.connect(dlg.accept); row.addWidget(b)
        lay.addLayout(row)
        dlg.exec()

    def _remove(self, row):
        actual = len(history.load()) - 1 - row  # lista é mostrada invertida
        history.remove(actual)
        self.refresh()

    def _open_folder(self, out):
        if not out:
            return
        d = os.path.dirname(out)
        if d and os.path.isdir(d):
            self._open_path(d)

    def _open_path(self, p: str):
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
