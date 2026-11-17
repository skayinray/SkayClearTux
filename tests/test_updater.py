"""Юнит-тесты дистанционных обновлений (``skaycleartux.updater``).

Сеть не используется: ``urllib.request.urlopen`` и ``subprocess.Popen``
подменяются. Отдельно проверяем враждебный ввод — мусорный JSON, пустой
адрес и несовпадение контрольной суммы.
"""
from __future__ import annotations
import sys

import hashlib
import json
from pathlib import Path

import pytest

from skaycleartux import updater


# --------------------------------------------------------------------------- #
#  Версии
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("1.3.0", (1, 3, 0)),
    ("v1.2.10", (1, 2, 10)),
    ("", ()),
    ("abc", ()),
])
def test_parse_version(text, expected):
    assert updater.parse_version(text) == expected


@pytest.mark.parametrize("remote,current,expected", [
    ("1.3.0", "1.2.0", True),
    ("1.2.0", "1.3.0", False),
    ("1.2.0", "1.2.0", False),
    ("1.2", "1.2.0", False),
    ("1.2.1", "1.2", True),
    ("мусор", "1.0.0", False),
])
def test_is_newer(remote, current, expected):
    assert updater.is_newer(remote, current) is expected


# --------------------------------------------------------------------------- #
#  Манифест
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Минимальная замена ответа urlopen (контекстный менеджер + read)."""

    def __init__(self, body: bytes, content_length: int | None = None,
                 final_url: str | None = None):
        self._body = body
        self._final_url = final_url
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def geturl(self) -> str:
        return self._final_url or "https://example.invalid/x"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            data, self._body = self._body, b""
            return data
        data, self._body = self._body[:size], self._body[size:]
        return data


def test_fetch_manifest_ok(monkeypatch):
    payload = {"version": "9.9.9", "url": "https://x/y"}
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(
                            json.dumps(payload).encode()))
    assert updater.fetch_manifest("https://x/manifest.json") == payload


@pytest.mark.parametrize("url", ["", "   "])
def test_fetch_manifest_empty_url(url):
    with pytest.raises(ValueError):
        updater.fetch_manifest(url)


@pytest.mark.parametrize("url", [
    "http://x/manifest.json",       # небезопасная схема
    "ftp://x/manifest.json",
    "file:///etc/passwd",
    "https://",                     # нет хоста
])
def test_fetch_manifest_rejects_unsafe_url(url):
    with pytest.raises(ValueError):
        updater.fetch_manifest(url)


def test_fetch_manifest_rejects_redirect_to_http(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(
                            b'{"version": "9.9.9"}',
                            final_url="http://evil/manifest.json"))
    with pytest.raises(ValueError, match="HTTPS"):
        updater.fetch_manifest("https://x/m.json")


def test_fetch_manifest_garbage_json(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(b"{not json"))
    with pytest.raises(json.JSONDecodeError):
        updater.fetch_manifest("https://x/m.json")


def test_fetch_manifest_not_dict(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(b"[1, 2, 3]"))
    with pytest.raises(ValueError):
        updater.fetch_manifest("https://x/m.json")


def test_fetch_manifest_without_version(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(b'{"url": "x"}'))
    with pytest.raises(ValueError):
        updater.fetch_manifest("https://x/m.json")


# --------------------------------------------------------------------------- #
#  Путь к текущему AppImage
# --------------------------------------------------------------------------- #
def test_appimage_path_set(monkeypatch, tmp_path):
    appimage = tmp_path / "App.AppImage"
    appimage.write_text("x")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    assert updater.appimage_path() == str(appimage)


def test_appimage_path_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("APPIMAGE", str(tmp_path / "gone"))
    assert updater.appimage_path() is None
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert updater.appimage_path() is None


# --------------------------------------------------------------------------- #
#  Скачивание
# --------------------------------------------------------------------------- #
def test_download_ok_and_checksum(monkeypatch, tmp_path):
    body = b"new appimage payload"
    digest = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(body, len(body)))
    seen = []
    dest = tmp_path / "dl.AppImage"
    updater.download("https://x/a", dest, expected_sha256=digest,
                     progress=lambda done, total: seen.append((done, total)))
    assert dest.read_bytes() == body
    assert seen and seen[-1] == (len(body), len(body))


def test_download_bad_checksum_removes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(b"tampered"))
    dest = tmp_path / "dl.AppImage"
    with pytest.raises(ValueError, match="контрольная сумма"):
        updater.download("https://x/a", dest, expected_sha256="deadbeef")
    assert not dest.exists()


def test_download_without_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(b"data"))
    dest = tmp_path / "dl.AppImage"
    updater.download("https://x/a", dest)
    assert dest.read_bytes() == b"data"


@pytest.mark.parametrize("url", [
    "http://x/a", "ftp://x/a", "file:///etc/passwd", "", "https://",
])
def test_download_rejects_unsafe_url(url, tmp_path):
    with pytest.raises(ValueError):
        updater.download(url, tmp_path / "dl.AppImage")


def test_download_rejects_redirect_to_http(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResponse(
                            b"data", final_url="http://evil/a"))
    with pytest.raises(ValueError, match="HTTPS"):
        updater.download("https://x/a", tmp_path / "dl.AppImage")


# --------------------------------------------------------------------------- #
#  Безопасность имён файлов (path traversal)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,expected", [
    ("SkayClearTux-1.3.0.AppImage", "SkayClearTux-1.3.0.AppImage"),
    ("../../etc/passwd", "passwd"),
    ("/etc/shadow", "shadow"),
    ("..\\..\\Windows\\system32\\evil.exe", "evil.exe"),
    ("..", "SkayClearTux.AppImage"),
    (".", "SkayClearTux.AppImage"),
    ("", "SkayClearTux.AppImage"),
    (".hidden", "SkayClearTux.AppImage"),
])
def test_safe_filename(name, expected):
    assert updater.safe_filename(name) == expected


def test_temp_download_path_ignores_traversal():
    path = updater.temp_download_path("../../etc/passwd")
    try:
        assert path.name.startswith("skaycleartux-update-")
        assert path.suffix == ".AppImage"
    finally:
        path.unlink(missing_ok=True)


def test_install_appimage_rejects_directory(tmp_path):
    downloaded = tmp_path / "new.AppImage"
    downloaded.write_bytes(b"new")
    with pytest.raises(ValueError):
        updater.install_appimage(downloaded, str(tmp_path))



# --------------------------------------------------------------------------- #
#  Установка
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(sys.platform == "win32", reason="No AppImage on Windows")
def test_install_appimage_replaces_target(tmp_path):
    downloaded = tmp_path / "new.AppImage"
    downloaded.write_bytes(b"new")
    target = tmp_path / "old.AppImage"
    target.write_bytes(b"old")
    updater.install_appimage(downloaded, str(target))
    assert target.read_bytes() == b"new"
    assert target.stat().st_mode & 0o111  # исполняемый


def test_install_appimage_cross_device_fallback(monkeypatch, tmp_path):
    downloaded = tmp_path / "new.AppImage"
    downloaded.write_bytes(b"new")
    target = tmp_path / "old.AppImage"
    target.write_bytes(b"old")

    real_replace = updater.os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("cross-device link")
        return real_replace(src, dst)

    monkeypatch.setattr(updater.os, "replace", flaky_replace)
    updater.install_appimage(downloaded, str(target))
    assert target.read_bytes() == b"new"


# --------------------------------------------------------------------------- #
#  Перезапуск и временный путь
# --------------------------------------------------------------------------- #
def test_restart_popen(monkeypatch, tmp_path):
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        return object()

    monkeypatch.setattr(updater.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("APPIMAGE_EXTRACT_AND_RUN", "1")
    updater.restart(str(tmp_path / "App.AppImage"))
    assert captured["cmd"] == [str(tmp_path / "App.AppImage")]
    assert "APPIMAGE_EXTRACT_AND_RUN" not in captured["env"]


def test_temp_download_path():
    path = updater.temp_download_path("SkayClearTux-1.3.0-x86_64.AppImage")
    assert isinstance(path, Path)
    assert path.suffix == ".AppImage"
    assert path.exists()
    path.unlink()


def test_temp_download_path_default_suffix():
    path = updater.temp_download_path("noext")
    assert path.suffix == ".AppImage"
    path.unlink()
