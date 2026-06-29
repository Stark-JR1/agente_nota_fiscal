from pathlib import Path

from ..classificador import classificar_texto
from ..extrator_campos import extrair_campos
from ..leitor_pdf import extrair_texto_paginas
from .processamento_service import normalizar_paginas_mesmo_arquivo


def ler_documento(pdf: Path, config) -> list[dict]:
    return extrair_texto_paginas(
        pdf,
        config.limite_texto_minimo_pdf_digital,
        config.tesseract_path,
        habilitar_cache=config.habilitar_cache,
    )


def classificar_documento(pagina: dict) -> tuple[str, float]:
    return classificar_texto(pagina.get("texto", ""))


def extrair_campos_documento(pagina: dict, tipo: str, confianca: float) -> dict:
    return extrair_campos(pagina, tipo, confianca)


def normalizar_paginas(documentos: list[dict]) -> list[dict]:
    return normalizar_paginas_mesmo_arquivo(documentos)
