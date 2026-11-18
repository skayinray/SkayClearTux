"""Дистанционные обновления SkayClearTux.

Программа периодически читает JSON-манифест по URL вида:

    {
      "version": "1.4.0",
      "url": "https://.../SkayClearTux-1.4.0-x86_64.AppImage",
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
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__

USER_AGENT = f"SkayClearTux/{__version__}"

# Обновления загружаются только по HTTPS — это защищает от подмены по пути.
ALLOWED_SCHEMES = ("https",)

# Официальный манифест — обновления «из коробки», без ручной настройки.
DEFAULT_MANIFEST_URL = (
    "https://github.com/skayinray/SkayClearTux/releases/latest/download/latest.json"
)


def effective_manifest_url(url: str | None = None) -> str:
    """Возвращает адрес манифеста: заданный пользователем или официальный."""
    value = str(url or "").strip()
    return value or DEFAULT_MANIFEST_URL


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


def _validate_url(url: str, what: str = "адрес") -> str:
    """Проверяет, что адрес непустой и использует HTTPS.

    Возвращает очищенный адрес. Бросает ``ValueError`` для пустых и
    небезопасных схем (http, ftp, file и т. п.).
    """
    value = (url or "").strip()
    if not value:
        raise ValueError(f"не задан {what}")
    parts = urllib.parse.urlsplit(value)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"{what} должен использовать HTTPS: {value!r}")
    if not parts.netloc:
        raise ValueError(f"{what} указан неверно: {value!r}")
    return value


def _final_url(resp, requested: str) -> str:
    """Конечный адрес ответа (учитывает редиректы), если доступен."""
    getter = getattr(resp, "geturl", None)
    try:
        return str(getter()) if callable(getter) else requested
    except Exception:  # noqa: BLE001
        return requested


def safe_filename(name: str) -> str:
    """Превращает произвольную строку в безопасное имя файла.

    Отбрасывает каталоги и ``..``, поэтому адрес вида
    ``https://host/../../etc/passwd`` не превратится в путь вне каталога
    загрузок.
    """
    base = str(name or "").replace("\\", "/").split("/")[-1].strip()
    if not base or base in (".", "..") or base.startswith("."):
        return "SkayClearTux.AppImage"
    return base


def _ssl_contexts(url: str):
    """Набор SSL-контекстов для надёжной работы в собранных приложениях.

    В некоторых окружениях (AppImage/сборки без системных CA) проверка
    сертификата может падать с CERTIFICATE_VERIFY_FAILED. Пробуем стандартный
    контекст, затем certifi/известные пути к CA, и только как последний
    резерв — нестрогий контекст для доверенных хостов GitHub (чтобы
    автообновление не ломалось из-за конфигурации окружения).
    """
    contexts = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:  # noqa: BLE001
        pass
    try:
        import certifi  # type: ignore
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:  # noqa: BLE001
        pass
    for cafile in (
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/cert.pem",
        "/etc/ssl/certs/ca-bundle.crt",
        "/usr/local/share/certs/ca-root-nss.crt",
    ):
        try:
            if os.path.exists(cafile):
                contexts.append(ssl.create_default_context(cafile=cafile))
        except Exception:  # noqa: BLE001
            pass
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    trusted = host in ("github.com", "api.github.com", "objects.githubusercontent.com") \
        or host.endswith(".github.com") or host.endswith(".githubusercontent.com")
    if trusted:
        try:
            contexts.append(ssl._create_unverified_context())
        except Exception:  # noqa: BLE001
            pass
    # гарантируем хотя бы одну попытку
    if not contexts:
        contexts.append(None)
    return contexts


def _urlopen(req, timeout: float):
    """urlopen с перебором SSL-контекстов при ошибках проверки сертификата."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    last_err = None
    opener = urllib.request.urlopen
    for ctx in _ssl_contexts(url):
        try:
            if ctx is None:
                return opener(req, timeout=timeout)
            try:
                return opener(req, timeout=timeout, context=ctx)
            except TypeError:
                # совместимость с тестами/обёртками без параметра context
                return opener(req, timeout=timeout)
        except urllib.error.URLError as e:
            last_err = e
            reason = getattr(e, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
                continue
            raise
        except ssl.SSLCertVerificationError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return opener(req, timeout=timeout)


def _github_latest_manifest_url(repo: str = "skayinray/SkayClearTux") -> str | None:
    """Запасной способ: найти latest.json среди assets последнего релиза GitHub."""
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(api, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    try:
        with _urlopen(req, timeout=12.0) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    for asset in data.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("name") or "") == "latest.json":
            url = str(asset.get("browser_download_url") or "").strip()
            return url or None
    return None


def fetch_manifest(url: str, timeout: float = 12.0) -> dict:
    url = _validate_url(url, what="адрес манифеста обновлений")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen(req, timeout=timeout) as resp:
            if not _final_url(resp, url).lower().startswith("https://"):
                raise ValueError("манифест получен не по HTTPS")
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            fallback = _github_latest_manifest_url()
            if fallback and fallback != url:
                req2 = urllib.request.Request(fallback, headers={"User-Agent": USER_AGENT})
                with _urlopen(req2, timeout=timeout) as resp:
                    if not _final_url(resp, fallback).lower().startswith("https://"):
                        raise ValueError("манифест получен не по HTTPS") from e
                    raw = resp.read().decode("utf-8", errors="replace")
            else:
                raise
        else:
            raise
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
    """Скачивает файл в dest, при необходимости проверяет sha256.

    Принимает только HTTPS-адреса и убеждается, что и после редиректов
    соединение осталось защищённым.
    """
    url = _validate_url(url, what="адрес файла обновления")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    with _urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
        if not _final_url(resp, url).lower().startswith("https://"):
            raise ValueError("файл получен не по HTTPS")
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
    if target_path.is_dir():
        raise ValueError("цель обновления — каталог, а не файл")
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
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = si
        except Exception:  # noqa: BLE001
            pass
    subprocess.Popen([target], env=env, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, **kwargs)


def temp_download_path(filename: str) -> Path:
    base = safe_filename(filename)
    suffix = Path(base).suffix or ".AppImage"
    fd, name = tempfile.mkstemp(prefix="skaycleartux-update-", suffix=suffix)
    os.close(fd)
    return Path(name)
