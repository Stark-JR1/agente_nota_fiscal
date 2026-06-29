from app.renomeador import montar_nome_curto


def test_nome_final_permanece_curto_e_pdf():
    nome = montar_nome_curto("FORNECEDOR MUITO LONGO LTDA", "NF 123", 100, "PROCESSO COMPLETO")
    assert nome.endswith(".pdf")
    assert len(nome) <= 82
