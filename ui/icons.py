"""Ícones vetoriais do app — SVGs de traço (estilo Lucide) tingidos pelo tema.

Uso:
    pixmap("settings", theme.token("fg_dim"), 18)   # QPixmap tingido
    icon("play", "#ffffff", 16)                      # QIcon (para botões)
    IconLabel("upload", "fg_dim", 22)                # QLabel que se re-tinge
                                                     # quando o tema troca

IconLabel recebe o NOME do token (não a cor) e se atualiza sozinha no
StyleChange disparado pela troca de stylesheet do QApplication.
"""
from PySide6.QtCore import QByteArray, QEvent, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel

# Corpos SVG (viewBox 24x24, stroke-based). Fonte: Lucide/Feather (ISC).
_PATHS = {
    "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                 '<polyline points="14 2 14 8 20 8"/>'
                 '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "table":     '<rect x="3" y="3" width="18" height="18" rx="2"/>'
                 '<line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/>'
                 '<line x1="9" y1="9" x2="9" y2="21"/>',
    "code":      '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "history":   '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "settings":  '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
                 '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
                 '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
                 '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
                 '<line x1="17" y1="16" x2="23" y2="16"/>',
    "play":      '<polygon points="6 4 20 12 6 20 6 4"/>',
    "check":     '<polyline points="20 6 9 17 4 12"/>',
    "x":         '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "upload":    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                 '<polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "refresh":   '<polyline points="23 4 23 10 17 10"/>'
                 '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
    "zap":       '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
}

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round">{body}</svg>')


def pixmap(name: str, color: str, size: int = 18, dpr: float = 2.0) -> QPixmap:
    """QPixmap do ícone `name` na cor dada (hex). Renderiza em 2x para nitidez."""
    body = _PATHS[name]
    svg = _SVG.format(color=color, body=body)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str, size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))


class IconLabel(QLabel):
    """QLabel com ícone tingido por um TOKEN do tema; re-tinge na troca de tema."""

    def __init__(self, name: str, token: str = "fg_dim", size: int = 18, parent=None):
        super().__init__(parent)
        self._name = name
        self._token = token
        self._size = size
        self.setStyleSheet("background: transparent; border: none;")
        self._repaint()

    def set_icon(self, name: str, token: str = None) -> None:
        self._name = name
        if token is not None:
            self._token = token
        self._repaint()

    def _repaint(self) -> None:
        from ui import theme
        self.setPixmap(pixmap(self._name, theme.token(self._token), self._size))

    def changeEvent(self, ev):
        if ev.type() == QEvent.StyleChange:
            self._repaint()
        super().changeEvent(ev)
