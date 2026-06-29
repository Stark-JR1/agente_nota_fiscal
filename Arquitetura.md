# ARQUITETURA.md

## Visão geral

Este projeto é um robô fiscal em Python com interface Flask.

Ele processa documentos fiscais em PDF, classifica documentos, agrupa processos e gera saídas organizadas para conferência financeira.

---

## Estrutura principal do código

```text
app/
├── main.py
├── config.py
├── paths.py
├── leitor_pdf.py
├── ocr.py
├── classificador.py
├── extrator_campos.py
├── agrupador.py
├── validador.py
├── renomeador.py
├── unificador.py
├── relatorio.py
├── utils.py
├── services/
├── models/
├── validators/
├── extractors/
├── grouping/
├── web/
├── watchers/
└── tools/
```

---

## Responsabilidades

### `app/main.py`

Ponto de entrada do robô via terminal.

Deve apenas:

* Carregar configuração.
* Receber argumentos.
* Chamar o serviço de processamento.
* Exibir resumo.

Não deve conter regra fiscal pesada.

---

### `app/services/processamento_service.py`

Orquestra o fluxo principal:

* Lê arquivos da ENTRADA.
* Classifica páginas/documentos.
* Agrupa processos.
* Valida.
* Gera arquivos aprovados.
* Separa pendências.
* Gera relatórios.

É o módulo crítico da execução.

---

### `app/paths.py`

Centraliza caminhos.

Deve ser a única fonte para montar:

```text
PROCESSOS
ASSINADOS
PENDENCIAS
RELATORIOS
LOGS
CONFIG
HISTORICO_LEGADO
```

Não montar caminhos manualmente em outros módulos.

---

### `app/leitor_pdf.py`

Responsável por leitura de PDFs.

Fluxo:

1. Tentar texto digital.
2. Se insuficiente, usar OCR.
3. Retornar páginas com texto, origem e confiança.

---

### `app/ocr.py`

Responsável por OCR.

Não usar OCR quando texto digital for suficiente.

OCR é caro e deve ser usado com cuidado.

---

### `app/classificador.py`

Classifica documentos:

* NF_PRODUTO
* NF_SERVICO
* BOLETO
* PEDIDO_COMPRA
* DACTE
* CONTRATO
* RECIBO
* OUTRO_ANEXO
* DESCONHECIDO

---

### `app/extractors/`

Extratores por tipo de documento.

Cada extrator deve cuidar de apenas um tipo documental.

Exemplo:

```text
nf_produto_extractor.py
nf_servico_extractor.py
boleto_extractor.py
pedido_extractor.py
```

---

### `app/validators/`

Validações específicas.

Separar regras por responsabilidade:

* CNPJ.
* Valor.
* Pedido.
* Exceções.
* Processo.

---

### `app/grouping/`

Agrupamento de documentos em processos.

Cuida de:

* Chaves de agrupamento.
* Similaridade de fornecedor.
* Múltiplos pedidos.
* Boletos parcelados.
* Junção de documentos compatíveis.

---

### `app/renomeador.py`

Gera nomes finais dos arquivos.

Padrões:

```text
FORNECEDOR - NF NUMERO - TIPO.pdf
FORNECEDOR - NF NUMERO - R$ VALOR - PROCESSO COMPLETO.pdf
```

---

### `app/unificador.py`

Une PDFs do mesmo processo.

Ordem recomendada:

```text
NF
Boleto
Pedido
Outros anexos
```

---

### `app/relatorio.py`

Gera relatórios:

* Processamento.
* Pendências.
* Resumo.
* Histórico.

---

### `app/web/`

Interface Flask.

Deve conter apenas rotas, helpers visuais e montagem de dados para tela.

Não colocar regra fiscal dentro da camada web.

---

### `app/tools/historico_builder.py`

Indexação histórica.

Função:

* Ler `HISTORICO_LEGADO`.
* Gerar banco histórico.
* Gerar estatísticas.
* Atualizar fornecedores e regras sugeridas.

Não deve mover, apagar ou renomear arquivos históricos.

---

## Estrutura de pastas operacional

```text
13 - PROCESSAMENTO FISCAL
├── PROCESSOS
│   └── ANO
│       └── MES
│           └── DIA
│               ├── ENTRADA
│               ├── PROCESSADOS
│               ├── COMPLETOS
│               └── PENDENCIAS
├── ASSINADOS
├── PENDENCIAS
├── RELATORIOS
├── LOGS
├── CONFIG
└── HISTORICO_LEGADO
```

---

## Fluxo operacional

```text
ENTRADA
↓
Leitura PDF
↓
OCR, se necessário
↓
Classificação
↓
Extração de campos
↓
Agrupamento
↓
Validação
↓
PROCESSADOS / COMPLETOS / PENDENCIAS
↓
RELATORIOS / LOGS
```

---

## Regra crítica de caminhos

Nunca reconstruir caminho físico de arquivo usando nome normalizado.

Errado:

```python
origem = pasta_entrada / documento.nome_normalizado
```

Correto:

```python
origem = documento.caminho_original
```

O nome normalizado serve para saída.

O caminho original serve para leitura.

---

## Testes obrigatórios

Antes de finalizar qualquer alteração:

```bash
python -m pytest -q
```

Para testar fluxo real sem mover arquivos:

```bash
python -m app.main --dry-run
```

Para execução real:

```bash
python -m app.main
```
# Interface Flask atual

`app/web_legacy.py` permanece em uso: o pacote `app/web/` importa a aplicacao
e as rotas desse arquivo durante a migracao gradual.

# Tratamento de erro por processo

Erros de leitura ou geracao sao isolados. O lote continua e o processo afetado
recebe `PENDENTE_ERRO_ARQUIVO`.
