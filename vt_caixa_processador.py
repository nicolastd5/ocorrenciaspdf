import csv
import re
from datetime import date, datetime

import pdfplumber
import xlrd

COLUNAS_CSV = [
    'CNPJ', 'CEP', 'LOGRADOURO', 'NÚMERO', 'COMPLEMENTO', 'PONTO REFERENCIA',
    'UF', 'ESTADO', 'MATRÍCULA', 'NOME DO FUNCIONÁRIO', 'CPF', 'RG',
    'DATA DE NASCIMENTO', 'CARGO', 'DEPARTAMENTO', 'NOME DA MÃE',
    'BENEFÍCIO DO FUNCIONÁRIO', 'VALOR UNITÁRIO', 'QUANTIDADE DIÁRIA',
    'PERÍODO DE DIAS TRABALHADOS', 'TIPO VALOR', 'REDE RECARGA',
    'CEP RESIDENCIAL', 'LOGRADOURO RESIDENCIAL', 'NÚMERO RESIDENCIAL',
    'COMPLEMENTO RESIDENCIAL', 'ESTADO CIVIL', 'DATA DE EMISSÃO DO RG',
    'ÓRGÃO EXPEDIDOR', 'ESTADO EMISSÃO RG',
]


class ProcessadorVTCaixa:

    def _extrair_pdf(self, pdf_path):
        """Extrai linhas de dados do PDF Nautilus.
        Retorna lista de dicts com: codigo, colaborador, periodo,
        quantidade, valor_unitario, administradora.
        """
        rows = []
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                tabela = pagina.extract_table()
                if not tabela:
                    continue
                for linha in tabela:
                    if not linha:
                        continue
                    # Primeira célula deve ser numérica (Código/matrícula)
                    primeira = linha[0]
                    if primeira is None:
                        continue
                    codigo = str(primeira).strip().replace('\n', '')
                    if not codigo.isdigit():
                        continue
                    # Garante que há colunas suficientes
                    if len(linha) < 9:
                        continue

                    def _cel(idx):
                        v = linha[idx]
                        return str(v).strip().replace('\n', ' ') if v is not None else ''

                    rows.append({
                        'codigo':        codigo,
                        'colaborador':   _cel(1),
                        'periodo':       _cel(3),
                        'quantidade':    _cel(5),
                        'valor_unitario': _cel(6),
                        'administradora': _cel(8),
                    })
        return rows

    def _calcular_dias_uteis(self, periodo_str):
        """Conta dias úteis (seg–sex) no período 'dd/mm/yyyy a dd/mm/yyyy'."""
        if not periodo_str:
            return 0
        # Aceita separador ' a ' ou ' - '
        partes = re.split(r'\s+[aA\-]\s+', periodo_str.strip())
        if len(partes) != 2:
            return 0
        try:
            inicio = datetime.strptime(partes[0].strip(), '%d/%m/%Y').date()
            fim    = datetime.strptime(partes[1].strip(), '%d/%m/%Y').date()
        except ValueError:
            return 0
        dias = 0
        atual = inicio
        while atual <= fim:
            if atual.weekday() < 5:
                dias += 1
            atual = date.fromordinal(atual.toordinal() + 1)
        return dias

    def _formatar_cpf(self, valor):
        """Garante string com zeros à esquerda para CPF (11 dígitos)."""
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        s = str(valor).strip().split('.')[0]  # remove .0 de float
        digits = re.sub(r'\D', '', s)
        return digits.zfill(11) if digits else s

    def _formatar_rg(self, valor):
        """Preserva RG como string."""
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        return str(valor).strip().split('.')[0]

    def _formatar_data(self, valor, wb):
        """Converte valor de data do xlrd para dd/mm/yyyy."""
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            try:
                dt = xlrd.xldate_as_datetime(valor, wb.datemode)
                return dt.strftime('%d/%m/%Y')
            except Exception:
                return str(valor)
        return str(valor).strip()

    def _formatar_cep(self, valor):
        """Formata CEP como string com 8 dígitos."""
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        s = str(valor).strip().split('.')[0]
        digits = re.sub(r'\D', '', s)
        return digits.zfill(8) if digits else s

    def _formatar_numero(self, valor):
        """Formata número de endereço como string."""
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        return str(valor).strip().split('.')[0]

    def _carregar_excel(self, xls_path):
        """Carrega o Excel cadastral .xls.
        Retorna dict: {str(Cód Epr): {coluna: valor}}
        """
        wb = xlrd.open_workbook(xls_path)
        ws = wb.sheet_by_index(0)

        # Mapeia nome de coluna → índice (case-insensitive)
        cabecalhos = {}
        for col in range(ws.ncols):
            val = ws.cell_value(0, col)
            if val:
                cabecalhos[str(val).strip().lower()] = col

        def _idx(nome):
            return cabecalhos.get(nome.lower())

        idx_cod     = _idx('Cód Epr')
        idx_cpf     = _idx('CPF')
        idx_rg      = _idx('RG')
        idx_uf_rg   = _idx('UF RG')
        idx_org_rg  = _idx('Orgão RG')
        idx_dt_nasc = _idx('Data nascimento')
        idx_cargo   = _idx('Descrição cargo')
        idx_ccusto  = _idx('Descrição Ccusto')
        idx_end     = _idx('Endereço')
        idx_num     = _idx('Numero')
        idx_comp    = _idx('Complemento')
        idx_cep     = _idx('Cep')
        idx_cidade  = _idx('Cidade')
        idx_uf_end  = _idx('UF End')
        idx_est_civ = _idx('Estado Civil')

        if idx_cod is None:
            raise ValueError("Coluna 'Cód Epr' não encontrada no Excel.")

        dados = {}
        for row in range(1, ws.nrows):
            cod_raw = ws.cell_value(row, idx_cod)
            if cod_raw is None or cod_raw == '':
                continue
            if isinstance(cod_raw, float):
                cod_raw = int(cod_raw)
            chave = str(cod_raw).strip()

            def _val(idx):
                if idx is None:
                    return ''
                v = ws.cell_value(row, idx)
                if v is None:
                    return ''
                if isinstance(v, float):
                    return str(int(v))
                return str(v).strip()

            dados[chave] = {
                'CPF':              self._formatar_cpf(ws.cell_value(row, idx_cpf) if idx_cpf is not None else None),
                'RG':               self._formatar_rg(ws.cell_value(row, idx_rg) if idx_rg is not None else None),
                'UF RG':            _val(idx_uf_rg),
                'Orgão RG':         _val(idx_org_rg),
                'Data nascimento':  self._formatar_data(ws.cell_value(row, idx_dt_nasc) if idx_dt_nasc is not None else None, wb),
                'Descrição cargo':  _val(idx_cargo),
                'Descrição Ccusto': _val(idx_ccusto),
                'Endereço':         _val(idx_end),
                'Numero':           self._formatar_numero(ws.cell_value(row, idx_num) if idx_num is not None else None),
                'Complemento':      _val(idx_comp),
                'Cep':              self._formatar_cep(ws.cell_value(row, idx_cep) if idx_cep is not None else None),
                'Cidade':           _val(idx_cidade),
                'UF End':           _val(idx_uf_end),
                'Estado Civil':     _val(idx_est_civ),
            }
        return dados

    def _limpar_valor_unitario(self, valor_str):
        """Remove 'R$', espaços e converte vírgula para ponto."""
        v = valor_str.replace('R$', '').strip()
        v = v.replace('.', '').replace(',', '.')  # 1.234,56 → 1234.56
        return v

    def _cruzar_dados(self, pdf_rows, excel_data):
        """Cruza linhas do PDF com cadastro Excel.
        Retorna (registros: list[dict], nao_encontrados: list[str])
        """
        registros = []
        nao_encontrados = []

        for linha in pdf_rows:
            codigo = linha['codigo']
            ex = excel_data.get(codigo)

            if ex is None:
                nao_encontrados.append(f"{codigo} - {linha['colaborador']}")
                continue

            dias_uteis = self._calcular_dias_uteis(linha['periodo'])

            registros.append({
                'CNPJ':                        '',
                'CEP':                         ex['Cep'],
                'LOGRADOURO':                  ex['Endereço'],
                'NÚMERO':                      ex['Numero'],
                'COMPLEMENTO':                 ex['Complemento'],
                'PONTO REFERENCIA':            '',
                'UF':                          ex['UF End'],
                'ESTADO':                      ex['Cidade'],
                'MATRÍCULA':                   codigo,
                'NOME DO FUNCIONÁRIO':         linha['colaborador'],
                'CPF':                         ex['CPF'],
                'RG':                          ex['RG'],
                'DATA DE NASCIMENTO':          ex['Data nascimento'],
                'CARGO':                       ex['Descrição cargo'],
                'DEPARTAMENTO':                ex['Descrição Ccusto'],
                'NOME DA MÃE':                 '',
                'BENEFÍCIO DO FUNCIONÁRIO':    linha['administradora'],
                'VALOR UNITÁRIO':              self._limpar_valor_unitario(linha['valor_unitario']),
                'QUANTIDADE DIÁRIA':           linha['quantidade'],
                'PERÍODO DE DIAS TRABALHADOS': str(dias_uteis),
                'TIPO VALOR':                  '',
                'REDE RECARGA':                linha['administradora'],
                'CEP RESIDENCIAL':             ex['Cep'],
                'LOGRADOURO RESIDENCIAL':      ex['Endereço'],
                'NÚMERO RESIDENCIAL':          ex['Numero'],
                'COMPLEMENTO RESIDENCIAL':     ex['Complemento'],
                'ESTADO CIVIL':                ex['Estado Civil'],
                'DATA DE EMISSÃO DO RG':       '',
                'ÓRGÃO EXPEDIDOR':             ex['Orgão RG'],
                'ESTADO EMISSÃO RG':           ex['UF RG'],
            })

        return registros, nao_encontrados

    def _gerar_csv(self, registros, output_path):
        """Grava o CSV em latin-1 com separador ';'."""
        with open(output_path, 'w', newline='', encoding='latin-1', errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=COLUNAS_CSV, delimiter=';',
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(registros)

    def verificar_com_ia(self, registros, nao_encontrados, api_key):
        """Verifica consistência dos dados com Google Gemma 4 via AI Studio.
        Retorna lista de strings com alertas.
        """
        try:
            from google import genai
        except ImportError:
            return ['Erro: biblioteca google-genai não instalada. '
                    'Execute: pip install google-genai']

        if not api_key.strip():
            return ['Erro: API Key não informada.']

        # Monta amostra (máx 50 registros para não exceder tokens)
        amostra = registros[:50]
        linhas_texto = []
        for r in amostra:
            linhas_texto.append(
                f"Matrícula={r['MATRÍCULA']} | Nome={r['NOME DO FUNCIONÁRIO']} | "
                f"CPF={r['CPF']} | RG={r['RG']} | Nascimento={r['DATA DE NASCIMENTO']} | "
                f"CEP={r['CEP']} | ValorUnit={r['VALOR UNITÁRIO']} | "
                f"QtdDiaria={r['QUANTIDADE DIÁRIA']} | PeriodoDias={r['PERÍODO DE DIAS TRABALHADOS']} | "
                f"Beneficio={r['BENEFÍCIO DO FUNCIONÁRIO']}"
            )

        sem_corresp = '\n'.join(nao_encontrados) if nao_encontrados else 'Nenhuma'

        prompt = f"""Você é um assistente de RH verificando dados de Vale-Transporte para importação.
Analise os registros abaixo e reporte APENAS inconsistências reais. Seja objetivo e conciso.

Verifique:
1. Valor Unitário zerado ou vazio
2. Quantidade Diária zerada ou vazia
3. Período de Dias Trabalhados zerado (possível erro no período)
4. CPF, RG ou CEP vazios (campos obrigatórios)
5. Nome com caracteres estranhos ou truncado
6. Quantidade Diária maior que Período de Dias Trabalhados

Registros ({len(amostra)} de {len(registros)} total):
{chr(10).join(linhas_texto)}

Matrículas sem correspondência no cadastro:
{sem_corresp}

Responda em português com lista numerada de problemas encontrados. Se tudo estiver OK, diga apenas "Nenhuma inconsistência encontrada."
"""

        try:
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(
                model='gemma-4-31b-it',
                contents=prompt,
            )
            texto = response.text.strip()
            return texto.splitlines()
        except Exception as e:
            return [f'Erro ao chamar IA: {e}']

    def processar(self, pdf_path, xls_path, output_path,
                  progress_cb=None, usar_ia=False, api_key=''):
        """Orquestra extração, cruzamento, geração de CSV e verificação IA.

        Returns:
            dict com total_pdf, total_ok, nao_encontrados, alertas_ia
        """
        def _prog(pct, msg):
            if progress_cb:
                progress_cb(pct, msg)

        _prog(5, 'Lendo PDF...')
        pdf_rows = self._extrair_pdf(pdf_path)

        _prog(40, f'PDF lido ({len(pdf_rows)} registros). Carregando Excel...')
        excel_data = self._carregar_excel(xls_path)

        _prog(65, f'Excel carregado ({len(excel_data)} funcionários). Cruzando dados...')
        registros, nao_encontrados = self._cruzar_dados(pdf_rows, excel_data)

        _prog(85, f'Cruzamento concluído. Gerando CSV...')
        self._gerar_csv(registros, output_path)

        alertas_ia = []
        if usar_ia:
            _prog(90, 'CSV salvo. Verificando com IA (Gemma 4)...')
            alertas_ia = self.verificar_com_ia(registros, nao_encontrados, api_key)
        else:
            _prog(90, 'CSV salvo.')

        _prog(100, 'Concluído!')

        return {
            'total_pdf':       len(pdf_rows),
            'total_ok':        len(registros),
            'nao_encontrados': nao_encontrados,
            'alertas_ia':      alertas_ia,
        }
