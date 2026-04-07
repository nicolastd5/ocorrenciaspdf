import csv
import re
import unicodedata
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

# Endereço fixo da empresa (primeira parte do CSV — linhas antes da MATRÍCULA)
EMPRESA_CNPJ         = ''
EMPRESA_CEP          = '06455000'
EMPRESA_LOGRADOURO   = 'ALAMEDA ARAGUAIA'
EMPRESA_NUMERO       = '3354'
EMPRESA_COMPLEMENTO  = 'ALPHAVILLE INDUSTRIAL'
EMPRESA_UF           = 'SP'
EMPRESA_ESTADO       = 'BARUERI'

# Para cada campo canônico usado no cruzamento, os nomes normalizados (sem
# acentos, minúsculo) que podem aparecer como cabeçalho no Excel cadastral.
# A ordem da lista é a ordem de preferência (primeiro = mais específico).
_COL_ALIASES = {
    'Cód Epr':          ['cod epr', 'codigo epr', 'codigo empresa', 'matricula'],
    'CPF':              ['cpf'],
    'RG':               ['rg', 'numero rg', 'no rg'],
    'UF RG':            ['uf rg', 'uf do rg', 'estado rg'],
    'Orgão RG':         ['orgao rg', 'orgao expedidor', 'orgao emissor', 'orgao exp'],
    'Data nascimento':  ['data nascimento', 'data de nascimento', 'dt nascimento', 'dt nasc', 'nascimento'],
    'Descrição cargo':  ['descricao cargo', 'desc cargo', 'cargo'],
    'Descrição Ccusto': ['descricao ccusto', 'desc ccusto', 'descricao centro de custo',
                         'centro de custo', 'ccusto'],
    'Endereço':         ['endereco', 'logradouro', 'end'],
    'Numero':           ['numero', 'num', 'numero end', 'numero endereco', 'nro'],
    'Complemento':      ['complemento', 'compl'],
    'Cep':              ['cep'],
    'Cidade':           ['cidade', 'municipio'],
    'UF End':           ['uf end', 'uf endereco', 'uf', 'estado end'],
    'Estado Civil':     ['estado civil'],
}


# ──────────────────────────────────────────────────────────────────────────────
# Funções auxiliares de módulo
# ──────────────────────────────────────────────────────────────────────────────

def _norm(texto):
    """Remove acentos e converte para minúsculas para comparação robusta."""
    return unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode().lower().strip()


def _extrair_codigo(valor):
    """Extrai código numérico de célula, lidando com '123.0', '  123 ', etc."""
    if valor is None:
        return ''
    s = str(valor).strip().replace('\n', '').replace('\r', '')
    s = re.sub(r'\.0+$', '', s)
    m = re.match(r'^(\d+)', s)
    return m.group(1) if m else ''


def _pode_latin1(c):
    """Verifica se o caractere pode ser codificado em latin-1."""
    try:
        c.encode('latin-1')
        return True
    except UnicodeEncodeError:
        return False


def _mascarar_pii(registros):
    """Substitui dados pessoais por indicadores de presença para envio à IA."""
    mascarados = []
    for r in registros:
        def _pres(v):
            return 'preenchido' if str(v).strip() else 'vazio'

        def _ano_nasc(v):
            m = re.search(r'\d{4}', str(v))
            return m.group(0) if m else ('preenchido' if v else 'vazio')

        mascarados.append({
            'MATRÍCULA':                   r['MATRÍCULA'],
            'NOME DO FUNCIONÁRIO':         r['NOME DO FUNCIONÁRIO'],
            'CPF':                         _pres(r['CPF']),
            'RG':                          _pres(r['RG']),
            'DATA DE NASCIMENTO':          _ano_nasc(r['DATA DE NASCIMENTO']),
            'CEP':                         _pres(r['CEP']),
            'VALOR UNITÁRIO':              r['VALOR UNITÁRIO'],
            'QUANTIDADE DIÁRIA':           r['QUANTIDADE DIÁRIA'],
            'PERÍODO DE DIAS TRABALHADOS': r['PERÍODO DE DIAS TRABALHADOS'],
            'BENEFÍCIO DO FUNCIONÁRIO':    r['BENEFÍCIO DO FUNCIONÁRIO'],
            'CARGO':                       r['CARGO'],
        })
    return mascarados


