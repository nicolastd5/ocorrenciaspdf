from ui.widgets.conflict_dialog import ConflictDialog


def _conflito(**o):
    base = {"re": "123", "nome": "FULANO", "codigo": "FA",
            "valores": {"v1": 2, "v2": 3, "ia": 3}, "sugestao": 3}
    base.update(o)
    return base


def test_dialog_preseleciona_sugestao_e_retorna_escolhas(qtbot):
    dlg = ConflictDialog([_conflito()])
    qtbot.addWidget(dlg)
    dlg._on_accept()
    assert dlg.resultado() == [("123", "FA", 3)]


def test_dialog_agrupa_valores_unicos(qtbot):
    dlg = ConflictDialog([_conflito()])
    qtbot.addWidget(dlg)
    group = dlg._grupos[("123", "FA")]
    assert len(group.buttons()) == 2


def test_dialog_multiplos_conflitos(qtbot):
    dlg = ConflictDialog([_conflito(), _conflito(re="999", codigo="AT",
                                                  valores={"v1": 1, "v2": 0}, sugestao=1)])
    qtbot.addWidget(dlg)
    dlg._on_accept()
    res = dict(((r, c), v) for r, c, v in dlg.resultado())
    assert res[("123", "FA")] == 3
    assert res[("999", "AT")] == 1
