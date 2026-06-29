from __future__ import annotations

import argparse

from .config import carregar_config
from .services.processamento_service import (
    backup_originais,
    caminho_unico,
    configurar_logs,
    imprimir_resumo,
    imprimir_resumo_resultado,
    listar_pdfs,
    main as service_main,
    nome_documento_pendencia,
    nome_pasta_pendencia,
    normalizar_paginas_mesmo_arquivo,
    processar_aprovado,
    processar_arquivo,
    processar_documentos,
    processar_pasta,
    processar_pendente,
    salvar_pagina_individual,
    texto_erro,
    validar_processos_com_progresso,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Robo de conferencia de PDFs fiscais.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    resultado = processar_pasta(config=carregar_config(), dry_run=args.dry_run)
    imprimir_resumo_resultado(resultado)


if __name__ == "__main__":
    main()
