"""Юнит-тесты менеджеров пакетов Linux (``backends.linux_pkg``)."""
from __future__ import annotations

import subprocess

import pytest

from skaycleartux.backends import linux_pkg
from skaycleartux.backends.linux_pkg import (
    ApkPkg,
    AptPkg,
    DnfPkg,
    PacmanPkg,
    PkgManager,
    ZypperPkg,
    _human_size,
    _os_ids,
    _os_release,
    detect,
    os_release_id,
)


def res(stdout="", code=0, stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    monkeypatch.setattr(linux_pkg, "_cached", None)


# --------------------------------------------------------------------------- #
#  Утилиты
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("12,3 MiB", int(12.3 * 1024 ** 2)),
    ("4.5 MB", int(4.5 * 1000 ** 2)),
    ("1 GiB", 1024 ** 3),
    ("512 B", 512),
    ("no size here", 0),
])
def test_human_size(text, expected):
    assert _human_size(text) == expected


def test_os_release_and_ids(monkeypatch):
    content = 'ID=ubuntu\nID_LIKE="debian"\nPRETTY_NAME="Ubuntu 24.04"\n'
    monkeypatch.setattr(linux_pkg.Path, "read_text",
                        lambda self, *a, **k: content)
    assert _os_release()["ID"] == "ubuntu"
    assert {"ubuntu", "debian"} <= _os_ids()
    assert os_release_id() == "ubuntu"


def test_base_manager_stubs():
    m = PkgManager()
    assert m.search("x") == []
    assert m.install(["x"])[0] is False
    assert m.remove(["x"])[0] is False
    assert "Недоступно" in m.files("x")
    assert "Недоступно" in m.owner("/x")
    assert "Недоступно" in m.info("x")
    assert m.updates() == []
    assert m.upgrade()[0] is False
    assert m.cache_scan() == (0, "кэш пакетов недоступен")
    assert m.orphans_scan() == (0, "не поддерживается")


def test_tail_helper():
    r = res("out", 0, "err")
    assert PkgManager._tail(r) == "out\nerr"


# --------------------------------------------------------------------------- #
#  pacman
# --------------------------------------------------------------------------- #
def test_pacman_search(fake_run):
    out = ("extra/neovim 0.10.0-1 [installed]\n"
           "    Vim-fork focused on extensibility\n"
           "extra/vim 9.1-1\n"
           "    Vi IMproved\n")
    fake_run(default=res(out))
    rows = PacmanPkg().search("vim")
    assert rows[0]["name"] == "neovim"
    assert rows[0]["installed"] is True
    assert "Vim-fork" in rows[0]["desc"]
    assert rows[1]["installed"] is False


def test_pacman_search_empty(fake_run):
    assert PacmanPkg().search("  ") == []


def test_pacman_updates(fake_run):
    fake_run(default=res("vim 9.0 -> 9.1\nfirefox 100\n"))
    rows = PacmanPkg().updates()
    assert rows[0] == {"name": "vim", "old": "9.0", "new": "9.1"}
    assert rows[1]["name"] == "firefox"


def test_pacman_install(fake_run):
    fake_run(default=res("installed ok", 0))
    ok, out = PacmanPkg().install(["vim"])
    assert ok and "installed ok" in out


def test_pacman_files_owner_info(fake_run):
    fake_run(default=res("/usr/bin/vim", 0))
    assert PacmanPkg().files("vim") == "/usr/bin/vim"
    assert PacmanPkg().files("") == "Укажи имя пакета"


# --------------------------------------------------------------------------- #
#  apt
# --------------------------------------------------------------------------- #
def test_apt_installed_and_madison(fake_run):
    def handler(cmd, **kwargs):
        if cmd[0] == "dpkg-query":
            return res("vim\t9.0\tinstall ok installed\n")
        if cmd[0] == "apt-cache" and cmd[1] == "madison":
            return res(" vim | 9.1 | http://deb.debian.org/debian unstable/main amd64\n")
        return res("")

    fake_run(handler=handler)
    assert AptPkg()._installed() == {"vim": "9.0"}
    assert AptPkg()._madison(["vim"]) == {"vim": ("9.1", "unstable")}


def test_apt_search(fake_run):
    def handler(cmd, **kwargs):
        if cmd[:2] == ["apt-cache", "search"]:
            return res("vim - Vi IMproved\nnano - editor\n")
        if cmd[1] == "madison":
            return res(" vim | 9.1 | http://x/debian main\n")
        if cmd[0] == "dpkg-query":
            return res("vim\t9.0\tinstall ok installed\n")
        return res("")

    fake_run(handler=handler)
    rows = AptPkg().search("vim")
    assert rows[0]["name"] == "vim"
    assert rows[0]["installed"] is True
    assert rows[0]["version"] == "9.0"  # установленная версия приоритетнее


def test_apt_updates(fake_run):
    fake_run(default=res(
        "Listing...\nvim/stable 9.1 amd64 [upgradable from: 9.0]\n"))
    rows = AptPkg().updates()
    assert rows[0] == {"name": "vim", "old": "9.0", "new": "9.1"}


def test_apt_orphans(fake_run):
    def handler(cmd, **kwargs):
        if cmd[:3] == ["apt-get", "-s", "autoremove"]:
            return res("Remv libfoo [1.0]\n")
        if cmd[0] == "dpkg-query":
            return res("libfoo\t100\n")
        return res("")

    fake_run(handler=handler)
    assert AptPkg()._orphan_names() == ["libfoo"]
    size, names = AptPkg().orphans_scan()
    assert size == 100 * 1024
    assert names == "libfoo"


