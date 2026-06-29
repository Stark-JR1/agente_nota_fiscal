"""Interface web modular com migracao gradual de rotas."""

from ..web_legacy import *  # noqa: F401,F403
from ..web_legacy import app

__all__ = ["app"]
