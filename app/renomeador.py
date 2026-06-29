from __future__ import annotations

from decimal import Decimal
import re

from .utils import formatar_valor_brl, sanitizar_nome_arquivo


SUFIXOS = {
    "NF_PRODUTO": "NF",
    "NF_SERVICO": "NF",
    "RECIBO_LOCACAO": "RECIBO LOCACAO",
    "BOLETO": "BOLETO",
    "FATURA_CONTRATO": "FATURA",
    "RECIBO_CONTRATO": "RECIBO",
    "PEDIDO_COMPRA": "PEDIDO",
    "DACTE": "DACTE",
    "OUTRO_ANEXO": "ANEXO",
    "DESCONHECIDO": "OUTRO",
}


def dados_nome_processo(processo: dict) -> tuple[str, str, Decimal | None]:
    docs = processo["documentos"]
    if processo.get("contrato_sem_pedido") == "INTERNET_SUPER":
        valor = maior_valor(docs)
        return "INTERNET SUPER LTDA - ME", "CONTRATO", valor
    if processo.get("contrato_sem_pedido") == "VIGILANCIA_SEGURANCA":
        valor = processo.get("valor_nf") or processo.get("valor_boletos") or maior_valor(docs)
        return "VIGILANCIA SEGURANCA ELETRONICA", "CONTRATO", valor
    if processo.get("contrato_sem_pedido") in {"MARIA_INES_ALUGUEL", "MARIA_INES_ENERGIA"}:
        valor = processo.get("valor_boletos") or maior_valor(docs)
        rotulo = "ALUGUEL" if processo.get("contrato_sem_pedido") == "MARIA_INES_ALUGUEL" else "ENERGIA"
        return "MARIA INES COTA PINHEIRO", rotulo, valor

    fornecedor = _primeiro_por_tipo(docs, "fornecedor_nome", ["PEDIDO_COMPRA", "NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "BOLETO"]) or "FORNECEDOR"
    nf = _primeiro_por_tipo(docs, "numero_nf", ["NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "DACTE", "BOLETO", "PEDIDO_COMPRA"]) or "SEM NF"
    valor = processo.get("valor_nf") or next((d.get("valor_total") for d in docs if d.get("valor_total") is not None), None)
    return limpar_nome_fornecedor(fornecedor), nf, valor


def nome_documento(doc: dict, processo: dict) -> str:
    fornecedor, nf, valor = dados_nome_processo(processo)
    sufixo = SUFIXOS.get(doc.get("tipo_documento"), "OUTRO")
    rotulo = "CONTRATO" if nf == "CONTRATO" else f"NF {nf}"
    return montar_nome_curto(fornecedor, rotulo, valor, sufixo)


def nome_pdf_unido(processo: dict) -> str:
    fornecedor, nf, valor = dados_nome_processo(processo)
    rotulo = "CONTRATO" if nf == "CONTRATO" else f"NF {nf}"
    return montar_nome_curto(fornecedor, rotulo, valor, "PROCESSO COMPLETO")


def _primeiro_por_tipo(docs: list[dict], campo: str, ordem_tipos: list[str]) -> str | None:
    for tipo in ordem_tipos:
        for doc in docs:
            valor = doc.get(campo)
            if doc.get("tipo_documento") == tipo and valor:
                return str(valor)
    return None


def limpar_nome_fornecedor(nome: str) -> str:
    nome = re.sub(r"^\d+\s*-\s*", "", nome)
    nome = re.sub(r"^RAZ[ÃA]O\s+SOCIAL\s*:?\s*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"^NOME\s*/?\s*RAZ[ÃA]O\s+SOCIAL\s*:?\s*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s*\|\s*", " ", nome)
    nome = re.sub(r"\bCPFSCNPI\b\s*:?", "CNPJ:", nome, flags=re.IGNORECASE)
    lixo = [
        "Documento Auxiliar",
        "Data do documento",
        "ou no site da Sefaz Autorizadora",
        "E-mail:",
        "Chave de acesso",
    ]
    for termo in lixo:
        if termo.upper() in nome.upper():
            return "FORNECEDOR"
    partes = [parte.strip() for parte in nome.split(" - ") if parte.strip()]
    if len(partes) >= 2:
        ultimo = partes[-1].upper()
        anteriores = " - ".join(partes[:-1])
        anteriores_norm = anteriores.upper()
        sufixos_operacionais = {"BANCODOC", "BANCO", "BANC", "BOLETO", "NF", "NOTA", "PC", "PEDIDO"}
        tem_razao_social = any(marca in anteriores_norm for marca in ("LTDA", "EIRELI", " ME", " S/A", "SA "))
        if ultimo in sufixos_operacionais or (tem_razao_social and ultimo in anteriores_norm):
            nome = anteriores
        elif partes[0].upper() in ultimo:
            nome = partes[-1]
    return nome


def maior_valor(docs: list[dict]) -> Decimal | None:
    valores = [Decimal(doc["valor_total"]) for doc in docs if doc.get("valor_total") is not None]
    return max(valores) if valores else None


def montar_nome_curto(fornecedor: str, rotulo: str, valor: Decimal | None, sufixo: str) -> str:
    fornecedor_curto = sanitizar_nome_arquivo(limpar_nome_fornecedor(fornecedor), limite=24)
    rotulo_curto = sanitizar_nome_arquivo(rotulo, limite=14)
    nome = f"{fornecedor_curto} - {rotulo_curto} - {formatar_valor_brl(valor)} - {sufixo}.pdf"
    return sanitizar_nome_arquivo(nome, limite=82)
