from core.vt_caixa_processador import ProcessadorVTCaixa


def test_ia_removida():
    assert not hasattr(ProcessadorVTCaixa, 'verificar_com_ia')
    assert not hasattr(ProcessadorVTCaixa, 'listar_modelos')


def test_constantes_de_referencia_expostas():
    assert len(ProcessadorVTCaixa._CODIGOS_BENEFICIO) > 0
    assert len(ProcessadorVTCaixa._DEPART_MAP) > 0


def test_resolver_codigo_extras_tem_precedencia():
    p = ProcessadorVTCaixa()
    # embutido: ('SPTRANS', '11,64', '701')
    extras = [('SPTRANS', '11,64', '999')]
    assert p._resolver_codigo_beneficio('SPTRANS SP', '11,64', extras) == '999'
    # sem extras, embutido continua valendo
    assert p._resolver_codigo_beneficio('SPTRANS SP', '11,64') == '701'
    # operadora só nos extras
    extras2 = [('OPERADORA NOVA', None, '555')]
    assert p._resolver_codigo_beneficio('OPERADORA NOVA LTDA', '10,00', extras2) == '555'
    assert p._resolver_codigo_beneficio('OPERADORA NOVA LTDA', '10,00') is None


def test_cruzar_dados_usa_depart_extras():
    p = ProcessadorVTCaixa()
    pdf_rows = [{'codigo': '111', 'colaborador': 'ANA',
                 'administradora': 'QUALQUER', 'valor_unitario': '5,00',
                 'quantidade': '20'}]
    excel_data = {'111': {
        'CPF': '1', 'RG': '2', 'Data nascimento': '', 'Descrição cargo': '',
        'Descrição Ccusto': 'MEU DEPTO', 'Descrição Dpto': '', 'Nome Mae': '',
        'Endereço': '', 'Numero': '', 'Complemento': '', 'Cep': '',
        'Estado Civil': '', 'Data EX': '', 'Orgão RG': '', 'UF RG': '',
    }}
    regs, _ = p._cruzar_dados(pdf_rows, excel_data,
                              depart_extras={'MEU DEPTO': 'DEPTO NOVO'})
    assert regs[0]['DEPARTAMENTO'] == 'DEPTO NOVO'
    # depart_extras sobrepõe _DEPART_MAP quando a chave coincide
    regs2, _ = p._cruzar_dados(pdf_rows, excel_data)
    assert regs2[0]['DEPARTAMENTO'] == 'MEU DEPTO'
