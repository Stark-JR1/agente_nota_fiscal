from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


NOME_ARQUIVO = "ultima_execucao.json"


def registrar_execucao(
    pasta_logs: Path,
    inicio: datetime,
    fim: datetime,
    total_arquivos: int,
    processos: list[dict],
    erros: int = 0,
) -> Path:
    aprovados = sum(1 for processo in processos if processo.get("status") == "APROVADO")
    dados = {
        "inicio": inicio.isoformat(timespec="seconds"),
        "fim": fim.isoformat(timespec="seconds"),
        "duracao_segundos": round((fim - inicio).total_seconds(), 2),
        "arquivos_encontrados": total_arquivos,
        "arquivos_processados": total_arquivos,
        "processos_aprovados": aprovados,
        "processos_pendentes": len(processos) - aprovados,
        "erros_encontrados": erros,
    }
    pasta_logs.mkdir(parents=True, exist_ok=True)
    destino = pasta_logs / NOME_ARQUIVO
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(destino)
    return destino


def carregar_ultima_execucao(pasta_logs: Path) -> dict:
    caminho = pasta_logs / NOME_ARQUIVO
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
