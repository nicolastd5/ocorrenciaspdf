# Design: Dupla Verificação + IA em Ocorrências

**Data:** 2026-04-29
**Status:** Aprovado

---

## Resumo

Adicionar duas camadas opcionais de verificação ao processamento de ocorrências:
1. **Dupla varredura** — segunda extração independente do PDF usando método diferente (texto + regex, em vez de tabelas)
2. **IA (Gemini Vision)** — terceira camada que envia páginas do PDF como imagem ao Gemini e pede a lista de ocorrências por RE

Quando há divergência entre camadas ativas, o usuário decide manualmente qual valor usar antes de gravar. Quando todas concordam, processa automaticamente.

---

## Arquitetura

### Novos métodos em `processador.py`

#### `extrair_ocorrencias_texto(pdf_path, codigos_alvo) → dict`
Segunda varredura. Usa `page.extract_text()` por página + regex posicional para encontrar ocorrências, sem depender da detecção de tabelas do pdfplumber. Retorna o mesmo formato do método atual:
```
{re: {'nome': str, 'ocorrencias': {codigo: contagem}}}
```

Estratégia de parsing:
- Para cada página, extrai o texto bruto
- Identifica linhas que começam com RE numérico (regex `^\d{5,}`)
- Varre os tokens da linha procurando códigos do `codigos_alvo`
- Acumula contagens por RE

#### `verificar_com_ia(pdf_path, codigos_alvo, api_key, modelo) → dict | None`
Terceira camada, opcional. Converte cada página do PDF em imagem PNG usando `pypdfium2` (já no projeto). Envia as imagens ao Gemini Vision com prompt estruturado:

> "Liste todas as ocorrências encontradas nesta folha de ponto. Para cada linha com RE numérico, informe o RE, o nome e a contagem de cada código presente (códigos: FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13). Responda apenas em JSON no formato: [{re, nome, ocorrencias: {codigo: contagem}}]"

Retorna o mesmo formato dos outros métodos, ou `None` em caso de erro (timeout, quota, formato inválido).

#### `reconciliar(resultados: list[dict], codigos_alvo) → dict`
Recebe lista de 2 ou 3 dicts de resultados (camadas ativas). Retorna:
```python
{
  'concordantes': {re: {'nome': str, 'ocorrencias': {codigo: contagem}}},
  'conflitos': [
    {
      're': str,
      'nome': str,
      'codigo': str,
      'valores': {'v1': int, 'v2': int, 'ia': int | None},
      'sugestao': int  # valor com mais votos, pré-selecionado na UI
    }
  ]
}
```

Lógica de conflito: para cada RE e código, se os valores das camadas ativas não são todos iguais → conflito. A `sugestao` é o valor mais frequente entre as camadas (maioria). Se empate, usa o valor mais alto.

### Fluxo de processamento atualizado

```
1. Varredura 1 (tabelas) — sempre
2. Varredura 2 (texto/regex) — se modo dupla ou dupla+IA
3. Varredura 3 (Gemini Vision) — se modo dupla+IA
4. Reconciliar(camadas ativas)
   → se conflitos: abrir modal de resolução
   → se sem conflitos: continuar direto
5. processar() com dados reconciliados — igual ao fluxo atual
```

O método `processar()` existente não muda sua assinatura. Recebe o dict de resultados já resolvido (concordantes + escolhas do usuário).

---

## Interface

### Card "🔍 Verificação" na aba Processar

Novo card abaixo do card de códigos. Três chips de seleção exclusiva (radio):

| Chip | Comportamento |
|------|--------------|
| Varredura única | Comportamento atual, sem mudança |
| Dupla varredura | Roda V1 + V2, reconcilia antes de gravar |
| Dupla + IA (Gemini) | Roda V1 + V2 + V3, reconcilia |

Quando "Dupla + IA" selecionado, expande um subpainel com:
- Campo de API Key (salvo em `~/.ocorrencias_config.json` sob `gemini_api_key_ocorrencias`)
- Combobox de modelo (populado via botão "Carregar modelos", igual ao VT Caixa)
- Último modelo usado é lembrado na config local

### Modal de conflitos (nova janela)

Abre antes de gravar quando `reconciliar` retorna conflitos. Bloqueia a janela principal (`grab_set`).

Layout:
- Título: "Conflitos encontrados — X item(s) precisam de revisão"
- Para cada conflito: card com RE, nome, código e botões de escolha lado a lado mostrando o valor de cada camada
  - Ex: `[2 AT — V1]  [1 AT — V2]  [2 AT — IA]`
  - Sugestão pré-selecionada (highlight em accent)
- Botão "Confirmar e gravar" — aplica escolhas e continua fluxo normal
- Botão "Cancelar" — aborta sem gravar nada

### Tela de resumo (adição)

Novo bloco "Verificação" no resumo existente mostrando:
- Modo usado (única / dupla / dupla+IA)
- Nº de REs concordantes automáticos
- Nº de conflitos resolvidos manualmente (0 se nenhum)
- Indicador se IA foi usada ou caiu para fallback

### Etapas de progresso (adição)

Quando verificação ativa, janela de progresso ganha etapas extras entre "Lendo PDF" e "Abrindo planilha":
- "Varredura 2 (texto)..."
- "Verificando com IA..." (só se modo IA)
- "Reconciliando..."

---

## Tratamento de erros

| Situação | Comportamento |
|----------|--------------|
| IA sem API key | Modo cai para dupla varredura; aviso no resumo |
| IA timeout / quota esgotada | Mesmo: cai para dupla; aviso no resumo |
| IA retorna JSON inválido | Descarta resposta da IA; processa como dupla |
| V2 não encontra nenhum RE | Avisa usuário com opção de continuar com varredura única |
| V2 encontra REs mas com divergência total | Abre modal normalmente |

---

## Configuração persistida

Chaves adicionadas ao `~/.ocorrencias_config.json`:
- `gemini_api_key_ocorrencias` — API Key do Gemini para ocorrências (separada da do VT Caixa)
- `gemini_modelo_ocorrencias` — último modelo selecionado

---

## Dependências

- `pypdfium2` — já presente no projeto (usado pelo VT Caixa)
- `google-generativeai` — já presente no projeto (usado pelo VT Caixa)
- Nenhuma dependência nova necessária

---

## O que NÃO muda

- Assinatura e comportamento do método `processar()` com varredura única
- Fluxo completo da aba VT Caixa
- Formato do histórico de ocorrências
- Todos os códigos existentes (FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13)
