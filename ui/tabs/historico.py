import csv
import os
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget
)

from ui import history, theme
from ui.utils import open_path
from ui.widgets import KpiStrip, KpiTile
from ui.widgets.text_dialog import show_text_dialog


COLUMNS = ["Data/hora", "Tipo", "Entrada", "Saída", "Status", "Duração"]

_STATUS_TOKEN = {"ok": "ok_text", "error": "err_text", "cancelled": "warn_text"}


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
            key = _STATUS_TOKEN.get(entry.get("status"))
            return QColor(theme.token(key)) if key else None
        return None


class _HistoryFilterProxy(QSortFilterProxyModel):
    """Filtra por texto livre (arquivos/tipo/data) e por status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search = ""
        self._status = ""

    def set_filters(self, search: str, status: str) -> None:
        self._search = search.lower().strip()
        self._status = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        entry = self.sourceModel().entry_at(source_row)
        if entry is None:
            return False
        if self._status and entry.get("status") != self._status:
            return False
        if self._search:
            campos = [
                entry.get("timestamp", "") or "",
                entry.get("tipo", "") or "",
                os.path.basename(entry.get("output") or ""),
            ] + [os.path.basename(p) for p in entry.get("inputs", []) if p]
            if not any(self._search in c.lower() for c in campos):
                return False
        return True


class HistoricoTab(QWidget):
    _STATUS_FILTERS = [("Todos", ""), ("Concluídos", "ok"),
                       ("Erros", "error"), ("Cancelados", "cancelled")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = _HistoryModel(self)
        self._proxy = _HistoryFilterProxy(self)
        self._proxy.setSourceModel(self._model)

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

        # barra: busca + filtro de status + ações
        bar = QHBoxLayout()
        self._ed_busca = QLineEdit()
        self._ed_busca.setPlaceholderText("Buscar por arquivo, tipo ou data…")
        self._ed_busca.setClearButtonEnabled(True)
        self._ed_busca.textChanged.connect(self._apply_filters)
        bar.addWidget(self._ed_busca, stretch=1)
        self._cb_status = QComboBox()
        for label, _val in self._STATUS_FILTERS:
            self._cb_status.addItem(label)
        self._cb_status.currentIndexChanged.connect(self._apply_filters)
        bar.addWidget(self._cb_status)
        self._btn_detalhes = QPushButton("Ver detalhes")
        self._btn_detalhes.setEnabled(False)
        self._btn_detalhes.clicked.connect(self._detalhes_selecionado)
        bar.addWidget(self._btn_detalhes)
        self._btn_export = QPushButton("Exportar CSV")
        self._btn_export.clicked.connect(self._exportar_csv)
        bar.addWidget(self._btn_export)
        self._btn_clear = QPushButton("Limpar histórico")
        self._btn_clear.clicked.connect(self._on_clear)
        bar.addWidget(self._btn_clear)
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;"); wrap.setLayout(bar)
        layout.addWidget(wrap)

        self._view = QTableView(self)
        self._view.setModel(self._proxy)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._view.verticalHeader().setVisible(False)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.setEditTriggers(QTableView.NoEditTriggers)
        self._view.doubleClicked.connect(self._open_output)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._view, stretch=1)

        # estado vazio
        self._lbl_vazio = QLabel(
            "Nenhum processamento por aqui ainda.\n"
            "Use as abas Ocorrências ou VT-Caixa — os resultados aparecem nesta lista."
        )
        self._lbl_vazio.setAlignment(Qt.AlignCenter)
        self._lbl_vazio.setObjectName("helpText")
        layout.addWidget(self._lbl_vazio)

        QShortcut(QKeySequence(Qt.Key_F5), self, activated=self.refresh)

        self._update_stats()
        self._update_empty_state()

    # ---------- filtros ----------
    def _apply_filters(self, *_):
        _label, status = self._STATUS_FILTERS[self._cb_status.currentIndex()]
        self._proxy.set_filters(self._ed_busca.text(), status)
        self._update_empty_state()

    def _update_empty_state(self):
        tem_dados = self._model.rowCount() > 0
        tem_visiveis = self._proxy.rowCount() > 0
        self._view.setVisible(tem_visiveis)
        if not tem_dados:
            self._lbl_vazio.setText(
                "Nenhum processamento por aqui ainda.\n"
                "Use as abas Ocorrências ou VT-Caixa — os resultados aparecem nesta lista.")
        else:
            self._lbl_vazio.setText("Nenhum resultado para o filtro atual.")
        self._lbl_vazio.setVisible(not tem_visiveis)

    def _entry_from_proxy(self, proxy_index):
        if not proxy_index.isValid():
            return None
        src = self._proxy.mapToSource(proxy_index)
        return self._model.entry_at(src.row())

    def _on_selection_changed(self, *_):
        entry = self._entry_from_proxy(self._view.currentIndex())
        tem_detalhes = bool(entry and (entry.get("nao_encontrados")
                                       or entry.get("avisos_csv")
                                       or entry.get("alertas_ia")
                                       or entry.get("error")))
        self._btn_detalhes.setEnabled(tem_detalhes)

    # ---------- dados ----------
    def refresh(self):
        self._model.reload()
        self._update_stats()
        self._update_empty_state()

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

    def _exportar_csv(self):
        if self._proxy.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "Não há linhas para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar histórico",
                                              "historico.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            # utf-8-sig: Excel reconhece a acentuação ao abrir direto
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(COLUMNS)
                for r in range(self._proxy.rowCount()):
                    w.writerow([
                        self._proxy.data(self._proxy.index(r, c), Qt.DisplayRole) or ""
                        for c in range(len(COLUMNS))
                    ])
        except OSError as e:
            QMessageBox.warning(self, "Exportar", f"Falha ao salvar: {e}")
            return
        win = self.window()
        if hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage(f"Histórico exportado para {path}", 4000)

    # ---------- ações por linha ----------
    def _open_output(self, proxy_index):
        entry = self._entry_from_proxy(proxy_index)
        if not entry:
            return
        out = entry.get("output")
        if out and Path(out).is_file():
            open_path(out)

    def _show_context_menu(self, pos):
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            return
        entry = self._entry_from_proxy(idx)
        if entry is None:
            return
        src_row = self._proxy.mapToSource(idx).row()
        menu = QMenu(self)
        a_open = QAction("Abrir saída", self)
        a_folder = QAction("Abrir pasta da saída", self)
        a_remove = QAction("Remover do histórico", self)
        a_open.triggered.connect(lambda: self._open_output(idx))
        a_folder.triggered.connect(lambda: self._open_folder(entry.get("output")))
        a_remove.triggered.connect(lambda: self._remove(src_row))
        menu.addAction(a_open); menu.addAction(a_folder)
        # Detalhes (não-encontrados / avisos / alertas IA) — só quando houver
        if (entry.get("nao_encontrados") or entry.get("avisos_csv")
                or entry.get("alertas_ia") or entry.get("error")):
            a_det = QAction("Ver detalhes", self)
            a_det.triggered.connect(lambda: self._ver_detalhes(entry))
            menu.addAction(a_det)
        menu.addSeparator(); menu.addAction(a_remove)
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _detalhes_selecionado(self):
        entry = self._entry_from_proxy(self._view.currentIndex())
        if entry:
            self._ver_detalhes(entry)

    def _ver_detalhes(self, entry):
        linhas = []
        erro = entry.get("error")
        nao_enc = entry.get("nao_encontrados") or []
        avisos = entry.get("avisos_csv") or []
        alertas = entry.get("alertas_ia") or []
        if erro:
            linhas.append("Erro:")
            linhas.append(f"  {erro}")
            linhas.append("")
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
        show_text_dialog(self, "Detalhes do processamento", "\n".join(linhas))

    def _remove(self, row):
        actual = len(history.load()) - 1 - row  # lista é mostrada invertida
        history.remove(actual)
        self.refresh()

    def _open_folder(self, out):
        if not out:
            return
        d = os.path.dirname(out)
        if d and os.path.isdir(d):
            open_path(d)
