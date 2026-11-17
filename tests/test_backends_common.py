"""Юнит-тесты общего слоя ``skaycleartux.backends.common``."""
from __future__ import annotations

import subprocess
import sys

import pytest

from skaycleartux.backends import common


# --------------------------------------------------------------------------- #
#  Определение платформы
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("platform,expected", [
    ("linux", "linux"),
    ("linux2", "linux"),
    ("darwin", "macos"),
    ("win32", "windows"),
    ("cygwin", "other"),
])
def test_family(monkeypatch, platform, expected):
    monkeypatch.setattr(sys, "platform", platform)
    assert common.family() == expected


def test_os_short_name(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "macos")
    assert common.os_short_name() == "macOS"


def test_os_pretty_name_linux(monkeypatch, tmp_path):
    content = 'NAME=Test\nPRETTY_NAME="Arch Linux"\n'
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common.Path, "read_text",
                        lambda self, *a, **k: content)
    assert common.os_pretty_name() == "Arch Linux"


def test_os_pretty_name_linux_missing(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")

    def boom(self, *a, **k):
        raise OSError("нет файла")

    monkeypatch.setattr(common.Path, "read_text", boom)
    assert common.os_pretty_name() == "Linux"


# --------------------------------------------------------------------------- #
#  Права и повышение
# --------------------------------------------------------------------------- #
def test_is_admin_linux(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common.os, "geteuid", lambda: 0, raising=False)
    assert common.is_admin() is True
    monkeypatch.setattr(common.os, "geteuid", lambda: 1000, raising=False)
    assert common.is_admin() is False


def test_elevate_linux_pkexec(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common.shutil, "which",
                        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None)
    assert common._elevate(["foo", "bar"]) == ["pkexec", "foo", "bar"]


def test_elevate_linux_sudo_fallback(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common.shutil, "which",
                        lambda name: "/usr/bin/sudo" if name == "sudo" else None)
    assert common._elevate(["foo"]) == ["sudo", "-n", "foo"]


def test_elevate_linux_nothing(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common.shutil, "which", lambda name: None)
    assert common._elevate(["foo"]) == ["foo"]


def test_macos_root_quoting(monkeypatch):
    cmd = common._macos_root(["echo", "it's", 'say "hi"'])
    assert cmd[0] == "osascript"
    assert "administrator privileges" in cmd[-1]


# --------------------------------------------------------------------------- #
#  Запуск команд (мок subprocess)
# --------------------------------------------------------------------------- #
def test_run_uses_list_without_shell(monkeypatch):
    captured = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr(common.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(common, "FAMILY", "other")
    r = common.run(["echo", "hi"], timeout=5)
    assert r.stdout == "ok"
    assert isinstance(captured["cmd"], list)
    assert captured["kwargs"].get("shell") in (None, False)
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["timeout"] == 5


def test_run_never_raises_on_missing_binary(monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError("нет программы")

    monkeypatch.setattr(common.subprocess, "run", boom)
    monkeypatch.setattr(common, "FAMILY", "other")
    r = common.run(["nope"])
    assert r.returncode == 127


def test_run_timeout_returns_127(monkeypatch):
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(common.subprocess, "run", boom)
    monkeypatch.setattr(common, "FAMILY", "other")
    assert common.run(["slow"]).returncode == 127


def test_run_elevates_when_root(monkeypatch):
    captured = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(common.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common, "is_admin", lambda: False)
    monkeypatch.setattr(common.shutil, "which",
                        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None)
    common.run(["systemctl", "restart", "x"], root=True)
    assert captured["cmd"][:2] == ["pkexec", "systemctl"]


def test_run_no_elevation_when_admin(monkeypatch):
    captured = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(common.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(common, "is_admin", lambda: True)
    common.run(["whoami"], root=True)
    assert captured["cmd"] == ["whoami"]


def test_run_out_filters_sudo_noise(monkeypatch):
    out = "sudo: a password is required\nreal line\nSorry, try again"
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 1, out, ""))
    assert common.run_out(["x"]) == "real line"


def test_run_out_empty(monkeypatch):
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 0, "", ""))
    assert common.run_out(["x"]) == ""


# --------------------------------------------------------------------------- #
#  Файловые утилиты
# --------------------------------------------------------------------------- #
def test_read_text_and_write_text(tmp_path):
    path = tmp_path / "sub" / "file.txt"
    assert common.write_text(path, "  hello  ") is True
    assert common.read_text(path) == "hello"


