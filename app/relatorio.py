from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .utils import formatar_valor_brl


COLUNAS = [
    "Data",
    "Status",
    "Fornecedor",
    "CNPJ",
    "NF",
    "Pedido(s)",
    "Valor Pedido(s)",
    "Valor NF",
    "Valor Produtos NF",
    "Valor Frete",
    "Outras Despesas",
    "Valor Boleto(s)",
    "Diferenca",
    "Documentos Encontrados",
    "Pasta Origem",
    "Pasta Destino",
    "Vencimento(s)",
    "Tipo Documento",
    "Arquivo Original",
    "Arquivo Final",
    "Observacoes",
    "Erro Encontrado",
    "Confianca OCR",
    "Confianca Documento",
    "Confianca Processo",
]


def gerar_relatorios(processos: list[dict], pasta_relatorios: Path, data_ref) -> tuple[Path, Path, Path]:
    pasta_relatorios.mkdir(parents=True, exist_ok=True)
    linhas = montar_linhas(processos)
    linhas_pendencias = [linha for linha in linhas if linha.get("Status") != "APROVADO" or linha.get("Erro Encontrado")]
    sufixo = data_ref.strftime("%d-%m-%Y")
    caminho_xlsx = pasta_relatorios / f"relatorio_processamento_{sufixo}.xlsx"
    caminho_pendencias = pasta_relatorios / f"relatorio_pendencias_{sufixo}.xlsx"
    caminho_txt = pasta_relatorios / f"resumo_processamento_{sufixo}.txt"

    try:
        gerar_excel(linhas, caminho_xlsx)
    except PermissionError:
        caminho_xlsx = caminho_unico(caminho_xlsx)
        gerar_excel(linhas, caminho_xlsx)

    try:
        gerar_excel(linhas_pendencias, caminho_pendencias)
    except PermissionError:
        caminho_pendencias = caminho_unico(caminho_pendencias)
        gerar_excel(linhas_pendencias, caminho_pendencias)

    try:
        gerar_txt(processos, linhas, caminho_txt)
    except PermissionError:
        caminho_txt = caminho_unico(caminho_txt)
        gerar_txt(processos, linhas, caminho_txt)
    return caminho_xlsx, caminho_pendencias, caminho_txt


def montar_linhas(processos: list[dict]) -> list[dict]:
    linhas = []
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    for processo in processos:
        docs = processo["documentos"]
        vencimentos = ", ".join(sorted({d["vencimento"] for d in docs if d.get("vencimento")}))
        pedidos = ", ".join(sorted({str(d["numero_pedido"]) for d in docs if d.get("numero_pedido")}))
        erro = "; ".join(processo.get("erros", []))
        tipos = ", ".join(sorted({str(d.get("tipo_documento")) for d in docs if d.get("tipo_documento")}))
        pasta_origem = primeiro_texto(Path(d["arquivo_origem"]).parent for d in docs if d.get("arquivo_origem"))
        pasta_destino = primeiro_texto(Path(str(d["arquivo_final"])).parent for d in docs if d.get("arquivo_final"))
        diferenca = calcular_diferenca(processo)
        for doc in docs:
            linhas.append(
                {
                    "Data": agora,
                    "Status": processo.get("status"),
                    "Fornecedor": doc.get("fornecedor_nome"),
                    "CNPJ": doc.get("fornecedor_cnpj"),
                    "NF": doc.get("numero_nf"),
                    "Pedido(s)": pedidos,
                    "Valor Pedido(s)": _fmt(processo.get("valor_pedidos")),
                    "Valor NF": _fmt(processo.get("valor_nf")),
                    "Valor Produtos NF": _fmt(processo.get("valor_produtos_nf")),
                    "Valor Frete": _fmt(doc.get("valor_frete")),
                    "Outras Despesas": _fmt(doc.get("outras_despesas")),
                    "Valor Boleto(s)": _fmt(processo.get("valor_boletos")),
                    "Diferenca": _fmt(diferenca),
                    "Documentos Encontrados": tipos,
                    "Pasta Origem": str(pasta_origem) if pasta_origem else None,
                    "Pasta Destino": str(pasta_destino) if pasta_destino else None,
                    "Vencimento(s)": vencimentos,
                    "Tipo Documento": doc.get("tipo_documento"),
                    "Arquivo Original": doc.get("arquivo_nome"),
                    "Arquivo Final": doc.get("arquivo_final"),
                    "Observacoes": doc.get("observacoes"),
                    "Erro Encontrado": erro,
                    "Confianca OCR": doc.get("confianca_extracao"),
                    "Confianca Documento": doc.get("confianca_documento"),
                    "Confianca Processo": processo.get("confianca_processo"),
                }
            )
    return linhas


def primeiro_texto(valores) -> object | None:
    for valor in valores:
        if valor not in (None, ""):
            return valor
    return None


def calcular_diferenca(processo: dict) -> Decimal | None:
    nf = processo.get("valor_nf")
    pedido = processo.get("valor_pedidos")
    boleto = processo.get("valor_boletos")
    referencia = boleto if boleto is not None else pedido
    if nf is None or referencia is None:
        return None
    return Decimal(nf) - Decimal(referencia)


def gerar_excel(linhas: list[dict], caminho: Path) -> None:
    try:
        import pandas as pd

        pd.DataFrame(linhas, columns=COLUNAS).to_excel(caminho, index=False)
    except ImportError:
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Conferencia"
            ws.append(COLUNAS)
            for linha in linhas:
                ws.append([linha.get(coluna) for coluna in COLUNAS])
            wb.save(caminho)
        except ImportError:
            gerar_xlsx_minimo(linhas, caminho)


def gerar_txt(processos: list[dict], linhas: list[dict], caminho: Path) -> None:
    aprovados = sum(1 for p in processos if p.get("status") == "APROVADO")
    pendentes = len(processos) - aprovados
    with caminho.open("w", encoding="utf-8") as arquivo:
        arquivo.write("RELATORIO DE CONFERENCIA PDF\n")
        arquivo.write(f"Processos aprovados: {aprovados}\n")
        arquivo.write(f"Processos pendentes: {pendentes}\n\n")
        for processo in processos:
            arquivo.write(f"{processo['id']} - {processo.get('status')}\n")
            if processo.get("erros"):
                arquivo.write("Erros: " + "; ".join(processo["erros"]) + "\n")
            for doc in processo["documentos"]:
                arquivo.write(f"  - {doc.get('tipo_documento')} | {doc.get('arquivo_nome')} | pagina {doc.get('pagina')}\n")
            arquivo.write("\n")


def _fmt(valor: Decimal | None) -> str | None:
    return formatar_valor_brl(valor) if valor is not None else None


def gerar_xlsx_minimo(linhas: list[dict], caminho: Path) -> None:
    rows = [COLUNAS] + [[linha.get(coluna) for coluna in COLUNAS] for linha in linhas]
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{_coluna_excel(col_index)}{row_index}"
            texto = escape("" if value is None else str(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{texto}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Conferencia" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    with ZipFile(caminho, "w", ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", content_types)
        xlsx.writestr("_rels/.rels", rels)
        xlsx.writestr("xl/workbook.xml", workbook)
        xlsx.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        xlsx.writestr("xl/worksheets/sheet1.xml", worksheet)


def _coluna_excel(indice: int) -> str:
    letras = ""
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def caminho_unico(caminho: Path) -> Path:
    if not caminho.exists():
        return caminho
    contador = 2
    while True:
        candidato = caminho.with_name(f"{caminho.stem} ({contador}){caminho.suffix}")
        if not candidato.exists():
            return candidato
        contador += 1
