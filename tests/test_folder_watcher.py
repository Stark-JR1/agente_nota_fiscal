from pathlib import Path

from app.watchers import folder_watcher


def test_arquivo_pdf_e_aceito():
    assert folder_watcher.pdf_monitoravel(Path("nota.PDF"))


def test_arquivo_temporario_e_ignorado():
    assert not folder_watcher.pdf_monitoravel(Path("nota.tmp"))
    assert not folder_watcher.pdf_monitoravel(Path("nota.pdf.crdownload"))
    assert not folder_watcher.pdf_monitoravel(Path("~$nota.pdf"))
    assert not folder_watcher.pdf_monitoravel(Path("Thumbs.db"))


def test_arquivo_nao_pdf_e_ignorado():
    assert not folder_watcher.pdf_monitoravel(Path("nota.txt"))
    assert not folder_watcher.pdf_monitoravel(Path("nota.xlsx"))


def test_verificacao_de_estabilizacao_retorna_true_quando_tamanho_nao_muda(monkeypatch):
    tamanhos = iter([10, 10, 10, 10])
    monkeypatch.setattr(folder_watcher, "tamanho_arquivo", lambda _caminho: next(tamanhos))

    assert folder_watcher.aguardar_estabilizacao(
        "nota.pdf",
        delay_seconds=0,
        stable_checks=3,
        stable_interval_seconds=1,
        sleep=lambda _segundos: None,
    )


def test_verificacao_de_estabilizacao_retorna_false_quando_tamanho_muda(monkeypatch):
    tamanhos = iter([10, 20])
    monkeypatch.setattr(folder_watcher, "tamanho_arquivo", lambda _caminho: next(tamanhos))

    assert not folder_watcher.aguardar_estabilizacao(
        "nota.pdf",
        delay_seconds=0,
        stable_checks=3,
        stable_interval_seconds=1,
        sleep=lambda _segundos: None,
    )