def test_read_text_missing(tmp_path):
    assert common.read_text(tmp_path / "nope") == ""


def test_write_text_error(monkeypatch, tmp_path):
    monkeypatch.setattr(common.Path, "write_text",
                        lambda self, *a, **k: (_ for _ in ()).throw(OSError()))
    assert common.write_text(tmp_path / "x", "y") is False


def test_which(monkeypatch):
    monkeypatch.setattr(common.shutil, "which", lambda name: f"/bin/{name}")
    assert common.which("ls") == "/bin/ls"


# --------------------------------------------------------------------------- #
#  Пути приложения
# --------------------------------------------------------------------------- #
def test_app_data_dir_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert common.app_data_dir() == tmp_path / "SkayClearTux"


def test_app_data_dir_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "FAMILY", "windows")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert common.app_data_dir() == tmp_path / "SkayClearTux"


def test_app_data_dir_macos(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "macos")
    assert common.app_data_dir().name == "SkayClearTux"
    assert "Application Support" in str(common.app_data_dir())


def test_downloads_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(common.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Downloads").mkdir()
    assert common.downloads_dir() == tmp_path / "Downloads"


def test_downloads_dir_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(common.Path, "home", classmethod(lambda cls: tmp_path))
    assert common.downloads_dir() == tmp_path


# --------------------------------------------------------------------------- #
#  Размеры
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value,expected", [
    (0, "0 Б"),
    (512, "512 Б"),
    (1024, "1.0 КБ"),
    (1024 * 1024, "1.0 МБ"),
    (1024 ** 4, "1.0 ТБ"),
])
def test_human(value, expected):
    assert common.human(value) == expected


def test_dir_size_file_and_dir(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 100)
    assert common.dir_size(f) == 100
    assert common.dir_size(tmp_path) == 100
    assert common.dir_size(tmp_path / "missing") == 0


# --------------------------------------------------------------------------- #
#  Хэши и преобразования
# --------------------------------------------------------------------------- #
def test_hash_text_and_verify(tmp_path):
    assert common.hash_text("abc", "sha256") == \
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    f = tmp_path / "x"
    f.write_bytes(b"abc")
    digest = common.hash_file(str(f))
    assert common.verify_hash(str(f), digest) is True
    assert common.verify_hash(str(f), digest.upper()) is True
    assert common.verify_hash(str(f), "deadbeef") is False


@pytest.mark.parametrize("mode,text,expected", [
    ("base64e", "hi", "aGk="),
    ("base64d", "aGk=", "hi"),
    ("urle", "a b", "a%20b"),
    ("urld", "a%20b", "a b"),
    ("upper", "ab", "AB"),
    ("lower", "AB", "ab"),
    ("reverse", "abc", "cba"),
    ("strip", " a \n b ", "a\nb"),
    ("sort", "b\na", "a\nb"),
])
def test_text_transform(mode, text, expected):
    assert common.text_transform(mode, text) == expected


def test_text_transform_json():
    assert common.text_transform("json", '{"b":1}') == '{\n  "b": 1\n}'
    assert common.text_transform("jsonmin", '{ "b" : 1 }') == '{"b":1}'


def test_text_transform_count_and_error():
    assert "Символов: 3" in common.text_transform("count", "a b")
    assert common.text_transform("json", "{not json").startswith("Ошибка:")
    assert common.text_transform("unknown", "x") == "x"


# --------------------------------------------------------------------------- #
#  Копирование
# --------------------------------------------------------------------------- #
def test_copy_tree_file(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    ok, msg = common.copy_tree(str(src), str(tmp_path / "dst" / "src.txt"))
    assert ok and (tmp_path / "dst" / "src.txt").read_text() == "hello"


def test_copy_tree_dir_with_delete(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.txt").write_text("1")
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "extra.txt").write_text("2")
    ok, _msg = common.copy_tree(str(src), str(dst), delete=True)
    assert ok
    assert (dst / "keep.txt").exists()
    assert not (dst / "extra.txt").exists()


def test_copy_tree_missing_source(tmp_path):
    ok, msg = common.copy_tree(str(tmp_path / "nope"), str(tmp_path / "dst"))
    assert ok is False
    assert "источник не найден" in msg
