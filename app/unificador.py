from __future__ import annotations

from pathlib import Path

from .origem_documento import caminho_fisico_documento


ORDEM = {
    "NF_PRODUTO": 10,
    "NF_SERVICO": 10,
    "RECIBO_LOCACAO": 10,
    "BOLETO": 20,
    "FATURA_CONTRATO": 25,
    "RECIBO_CONTRATO": 26,
    "PEDIDO_COMPRA": 30,
    "ORDEM_SERVICO": 40,
    "DACTE": 50,
    "OUTRO_ANEXO": 90,
    "DESCONHECIDO": 99,
}


def unir_processo(processo: dict, destino: Path) -> Path:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError("Instale as dependencias com: pip install -r requirements.txt") from exc

    writer = PdfWriter()
    paginas_adicionadas: set[tuple[str, int]] = set()
    docs = sorted(processo["documentos"], key=lambda d: (ORDEM.get(d.get("tipo_documento"), 99), d.get("arquivo_origem", ""), d.get("pagina", 0)))

    for doc in docs:
        origem = caminho_fisico_documento(doc)
        pagina = int(doc.get("pagina") or 1) - 1
        chave = (str(origem.resolve()), pagina)
        if chave in paginas_adicionadas:
            continue
        reader = PdfReader(str(origem))
        if 0 <= pagina < len(reader.pages):
            writer.add_page(reader.pages[pagina])
            paginas_adicionadas.add(chave)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as arquivo:
        writer.write(arquivo)
    return destino
