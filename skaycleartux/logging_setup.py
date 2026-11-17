"""Логирование SkayClearTux в стандартный каталог логов ОС.

Ошибки бэкендов и необработанные исключения пишутся в файл с ротацией, чтобы
пользователь мог приложить лог к Issue, а программа не «молчала» при сбоях.

Путь к логу:

* Linux — ``$XDG_STATE_HOME/SkayClearTux/skaycleartux.log``
  (по умолчанию ``~/.local/state/SkayClearTux/skaycleartux.log``);
* macOS — ``~/Library/Logs/SkayClearTux/skaycleartux.log``;
* Windows — ``%LOCALAPPDATA%\\SkayClearTux\\Logs\\skaycleartux.log``.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "skaycleartux"
FILE_NAME = "skaycleartux.log"
MAX_BYTES = 512 * 1024
BACKUPS = 3

_configured = False


def _family() -> str:
    # ленивый импорт: logging_setup не должен тянуть backends на старте
    from .backends import common
    return common.FAMILY


def log_dir() -> Path:
    """Каталог логов в стандартном для текущей ОС месте."""
    fam = _family()
    if fam == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local")
        return Path(base) / "SkayClearTux" / "Logs"
    if fam == "macos":
        return Path.home() / "Library" / "Logs" / "SkayClearTux"
    base = os.environ.get("XDG_STATE_HOME") or str(
        Path.home() / ".local" / "state")
    return Path(base) / "SkayClearTux"


def log_path() -> Path:
    return log_dir() / FILE_NAME


def get_logger(name: str = "") -> logging.Logger:
    """Логгер ``skaycleartux`` (или его потомок ``skaycleartux.<name>``)."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def _install_excepthook(logger: logging.Logger) -> None:
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        logger.error("Необработанное исключение",
                     exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = hook


def setup_logging(level: int = logging.INFO) -> Path | None:
    """Включает файловый лог с ротацией.

    Возвращает путь к файлу лога или ``None``, если каталог недоступен для
    записи (в этом случае приложение продолжает работать без файла лога).
    """
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return log_path()

    logger.setLevel(level)
    logger.propagate = False
    try:
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            directory / FILE_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS,
            encoding="utf-8")
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    _configured = True
    _install_excepthook(logger)
    logger.info("SkayClearTux запущен, лог: %s", directory / FILE_NAME)
    return directory / FILE_NAME
