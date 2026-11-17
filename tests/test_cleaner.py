"""Юнит-тесты движка очистки (``skaycleartux.cleaner``)."""
from __future__ import annotations

import subprocess

from skaycleartux import cleaner
from skaycleartux.cleaner import (
    BY_KEY,
    CATEGORIES,
    Category,
    _clean_dir,
    _clean_trash,
    _linux_categories,
    _macos_categories,
    _scan_dir,
    _scan_trash,
    _trash_dirs,
    _windows_categories,
    clear_contents,
    disk_free,
    du_bytes,
    scan_all,
)


def res(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout, "")


# --------------------------------------------------------------------------- #
#  Category
# --------------------------------------------------------------------------- #
def test_category_properties():
    c = Category("k", "T", "D", "low")
    assert c.risk_ru == "безопасно"
    assert c.safe is True
    assert Category("k", "T", "D", "medium").risk_ru == "внимание"
    assert Category("k", "T", "D", "high").risk_ru == "опасно"


# --------------------------------------------------------------------------- #
#  Работа с каталогами
# --------------------------------------------------------------------------- #
def test_clear_contents(tmp_path):
    d = tmp_path / "cache"
    d.mkdir()
    (d / "a.txt").write_text("x" * 10)
    sub = d / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("y" * 20)
    freed = clear_contents(d)
    assert freed >= 30
    assert list(d.iterdir()) == []


