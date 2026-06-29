from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..config import carregar_config
from ..paths import montar_pastas


TEMP_SUFFIXES = {".tmp", ".crdownload", ".part", ".download", ".sync"}
TEMP_NAMES = {"desktop.ini", "thumbs.db"}


def arquivo_temporario(caminho: Path) -> bool:
    nome = caminho.name.lower()
    return nome in TEMP_NAMES or nome.startswith("~$") or caminho.suffix.lower() in TEMP_SUFFIXES


def pdf_monitoravel(caminho: str | Path) -> bool:
    arquivo = Path(caminho)
    return arquivo.suffix.lower() == ".pdf" and not arquivo_temporario(arquivo)


def aguardar_estabilizacao(
    arquivo: str | Path,
    delay_seconds: int = 30,
    stable_checks: int = 3,
    stable_interval_seconds: float = 5,
    sleep: Callable[[float], None] = time.sleep,
    segundos: int | None = None,
    intervalo: float | None = None,
) -> bool:
    caminho = Path(arquivo)
    if segundos is not None:
        delay_seconds = 0
        stable_checks = max(1, int(segundos))
    if intervalo is not None:
        stable_interval_seconds = intervalo

    sleep(max(0, delay_seconds))
    tamanho_anterior = tamanho_arquivo(caminho)
    if tamanho_anterior is None or tamanho_anterior <= 0:
        logging.info("Arquivo nao estabilizado ou inacessivel: %s", caminho)
        return False

    for _ in range(max(1, stable_checks)):
        sleep(max(0, stable_interval_seconds))
        tamanho_atual = tamanho_arquivo(caminho)
        if tamanho_atual is None or tamanho_atual <= 0:
            logging.info("Arquivo nao estabilizado ou inacessivel: %s", caminho)
            return False
        if tamanho_atual != tamanho_anterior:
            logging.info("Arquivo ainda em alteracao: %s", caminho)
            return False
        tamanho_anterior = tamanho_atual

    logging.info("Arquivo estabilizado: %s", caminho)
    return True


def tamanho_arquivo(caminho: Path) -> int | None:
    try:
        return caminho.stat().st_size
    except OSError:
        return None


class CoordenadorProcessamento:
    def __init__(self, callback: Callable[[], object]) -> None:
        self.callback = callback
        self._lock = threading.Lock()
        self._processamento_em_andamento = False
        self._novo_processamento_pendente = False

    def solicitar_processamento(self) -> None:
        with self._lock:
            if self._processamento_em_andamento:
                self._novo_processamento_pendente = True
                logging.info("Processamento ja em andamento. Novo processamento ficou pendente.")
                return
            self._processamento_em_andamento = True

        try:
            while True:
                logging.info("Processamento iniciado pelo watchdog.")
                try:
                    self.callback()
                    logging.info("Processamento finalizado pelo watchdog.")
                except Exception:
                    logging.exception("Erro no processamento automatico acionado pelo watchdog.")

                with self._lock:
                    if not self._novo_processamento_pendente:
                        self._processamento_em_andamento = False
                        return
                    self._novo_processamento_pendente = False
                    logging.info("Novo arquivo chegou durante o processamento. Rodando novamente.")
        except Exception:
            with self._lock:
                self._processamento_em_andamento = False
            logging.exception("Erro no monitoramento.")


class EntradaEventHandler:
    def __init__(self, config, coordenador: CoordenadorProcessamento) -> None:
        self.config = config
        self.coordenador = coordenador
        self._arquivos_em_estabilizacao: set[Path] = set()
        self._lock = threading.Lock()

    def on_created(self, event) -> None:
        self._tratar_evento(event)

    def on_moved(self, event) -> None:
        destino = getattr(event, "dest_path", None)
        if destino:
            self._tratar_caminho(Path(destino))

    def on_modified(self, event) -> None:
        self._tratar_evento(event)

    def _tratar_evento(self, event) -> None:
        if getattr(event, "is_directory", False):
            return
        origem = getattr(event, "src_path", None)
        if origem:
            self._tratar_caminho(Path(origem))

    def _tratar_caminho(self, caminho: Path) -> None:
        if not pdf_monitoravel(caminho):
            logging.info("Arquivo ignorado pelo watchdog: %s", caminho)
            return

        caminho = caminho.resolve()
        with self._lock:
            if caminho in self._arquivos_em_estabilizacao:
                return
            self._arquivos_em_estabilizacao.add(caminho)

        logging.info("Arquivo detectado pelo watchdog: %s", caminho)
        thread = threading.Thread(target=self._aguardar_e_processar, args=(caminho,), daemon=True)
        thread.start()

    def _aguardar_e_processar(self, caminho: Path) -> None:
        try:
            estabilizado = aguardar_estabilizacao(
                caminho,
                delay_seconds=self.config.watchdog_delay_seconds,
                stable_checks=self.config.watchdog_stable_checks,
                stable_interval_seconds=self.config.watchdog_stable_interval_seconds,
            )
            if estabilizado:
                self.coordenador.solicitar_processamento()
        finally:
            with self._lock:
                self._arquivos_em_estabilizacao.discard(caminho)


def configurar_log_watchdog(pasta_logs: Path) -> None:
    pasta_logs.mkdir(parents=True, exist_ok=True)
    caminho_log = pasta_logs / f"watchdog_{datetime.now().strftime('%Y-%m-%d')}.log"
    logging.basicConfig(
        filename=caminho_log,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
        force=True,
    )


def criar_callback_processamento(config):
    from ..services.processamento_service import processar_pasta

    return lambda: processar_pasta(config=config)


def iniciar_watchdog(callback=None, config=None, parar: threading.Event | None = None) -> None:
    config = config or carregar_config()
    pastas = montar_pastas(config)
    configurar_log_watchdog(pastas.logs)

    if not config.habilitar_watchdog:
        logging.info("Watchdog desativado na configuracao.")
        return

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise RuntimeError("Instale as dependencias com: pip install -r requirements.txt") from exc

    callback = callback or criar_callback_processamento(config)
    coordenador = CoordenadorProcessamento(callback)
    entrada_handler = EntradaEventHandler(config, coordenador)

    class Handler(FileSystemEventHandler):
        def on_created(self, event) -> None:
            entrada_handler.on_created(event)

        def on_moved(self, event) -> None:
            entrada_handler.on_moved(event)

        def on_modified(self, event) -> None:
            entrada_handler.on_modified(event)

    handler = Handler()
    observer = Observer()
    observer.schedule(handler, str(pastas.entrada), recursive=False)
    observer.start()

    logging.info("Watchdog iniciado.")
    logging.info("Pasta monitorada: %s", pastas.entrada)

    parar = parar or threading.Event()
    try:
        while not parar.wait(1):
            pass
    except KeyboardInterrupt:
        logging.info("Watchdog interrompido pelo usuario.")
    except Exception:
        logging.exception("Erro no monitoramento.")
    finally:
        observer.stop()
        observer.join()


def iniciar_watchdog_background(callback=None, config=None) -> threading.Thread:
    thread = threading.Thread(
        target=iniciar_watchdog,
        args=(callback, config),
        daemon=True,
        name="fiscal-folder-watcher",
    )
    thread.start()
    return thread


def main() -> None:
    iniciar_watchdog()


if __name__ == "__main__":
    main()
