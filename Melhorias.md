# MELHORIAS.md

## Como usar este arquivo

Este arquivo é o backlog oficial do projeto.

O Codex deve executar apenas o item solicitado.

Não executar vários itens de uma vez.

Formato recomendado de pedido:

```text
Execute somente o item M001.
Arquivos permitidos:
- app/services/processamento_service.py
Não alterar outros módulos.
```

---

# Prioridade Alta

## M001 - Corrigir FileNotFoundError na geração de aprovados

Problema:

O sistema aprova o processo, mas falha ao gerar PDF individual/final porque tenta abrir arquivo usando nome reconstruído.

Sintoma:

```text
FileNotFoundError
```

Regra:

* Usar sempre `caminho_original` para abrir arquivo.
* Usar nome normalizado apenas para salvar saída.

Arquivos prováveis:

```text
app/services/processamento_service.py
app/models/documento.py
```

Critério de aceite:

```text
python -m app.main --dry-run
python -m app.main
```

Processos aprovados devem gerar arquivos em PROCESSADOS e COMPLETOS.

---

## M002 - Melhorar log de processo aprovado

Problema:

O log informa aprovado, mas não mostra claramente quais arquivos compõem o processo.

Adicionar no log:

* ID do processo.
* Fornecedor.
* NF.
* Pedido.
* Valor.
* Arquivos usados.
* Pasta de saída.

Arquivos prováveis:

```text
app/services/processamento_service.py
app/relatorio.py
```

---

## M003 - Melhorar relatório de pendências

Problema:

Relatório precisa mostrar motivo claro.

Adicionar colunas:

* Motivo principal.
* Motivos detalhados.
* Arquivos envolvidos.
* Ação recomendada.
* Valor NF.
* Valor pedido.
* Valor boleto.
* Diferença.

Arquivos prováveis:

```text
app/relatorio.py
app/services/processamento_service.py
```

---

## M004 - Criar score de auditoria do processo

Objetivo:

Cada processo deve ter score de 0 a 100.

Critérios:

* Fornecedor identificado.
* CNPJ confere.
* Pedido localizado.
* NF localizada.
* Boleto localizado.
* Valor PC = NF.
* Valor NF = boleto.
* OCR confiável.

Classificação:

```text
90 a 100 = BAIXO_RISCO
70 a 89 = MEDIO_RISCO
0 a 69 = ALTO_RISCO
```

Arquivos prováveis:

```text
app/validators/processo_validator.py
app/services/processamento_service.py
```

---

## M005 - Usar histórico como sugestão, não como regra

Objetivo:

Usar `CONFIG/fornecedores.json` e `CONFIG/regras.json` para sugerir padrões.

Não aprovar automaticamente por histórico.

Usar para:

* Normalizar nome de fornecedor.
* Sugerir regra recorrente.
* Ajudar classificação.
* Melhorar tela.

Arquivos prováveis:

```text
app/services/processo_service.py
app/grouping/
app/validators/
```

---

# Prioridade Média

## M006 - Melhorar OCR em documentos escaneados problemáticos

Problema:

Alguns PDFs escaneados extraem valores errados.

Melhorar:

* Pré-processamento de imagem.
* Threshold.
* Rotação.
* Confiança.
* Separação entre valor real e número aleatório.

Arquivos prováveis:

```text
app/ocr.py
app/leitor_pdf.py
app/extractors/
```

---

## M007 - Watchdog para monitorar ENTRADA

Objetivo:

Processar automaticamente quando novo PDF entrar na pasta.

Regras:

* Aguardar arquivo estabilizar.
* Não processar arquivo incompleto do OneDrive.
* Permitir ativar/desativar por config.

Arquivos prováveis:

```text
app/watchers/folder_watcher.py
app/config.py
```

---

## M008 - Melhorar dashboard operacional

Adicionar cards:

* Processos do dia.
* Aprovados.
* Pendentes.
* Valor processado.
* Erros por tipo.
* Último processamento.
* Tempo de execução.

Arquivos prováveis:

```text
app/web/
templates/
static/
```

---

## M009 - Melhorar tela detalhe do processo

Layout desejado:

```text
25% painel lateral
75% visualizador PDF
```

Painel lateral:

* Status.
* Validações.
* Documentos.
* Confiabilidade.
* Resumo.

Área principal:

* PDF Viewer com abas NF, Boleto, Pedido e PDF Final.

Arquivos prováveis:

```text
templates/
static/
app/web/
```

---

# Prioridade Baixa

## M010 - Integração Planner

Objetivo futuro:

Criar tarefa no Planner para pendências.

Não implementar agora sem pedido explícito.

---

## M011 - Integração ZapSign

Objetivo futuro:

Enviar processos aprovados para assinatura.

Não implementar agora sem pedido explícito.

---

## M012 - Exportação gerencial mensal

Criar relatório mensal consolidado.

Dados:

* Total processado.
* Top fornecedores.
* Pendências.
* Valores.
* Status.

---

## M013 - Remover wrappers mortos com testes

Objetivo futuro:

Identificar wrappers Python sem uso real e remover somente com cobertura de testes.

Nao executar agora.

---

## M014 - Separar web_legacy.py

Objetivo futuro:

Dividir a interface Flask legada em rotas, helpers e servicos menores, preservando comportamento.

Nao executar agora.

---

## M015 - Dividir extrator_campos.py

Objetivo futuro:

Separar extracao por tipo documental e reduzir a funcao principal de extracao.

Nao executar agora.

---

## M016 - Dividir validador.py

Objetivo futuro:

Separar validacoes de CNPJ, valores, pedidos e excecoes em modulos menores.

Nao executar agora.

---

## M017 - Dividir agrupador.py

Objetivo futuro:

Separar regras de agrupamento, similaridade, multiplos pedidos e boletos parcelados.

Nao executar agora.

---

## M018 - Otimizar dashboard

Objetivo futuro:

Reduzir releituras e melhorar o desempenho da interface sem alterar regras fiscais.

Nao executar agora.

---

# Regras para executar melhorias

Sempre:

```text
1. Ler AGENTS.md
2. Ler ARQUITETURA.md
3. Executar somente item solicitado
4. Alterar poucos arquivos
5. Rodar testes
6. Informar resultado
```

Nunca:

```text
- Refatorar tudo junto
- Alterar regra fiscal sem pedido
- Mexer em histórico legado
- Apagar PDFs
- Renomear arquivos históricos
- Integrar ZapSign sem autorização
- Integrar Planner sem autorização
```
# Status M001

- Leitura e unificacao usam caminho fisico original.
- Arquivo ausente gera `PENDENTE_ERRO_ARQUIVO`.
- Erro individual nao interrompe o lote.
- Validacao: testes, dry-run e execucao real com lote pequeno.
