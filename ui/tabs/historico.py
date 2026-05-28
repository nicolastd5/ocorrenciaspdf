import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QMenu, QMessageBox, QPushButton,
    QTableView, QVBoxLayout, QWidget
)

from ui import history


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
        layout.setContentsMargins(16, 16, 16, 16)

        bar = QHBoxLayout()
        bar.addStretch()
        self._btn_reload = QPushButton("Atualizar")
        self._btn_clear = QPushButton("Limpar histórico")
        self._btn_reload.clicked.connect(self._model.reload)
        self._btn_clear.clicked.connect(self._on_clear)
        bar.addWidget(self._btn_reload); bar.addWidget(self._btn_clear)
        wrap = QWidget(); wrap.setLayout(bar)
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

    def refresh(self):
        self._model.reload()

    def _on_clear(self):
        if QMessageBox.question(self, "Limpar histórico",
                                "Tem certeza? Esta ação não pode ser desfeita.") == QMessageBox.Yes:
            history.clear()
            self._model.reload()

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
        menu.addAction(a_open); menu.addAction(a_folder); menu.addSeparator(); menu.addAction(a_remove)
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _remove(self, row):
        actual = len(history.load()) - 1 - row  # lista é mostrada invertida
        history.remove(actual)
        self._model.reload()

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
