# Processador de Ocorrências

Aplicação desktop para Windows que extrai ocorrências de PDFs de jornada de trabalho e preenche automaticamente a coluna **MOTIVO** em planilhas Excel de pedido.

---

## O que o programa faz

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

---

## Requisitos da planilha Excel

- Deve conter uma coluna chamada exatamente **`Folha Re`** com os números de matrícula
- Deve conter uma coluna chamada exatamente **`MOTIVO`** onde o programa irá escrever

---

## Tecnologias

- Python 3
- tkinter (interface gráfica)
- pdfplumber (leitura de PDF)
- openpyxl (leitura e escrita de Excel)
- PyInstaller (geração do executável)

---

## Autor

**Nicolas Almeida Hader Dias**

Versão atual: **1.16**
