from ..web_legacy import (
    calcular_confianca,
    campo_por_tipo,
    diferenca_linha,
    diferenca_processo,
    formatar_brl,
    limpar_fornecedor_ui,
    limpar_nf_ui,
    parse_brl,
    primeiro_texto,
    proxima_acao,
    responsavel,
    resumo_documentos,
    status_operacional,
    status_validacao_pedido,
)

__all__ = [nome for nome in globals() if not nome.startswith("_")]
