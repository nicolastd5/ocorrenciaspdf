from core.vt_caixa_processador import ProcessadorVTCaixa


def test_ia_removida():
    assert not hasattr(ProcessadorVTCaixa, 'verificar_com_ia')
    assert not hasattr(ProcessadorVTCaixa, 'listar_modelos')


def test_constantes_de_referencia_expostas():
    assert len(ProcessadorVTCaixa._CODIGOS_BENEFICIO) > 0
    assert len(ProcessadorVTCaixa._DEPART_MAP) > 0
