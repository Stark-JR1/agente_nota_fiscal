import sqlite3
from decimal import Decimal
from pathlib import Path

import fitz

from app.tools.historico_builder import (
    conectar_banco,
    extrair_fornecedor_nome_arquivo,
    extrair_nf_nome_arquivo,
    extrair_pedido_nome_arquivo,
    extrair_tipo_nome_arquivo,
    extrair_valor_nome_arquivo,
    extrair_valor_historico,
    fornecedor_valido,
    indexar_historico,
    inserir_lote,
    normalizar_fornecedor,
    normalizar_mes_historico,
    classificar_valor,
)


def criar_pdf(caminho: Path, texto: str = "") -> None:
    pdf = fitz.open()
    pagina = pdf.new_page()
    if texto:
        pagina.insert_text((72, 72), texto)
    pdf.save(caminho)
    pdf.close()


def test_extracao_pelo_nome():
    nome = "COMERCIAL FRAGA LTDA - NF 69264 - R$ 375,00 - PROCESSO COMPLETO.pdf"
    assert extrair_fornecedor_nome_arquivo(nome) == "COMERCIAL FRAGA LTDA"
    assert extrair_nf_nome_arquivo(nome) == "69264"
    assert extrair_valor_nome_arquivo(nome) == Decimal("375.00")
    assert extrair_tipo_nome_arquivo(nome) == "PROCESSO_COMPLETO"


def test_extrai_pedido_oc():
    assert extrair_pedido_nome_arquivo("AUTO PECAS LAGE-OC 11894.pdf") == "11894"
    assert extrair_tipo_nome_arquivo("AUTO PECAS LAGE-OC 11894.pdf") == "PEDIDO_COMPRA"


def test_valores_historicos_e_limites():
    assert extrair_valor_nome_arquivo("VF-R$ 1.045.00.pdf") == Decimal("1045.00")
    assert extrair_valor_historico("CNPJ 12.345.678/0001-95", "SEM VALOR.pdf") == (None, "NAO_ENCONTRADO")
    assert classificar_valor(Decimal("100000.00")) == "VALOR_OK"
    assert classificar_valor(Decimal("100000.01")) == "VALOR_ALTO_REVISAR"
    assert classificar_valor(Decimal("500000.01")) == "VALOR_SUSPEITO"


def test_fornecedor_invalido_e_normalizacao():
    assert not fornecedor_valido("000000429031")
    assert not fornecedor_valido("1E30429D-8689-47E8-ADA1-5E64F59C43BA")
    assert not fornecedor_valido("ART-COMPROVANTE DE PAGAMENTO")
    assert normalizar_fornecedor("Comercial Fraga Ltda - ME") == "COMERCIAL FRAGA"


def test_normaliza_meses_historicos():
    assert normalizar_mes_historico("04-ABRIL") == "04"
    assert normalizar_mes_historico("Notas Enviadas Setembro - 2022") == "09"
    assert normalizar_mes_historico("sem identificacao") == "SEM_MES"


def test_hash_duplicado_nao_e_inserido(tmp_path):
    banco = conectar_banco(tmp_path / "historico.db")
    registro = {
        "origem": "BRUTO", "ano": "2024", "mes": "08", "dia": "01-08-2024",
        "caminho_arquivo": "a.pdf", "nome_arquivo": "a.pdf", "extensao": ".pdf",
        "fornecedor": "FORNECEDOR", "cnpj": None, "numero_nf": "1", "numero_pedido": None,
        "valor": Decimal("10.00"), "tipo_documento": "NF_PRODUTO",
        "status_historico": "DOCUMENTO_BRUTO", "confianca": 0.5,
        "data_indexacao": "2026-06-11T00:00:00", "hash_arquivo": "abc",
    }
    assert inserir_lote(banco, [registro]) == (1, 0)
    assert inserir_lote(banco, [registro]) == (0, 1)
    banco.close()


def test_dry_run_nao_grava_artefatos(tmp_path):
    pasta = tmp_path / "HISTORICO_LEGADO" / "01 - BRUTO" / "2024" / "08" / "01-08-2024"
    pasta.mkdir(parents=True)
    criar_pdf(pasta / "FORNECEDOR-NF 123-R$ 10,00.pdf")
    resultado = indexar_historico(tmp_path, dry_run=True, ano="2024")
    assert resultado["indexados"] == 1
    assert not (tmp_path / "HISTORICO_LEGADO" / "_DATABASE").exists()
    assert not (tmp_path / "CONFIG").exists()


def test_indexacao_cria_banco_e_artefatos(tmp_path):
    pasta = tmp_path / "HISTORICO_LEGADO" / "03 - ASSINADO" / "2025" / "01" / "02-01-2025"
    pasta.mkdir(parents=True)
    criar_pdf(pasta / "FORNECEDOR-NF 456-R$ 20,00-PROCESSO COMPLETO.pdf")
    resultado = indexar_historico(tmp_path, ano="2025")
    assert resultado["indexados"] == 1
    banco = tmp_path / "HISTORICO_LEGADO" / "_DATABASE" / "data_historica.db"
    with sqlite3.connect(banco) as conexao:
        assert conexao.execute("SELECT COUNT(*) FROM documentos_historicos").fetchone()[0] == 1
    assert (tmp_path / "HISTORICO_LEGADO" / "_DATABASE" / "estatisticas.json").exists()
    assert (tmp_path / "CONFIG" / "fornecedores.json").exists()
    assert (tmp_path / "CONFIG" / "excecoes.json").read_text(encoding="utf-8").strip()
    assert (tmp_path / "RELATORIOS" / "HISTORICO" / "relatorio_historico.xlsx").exists()
