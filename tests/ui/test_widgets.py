import pytest
from PySide6.QtCore import Qt, QPoint, QUrl, QMimeData
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QLabel
from ui.widgets import PrimaryButton, SectionCard, DropZone, LogPanel


def test_primary_button_constructs(qtbot):
    btn = PrimaryButton("Processar")
    qtbot.addWidget(btn)
    assert btn.text() == "Processar"
    assert btn.objectName() == "primary"


def test_primary_button_set_mode_changes_object_name(qtbot):
    btn = PrimaryButton("X")
    qtbot.addWidget(btn)
    btn.set_mode("warning")
    assert btn.objectName() == "warning"


def test_section_card_adds_widgets(qtbot):
    card = SectionCard(1, "PDF de jornada")
    qtbot.addWidget(card)
    card.add(QLabel("hello"))
    # título agora é um QLabel no cabeçalho do card (não mais QGroupBox.title())
    titulos = [w.text() for w in card.findChildren(QLabel) if w.objectName() == "cardTitle"]
    assert "PDF de jornada" in titulos


def test_section_card_set_done_flips_step(qtbot):
    card = SectionCard(2, "Planilha")
    qtbot.addWidget(card)
    assert card._step.text() == "2"
    card.set_done(True)
    assert card._step.objectName() == "stepDone"
    card.set_done(False)
    assert card._step.text() == "2"
    assert card._step.objectName() == "step"


def test_drop_zone_emits_on_drop(qtbot, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    dz = DropZone("Arraste PDF", accept_extensions=(".pdf",))
    qtbot.addWidget(dz)
    received = []
    dz.files_selected.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    dz.dropEvent(ev)
    assert received == [[str(pdf)]]


def test_drop_zone_rejects_wrong_extension(qtbot, tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("x")
    dz = DropZone("Arraste PDF", accept_extensions=(".pdf",))
    qtbot.addWidget(dz)
    received = []
    dz.files_selected.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(txt))])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    dz.dropEvent(ev)
    assert received == []


def test_log_panel_append_and_progress(qtbot):
    lp = LogPanel()
    qtbot.addWidget(lp)
    lp.append("hello", level="info")
    lp.append("err", level="error")
    lp.set_progress(42, visible=True)
    assert "hello" in lp.text()
    assert "err" in lp.text()
