from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook


ABA_PROCESSOS = "PROCESSOS_ENVIADOS"
ARQUIVO_CONTROLE = "CONTROLE_FISCAL.xlsx"
STATUS_FISCAL_INICIAL = "PRONTO_PARA_ENVIO"

COLUNAS = [
    "Data Processamento",
    "Pedido",
    "Fornecedor",
    "CNPJ",
    "NF",
    "Valor",
    "Status Processo",
    "Arquivo Completo",
    "Status Fiscal",
    "Data Envio Fiscal",
    "Observação",
]

COLUNAS_MANUAIS = {"Status Fiscal", "Data Envio Fiscal", "Observação", "ObservaÃ§Ã£o"}


def atualizar_controle_fiscal(processos: list[dict], pasta_relatorios_base: Path, data_processamento=None) -> Path:
    caminho = pasta_relatorios_base / ARQUIVO_CONTROLE
    caminho.parent.mkdir(parents=True, exist_ok=True)

    wb = load_workbook(caminho) if caminho.exists() else Workbook()
    ws = _obter_aba(wb)
    _garantir_cabecalho(ws)

    indices = _indices_colunas(ws)
    existentes = _mapear_linhas_existentes(ws, indices)
    data_texto = _formatar_data(data_processamento or datetime.now())

    for processo in processos:
        if processo.get("status") != "APROVADO":
            continue

        linha = montar_linha_controle(processo, data_texto)
        chave = chave_linha(linha)
        row_idx = existentes.get(chave)
        if row_idx:
            _atualizar_linha_existente(ws, row_idx, indices, linha)
            continue

        ws.append([linha.get(coluna) for coluna in COLUNAS])
        existentes[chave] = ws.max_row

    wb.save(caminho)
    return caminho


def montar_linha_controle(processo: dict, data_processamento: str) -> dict[str, Any]:
    docs = processo.get("documentos", [])
    pedido = _juntar_unicos(doc.get("numero_pedido") for doc in docs)
    fornecedor = _primeiro(doc.get("fornecedor_nome") for doc in docs)
    cnpj = _primeiro(doc.get("fornecedor_cnpj") for doc in docs)
    nf = _juntar_unicos(doc.get("numero_nf") for doc in docs)
    valor = processo.get("valor_nf") or _primeiro(doc.get("valor_total") for doc in docs)

    return {
        "Data Processamento": data_processamento,
        "Pedido": pedido,
        "Fornecedor": fornecedor,
        "CNPJ": cnpj,
        "NF": nf,
        "Valor": _normalizar_valor_saida(valor),
        "Status Processo": processo.get("status"),
        "Arquivo Completo": processo.get("arquivo_unido"),
        "Status Fiscal": STATUS_FISCAL_INICIAL,
        "Data Envio Fiscal": None,
        "Observação": None,
    }


def chave_linha(linha: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _normalizar_texto_chave(linha.get("Pedido")),
        _normalizar_texto_chave(linha.get("NF")),
        _normalizar_texto_chave(linha.get("Fornecedor")),
        _normalizar_valor_chave(linha.get("Valor")),
    )


def _obter_aba(wb):
    if ABA_PROCESSOS in wb.sheetnames:
        return wb[ABA_PROCESSOS]
    if wb.active and wb.active.max_row == 1 and wb.active.max_column == 1 and wb.active["A1"].value is None:
        ws = wb.active
        ws.title = ABA_PROCESSOS
        return ws
    return wb.create_sheet(ABA_PROCESSOS)


def _garantir_cabecalho(ws) -> None:
    cabecalho_atual = [ws.cell(row=1, column=col).value for col in range(1, ws.max_column + 1)]
    if not any(cabecalho_atual):
        for col, coluna in enumerate(COLUNAS, start=1):
            ws.cell(row=1, column=col, value=coluna)
        return

    for coluna in COLUNAS:
        if coluna not in cabecalho_atual:
            ws.cell(row=1, column=len(cabecalho_atual) + 1, value=coluna)
            cabecalho_atual.append(coluna)


def _indices_colunas(ws) -> dict[str, int]:
    indices = {
        str(ws.cell(row=1, column=col).value): col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row=1, column=col).value
    }
    if "ObservaÃ§Ã£o" in indices and "Observação" not in indices:
        indices["Observação"] = indices["ObservaÃ§Ã£o"]
    return indices


def _mapear_linhas_existentes(ws, indices: dict[str, int]) -> dict[tuple[str, str, str, str], int]:
    existentes = {}
    for row_idx in range(2, ws.max_row + 1):
        linha = {coluna: ws.cell(row=row_idx, column=indices[coluna]).value for coluna in COLUNAS if coluna in indices}
        chave = chave_linha(linha)
        if any(chave):
            existentes[chave] = row_idx
    return existentes


def _atualizar_linha_existente(ws, row_idx: int, indices: dict[str, int], linha: dict[str, Any]) -> None:
    for coluna, valor in linha.items():
        if coluna in COLUNAS_MANUAIS:
            continue
        ws.cell(row=row_idx, column=indices[coluna], value=valor)

    status_fiscal_col = indices["Status Fiscal"]
    if ws.cell(row=row_idx, column=status_fiscal_col).value in (None, ""):
        ws.cell(row=row_idx, column=status_fiscal_col, value=STATUS_FISCAL_INICIAL)


def _juntar_unicos(valores) -> str | None:
    unicos = sorted({str(valor).strip() for valor in valores if valor not in (None, "")})
    return ", ".join(unicos) if unicos else None


def _primeiro(valores):
    for valor in valores:
        if valor not in (None, ""):
            return valor
    return None


def _formatar_data(valor) -> str:
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y %H:%M:%S")
    return str(valor)


def _normalizar_texto_chave(valor) -> str:
    return " ".join(str(valor or "").strip().upper().split())


def _normalizar_valor_saida(valor):
    if valor in (None, ""):
        return None
    try:
        return float(Decimal(str(valor)))
    except (InvalidOperation, ValueError):
        return valor


def _normalizar_valor_chave(valor) -> str:
    if valor in (None, ""):
        return ""
    try:
        return f"{Decimal(str(valor)).quantize(Decimal('0.01'))}"
    except (InvalidOperation, ValueError):
        texto = str(valor).replace("R$", "").strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            return f"{Decimal(texto).quantize(Decimal('0.01'))}"
        except InvalidOperation:
            return _normalizar_texto_chave(valor)

