import logging

import pytest
from pypdf import PdfReader, PdfWriter

from app.leitor_pdf import extrair_texto_paginas
from app.origem_documento import caminho_fisico_documento
from app.services.processamento_service import salvar_pagina_individual
from app.unificador import unir_processo


def criar_pdf(caminho):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with caminho.open("wb") as arquivo:
        writer.write(arquivo)


def test_cache_reassocia_caminho_fisico_atual(monkeypatch, tmp_path):
    atual = tmp_path / "INOVAR - NF 1035 - R$ 2868,60 - NF.pdf"
    atual.write_bytes(b"conteudo")
    cache_antigo = [{"arquivo_origem": r"C:\CAMINHO ANTIGO\INOVAR - NF 1035 - NF.pdf", "pagina": 1, "texto": "NF"}]
    monkeypatch.setattr("app.leitor_pdf._ler_cache", lambda _caminho: cache_antigo)

    paginas = extrair_texto_paginas(atual, 150)

    assert paginas[0]["arquivo_origem"] == str(atual)
    assert paginas[0]["caminho_original"] == str(atual)


def test_geracao_usa_caminho_original_e_nao_nome_normalizado(tmp_path):
    origem = tmp_path / "INOVAR - NF 1035 - R$ 2868,60 - NF.pdf"
    criar_pdf(origem)
    documento = {
        "tipo_documento": "NF_PRODUTO",
        "caminho_original": str(origem),
        "arquivo_origem": str(tmp_path / "INOVAR - NF 1035 - NF.pdf"),
        "arquivo_nome": origem.name,
        "nome_normalizado": "INOVAR - NF 1035 - NF.pdf",
        "pagina": 1,
    }

    individual = tmp_path / "processado.pdf"
    unificado = tmp_path / "unificado.pdf"
    salvar_pagina_individual(documento, individual)
    unir_processo({"documentos": [documento]}, unificado)

    assert len(PdfReader(str(individual)).pages) == 1
    assert len(PdfReader(str(unificado)).pages) == 1


def test_caminho_inexistente_registra_detalhes(caplog, tmp_path):
    documento = {
        "caminho_original": str(tmp_path / "original inexistente.pdf"),
        "arquivo_nome": "original.pdf",
        "nome_normalizado": "normalizado.pdf",
    }
    with caplog.at_level(logging.ERROR), pytest.raises(FileNotFoundError, match="Arquivo nao encontrado"):
        caminho_fisico_documento(documento)
    assert "nome_original=original.pdf" in caplog.text
    assert "nome_normalizado=normalizado.pdf" in caplog.text
