"""Дистанционные обновления SkayClearTux.

Программа периодически читает JSON-манифест по URL вида:

    {
      "version": "1.2.0",
      "url": "https://.../SkayClearTux-1.2.0-x86_64.AppImage",
      "sha256": "....",           // необязательно, но рекомендуется
      "notes": "Что нового...",
      "published": "2026-11-16"
    }

Если версия в манифесте новее текущей — показываем уведомление, а по нажатию
кнопки «Обновить» скачиваем новый AppImage, проверяем контрольную сумму,
подменяем файл и перезапускаем программу.

Всё, что нужно, — разместить манифест и файл на любом статическом хостинге
(GitHub Releases, Gist, свой сервер). Готовый CI для этого лежит в
.github/workflows/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

USER_AGENT = f"SkayClearTux/{__version__}"


# --------------------------------------------------------------------------- #
def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(text)))


def is_newer(remote: str, current: str = __version__) -> bool:
    r, c = parse_version(remote), parse_version(current)
    if not r:
        return False
    # выравниваем длину
    length = max(len(r), len(c))
    r += (0,) * (length - len(r))
    c += (0,) * (length - len(c))
    return r > c


def fetch_manifest(url: str, timeout: float = 12.0) -> dict:
    if not url or not url.strip():
        raise ValueError("не задан адрес манифеста обновлений")
    req = urllib.request.Request(url.strip(), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict) or "version" not in data:
        raise ValueError("манифест повреждён: нет поля version")
    return data


def appimage_path() -> str | None:
    """Путь к запущенному AppImage (переменную ставит сам AppImage)."""
    path = os.environ.get("APPIMAGE")
    if path and Path(path).exists():
        return path
    return None


def download(url: str, dest: Path, expected_sha256: str = "",
             progress=None) -> Path:
    """Скачивает файл в dest, при необходимости проверяет sha256."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            hasher.update(chunk)
            done += len(chunk)
            if progress is not None:
                progress(done, total)
    if expected_sha256:
        actual = hasher.hexdigest().lower()
        if actual != expected_sha256.strip().lower():
            try:
                dest.unlink()
            except OSError:
                pass
            raise ValueError(
                "контрольная сумма не совпала — файл повреждён или подменён")
    return dest


def install_appimage(downloaded: Path, target: str) -> None:
    """Заменяет текущий AppImage новым (атомарно) и делает его исполняемым."""
    target_path = Path(target)
    os.chmod(downloaded, 0o755)
    try:
        os.replace(downloaded, target_path)
    except OSError:
        # на случай разных файловых систем — копируем рядом и подменяем
        tmp = target_path.with_suffix(target_path.suffix + ".new")
        with open(downloaded, "rb") as src, open(tmp, "wb") as dst:
            dst.write(src.read())
        os.chmod(tmp, 0o755)
        os.replace(tmp, target_path)


def restart(target: str) -> None:
    """Запускает новую копию и не мешает текущему процессу закрыться."""
    env = dict(os.environ)
    env.pop("APPIMAGE_EXTRACT_AND_RUN", None)
    subprocess.Popen([target], env=env, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def temp_download_path(filename: str) -> Path:
    suffix = Path(filename).suffix or ".AppImage"
    fd, name = tempfile.mkstemp(prefix="skaycleartux-update-", suffix=suffix)
    os.close(fd)
    return Path(name)
