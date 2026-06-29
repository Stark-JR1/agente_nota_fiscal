from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from ..config import carregar_config
from ..paths import montar_pastas


def aguardar_estabilizacao(arquivo: Path, segundos: int, intervalo: float = 1.0) -> bool:
    prazo = time.monotonic() + segundos
    tamanho_anterior = -1
    estavel_desde = time.monotonic()
    while time.monotonic() < prazo:
        try:
            tamanho = arquivo.stat().st_size
        except OSError:
            return False
        if tamanho != tamanho_anterior:
            tamanho_anterior = tamanho
            estavel_desde = time.monotonic()
        elif time.monotonic() - estavel_desde >= min(3, segundos):
            return tamanho > 0
        time.sleep(intervalo)
    return arquivo.exists() and arquivo.stat().st_size > 0


def iniciar_watchdog(callback=None, config=None, parar: threading.Event | None = None) -> None:
    config = config or carregar_config()
    if not config.habilitar_watchdog:
        logging.info("Watchdog desativado na configuracao.")
        return
    if callback is None:
        from ..services.processamento_service import processar_pasta

        callback = lambda: processar_pasta(config=config)

    parar = parar or threading.Event()
    entrada_inicial = montar_pastas(config).entrada
    conhecidos: dict[Path, int] = {
        pdf: pdf.stat().st_size for pdf in entrada_inicial.glob("*.pdf") if pdf.is_file()
    }
    logging.info("Watchdog iniciado para a pasta de entrada.")
    while not parar.wait(2):
        entrada = montar_pastas(config).entrada
        atuais = {pdf: pdf.stat().st_size for pdf in entrada.glob("*.pdf") if pdf.is_file()}
        novos = [pdf for pdf, tamanho in atuais.items() if conhecidos.get(pdf) != tamanho]
        conhecidos = atuais
        if novos and parar.wait(config.watchdog_delay_seconds):
            return
        prontos = [pdf for pdf in novos if aguardar_estabilizacao(pdf, segundos=3)]
        if prontos:
            logging.info("%s novo(s) PDF(s) estabilizado(s). Processamento automatico iniciado.", len(prontos))
            try:
                callback()
            except Exception:
                logging.exception("Falha no processamento automatico acionado pelo watchdog.")


def iniciar_watchdog_background(callback=None, config=None) -> threading.Thread:
    thread = threading.Thread(target=iniciar_watchdog, args=(callback, config), daemon=True, name="fiscal-folder-watcher")
    thread.start()
    return thread
