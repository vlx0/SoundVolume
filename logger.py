"""
logger.py
=========
Логгер в `soundvolume.log` + stderr. Rotating: 3 × 500 КБ.
"""

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOGGER_NAME = "soundvolume"
_LOGGER: logging.Logger | None = None


def setup() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    log_path = Path(__file__).parent / "soundvolume.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh = RotatingFileHandler(
            log_path, maxBytes=500_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(fmt)
        try:
            sh.stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
        except (AttributeError, OSError):
            pass
        logger.addHandler(sh)

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.error(
            "UNCAUGHT: %s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
    sys.excepthook = _hook

    _LOGGER = logger
    return logger


def get() -> logging.Logger:
    return _LOGGER or setup()