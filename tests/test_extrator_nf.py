from app.extractors.nf_servico_extractor import extrair_nf_servico


def test_extrator_nf_servico_usa_nome_arquivo_quando_cabecalho_invalido():
    pagina = {
        "texto": "NOTA FISCAL DE SERVICO\nNome/Razao Social\nVALOR TOTAL DOS SERVICOS 100,00",
        "arquivo_origem": "FORNECEDOR TESTE - NF 123.pdf",
        "pagina": 1,
        "origem_texto": "digital",
        "confianca_ocr": 1.0,
    }
    campos = extrair_nf_servico(pagina, 1.0)
    assert campos["fornecedor_nome"] == "FORNECEDOR TESTE"
    assert campos["valor_total"] == 100
