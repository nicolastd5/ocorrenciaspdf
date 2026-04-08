# Processador de Ocorrências

Aplicação desktop para Windows que extrai ocorrências de PDFs de jornada de trabalho e preenche automaticamente planilhas Excel com dados processados. Inclui processador padrão para preenchimento de **MOTIVO** e processador especializado para **VT Caixa** com assistência de IA.

---

## O que o programa faz

### Processador Padrão (Ocorrências)

1. **Lê um PDF de jornada de trabalho** e identifica as ocorrências de cada funcionário (faltas, atestados, afastamentos, etc.)
2. **Cruza os dados com uma planilha Excel** usando o número de matrícula (RE) como chave
3. **Preenche a coluna MOTIVO** automaticamente na planilha com os códigos encontrados
4. **Gera uma planilha nova** com os dados atualizados, sem alterar o arquivo original
5. **Exibe um resumo** ao final com estatísticas e lista de pessoas não localizadas na planilha

---

## Códigos de ocorrência suportados

| Código | Descrição               | Quantidade |
|--------|-------------------------|------------|
| AT     | Atestado                | Sim        |
| FA     | Faltas                  | Sim        |
| LC     | Licença Casamento       | Sim        |
| SD     | Suspensão Disciplinar   | Sim        |
| AA     | Ausência Autorizada     | Sim        |
| AP     | Afastamento Previdenciário | Não     |
| LM     | Afastamento Maternidade | Não        |
| FE     | Férias                  | Não        |

Códigos marcados como **Sem quantidade** aparecem apenas com o código (ex: `AP`), sem número na frente. Os demais exibem a quantidade quando maior que 1 (ex: `2 AT, FA`).

---

## Requisitos da planilha Excel (Processador Padrão)

- Deve conter uma coluna chamada exatamente **`Folha Re`** com os números de matrícula
- Deve conter uma coluna chamada exatamente **`MOTIVO`** onde o programa irá escrever

---

## Como usar

1. Abra o programa `ProcessadorOcorrencias.exe`
2. Na aba **Processar**:
   - Selecione o **PDF de faltas** (jornada de trabalho)
   - Selecione a **planilha Excel** de pedido (deve conter colunas `Folha Re` e `MOTIVO`)
   - Marque os códigos de ocorrência desejados
   - Clique em **PROCESSAR ARQUIVOS**
3. Escolha onde salvar a planilha atualizada
4. Aguarde — uma janela de progresso mostrará o andamento
5. Ao concluir, um resumo exibe os resultados e lista quem não foi localizado na planilha

Na aba **Histórico** você pode consultar os resultados dos processamentos anteriores da sessão.

### Processador VT Caixa

1. Abra o programa e vá para a aba **VT Caixa**
2. Configure sua **API Key do Google Gemini** — será armazenada localmente e usada para análise com IA
3. Selecione o **arquivo CSV cadastral** (com dados dos funcionários)
4. Selecione o **PDF de jornada** (com datas e ocorrências)
5. Escolha o **modelo de IA** (padrão: Gemini 2.5 Flash — otimizado para custo-benefício)
6. Marque os campos desejados (CNPJ, Data de Emissão do RG, Data de Nascimento, etc.)
7. Clique em **PROCESSAR ARQUIVOS**
8. A IA analisará os dados e gerará um novo CSV com os campos preenchidos

A IA verifica automaticamente:
- Consistência de dados entre PDF e cadastro
- Quantidade diária vs. período trabalhado
- Extração correta de nomes e datas
- Preenchimento de campos adicionais do cadastro (CNPJ, CPF, RG, datas, endereço, etc.)

---

## Configuração

### Variáveis de Ambiente (opcional)
- `GOOGLE_API_KEY`: Define a API key padrão do Google Gemini para VT Caixa (evita precisar digitar toda vez)

### Arquivo de Configuração Local
A aplicação salva preferências em `~/.ocorrencias_config.json`:
- API key usada (local e não versionado — não é sincronizado no git)
- Últimos diretórios acessados
- Preferências de UI

## Tecnologias

- Python 3.10+
- tkinter (interface gráfica)
- pdfplumber (leitura de PDF)
- openpyxl (leitura e escrita de Excel)
- xlrd (leitura de arquivos cadastrais)
- Google Gemini API (análise com IA no processador VT Caixa)
- PyInstaller (geração do executável)

---

## Autor

**Nicolas Almeida Hader Dias**

Versão atual: **1.22**
