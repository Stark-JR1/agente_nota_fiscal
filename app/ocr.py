from __future__ import annotations

import logging
from pathlib import Path

from .utils import normalizar_texto


def configurar_tesseract(tesseract_path: str | None) -> None:
    if not tesseract_path:
        return
    try:
        import pytesseract

        caminho = Path(tesseract_path)
        if caminho.exists():
            pytesseract.pytesseract.tesseract_cmd = str(caminho)
    except Exception as exc:  # pragma: no cover - depende do ambiente local
        logging.warning("Nao foi possivel configurar o Tesseract: %s", exc)


def preprocessar_imagem(imagem):
    try:
        import cv2
        import numpy as np

        arr = np.array(imagem)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.35, beta=10)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh
    except Exception:
        return imagem


def ocr_pdf_pagina(pdf_path: Path, pagina_index: int, tesseract_path: str | None = None) -> str:
    configurar_tesseract(tesseract_path)
    try:
        import pytesseract
    except ImportError as exc:
        logging.warning("OCR indisponivel. Dependencia ausente: %s", exc)
        return ""

    try:
        imagem = renderizar_pagina_pymupdf(pdf_path, pagina_index)
        return melhor_ocr_por_rotacao(pytesseract, imagem)
    except Exception as exc:
        logging.warning("Falha ao aplicar OCR em %s pagina %s: %s", pdf_path.name, pagina_index + 1, exc)
        return ""


def renderizar_pagina_pymupdf(pdf_path: Path, pagina_index: int):
    import fitz
    from PIL import Image

    with fitz.open(pdf_path) as doc:
        page = doc[pagina_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        imagem = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return imagem


def melhor_ocr_por_rotacao(pytesseract, imagem) -> str:
    candidatos = []
    for angulo in (0, 90, 180, 270):
        img = imagem.rotate(angulo, expand=True) if angulo else imagem
        img = preprocessar_imagem(img)
        texto = ocr_imagem(pytesseract, img)
        candidatos.append((pontuar_texto_ocr(texto), texto))
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1]


def ocr_imagem(pytesseract, imagem) -> str:
    try:
        return pytesseract.image_to_string(imagem, lang="por")
    except Exception:
        logging.warning("Idioma portugues do Tesseract nao encontrado. Usando OCR em ingles.")
        return pytesseract.image_to_string(imagem, lang="eng")


def pontuar_texto_ocr(texto: str) -> int:
    texto_norm = normalizar_texto(texto)
    palavras = [
        "CNPJ",
        "VENCIMENTO",
        "BENEFICIARIO",
        "PAGADOR",
        "NOTA FISCAL",
        "NFS",
        "NF-E",
        "BOLETO",
        "VALOR",
        "SISTERMI",
        "FICHA DE COMPENSACAO",
        "PAGAVEL",
        "PEDIDO",
    ]
    return len(texto_norm) + (250 * sum(1 for palavra in palavras if palavra in texto_norm))
