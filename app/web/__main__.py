import os

from . import app
from ..config import carregar_config
from ..watchers.folder_watcher import iniciar_watchdog_background


if __name__ == "__main__":
    config = carregar_config()
    if config.habilitar_watchdog:
        iniciar_watchdog_background(config=config)
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
