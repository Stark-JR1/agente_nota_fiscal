from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path

from .config import ROOT_DIR
from .ocr import ocr_pdf_pagina


def extrair_texto_paginas(
    pdf_path: Path,
    limite_texto_minimo: int,
    tesseract_path: str | None = None,
    habilitar_cache: bool = True,
) -> list[dict]:
    cache = _ler_cache(pdf_path) if habilitar_cache else None
    if cache is not None:
        logging.info("Cache utilizado: %s", pdf_path)
        for pagina in cache:
            pagina["arquivo_origem"] = str(pdf_path)
            pagina["caminho_original"] = str(pdf_path)
        return cache
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Instale as dependencias com: pip install -r requirements.txt") from exc

    paginas = []
    with fitz.open(pdf_path) as doc:
        logging.info("Arquivo lido: %s", pdf_path)
        logging.info("Quantidade de paginas: %s", doc.page_count)
        for index, page in enumerate(doc):
            texto = page.get_text("text") or ""
            origem = "digital"
            if len(texto.strip()) < limite_texto_minimo:
                print(f"    OCR acionado: {pdf_path.name} pagina {index + 1}", flush=True)
                logging.info("Texto digital insuficiente em %s pagina %s. OCR acionado.", pdf_path.name, index + 1)
                texto_ocr = ocr_pdf_pagina(pdf_path, index, tesseract_path)
                if texto_ocr.strip():
                    texto = texto_ocr
                    origem = "ocr"
                else:
                    origem = "vazio"
            else:
                print(f"    Texto digital: {pdf_path.name} pagina {index + 1}", flush=True)
                logging.info("Texto digital encontrado em %s pagina %s.", pdf_path.name, index + 1)

            paginas.append(
                {
                    "arquivo_origem": str(pdf_path),
                    "caminho_original": str(pdf_path),
                    "pagina": index + 1,
                    "texto": texto,
                    "origem_texto": origem,
                    "confianca_ocr": 0.70 if origem == "ocr" else (1.0 if origem == "digital" else 0.0),
                }
            )
    if habilitar_cache:
        _salvar_cache(pdf_path, paginas)
    return paginas


def _hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _caminho_cache(caminho: Path) -> Path:
    pasta = ROOT_DIR / ".cache"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{_hash_arquivo(caminho)}.json"


def _ler_cache(caminho: Path) -> list[dict] | None:
    arquivo = _caminho_cache(caminho)
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return dados.get("paginas") if dados.get("hash") == arquivo.stem else None
    except (OSError, ValueError):
        return None


def _salvar_cache(caminho: Path, paginas: list[dict]) -> None:
    arquivo = _caminho_cache(caminho)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(
        json.dumps({"arquivo": str(caminho), "hash": arquivo.stem, "paginas": paginas}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporario.replace(arquivo)
