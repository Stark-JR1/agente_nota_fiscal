# PATCH FINAL - ESTABILIZAÇÃO, LIMPEZA E CORREÇÃO DE BUGS

## Objetivo

Finalizar o projeto sem criar funcionalidades novas.

Não inventar novos módulos.

Não integrar ZapSign.

Não integrar Planner.

Não alterar regra fiscal.

Não alterar fluxo principal.

Foco exclusivo:

```text
corrigir bugs
corrigir caminhos
remover código morto
limpar arquivos desnecessários
melhorar manutenção
garantir testes passando
```

---

# Escopo permitido

Pode alterar somente se necessário:

```text
app/services/processamento_service.py
app/paths.py
app/models/documento.py
app/services/arquivo_service.py
app/web/
templates/
static/
.gitignore
requirements.txt
```

Evitar mexer em:

```text
validators/
extractors/
grouping/
ocr.py
classificador.py
historico_builder.py
```

A menos que algum teste quebre diretamente nesses módulos.

---

# Tarefa 1 - Corrigir bug de caminho físico

## Problema

Durante execução real, o sistema aprovou processos, mas falhou ao gerar arquivos:

```text
FileNotFoundError
```

Causa provável:

O sistema está reconstruindo caminho usando nome normalizado.

Regra correta:

```text
caminho original = usado para abrir arquivo
nome normalizado = usado apenas para salvar saída
```

## Proibido

Não fazer:

```python
origem = pasta_entrada / documento.nome_normalizado
```

## Correto

Usar algo como:

```python
origem = documento.caminho_original
```

ou campo equivalente já existente.

## Validar

Antes de abrir PDF:

```python
if not Path(origem).exists():
    registrar log com:
        caminho_original
        nome_original
        nome_final
    mover processo para pendência técnica
    não quebrar execução inteira
```

O programa não deve parar todo o lote por causa de 1 arquivo.

---

# Tarefa 2 - Não quebrar lote inteiro

Se um processo aprovado falhar na geração de PDF:

```text
não derrubar o programa
```

Deve virar:

```text
PENDENTE_ERRO_ARQUIVO
```

Com motivo:

```text
Arquivo físico não encontrado
```

E o robô deve continuar processando os demais processos.

---

# Tarefa 3 - Limpeza segura

Remover do repositório:

```text
__pycache__/
.pytest_cache/
*.pyc
*.pyo
static.zip
flask_stdout.tmp.log
flask_stderr.tmp.log
```

Remover apenas se forem artefatos locais:

```text
.cache/
logs/
saida/
```

Não remover se forem necessários em teste versionado.

---

# Tarefa 4 - Atualizar .gitignore

Garantir:

```gitignore
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.cache/
logs/
saida/
.venv/
venv/
.env
*.log
*.tmp.log
*.zip
Thumbs.db
.DS_Store
```

---

# Tarefa 5 - Verificar web_legacy.py

Verificar se existe importação de:

```text
app/web_legacy.py
```

Se não houver uso:

```text
remover
```

Se houver uso:

```text
manter e documentar onde é usado
```

Não migrar nada agora.

---

# Tarefa 6 - Padronizar documentação

Garantir que existam na raiz:

```text
AGENTS.md
ARQUITETURA.md
MELHORIAS.md
DECISOES.md
PROMPTS_CODEX.md
```

Se os nomes estiverem como:

```text
Agents.md
Arquitetura.md
Melhorias.md
```

renomear para maiúsculo padronizado.

---

# Tarefa 7 - Testes obrigatórios

Rodar:

```bash
python -m pytest -q
```

Esperado:

```text
38 passed
```

Depois rodar:

```bash
python -m app.main --dry-run
```

Depois, com lote pequeno:

```bash
python -m app.main
```

---

# Critério de aceite

Finalizar apenas quando:

```text
[ ] 38 testes passarem
[ ] dry-run funcionar
[ ] execução real não quebrar lote inteiro
[ ] processos aprovados gerarem arquivos
[ ] pendências forem separadas corretamente
[ ] .gitignore atualizado
[ ] pycache removido
[ ] zip/log temporário removido
[ ] web_legacy.py verificado
[ ] documentação padronizada
```

---

# Proibido nesta etapa

Não criar:

```text
novas funcionalidades
novas integrações
novo dashboard
novo banco
novo fluxo
nova estrutura de pastas
```

Este patch é apenas de estabilização final.
