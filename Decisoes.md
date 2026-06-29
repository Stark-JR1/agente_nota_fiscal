# DECISOES.md

# Objetivo

Registrar decisões definitivas do projeto.

O Codex deve consultar este arquivo antes de sugerir mudanças estruturais.

---

# Estrutura Oficial

A estrutura oficial do projeto é:

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

Não sugerir novas estruturas sem autorização.

---

# Histórico

O histórico foi migrado para:

```text
HISTORICO_LEGADO
├── 01 - BRUTO
├── 02 - PROCESSADO
└── 03 - ASSINADO
```

Total aproximado:

```text
31.500 PDFs
```

Não mover.

Não renomear.

Não apagar.

---

# ZapSign

Integração NÃO será implementada agora.

Motivo:

Processo ainda depende de decisão humana.

---

# Planner

Integração NÃO será implementada agora.

Motivo:

Prioridade menor que auditoria fiscal.

---

# Dashboard

Tecnologia oficial:

```text
Flask
```

Não utilizar:

```text
Streamlit
```

---

# OCR

OCR somente quando:

```text
Texto digital não disponível.
```

Prioridade:

```text
Texto digital
↓
OCR
```

---

# Pedido de Compra

Documento mestre do processo.

Hierarquia:

```text
Pedido
↓
NF
↓
Boleto
```

---

# Histórico Inteligente

O histórico serve para:

```text
Sugerir
Auxiliar
Normalizar
```

Nunca para:

```text
Aprovar automaticamente
```

---

# Regras de Segurança

Nunca:

* Apagar PDFs.
* Mover PDFs históricos.
* Renomear PDFs históricos.
* Alterar banco histórico sem backup.
* Modificar estrutura fiscal sem autorização.

---

# Regra Final

Sempre corrigir o menor módulo possível.

Evitar refatorações globais.
# Caminho fisico e nome de saida

- Abrir e ler PDF somente pelo `caminho_original`.
- Usar `nome_normalizado` somente na saida.
- Nao reconstruir entrada a partir do fornecedor ou nome final.
- Manter o lote em execucao quando um processo individual falhar.
