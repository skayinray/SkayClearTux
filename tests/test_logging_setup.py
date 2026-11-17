import sys
"""Тесты логирования — ``skaycleartux.logging_setup``.

Проверяем выбор каталога под каждую ОС, создание файла лога, ротацию и
поведение, когда каталог недоступен для записи.
"""
from __future__ import annotations

import logging
import logging.handlers

import pytest

from skaycleartux import logging_setup
from skaycleartux.backends import common


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch, tmp_path):
    monkeypatch.setattr(logging_setup, "_configured", False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(common, "FAMILY", "linux")
    logger = logging.getLogger(logging_setup.LOGGER_NAME)
    logger.propagate = True

    def drop_file_handlers():
        # трогаем только свой файловый лог, не сбрасывая хендлеры pytest
        for handler in list(logger.handlers):
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                logger.removeHandler(handler)
                handler.close()

    drop_file_handlers()
    yield
    drop_file_handlers()


# --------------------------------------------------------------------------- #
#  Пути
# --------------------------------------------------------------------------- #
def test_log_dir_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert logging_setup.log_dir() == tmp_path / "state" / "SkayClearTux"


def test_log_dir_linux_default(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(logging_setup.Path, "home",
                        classmethod(lambda cls: tmp_path))
    assert logging_setup.log_dir() == tmp_path / ".local" / "state" / "SkayClearTux"


def test_log_dir_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "macos")
    monkeypatch.setattr(logging_setup.Path, "home",
                        classmethod(lambda cls: tmp_path))
    assert logging_setup.log_dir() == tmp_path / "Library" / "Logs" / "SkayClearTux"


def test_log_dir_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert logging_setup.log_dir() == tmp_path / "Local" / "SkayClearTux" / "Logs"


def test_log_path_uses_file_name():
    assert logging_setup.log_path().name == logging_setup.FILE_NAME


# --------------------------------------------------------------------------- #
#  Настройка
# --------------------------------------------------------------------------- #
def test_get_logger_names():
    assert logging_setup.get_logger().name == logging_setup.LOGGER_NAME
    assert logging_setup.get_logger("backends.common").name == \
        f"{logging_setup.LOGGER_NAME}.backends.common"


def test_setup_logging_creates_file_and_writes():
    path = logging_setup.setup_logging()
    assert path is not None and path.exists()
    logging_setup.get_logger("test").error("проверка записи")
    for handler in logging.getLogger(logging_setup.LOGGER_NAME).handlers:
        handler.flush()
    assert "проверка записи" in path.read_text(encoding="utf-8")


def _file_handlers():
    logger = logging.getLogger(logging_setup.LOGGER_NAME)
    return [h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)]


def test_setup_logging_is_idempotent():
    first = logging_setup.setup_logging()
    second = logging_setup.setup_logging()
    assert first == second
    # pytest добавляет свои LogCaptureHandler, поэтому считаем только файловые
    assert len(_file_handlers()) == 1


def test_setup_logging_rotating_handler():
    logging_setup.setup_logging()
    handler = _file_handlers()[0]
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == logging_setup.MAX_BYTES
    assert handler.backupCount == logging_setup.BACKUPS


@pytest.mark.skipif(sys.platform == "win32", reason="Encoding issues on Windows")
def test_setup_logging_unwritable_returns_none(monkeypatch, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("я файл, а не каталог")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocker))
    assert logging_setup.setup_logging() is None


# --------------------------------------------------------------------------- #
#  Ошибки бэкендов попадают в лог
# --------------------------------------------------------------------------- #
def test_run_missing_command_is_logged(caplog, monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("нет такой программы")

    caplog.set_level(logging.WARNING, logger="skaycleartux.backends.common")
    from skaycleartux.backends import common as c
    monkeypatch.setattr(c.subprocess, "run", boom)
    result = c.run(["нет-такой-команды"])
    assert result.returncode == 127
    assert any("не удалось запустить" in rec.message for rec in caplog.records)


def test_run_timeout_is_logged(caplog, monkeypatch):
    import subprocess

    from skaycleartux.backends import common as c

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    caplog.set_level(logging.WARNING, logger="skaycleartux.backends.common")
    monkeypatch.setattr(c.subprocess, "run", timeout)
    result = c.run(["sleep", "999"], timeout=1)
    assert result.returncode == 127
    assert any("таймаут" in rec.message for rec in caplog.records)
