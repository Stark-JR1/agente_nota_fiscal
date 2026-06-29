from __future__ import annotations

from .utils import limpar_espacos, normalizar_texto


REGRAS = {
    "NF_PRODUTO": [
        "DANFE",
        "NF-E",
        "DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA",
        "CHAVE DE ACESSO",
        "NATUREZA DA OPERACAO",
        "DESTINATARIO",
    ],
    "NF_SERVICO": [
        "NFS-E",
        "NOTA FISCAL DE SERVICO",
        "NOTA FISCAL DE SERVICOS ELETRONICA",
        "DANFSE",
        "DOCUMENTO AUXILIAR DA NFS-E",
        "DOCUMENTO AUXILIAR DA NOTA FISCAL DE FATURA DE SERVICO DE COMUNICACAO",
        "NFCOM",
        "TOTAL A PAGAR",
        "PRESTADOR DO SERVICO",
        "TOMADOR DO SERVICO",
    ],
    "FATURA_CONTRATO": [
        "NOTA DE DEBITO",
        "INFORMACOES DA COBRANCA",
        "RESUMO DOS PLANOS CONTRATADOS",
        "SERVICOS CONTRATADOS",
        "FATURA",
        "LOCAL DE PAGAMENTO",
    ],
    "BOLETO": [
        "FICHA DE COMPENSACAO",
        "PAGAVEL EM QUALQUER BANCO",
        "VENCIMENTO",
        "NOSSO NUMERO",
        "BENEFICIARIO",
        "PAGADOR",
        "LINHA DIGITAVEL",
        "BRADESCO",
        "BANCO DO BRASIL",
        "SICOOB",
        "SANTANDER",
        "ITAU",
        "CAIXA",
    ],
    "PEDIDO_COMPRA": [
        "PEDIDO DE COMPRA DETALHADO",
        "PEDIDO / FILIAL",
        "FORNECEDOR",
        "CNPJ/CPF",
        "TOTAL PRD",
        "APROVADO POR",
        "VISUAL RODOPAR",
    ],
    "DACTE": [
        "DACTE",
        "DOCUMENTO AUXILIAR DO CONHECIMENTO DE TRANSPORTE ELETRONICO",
        "CT-E",
        "TOMADOR DO SERVICO",
        "REMETENTE",
        "DESTINATARIO",
        "VALOR TOTAL DA PRESTACAO",
    ],
    "RECIBO_CONTRATO": [
        "RECIBO DE ALUGUEL",
        "PROPRIETARIA",
        "VALOR LIQUIDO RECEBIDO",
        "DEMONSTRATIVO REFERENTE A PRODUCAO DE ENERGIA",
        "ENERGIA FOTOVOLTAICA",
        "VALOR DO REEMBOLSO",
    ],
    "RECIBO_LOCACAO": [
        "RECIBO DE LOCACAO",
        "DADOS DO LOCADOR",
        "DADOS DO LOCATARIO",
        "LOCADOR",
        "LOCATARIO",
        "VALOR TOTAL",
    ],
}


def classificar_texto(texto: str) -> tuple[str, float]:
    texto_norm = limpar_espacos(normalizar_texto(texto))
    if "RECIBO DE LOCACAO" in texto_norm and "DADOS DO LOCADOR" in texto_norm:
        return "RECIBO_LOCACAO", 1.0
    if "RECIBO DE ALUGUEL" in texto_norm:
        return "RECIBO_CONTRATO", 1.0
    if "DEMONSTRATIVO REFERENTE A PRODUCAO DE ENERGIA" in texto_norm or "ENERGIA FOTOVOLTAICA" in texto_norm:
        return "RECIBO_CONTRATO", 1.0
    if _danfe_confiavel(texto_norm):
        return "NF_PRODUTO", 1.0
    if _dacte_confiavel(texto_norm):
        return "DACTE", 1.0

    melhor_tipo = "DESCONHECIDO"
    melhor_score = 0
    for tipo, palavras in REGRAS.items():
        acertos = sum(1 for palavra in palavras if palavra in texto_norm)
        if acertos > melhor_score:
            melhor_tipo = tipo
            melhor_score = acertos

    if melhor_score == 0:
        return "DESCONHECIDO", 0.0
    if melhor_tipo == "PEDIDO_COMPRA" and melhor_score < 3:
        return "DESCONHECIDO", 0.0
    total = len(REGRAS[melhor_tipo])
    return melhor_tipo, round(melhor_score / total, 2)


def _danfe_confiavel(texto_norm: str) -> bool:
    return (
        "DANFE" in texto_norm
        and "CHAVE DE ACESSO" in texto_norm
        and "NATUREZA DA OPERACAO" in texto_norm
        and ("NOTA FISCAL" in texto_norm or "NF-E" in texto_norm or "NF -E" in texto_norm)
    )


def _dacte_confiavel(texto_norm: str) -> bool:
    return (
        "DACTE" in texto_norm
        and "CHAVE DE ACESSO" in texto_norm
        and ("CONHECIMENTO DE TRANSPORTE" in texto_norm or "CT-E" in texto_norm)
        and ("TOMADOR DO SERVICO" in texto_norm or "REMETENTE" in texto_norm or "DESTINATARIO" in texto_norm)
    )
