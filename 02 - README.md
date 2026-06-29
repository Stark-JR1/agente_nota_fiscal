# Robo de Conferencia PDF - Financeiro

Automacao local para ler PDFs fiscais, classificar documentos, extrair campos, agrupar processos, validar CNPJ/valores, renomear/unir PDFs e gerar relatorios.

## Como executar

```bash
python -m app.main
```

Modo de teste, sem mover nem renomear arquivos:

```bash
python -m app.main --dry-run
```

## Configuracao

Edite `config/caminhos.json` antes do uso real, principalmente `base_financeiro` e `tesseract_path`.

O programa procura PDFs na pasta do dia dentro de `01 - I LOVE PDF` e envia processos aprovados para `02 - CINTIA`.