def _normalizar_data_espacada(texto):
    return re.sub(r'\s+', '', texto)


def _limpar_nome_extraido(texto):
    texto = re.sub(r'\s+', ' ', texto).strip()
    # Remove dígitos misturados no meio do nome (artefato de pdfplumber em PDFs com
    # colunas adjacentes — ex: "SANTO1S" → "SANTOS", "OLIV9E1IR97A483" → "OLIVEIRA").
    # Só aplica se o texto contém letras (evita apagar matrículas puras).
    if re.search(r'[A-Za-zÀ-ÿ]', texto):
        texto = re.sub(r'\d', '', texto)
    # Normaliza espaços residuais e remove cauda vazia.
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


# ──────────────────────────────────────────────────────────────────────────────
# Classe principal
# ──────────────────────────────────────────────────────────────────────────────

class ProcessadorVTCaixa:

    # ── Extração PDF ───────────────────────────────────────────────────

    def _extrair_pdf(self, pdf_path):
        rows = []
        avisos = []

        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                tabelas = pagina.extract_tables() or []
                if not tabelas:
                    tabela = pagina.extract_table()
                    if tabela:
                        tabelas = [tabela]
                if not tabelas:
                    continue

                for tabela in tabelas:
                    if not tabela:
                        continue

                    for linha in tabela:
                        if not linha or all(c is None for c in linha):
                            continue

                        codigo = _extrair_codigo(linha[0])
                        if not codigo:
                            continue

                        while len(linha) < 9:
                            linha.append(None)

                        def _cel(idx, ln=linha):
                            v = ln[idx]
                            return str(v).strip().replace('\n', ' ').replace('\r', '') if v is not None else ''

                        rows.append({
                            'codigo':         codigo,
                            'colaborador':    _limpar_nome_extraido(_cel(1)),
                            'periodo':        _cel(3),
                            'quantidade':     re.sub(r'\.0+$', '', _cel(5)),
                            'valor_unitario': _cel(6),
                            'administradora': _cel(8),
                        })

        if not rows:
            avisos.append('AVISO: Nenhuma linha tabular extraída do PDF; tentando leitura por texto.')
            rows = self._extrair_pdf_por_texto(pdf_path)

        if not rows:
            avisos.append(
                'AVISO: Nenhuma linha de dados extraída do PDF. '
                'Verifique se o PDF é o relatório correto e se o layout continua compatível com a extração.'
            )

        return rows, avisos

    def _extrair_pdf_por_texto(self, pdf_path):
        rows = []
        date_re = re.compile(r'(\d\s*\d\s*/\s*\d\s*\d\s*/\s*\d\s*\d\s*\d\s*\d)')

        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text() or ''
                if not texto:
                    continue

                iniciou_dados = False
                for linha in texto.splitlines():
                    linha = linha.strip()
                    if not linha:
                        continue

                    if 'Tipo Benefício:' in linha:
                        iniciou_dados = True
                        continue

                    if not iniciou_dados:
                        continue

                    if linha.isdigit():
                        continue

                    m_cod = re.match(r'^(\d+)\s+', linha)
                    if not m_cod:
                        continue

                    datas = list(date_re.finditer(linha))
                    if len(datas) < 3:
                        continue

                    codigo = m_cod.group(1)
                    prefixo = linha[m_cod.end():datas[0].start()].strip()
                    colaborador = _limpar_nome_extraido(prefixo)

                    periodo_inicio = _normalizar_data_espacada(datas[0].group(1))
                    periodo_fim = _normalizar_data_espacada(datas[1].group(1))
                    periodo = f'{periodo_inicio} a {periodo_fim}'

                    cauda = linha[datas[2].end():].strip()
                    m_tail = re.match(r'^(\d+)\s+(\d+,\d{2})\s+(\d+,\d{2})\s+(.+)$', cauda)
                    if not m_tail:
                        continue

                    rows.append({
                        'codigo':         codigo,
                        'colaborador':    colaborador,
                        'periodo':        periodo,
                        'quantidade':     m_tail.group(1),
                        'valor_unitario': m_tail.group(2),
                        'administradora': m_tail.group(4).strip(),
                    })

        return rows

    # ── Dias úteis ─────────────────────────────────────────────────────

    def _calcular_dias_uteis(self, periodo_str):
        if not periodo_str:
            return 0

        partes = None
        s = periodo_str.strip()

        # Extrai as duas datas (dd/mm/yyyy) de qualquer forma que apareçam.
        # Aceita: 'a', 'A', '-', 'até', espaço duplo, ou qualquer separador entre elas.
        datas = re.findall(r'\d{2}/\d{2}/\d{4}', s)
        if len(datas) >= 2:
            partes = [datas[0], datas[1]]

        # Fallback: dd-mm-yyyy ou dd.mm.yyyy
        if not partes:
            datas_alt = re.findall(r'\d{2}[-\.]\d{2}[-\.]\d{4}', s)
            if len(datas_alt) >= 2:
                partes = [
                    re.sub(r'[-\.]', '/', datas_alt[0]),
                    re.sub(r'[-\.]', '/', datas_alt[1]),
                ]

        if not partes:
            return 0

        try:
            inicio = datetime.strptime(partes[0], '%d/%m/%Y').date()
            fim    = datetime.strptime(partes[1], '%d/%m/%Y').date()
        except ValueError:
            return 0

        dias = 0
        atual = inicio
        while atual <= fim:
            if atual.weekday() < 5:
                dias += 1
            atual = date.fromordinal(atual.toordinal() + 1)
        return dias

    # ── Formatadores ───────────────────────────────────────────────────

    def _formatar_cpf(self, valor):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            valor = str(int(valor))
        # Extrai apenas dígitos (remove pontuação '123.456.789-00', espaços, etc.)
        digits = re.sub(r'\D', '', str(valor))
        if not digits:
            return ''
        # CPF tem 11 dígitos; zeros à esquerda são preservados.
        return digits.zfill(11)

    def _formatar_rg(self, valor):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            return str(int(valor))
        s = str(valor).strip()
        # Remove apenas '.0' final (artefato de float→str), preserva pontuação interna.
        return re.sub(r'\.0+$', '', s)

    def _formatar_data(self, valor, wb):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            try:
                dt = xlrd.xldate_as_datetime(valor, wb.datemode)
                return dt.strftime('%d/%m/%Y')
            except Exception:
                return ''
        s = str(valor).strip()
        # Já no formato dd/mm/yyyy → devolve direto
        if re.match(r'^\d{2}/\d{2}/\d{4}$', s):
            return s
        # ISO yyyy-mm-dd ou yyyy-mm-dd hh:mm:ss
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
        return s

    def _formatar_cep(self, valor):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            valor = str(int(valor))
        digits = re.sub(r'\D', '', str(valor))
        if not digits:
            return ''
        # CEP tem 8 dígitos; zeros à esquerda são preservados.
        return digits.zfill(8)[:8]

    def _formatar_numero(self, valor):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            return str(int(valor))
        s = str(valor).strip()
        # Remove '.0' final se veio de float→str, mas preserva '123-A', '123/B'.
        return re.sub(r'\.0+$', '', s)

    # ── Carregar Excel ─────────────────────────────────────────────────

    def _carregar_excel(self, xls_path):
        wb = xlrd.open_workbook(xls_path)
        avisos = []

        ws = None
        for idx in range(wb.nsheets):
            candidato = wb.sheet_by_index(idx)
            cabecalhos = {
                _norm(candidato.cell_value(0, col))
                for col in range(candidato.ncols)
                if candidato.cell_value(0, col)
            }
            if 'cod epr' in cabecalhos:
                ws = candidato
                avisos.append(f'Aba selecionada no Excel: {candidato.name}')
                break

        if ws is None:
            ws = wb.sheet_by_index(0)
            avisos.append(
                f"Aviso: aba com 'Cód Epr' não encontrada; usando a primeira aba: {ws.name}"
            )

        cabecalhos_norm = {}
        cabecalhos_orig = {}
        for col in range(ws.ncols):
            val = ws.cell_value(0, col)
            if val:
                n = _norm(val)
                cabecalhos_norm[n] = col
                cabecalhos_orig[n] = str(val).strip()

        avisos.append(f'Colunas no Excel: {list(cabecalhos_orig.values())}')

        def _idx(nome_canonico):
            """Localiza coluna no Excel: exato → aliases conhecidos. Sem fuzzy."""
            alvo = _norm(nome_canonico)
            # 1) Match exato pelo nome canônico
            if alvo in cabecalhos_norm:
                return cabecalhos_norm[alvo]
            # 2) Tabela de aliases: testa cada variante conhecida, em ordem.
            for alias in _COL_ALIASES.get(nome_canonico, []):
                if alias in cabecalhos_norm:
                    return cabecalhos_norm[alias]
            return None

        mapa_colunas = {
            'Cód Epr':          _idx('Cód Epr'),
            'CPF':              _idx('CPF'),
            'RG':               _idx('RG'),
            'UF RG':            _idx('UF RG'),
            'Orgão RG':         _idx('Orgão RG'),
            'Data nascimento':  _idx('Data nascimento'),
            'Descrição cargo':  _idx('Descrição cargo'),
            'Descrição Ccusto': _idx('Descrição Ccusto'),
            'Endereço':         _idx('Endereço'),
            'Numero':           _idx('Numero'),
            'Complemento':      _idx('Complemento'),
            'Cep':              _idx('Cep'),
            'Cidade':           _idx('Cidade'),
            'UF End':           _idx('UF End'),
            'Estado Civil':     _idx('Estado Civil'),
        }
        idx_cod     = mapa_colunas['Cód Epr']
        idx_cpf     = mapa_colunas['CPF']
        idx_rg      = mapa_colunas['RG']
        idx_uf_rg   = mapa_colunas['UF RG']
        idx_org_rg  = mapa_colunas['Orgão RG']
        idx_dt_nasc = mapa_colunas['Data nascimento']
        idx_cargo   = mapa_colunas['Descrição cargo']
        idx_ccusto  = mapa_colunas['Descrição Ccusto']
        idx_end     = mapa_colunas['Endereço']
        idx_num     = mapa_colunas['Numero']
        idx_comp    = mapa_colunas['Complemento']
        idx_cep     = mapa_colunas['Cep']
        idx_cidade  = mapa_colunas['Cidade']
        idx_uf_end  = mapa_colunas['UF End']
        idx_est_civ = mapa_colunas['Estado Civil']

        if idx_cod is None:
            raise ValueError(
                f"Coluna 'Cód Epr' não encontrada.\n"
                f"Disponíveis: {list(cabecalhos_orig.values())}"
            )

        faltantes = [nome for nome, idx in mapa_colunas.items() if idx is None]
        if faltantes:
            avisos.append(
                f'AVISO: colunas não encontradas no Excel (campos ficarão vazios): {faltantes}'
            )

        avisos.append(
            f'Mapeamento: cod={idx_cod}, cpf={idx_cpf}, rg={idx_rg}, '
            f'nascimento={idx_dt_nasc}, cargo={idx_cargo}, ccusto={idx_ccusto}, '
            f'endereço={idx_end}, numero={idx_num}, cep={idx_cep}'
        )

        dados = {}
        for row in range(1, ws.nrows):
            cod_raw = ws.cell_value(row, idx_cod)
            if cod_raw is None or cod_raw == '':
                continue
            chave = _extrair_codigo(cod_raw) or str(cod_raw).strip()
            if not chave:
                continue

            def _val(idx, r=row):
                if idx is None:
                    return ''
                v = ws.cell_value(r, idx)
                if v is None or v == '':
                    return ''
                if isinstance(v, float):
                    # Inteiros guardados como float no xlrd (ex: 1234.0) → "1234"
                    if v.is_integer():
                        return str(int(v))
                    return str(v)
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

        if not dados:
            avisos.append(
                'AVISO: Nenhum funcionário carregado do Excel cadastral. '
                'Verifique se a aba selecionada contém cabeçalho e dados abaixo da coluna Cód Epr.'
            )

        return dados, avisos

    # ── Cruzamento ─────────────────────────────────────────────────────

    def _limpar_valor_unitario(self, valor_str):
        """Converte 'R$ 1.234,56' → '1234.56'. Aceita string vazia."""
        if valor_str is None:
            return ''
        v = str(valor_str).replace('R$', '').replace('\xa0', ' ').strip()
        if not v:
            return ''
        # Formato pt-BR: "1.234,56" → remove separador de milhar, troca decimal.
        if ',' in v:
            v = v.replace('.', '').replace(',', '.')
        # Sem vírgula: pode já estar em US ("1234.56") — preservar.
        try:
            return f'{float(v):.2f}'
        except ValueError:
            return ''

    def _sanitizar(self, texto):
        """Remove quebras de linha, tabs e normaliza espaços. Nunca retorna None."""
        if texto is None:
            return ''
        s = str(texto).replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    def _cruzar_dados(self, pdf_rows, excel_data):
        registros = []
        nao_encontrados = []

        for linha in pdf_rows:
            codigo = linha['codigo']
            ex = excel_data.get(codigo)

            if ex is None:
                nao_encontrados.append(f"{codigo} - {linha['colaborador']}")
                continue

            qtd_str = re.sub(r'\D', '', linha['quantidade'])  # só dígitos
            dias_trab = self._calcular_dias_uteis(linha['periodo'])

            registros.append({
                'CNPJ':                        EMPRESA_CNPJ,
                'CEP':                         EMPRESA_CEP,
                'LOGRADOURO':                  EMPRESA_LOGRADOURO,
                'NÚMERO':                      EMPRESA_NUMERO,
                'COMPLEMENTO':                 EMPRESA_COMPLEMENTO,
                'PONTO REFERENCIA':            '',
                'UF':                          EMPRESA_UF,
                'ESTADO':                      EMPRESA_ESTADO,
                'MATRÍCULA':                   codigo,
                'NOME DO FUNCIONÁRIO':         self._sanitizar(linha['colaborador']),
                'CPF':                         ex['CPF'],
                'RG':                          ex['RG'],
                'DATA DE NASCIMENTO':          ex['Data nascimento'],
                'CARGO':                       self._sanitizar(ex['Descrição cargo']),
                'DEPARTAMENTO':                self._sanitizar(ex['Descrição Ccusto']),
                'NOME DA MÃE':                 '',
                'BENEFÍCIO DO FUNCIONÁRIO':    self._sanitizar(linha['administradora']),
                'VALOR UNITÁRIO':              self._limpar_valor_unitario(linha['valor_unitario']),
                'QUANTIDADE DIÁRIA':           qtd_str,
                'PERÍODO DE DIAS TRABALHADOS': str(dias_trab),
                'TIPO VALOR':                  '',
                'REDE RECARGA':                self._sanitizar(linha['administradora']),
                'CEP RESIDENCIAL':             ex['Cep'],
                'LOGRADOURO RESIDENCIAL':      self._sanitizar(ex['Endereço']),
                'NÚMERO RESIDENCIAL':          ex['Numero'],
                'COMPLEMENTO RESIDENCIAL':     self._sanitizar(ex['Complemento']),
                'ESTADO CIVIL':                self._sanitizar(ex['Estado Civil']),
                'DATA DE EMISSÃO DO RG':       '',
                'ÓRGÃO EXPEDIDOR':             self._sanitizar(ex['Orgão RG']),
                'ESTADO EMISSÃO RG':           self._sanitizar(ex['UF RG']),
            })

        return registros, nao_encontrados

    # ── Geração CSV ────────────────────────────────────────────────────

    def _gerar_csv(self, registros, output_path):
        """Grava CSV em latin-1 (;), CRLF. Retorna avisos sobre chars substituídos."""
        avisos = []
        codec = 'latin-1'

        # 1) Sanity check dos nomes de campo — todos presentes e strings?
        for reg in registros:
            mat = reg.get('MATRÍCULA', '?')
            for col in COLUNAS_CSV:
                if col not in reg:
                    reg[col] = ''
                    continue
                if reg[col] is None:
                    reg[col] = ''
                elif not isinstance(reg[col], str):
                    reg[col] = str(reg[col])

            # 2) Detecta caracteres não-latin1 antes de gravar (ficariam '?').
            for col in COLUNAS_CSV:
                val = reg[col]
                problemas = sorted({c for c in val if not _pode_latin1(c)})
                if problemas:
                    avisos.append(
                        f"Matrícula {mat} / {col}: "
                        f"char(s) fora do latin-1 substituído(s) por '?': {problemas}"
                    )

        with open(output_path, 'w', newline='', encoding=codec, errors='replace') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=COLUNAS_CSV,
                delimiter=';',
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL,
                lineterminator='\r\n',
                extrasaction='ignore',
            )
            writer.writeheader()
            writer.writerows(registros)

        return avisos

    # ── Modelos disponíveis ────────────────────────────────────────────

    @staticmethod
    def listar_modelos(api_key):
        from google import genai
        _EXCLUIR = ('tts', 'embedding', 'imagen', 'veo', 'audio', 'lyria',
                    'robotics', 'computer-use', 'deep-research', 'aqa',
                    'clip', 'image', 'live')
        client = genai.Client(api_key=api_key.strip())
        resultado = []
        for m in client.models.list():
            nome = m.name.lower()
            if any(ex in nome for ex in _EXCLUIR):
                continue
            model_id = m.name.split('/')[-1]
            display  = m.display_name or model_id
            resultado.append((display, model_id))
        return resultado

    # ── Verificação IA ─────────────────────────────────────────────────

    def verificar_com_ia(self, registros, nao_encontrados, api_key, model_id='gemini-2.5-flash'):
        try:
            from google import genai
        except ImportError:
            return ['Erro: biblioteca google-genai não instalada. Execute: pip install google-genai']

        if not api_key.strip():
            return ['Erro: API Key não informada.']

        amostra = _mascarar_pii(registros[:50])
        linhas_texto = [
            f"Matrícula={r['MATRÍCULA']} | Nome={r['NOME DO FUNCIONÁRIO']} | "
            f"CPF={r['CPF']} | RG={r['RG']} | AnoNasc={r['DATA DE NASCIMENTO']} | "
            f"CEP={r['CEP']} | ValorUnit={r['VALOR UNITÁRIO']} | "
            f"QtdDiaria={r['QUANTIDADE DIÁRIA']} | PeriodoDias={r['PERÍODO DE DIAS TRABALHADOS']} | "
            f"Beneficio={r['BENEFÍCIO DO FUNCIONÁRIO']} | Cargo={r['CARGO']}"
            for r in amostra
        ]
        sem_corresp = '\n'.join(nao_encontrados) if nao_encontrados else 'Nenhuma'

        prompt = f"""Você é um assistente de RH verificando dados de Vale-Transporte para importação.
CPF e RG foram substituídos por "preenchido"/"vazio" por privacidade.
Analise os registros e reporte APENAS inconsistências reais. Seja objetivo e conciso.

Verifique:
1. Valor Unitário zerado ou vazio
2. Quantidade Diária zerada ou vazia
3. Período de Dias Trabalhados zerado (possível erro no período)
4. CPF, RG ou CEP indicados como "vazio" (campos obrigatórios)
5. Nome com caracteres estranhos ou aparentemente truncado
6. Quantidade Diária numericamente maior que Período de Dias Trabalhados

Registros ({len(amostra)} de {len(registros)} total):
{chr(10).join(linhas_texto)}

Matrículas sem correspondência no cadastro:
{sem_corresp}

Responda em português com lista numerada. Se tudo OK: "Nenhuma inconsistência encontrada."
"""
        try:
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(model=model_id, contents=prompt)
            return response.text.strip().splitlines()
        except Exception as e:
            return [f'Erro ao chamar IA: {e}']

    # ── Orquestrador ───────────────────────────────────────────────────

    def processar(self, pdf_path, xls_path, output_path,
                  progress_cb=None, usar_ia=False, api_key='', model_id='gemini-2.5-flash'):
        def _prog(pct, msg):
            if progress_cb:
                progress_cb(pct, msg)

        _prog(5, 'Lendo PDF...')
        pdf_rows, avisos_pdf = self._extrair_pdf(pdf_path)
        _prog(35, f'PDF: {len(pdf_rows)} linha(s) encontrada(s).')
        for av in avisos_pdf:
            _prog(35, av)
        if pdf_rows:
            _prog(35, f'1º código PDF: {pdf_rows[0]["codigo"]}  |  último: {pdf_rows[-1]["codigo"]}')

        _prog(40, 'Carregando Excel cadastral...')
        excel_data, avisos_xls = self._carregar_excel(xls_path)
        _prog(60, f'Excel: {len(excel_data)} funcionário(s).')
        for av in avisos_xls:
            _prog(60, av)
        if excel_data:
            _prog(60, f'Primeiros códigos Excel: {list(excel_data.keys())[:3]}')

        if not pdf_rows:
            raise ValueError(
                'Nenhuma linha válida foi extraída do PDF VT Caixa. '
                'Verifique se o PDF informado é o relatório correto e se o layout continua compatível com a extração.'
            )

        if not excel_data:
            raise ValueError(
                'Nenhum cadastro válido foi carregado do Excel. '
                'Verifique a aba usada e se a coluna Cód Epr possui dados.'
            )

        _prog(65, 'Cruzando dados...')
        registros, nao_encontrados = self._cruzar_dados(pdf_rows, excel_data)
        _prog(80, f'{len(registros)} correspondência(s) | {len(nao_encontrados)} sem correspondência.')

        if pdf_rows and not registros:
            raise ValueError(
                'Nenhuma correspondência encontrada entre o PDF e o Excel cadastral. '
                'Verifique se o cadastro está na aba correta e se a coluna Cód Epr corresponde aos códigos do PDF.'
            )

        _prog(85, 'Gerando CSV...')
        avisos_csv = self._gerar_csv(registros, output_path)
        for av in avisos_csv:
            _prog(87, f'AVISO encoding: {av}')
        _prog(90, f'CSV salvo em {output_path}')

        alertas_ia = []
        if usar_ia and registros:
            _prog(92, f'Verificando com IA ({model_id})...')
            alertas_ia = self.verificar_com_ia(registros, nao_encontrados, api_key, model_id)

        _prog(100, 'Concluído!')

        return {
            'total_pdf':       len(pdf_rows),
            'total_ok':        len(registros),
            'nao_encontrados': nao_encontrados,
            'alertas_ia':      alertas_ia,
            'avisos_csv':      avisos_csv,
        }
