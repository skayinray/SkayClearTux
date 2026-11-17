"""Проверка менеджеров пакетов Linux (pacman/apt/dnf/zypper/apk) на моках.

Не требует ни реальных утилит, ни Qt — работает на любой ОС. Подменяет вывод
команд и проверяет разбор поиска, обновлений, сирот и файлов пакета.

Запуск:

    python tools/pkg_check.py
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skaycleartux.backends import linux_pkg as lp  # noqa: E402

PROBLEMS: list[str] = []


def make_run(table):
    def fake_run(cmd, root=False, timeout=None, input_text=None, cwd=None):
        key = tuple(str(c) for c in cmd)
        return subprocess.CompletedProcess(list(key), 0, table.get(key, ""), "")
    return fake_run


def make_out(table):
    def fake_out(cmd, root=False, timeout=None):
        return table.get(tuple(str(c) for c in cmd), "").strip()
    return fake_out


def check(name: str, cond: bool, detail: object = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        PROBLEMS.append(f"{name}: {detail!r}")


def test_apt() -> None:
    table = {
        ("dpkg-query", "-W", "-f=${Package}\t${Version}\t${Status}\n"):
            "neovim\t0.9.0-1\tinstall ok installed\nfoo\t1.0\tinstall ok installed\n",
        ("apt-cache", "search", "neovim"):
            "neovim - Vim-fork focused on extensibility\nneovim-runtime - runtime\n",
        ("apt-cache", "madison", "neovim", "neovim-runtime"):
            "neovim | 0.9.5-1 | http://deb.debian.org/debian bookworm/main amd64 Packages\n"
            "neovim-runtime | 0.9.5-1 | http://deb.debian.org/debian bookworm/main amd64 Packages\n",
        ("apt", "list", "--upgradable"):
            "Listing...\nneovim/stable 0.9.5-1 amd64 [upgradable from: 0.9.0-1]\n",
        ("apt-get", "-s", "autoremove"): "Remv foo [1.0]\nRemv bar [2.0]\n",
        ("dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\n", "foo", "bar"):
            "foo\t100\nbar\t2048\n",
        ("dpkg", "-L", "neovim"): "/usr/bin/nvim\n",
        ("dpkg", "-S", "/usr/bin/nvim"): "neovim: /usr/bin/nvim\n",
    }
    lp.common.run, lp.common.run_out = make_run(table), make_out(table)
    apt = lp.AptPkg()
    rows = apt.search("neovim")
    print("== apt ==")
    check("search", len(rows) == 2, rows)
    check("поля строки", rows[0]["version"] == "0.9.0-1" and rows[0]["installed"]
          and rows[0]["repo"] == "bookworm", rows[0])
    check("версия доступного", rows[1]["version"] == "0.9.5-1", rows[1])
    check("обновления", apt.updates() == [
        {"name": "neovim", "old": "0.9.0-1", "new": "0.9.5-1"}], apt.updates())
    check("сироты", apt.orphans_scan() == (100 * 1024 + 2048 * 1024, "foo, bar"),
          apt.orphans_scan())
    check("пустой запрос", apt.search("") == [], apt.search(""))


def test_dnf() -> None:
    table = {
        ("rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"):
            "neovim\t0.9.0-1.fc39\nbash\t5.2-1.fc39\n",
        ("dnf", "-q", "list", "--available", "neovim"):
            "Last metadata expiration check: 0:00:01 ago\nAvailable Packages\n"
            "neovim.x86_64    0.9.5-1.fc39    fedora\n",
        ("dnf", "-q", "search", "neovim"):
            "=========== Name Exactly Matched: neovim ===========\n"
            "neovim.x86_64 : Vim-fork focused on extensibility\n"
            "=========== Name And Summary Matched: neovim ===========\n"
            "python3-neovim.noarch : Python client for Neovim\n",
        ("dnf", "-q", "check-update"): "neovim.x86_64  0.9.5-1.fc39  updates\n",
    }
    lp.common.run, lp.common.run_out = make_run(table), make_out(table)
    dnf = lp.DnfPkg()
    rows = dnf.search("neovim")
    print("== dnf ==")
    check("search", len(rows) == 2, rows)
    check("установленный", rows[0]["installed"] and rows[0]["version"] == "0.9.0-1.fc39",
          rows[0])
    check("доступный", not rows[1]["installed"], rows[1])
    check("обновления", dnf.updates() == [
        {"name": "neovim", "old": "", "new": "0.9.5-1.fc39"}], dnf.updates())


def test_zypper() -> None:
    search = (
        "S | Name    | Type    | Version | Arch   | Repository\n"
        "--+---------+---------+---------+--------+-----------\n"
        "i | neovim  | package | 0.9.0   | x86_64 | repo-oss\n"
        "  | htop    | package | 3.3.0   | x86_64 | repo-oss\n"
        "  | pattern | pattern | 202401  | x86_64 | repo-oss\n"
    )
    updates = (
        "S | Repository | Name   | Current Version | Available Version | Arch\n"
        "--+------------+--------+-----------------+-------------------+-----\n"
        "v | repo-oss   | neovim | 0.9.0           | 0.9.5             | x86_64\n"
    )
    orphans = (
        "S | Repository | Name | Version | Arch\n"
        "--+------------+------+---------+-----\n"
        "  | @System    | foo  | 1.0     | x86_64\n"
    )
    table = {
        ("zypper", "--no-refresh", "--quiet", "--non-interactive", "search", "neovim"): search,
        ("zypper", "--no-refresh", "--quiet", "--non-interactive", "list-updates"): updates,
        ("zypper", "--no-refresh", "--quiet", "--non-interactive", "packages", "--orphaned"): orphans,
    }
    lp.common.run, lp.common.run_out = make_run(table), make_out(table)
    zy = lp.ZypperPkg()
    rows = zy.search("neovim")
    print("== zypper ==")
    check("пропуск шаблонов", len(rows) == 2, rows)
    check("флаг установки", rows[0]["installed"] and not rows[1]["installed"], rows)
    check("обновления", zy.updates() == [
        {"name": "neovim", "old": "0.9.0", "new": "0.9.5"}], zy.updates())
    check("сироты", zy.orphans_scan() == (0, "foo"), zy.orphans_scan())


def test_apk() -> None:
    table = {
        ("apk", "info"): "neovim\nbash\n",
        ("apk", "search", "-v", "neovim"):
            "neovim-0.9.5-r0 - Vim-fork focused on extensibility\n"
            "neovim-doc-0.9.5-r0 - docs\n",
        ("apk", "version", "-l", "<"):
            "Installed:                      Available:\n"
            "neovim-0.9.0-r0                 neovim-0.9.5-r0\n",
        ("apk", "info", "-L", "neovim"): "neovim-0.9.5-r0:\nusr/bin/nvim\n",
    }
    lp.common.run, lp.common.run_out = make_run(table), make_out(table)
    apk = lp.ApkPkg()
    rows = apk.search("neovim")
    print("== apk ==")
    check("search", len(rows) == 2, rows)
    check("имя и версия", rows[0]["name"] == "neovim"
          and rows[0]["version"] == "0.9.5-r0", rows[0])
    check("обновления", apk.updates() == [
        {"name": "neovim", "old": "0.9.0-r0", "new": "0.9.5-r0"}], apk.updates())


def test_detect() -> None:
    print("== определение менеджера ==")
    original = {cls: cls.available for cls in lp._MANAGERS}
    try:
        lp._cached = None
        lp._os_ids = lambda: {"ubuntu", "debian"}
        for cls in lp._MANAGERS:
            cls.available = classmethod(lambda c: c is lp.AptPkg)
        check("apt по os-release", lp.detect(force=True).key == "apt",
              lp.detect(force=True).key)

        lp._cached = None
        lp._os_ids = lambda: set()
        for cls in lp._MANAGERS:
            cls.available = classmethod(lambda c: c is lp.DnfPkg)
        check("dnf по наличию утилиты", lp.detect(force=True).key == "dnf",
              lp.detect(force=True).key)

        lp._cached = None
        for cls in lp._MANAGERS:
            cls.available = classmethod(lambda c: False)
        check("неизвестный менеджер", lp.detect(force=True).key == "",
              lp.detect(force=True).key)
    finally:
        for cls, fn in original.items():
            cls.available = fn
        lp._cached = None
        import importlib
        importlib.reload(lp)


def main() -> int:
    test_apt()
    test_dnf()
    test_zypper()
    test_apk()
    test_detect()
    print()
    if PROBLEMS:
        print("ПРОБЛЕМЫ:")
        for problem in PROBLEMS:
            print(" -", problem)
        return 1
    print("Все проверки linux_pkg пройдены.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