def test_clear_contents_not_dir(tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    assert clear_contents(f) == 0


def test_scan_and_clean_dir(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "f").write_bytes(b"z" * 5)
    size, detail = _scan_dir(d)()
    assert size == 5
    assert "каталог" in detail
    freed, msg = _clean_dir(d)()
    assert freed == 5
    assert "очищено" in msg


def test_du_bytes(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"x" * 42)
    assert du_bytes(f) == 42


# --------------------------------------------------------------------------- #
#  Linux-категории
# --------------------------------------------------------------------------- #
class FakeMgr:
    key = "pacman"
    title = "pacman"

    def cache_scan(self):
        return 100, "кэш"

    def cache_clean(self):
        return 100, "очищено"

    def orphans_scan(self):
        return 0, "нет сирот"

    def orphans_clean(self):
        return 0, "сирот нет"


def test_linux_categories(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    cats = _linux_categories()
    keys = {c.key for c in cats}
    assert {"pkg-cache", "journal", "browser-cache", "orphans", "trash"} <= keys
    assert "yay-cache" not in keys
    pkg = next(c for c in cats if c.key == "pkg-cache")
    assert "pacman" in pkg.title
    assert pkg.needs_root is True


def test_linux_categories_yay(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which",
                        lambda n: "/usr/bin/yay" if n == "yay" else None)
    cats = _linux_categories()
    keys = [c.key for c in cats]
    assert "yay-cache" in keys
    assert "yay" in next(c for c in cats if c.key == "yay-cache").title


def test_linux_pkgcache_scan_clean(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    cats = {c.key: c for c in _linux_categories()}
    assert cats["pkg-cache"].scan() == (100, "кэш")
    assert cats["pkg-cache"].clean() == (100, "очищено")


def test_linux_journal_scan(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    monkeypatch.setattr(cleaner, "out",
                        lambda cmd, **k: "Archived and active journals take up 1.2G")
    cats = {c.key: c for c in _linux_categories()}
    size, detail = cats["journal"].scan()
    assert size == int(1.2e9)


def test_linux_journal_clean(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    seq = iter(["2G", "150M"])
    monkeypatch.setattr(cleaner, "out", lambda cmd, **k: next(seq))
    monkeypatch.setattr(cleaner, "run", lambda cmd, **k: res("", 0))
    cats = {c.key: c for c in _linux_categories()}
    freed, msg = cats["journal"].clean()
    assert freed == int(2e9) - int(150e6)
    assert "vacuum" in msg


def test_linux_flatpak_scan(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which",
                        lambda n: "/usr/bin/flatpak" if n == "flatpak" else None)
    monkeypatch.setattr(cleaner, "out", lambda cmd, **k: "Nothing unused")
    cats = {c.key: c for c in _linux_categories()}
    assert cats["flatpak-unused"].scan()[1] == "неиспользуемых нет"


def test_linux_docker_scan_no_docker(monkeypatch):
    monkeypatch.setattr(cleaner.linux_pkg, "detect", lambda *a, **k: FakeMgr())
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    cats = {c.key: c for c in _linux_categories()}
    assert cats["docker"].scan() == (0, "docker не установлен")


# --------------------------------------------------------------------------- #
#  macOS / Windows категории
# --------------------------------------------------------------------------- #
def test_macos_categories(monkeypatch):
    monkeypatch.setattr(cleaner.shutil, "which", lambda n: None)
    cats = _macos_categories()
    keys = {c.key for c in cats}
    assert {"brew-cache", "user-caches", "logs", "xcode", "trash"} == keys
    brew = next(c for c in cats if c.key == "brew-cache")
    assert brew.scan() == (0, "Homebrew не установлен")


def test_windows_categories(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    cats = _windows_categories()
    keys = {c.key for c in cats}
    assert {"temp", "browser-cache", "thumbnails", "trash"} <= keys


def test_windows_temp_scan_clean(monkeypatch, tmp_path):
    temp = tmp_path / "Temp"
    temp.mkdir()
    (temp / "a.tmp").write_bytes(b"x" * 10)
    sub = temp / "d"
    sub.mkdir()
    (sub / "b.tmp").write_bytes(b"y" * 20)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("TEMP", str(temp))
    cats = {c.key: c for c in _windows_categories()}
    assert cats["temp"].scan()[0] == 30
    freed, _ = cats["temp"].clean()
    assert freed >= 30


# --------------------------------------------------------------------------- #
#  Корзина
# --------------------------------------------------------------------------- #
def test_trash_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(cleaner, "HOME", tmp_path)
    monkeypatch.setattr(cleaner, "FAMILY", "macos")
    assert _trash_dirs() == [tmp_path / ".Trash"]
    monkeypatch.setattr(cleaner, "FAMILY", "linux")
    assert _trash_dirs() == [tmp_path / ".local" / "share" / "Trash"]


def test_scan_trash(monkeypatch, tmp_path):
    trash = tmp_path / ".local" / "share" / "Trash"
    (trash / "files").mkdir(parents=True)
    (trash / "files" / "a").write_bytes(b"x" * 7)
    monkeypatch.setattr(cleaner, "FAMILY", "linux")
    monkeypatch.setattr(cleaner, "HOME", tmp_path)
    size, detail = _scan_trash()
    assert size == 7
    assert detail == "корзина"
    freed, msg = _clean_trash()
    assert freed >= 7
    assert "очищена" in msg
    assert list((trash / "files").iterdir()) == []


def test_clean_trash_without_files_subdir(monkeypatch, tmp_path):
    trash = tmp_path / ".Trash"
    trash.mkdir()
    (trash / "loose").write_bytes(b"x" * 3)
    monkeypatch.setattr(cleaner, "HOME", tmp_path)
    monkeypatch.setattr(cleaner, "FAMILY", "macos")
    freed, _ = _clean_trash()
    assert freed >= 3


def test_windows_recycle_scan_clean(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setattr(cleaner, "out", lambda cmd, **k: "1234")
    monkeypatch.setattr(cleaner, "run", lambda cmd, **k: res("", 0))
    cats = {c.key: c for c in _windows_categories()}
    assert cats["trash"].scan() == (1234, "корзина Windows")
    assert cats["trash"].clean()[0] == 1234


def test_windows_recycle_scan_bad_output(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setattr(cleaner, "out", lambda cmd, **k: "не число")
    cats = {c.key: c for c in _windows_categories()}
    assert cats["trash"].scan() == (0, "корзина Windows")


# --------------------------------------------------------------------------- #
#  scan_all и disk_free
# --------------------------------------------------------------------------- #
def test_scan_all_handles_errors(monkeypatch):
    def boom():
        raise RuntimeError("сломалось")

    fake = [Category("a", "A", "d", "low", scan=lambda: (10, "ok")),
            Category("b", "B", "d", "low", scan=boom)]
    monkeypatch.setattr(cleaner, "CATEGORIES", fake)
    result = scan_all()
    assert result[0].size == 10
    assert result[1].size == 0
    assert "ошибка" in result[1].detail


def test_disk_free():
    free, total, percent = disk_free()
    assert total != "?"
    assert 0 <= percent <= 100


def test_module_categories_built():
    # на текущей ОС категории собраны и проиндексированы
    assert CATEGORIES
    assert set(BY_KEY) == {c.key for c in CATEGORIES}
