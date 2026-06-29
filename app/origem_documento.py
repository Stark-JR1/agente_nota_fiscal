from __future__ import annotations

import logging
from pathlib import Path


def caminho_fisico_documento(documento: dict) -> Path:
    caminho_original = documento.get("caminho_original") or documento.get("arquivo_origem")
    origem = Path(str(caminho_original or ""))
    logging.info("Abrindo arquivo: %s", origem)
    if origem.is_file():
        return origem

    nome_original = documento.get("arquivo_nome") or Path(str(documento.get("arquivo_origem") or "")).name
    nome_normalizado = documento.get("nome_normalizado") or documento.get("arquivo_final")
    logging.error(
        (
            "Arquivo fisico nao encontrado | caminho_esperado=%s | caminho_original=%s | "
            "nome_original=%s | nome_normalizado=%s | fornecedor=%s | nf=%s | pedido=%s"
        ),
        origem,
        caminho_original,
        nome_original,
        nome_normalizado,
        documento.get("fornecedor_nome"),
        documento.get("numero_nf"),
        documento.get("numero_pedido"),
    )
    raise FileNotFoundError(f"Arquivo nao encontrado: {origem}")
