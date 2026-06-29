# Robo de Conferencia PDF - Financeiro

Automacao local para ler PDFs fiscais, classificar documentos, extrair campos, agrupar processos, validar CNPJ/valores, renomear/unir PDFs e gerar relatorios.

## Estrutura operacional

O programa trabalha na estrutura oficial `13 - PROCESSAMENTO FISCAL`.

```text
13 - PROCESSAMENTO FISCAL
+-- PROCESSOS
|   +-- ANO
|       +-- MES
|           +-- DIA
|               +-- ENTRADA
|               +-- PROCESSADOS
|               +-- COMPLETOS
|               +-- PENDENCIAS
+-- ASSINADOS
+-- PENDENCIAS
+-- RELATORIOS
+-- LOGS
+-- CONFIG
+-- HISTORICO_LEGADO
```

Os PDFs de entrada ficam em `PROCESSOS\ANO\MES\DIA\ENTRADA`. Os processos aprovados sao gerados em `COMPLETOS`, os arquivos tratados em `PROCESSADOS` e os casos com erro ou validacao pendente em `PENDENCIAS`.

## Configuracao

Edite `config/caminhos.json` antes do uso real, principalmente:

```text
base_processamento_fiscal
tesseract_path
usar_data_atual
data_manual
max_workers
```

## Comandos

Dry-run, sem mover nem renomear arquivos:

```bash
python -m app.main --dry-run
```

Execucao real:

```bash
python -m app.main
```

Testes:

```bash
python -m pytest -q
```

## Publicacao no GitHub

Nao versionar PDFs reais, relatorios gerados, logs, caches, bases temporarias ou dados sensiveis de documentos fiscais.

Antes de publicar, conferir se permanecem fora do Git:

```text
saida/
logs/
.cache/
.pytest_cache/
.pytest_tmp/
*.zip
*.log
*.tmp.log
.env
```
