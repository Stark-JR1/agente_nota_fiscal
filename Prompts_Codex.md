# PROMPTS_CODEX.md

# Objetivo

Biblioteca de prompts padronizados para reduzir tokens.

---

# Correção de Bug

```text
Leia AGENTS.md e ARQUITETURA.md.

Problema:
[DESCREVER BUG]

Arquivos permitidos:
[ARQUIVO 1]
[ARQUIVO 2]

Não alterar outros módulos.

Executar testes.

Retornar:
- Arquivos alterados
- Motivo
- Resultado dos testes
```

---

# Nova Funcionalidade

```text
Leia AGENTS.md, ARQUITETURA.md e MELHORIAS.md.

Executar somente item:
[M001]

Arquivos permitidos:
[LISTA]

Não alterar outros módulos.

Executar testes.

Retornar:
- Arquivos alterados
- Resultado dos testes
- Riscos
```

---

# Ajuste Visual

```text
Leia AGENTS.md e ARQUITETURA.md.

Objetivo:
Alterar somente interface.

Arquivos permitidos:
templates/
static/

Não alterar:
services/
validators/
grouping/

Executar validação visual.
```

---

# Refatoração

```text
Leia AGENTS.md e ARQUITETURA.md.

Objetivo:
Refatorar apenas módulo informado.

Arquivos permitidos:
[ARQUIVOS]

Proibido:
Alterar regras fiscais.

Executar testes.

Retornar impacto.
```

---

# Auditoria

```text
Leia AGENTS.md e ARQUITETURA.md.

Auditar:

[ARQUIVO]

Retornar:

- Problemas encontrados
- Código morto
- Duplicidade
- Gargalos
- Melhorias

Não alterar código.
```

---

# Economia de Tokens

Nunca:

```text
Analise o projeto inteiro
Refatore tudo
Melhore tudo
```

Sempre:

```text
Executar item específico
Alterar módulo específico
Corrigir problema específico
```
# Estabilizacao final

```text
Corrigir somente falhas de execucao e caminho fisico.
Abrir PDF por caminho_original.
Usar nome_normalizado somente na saida.
Isolar erro por processo.
Marcar arquivo ausente como PENDENTE_ERRO_ARQUIVO.
Nao alterar regra fiscal, OCR, agrupamento, validacao ou historico.
```