# --------------------------------------------------------------------------- #
#  dnf
# --------------------------------------------------------------------------- #
def test_dnf_installed_and_available(fake_run):
    def handler(cmd, **kwargs):
        if cmd[0] == "rpm":
            return res("vim\t9.0-1\n")
        if cmd[1:3] == ["-q", "list"]:
            return res("vim.x86_64 9.1-1 fedora\n")
        return res("")

    fake_run(handler=handler)
    assert DnfPkg()._installed() == {"vim": "9.0-1"}
    assert DnfPkg()._available("vim") == {"vim": ("9.1-1", "fedora")}


def test_dnf_search(fake_run):
    def handler(cmd, **kwargs):
        if cmd[0] == "rpm":
            return res("")
        if cmd[1:3] == ["-q", "list"]:
            return res("")
        if cmd[1:3] == ["-q", "search"]:
            return res("vim.x86_64 : Vi IMproved\n")
        return res("")

    fake_run(handler=handler)
    rows = DnfPkg().search("vim")
    assert rows[0]["name"] == "vim"
    assert rows[0]["desc"] == "Vi IMproved"


def test_dnf_updates(fake_run):
    fake_run(default=res("vim.x86_64 9.1-1 fedora\n"))
    assert DnfPkg().updates() == [{"name": "vim", "old": "", "new": "9.1-1"}]


# --------------------------------------------------------------------------- #
#  zypper
# --------------------------------------------------------------------------- #
def test_zypper_table_and_search(fake_run):
    table = ("S | Name | Type    | Version | Repository\n"
             "--+------+---------+---------+-----------\n"
             "i | vim  | package | 9.0     | Main\n"
             "  | nano | package | 7.0     | Main\n")
    fake_run(default=res(table))
    rows = ZypperPkg().search("vim")
    assert rows[0]["name"] == "vim"
    assert rows[0]["installed"] is True
    assert rows[1]["installed"] is False


def test_zypper_updates(fake_run):
    table = ("S | Name | Current Version | Available Version\n"
             "v | vim  | 9.0             | 9.1\n")
    fake_run(default=res(table))
    assert ZypperPkg().updates() == [{"name": "vim", "old": "9.0", "new": "9.1"}]


def test_zypper_orphans(fake_run):
    table = ("S | Name  | Type\n"
             "  | libfoo | package\n")
    fake_run(default=res(table))
    _size, names = ZypperPkg().orphans_scan()
    assert names == "libfoo"


# --------------------------------------------------------------------------- #
#  apk
# --------------------------------------------------------------------------- #
def test_apk_installed_and_search(fake_run):
    def handler(cmd, **kwargs):
        if cmd[:2] == ["apk", "info"]:
            return res("vim-9.0-r1\n")
        if cmd[:2] == ["apk", "search"]:
            return res("vim-9.1-r0 - Vi IMproved\n")
        return res("")

    fake_run(handler=handler)
    assert ApkPkg()._installed() == {"vim-9.0-r1"}
    rows = ApkPkg().search("vim")
    assert rows[0]["name"] == "vim"
    assert rows[0]["version"] == "9.1-r0"


def test_apk_updates(fake_run):
    fake_run(default=res("neovim-0.9.0-r0    neovim-0.9.5-r0\n"))
    assert ApkPkg().updates() == [
        {"name": "neovim", "old": "0.9.0-r0", "new": "0.9.5-r0"}]


def test_apk_namever_regex():
    m = ApkPkg._NAMEVER.match("gcc-13.2.1-r0")
    assert m.group(1) == "gcc"
    assert m.group(2) == "13.2.1-r0"


# --------------------------------------------------------------------------- #
#  detect()
# --------------------------------------------------------------------------- #
def test_detect_prefers_hint(monkeypatch):
    monkeypatch.setattr(linux_pkg, "_os_ids", lambda: {"fedora"})
    monkeypatch.setattr(DnfPkg, "available", classmethod(lambda cls: True))
    monkeypatch.setattr(PacmanPkg, "available", classmethod(lambda cls: True))
    assert isinstance(detect(), DnfPkg)


def test_detect_falls_back_to_available(monkeypatch):
    monkeypatch.setattr(linux_pkg, "_os_ids", lambda: {"unknown-distro"})
    for cls in (PacmanPkg, AptPkg, DnfPkg, ZypperPkg, ApkPkg):
        monkeypatch.setattr(cls, "available", classmethod(lambda cls: False))
    monkeypatch.setattr(ZypperPkg, "available", classmethod(lambda cls: True))
    assert isinstance(detect(), ZypperPkg)


def test_detect_none_found(monkeypatch):
    monkeypatch.setattr(linux_pkg, "_os_ids", lambda: set())
    for cls in (PacmanPkg, AptPkg, DnfPkg, ZypperPkg, ApkPkg):
        monkeypatch.setattr(cls, "available", classmethod(lambda cls: False))
    result = detect()
    assert type(result) is PkgManager
    assert result.key == ""


def test_detect_caches(monkeypatch):
    monkeypatch.setattr(linux_pkg, "_os_ids", lambda: {"arch"})
    monkeypatch.setattr(PacmanPkg, "available", classmethod(lambda cls: True))
    first = detect()
    second = detect()
    assert first is second
    assert detect(force=True) is not first
