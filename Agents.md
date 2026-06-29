# AGENTS.md

## Projeto

Robô Fiscal de Conferência de PDFs.

Objetivo do sistema:

* Ler PDFs fiscais.
* Classificar documentos.
* Identificar NF, NFS-e, boleto, pedido, CT-e, contrato e anexos.
* Agrupar documentos do mesmo processo.
* Validar com base no Pedido de Compra.
* Gerar arquivos tratados, processos completos, pendências, relatórios e logs.
* Trabalhar na estrutura `13 - PROCESSAMENTO FISCAL`.

---

## Regras obrigatórias para o Codex

Antes de qualquer alteração:

1. Ler este arquivo.
2. Ler `ARQUITETURA.md`.
3. Ler apenas os arquivos necessários para a tarefa.
4. Não analisar o projeto inteiro sem necessidade.
5. Não alterar arquivos fora do escopo solicitado.

---

## Nunca alterar sem autorização

Não alterar:

* Estrutura de pastas oficial.
* Regras fiscais principais.
* Validação Pedido x NF x Boleto.
* OCR principal.
* Histórico legado.
* Arquivos dentro de `HISTORICO_LEGADO`.
* Dashboard, se a tarefa não for visual.
* Integração ZapSign, pois não será implementada agora.
* Integração Planner, salvo pedido explícito.

---

## Pastas oficiais

Base operacional:

```text
13 - PROCESSAMENTO FISCAL
├── PROCESSOS
├── ASSINADOS
├── PENDENCIAS
├── RELATORIOS
├── LOGS
├── CONFIG
└── HISTORICO_LEGADO
```

Fluxo do dia:

```text
PROCESSOS\ANO\MES\DIA
├── ENTRADA
├── PROCESSADOS
├── COMPLETOS
└── PENDENCIAS
```

---

## Regra de negócio principal

O Pedido de Compra é o documento mestre.

Hierarquia:

```text
Pedido de Compra
↓
Nota Fiscal
↓
Boleto
```

O robô deve validar:

* CNPJ fornecedor.
* CNPJ Sistermi.
* Número do pedido.
* Valor do pedido.
* Valor da NF.
* Valor do boleto ou soma dos boletos.
* Compatibilidade entre documentos.

---

## Como trabalhar para economizar tokens

Quando receber uma tarefa:

1. Identificar o módulo afetado.
2. Ler somente os arquivos relacionados.
3. Fazer patch pequeno.
4. Criar ou ajustar teste.
5. Rodar testes.
6. Resumir exatamente o que foi alterado.

Evitar:

```text
"Vou analisar todo o projeto"
```

Preferir:

```text
"Vou analisar apenas app/services/processamento_service.py"
```

---

## Comandos padrão

Rodar testes:

```bash
python -m pytest -q
```

Dry-run operacional:

```bash
python -m app.main --dry-run
```

Execução real:

```bash
python -m app.main
```

Indexação histórica:

```bash
python -m app.tools.historico_builder --dry-run
```

---

## Critério de entrega

Toda alteração deve informar:

* Arquivos alterados.
* Motivo da alteração.
* Testes executados.
* Resultado dos testes.
* Risco da alteração.
* Próximo passo recomendado.
# Estabilizacao final

- `caminho_original` abre, le, copia e unifica PDFs.
- `nome_normalizado` serve somente para arquivos de saida.
- Falha individual nao interrompe o lote.
- Arquivo fisico ausente gera `PENDENTE_ERRO_ARQUIVO`.
