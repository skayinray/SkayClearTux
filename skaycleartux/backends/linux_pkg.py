"""Менеджеры пакетов Linux: pacman, apt, dnf, zypper, apk.

Один и тот же интерфейс для всех дистрибутивов — `PkgManager`. Конкретный
менеджер определяется по `/etc/os-release` (ID/ID_LIKE) и по наличию
исполняемого файла, поэтому программа работает не только на Arch.

Использование:

    from . import linux_pkg
    mgr = linux_pkg.detect()
    mgr.search("neovim")
    mgr.install(["neovim"])

Все методы терпимы к отсутствию утилит: вместо исключения возвращается
пустой результат или понятное сообщение об ошибке.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import common

# --------------------------------------------------------------------------- #
#  Определение дистрибутива
# --------------------------------------------------------------------------- #
def _os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            text = Path(path).read_text(errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        if data:
            break
    return data


def _os_ids() -> set[str]:
    data = _os_release()
    ids: set[str] = set()
    for key in ("ID", "ID_LIKE"):
        for token in (data.get(key) or "").replace(",", " ").split():
            ids.add(token.lower())
    return ids


def os_release_id() -> str:
    return (_os_release().get("ID") or "").lower()


# --------------------------------------------------------------------------- #
#  Базовый менеджер
# --------------------------------------------------------------------------- #
class PkgManager:
    """Общий интерфейс менеджера пакетов. Значения по умолчанию — заглушки."""

    key = ""            # короткий идентификатор: pacman/apt/dnf/zypper/apk
    title = ""          # человекочитаемое имя для интерфейса
    binary = ""         # исполняемый файл для проверки наличия
    NOT_FOUND = "Пакет не найден"

    @classmethod
    def available(cls) -> bool:
        return bool(cls.binary and shutil.which(cls.binary))

    # --------------------------------------------------------------- поиск
    def search(self, query: str) -> list[dict]:
        return []

    def install(self, names: list[str]) -> tuple[bool, str]:
        return False, "Менеджер пакетов не определён"

    def remove(self, names: list[str]) -> tuple[bool, str]:
        return False, "Менеджер пакетов не определён"

    def files(self, pkg: str) -> str:
        return "Недоступно для этого менеджера пакетов"

    def owner(self, path: str) -> str:
        return "Недоступно для этого менеджера пакетов"

    def info(self, pkg: str) -> str:
        return "Недоступно для этого менеджера пакетов"

    # ----------------------------------------------------------- обновления
    def updates(self) -> list[dict]:
        return []

    def upgrade(self) -> tuple[bool, str]:
        return False, "Менеджер пакетов не определён"

    # ---------------------------------------------------- очистка (cleaner)
    def cache_scan(self) -> tuple[int, str]:
        return 0, "кэш пакетов недоступен"

    def cache_clean(self) -> tuple[int, str]:
        return 0, "кэш пакетов недоступен"

    def orphans_scan(self) -> tuple[int, str]:
        return 0, "не поддерживается"

    def orphans_clean(self) -> tuple[int, str]:
        return 0, "не поддерживается"

    # -------------------------------------------------------------- утилиты
    @staticmethod
    def _tail(result, limit: int = 4000) -> str:
        text = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else ""))
        return text.strip()[-limit:]


def _human_size(text: str) -> int:
    """Разбирает строку вида «12,3 MiB» / «4.5 MB» в байты."""
    m = re.search(r"([\d.,]+)\s*([KMGT]?i?B)\b", text, re.IGNORECASE)
    if not m:
        return 0
    num = float(m.group(1).replace(",", "."))
    unit = m.group(2).upper()
    factor = {
        "B": 1, "KB": 1000, "KIB": 1024,
        "MB": 1000 ** 2, "MIB": 1024 ** 2,
        "GB": 1000 ** 3, "GIB": 1024 ** 3,
        "TB": 1000 ** 4, "TIB": 1024 ** 4,
    }.get(unit, 1)
    return int(num * factor)


# =========================================================================== #
#  pacman (Arch и производные)
# =========================================================================== #
class PacmanPkg(PkgManager):
    key = "pacman"
    title = "pacman"
    binary = "pacman"
    CACHE = Path("/var/cache/pacman/pkg")

    def search(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        r = common.run(["pacman", "-Ss", query])
        rows: list[dict] = []
        cur: dict | None = None
        for line in (r.stdout or "").splitlines():
            if line.startswith((" ", "\t")):
                if cur is not None:
                    cur["desc"] = (cur["desc"] + " " + line.strip()).strip()
                continue
            head = line.split()
            if not head or "/" not in head[0]:
                continue
            repo, name = head[0].split("/", 1)
            version = head[1] if len(head) > 1 else ""
            rest = head[2:]
            installed = "[installed]" in rest
            cur = {"repo": repo, "name": name, "version": version,
                   "installed": installed,
                   "desc": " ".join(t for t in rest if t != "[installed]")}
            rows.append(cur)
        return rows

    def install(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["pacman", "-S", "--noconfirm", *names], root=True)
        return r.returncode == 0, self._tail(r)

    def remove(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["pacman", "-Rns", "--noconfirm", *names], root=True)
        return r.returncode == 0, self._tail(r)

    def files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["pacman", "-Ql", pkg.strip()]) or self.NOT_FOUND

    def owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        return common.run_out(["pacman", "-Qo", path.strip()]) or \
            "Файл не принадлежит ни одному пакету"

    def info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["pacman", "-Qi", pkg.strip()]) or self.NOT_FOUND

    def updates(self) -> list[dict]:
        tool = ["checkupdates"] if shutil.which("checkupdates") else ["pacman", "-Qu"]
        r = common.run(tool)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "->":
                rows.append({"name": parts[0], "old": parts[1], "new": parts[3]})
            elif len(parts) >= 2:
                rows.append({"name": parts[0], "old": "", "new": parts[-1]})
        return rows

    def upgrade(self) -> tuple[bool, str]:
        r = common.run(["pacman", "-Syu", "--noconfirm"], root=True, timeout=3600)
        return r.returncode == 0, self._tail(r, 6000)

    def cache_scan(self) -> tuple[int, str]:
        p = self.CACHE
        n = len(list(p.glob("*.pkg.tar.*"))) if p.is_dir() else 0
        return common.dir_size(p), f"{n} файлов пакетов"

    def cache_clean(self) -> tuple[int, str]:
        before = common.dir_size(self.CACHE)
        if shutil.which("paccache"):
            common.run(["paccache", "-rk1"], root=True)
            note = "paccache -rk1 (оставлена 1 версия)"
        else:
            common.run(["pacman", "-Sc", "--noconfirm"], root=True)
            note = "pacman -Sc (очищен кэш)"
        return max(0, before - common.dir_size(self.CACHE)), note

    def _orphan_names(self) -> list[str]:
        return [p for p in common.run_out(["pacman", "-Qdtq"]).split("\n") if p]

    def orphans_scan(self) -> tuple[int, str]:
        pkgs = self._orphan_names()
        total = 0
        for p in pkgs:
            for line in common.run_out(["pacman", "-Qi", p]).splitlines():
                if line.startswith("Installed Size"):
                    total += _human_size(line.split(":", 1)[1])
        return total, (", ".join(pkgs) if pkgs else "нет сирот")

    def orphans_clean(self) -> tuple[int, str]:
        pkgs = self._orphan_names()
        if not pkgs:
            return 0, "сирот нет"
        before = self.orphans_scan()[0]
        common.run(["pacman", "-Rns", "--noconfirm", *pkgs], root=True)
        return before, f"удалено {len(pkgs)} пакетов"


# =========================================================================== #
#  apt / dpkg (Debian, Ubuntu, Mint, …)
# =========================================================================== #
class AptPkg(PkgManager):
    key = "apt"
    title = "APT"
    binary = "apt-get"
    CACHE = Path("/var/cache/apt/archives")

    @classmethod
    def available(cls) -> bool:
        return bool(shutil.which("apt-get") or shutil.which("apt"))

    # ------------------------------------------------------------- установлено
    def _installed(self) -> dict[str, str]:
        out = common.run_out(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Status}\n"])
        result: dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[2].startswith("install ok installed"):
                result[parts[0]] = parts[1]
        return result

    def _madison(self, names: list[str]) -> dict[str, tuple[str, str]]:
        """Имя → (версия, репозиторий) для доступных пакетов."""
        if not names:
            return {}
        out = common.run_out(["apt-cache", "madison", *names])
        result: dict[str, tuple[str, str]] = {}
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3 or not parts[0]:
                continue
            name, version, source = parts[0], parts[1], parts[2]
            tokens = source.split()
            repo = tokens[1].split("/")[0] if len(tokens) > 1 else (tokens[0] if tokens else "apt")
            result.setdefault(name, (version, repo))
        return result

    def search(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        found = common.run(["apt-cache", "search", query])
        items: list[tuple[str, str]] = []
        for line in (found.stdout or "").splitlines():
            name, sep, desc = line.partition(" - ")
            name = name.strip()
            if not name or not sep:
                continue
            items.append((name, desc.strip()))
            if len(items) >= 150:
                break
        if not items:
            return []
        available = self._madison([n for n, _ in items])
        installed = self._installed()
        rows: list[dict] = []
        for name, desc in items:
            version, repo = available.get(name, ("", ""))
            is_installed = name in installed
            if is_installed:
                version = installed[name] or version
            rows.append({"repo": repo or "apt", "name": name, "version": version,
                         "installed": is_installed, "desc": desc})
        return rows

    def install(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["apt-get", "-y", "install", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def remove(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["apt-get", "-y", "remove", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["dpkg", "-L", pkg.strip()]) or self.NOT_FOUND

    def owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        return common.run_out(["dpkg", "-S", path.strip()]) or \
            "Файл не принадлежит ни одному пакету"

    def info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        text = common.run_out(["apt-cache", "show", pkg.strip()]) or \
            common.run_out(["dpkg", "-s", pkg.strip()])
        return text[:8000] or self.NOT_FOUND

    def updates(self) -> list[dict]:
        r = common.run(["apt", "list", "--upgradable"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if "/" not in line or line.startswith(("Listing", "WARNING")):
                continue
            name = line.split("/", 1)[0]
            parts = line.split()
            new = parts[1] if len(parts) > 1 else ""
            m = re.search(r"upgradable from:\s*([^\]]+)", line)
            old = m.group(1).strip() if m else ""
            rows.append({"name": name, "old": old, "new": new})
        return rows

    def upgrade(self) -> tuple[bool, str]:
        first = common.run(["apt-get", "update"], root=True, timeout=900)
        second = common.run(["apt-get", "-y", "upgrade"], root=True, timeout=3600)
        text = self._tail(first, 2000) + "\n" + self._tail(second, 6000)
        return second.returncode == 0, text.strip()

    def cache_scan(self) -> tuple[int, str]:
        p = self.CACHE
        n = len(list(p.glob("*.deb"))) if p.is_dir() else 0
        return common.dir_size(p), f"{n} файлов .deb"

    def cache_clean(self) -> tuple[int, str]:
        before = common.dir_size(self.CACHE)
        common.run(["apt-get", "clean"], root=True)
        return max(0, before - common.dir_size(self.CACHE)), "apt-get clean"

    def _orphan_names(self) -> list[str]:
        r = common.run(["apt-get", "-s", "autoremove"])
        names: list[str] = []
        for line in (r.stdout or "").splitlines():
            if line.startswith("Remv "):
                parts = line.split()
                if len(parts) > 1:
                    names.append(parts[1])
        return names

    def orphans_scan(self) -> tuple[int, str]:
        names = self._orphan_names()
        if not names:
            return 0, "нет сирот"
        sizes: dict[str, int] = {}
        out = common.run_out(
            ["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\n", *names])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[1].isdigit():
                sizes[parts[0]] = int(parts[1]) * 1024
        total = sum(sizes.get(n, 0) for n in names)
        return total, ", ".join(names)

    def orphans_clean(self) -> tuple[int, str]:
        before = self.orphans_scan()[0]
        r = common.run(["apt-get", "-y", "autoremove"], root=True, timeout=1800)
        return (before if r.returncode == 0 else 0), self._tail(r) or "готово"


# =========================================================================== #
#  dnf / rpm (Fedora, RHEL, CentOS, Rocky, Alma, …)
# =========================================================================== #
class DnfPkg(PkgManager):
    key = "dnf"
    title = "DNF"
    binary = "dnf"
    CACHE = Path("/var/cache/dnf")

    def _installed(self) -> dict[str, str]:
        out = common.run_out(
            ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"])
        result: dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                result[parts[0]] = parts[1]
        return result

    def _available(self, query: str) -> dict[str, tuple[str, str]]:
        out = common.run_out(["dnf", "-q", "list", "--available", query])
        result: dict[str, tuple[str, str]] = {}
        for line in out.splitlines():
            s = line.strip()
            if not s or s.endswith("Packages") or "." not in s:
                continue
            parts = s.split()
            if len(parts) < 3:
                continue
            name = parts[0].rsplit(".", 1)[0]
            result.setdefault(name, (parts[1], parts[2].lstrip("@")))
        return result

    def search(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        installed = self._installed()
        available = self._available(query)
        r = common.run(["dnf", "-q", "search", query])
        rows: list[dict] = []
        seen: set[str] = set()
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if " : " not in line or line.startswith("="):
                continue
            left, desc = line.split(" : ", 1)
            left = left.strip()
            if not left or left in ("Name", "Summary"):
                continue
            name = left.rsplit(".", 1)[0] if "." in left else left
            if not name or name in seen:
                continue
            seen.add(name)
            version, repo = available.get(name, ("", ""))
            if name in installed:
                version = installed[name] or version
            rows.append({"repo": repo or "dnf", "name": name, "version": version,
                         "installed": name in installed, "desc": desc.strip()})
            if len(rows) >= 150:
                break
        return rows

    def install(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["dnf", "-y", "install", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def remove(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["dnf", "-y", "remove", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["rpm", "-ql", pkg.strip()]) or self.NOT_FOUND

    def owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        return common.run_out(["rpm", "-qf", path.strip()]) or \
            "Файл не принадлежит ни одному пакету"

    def info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        text = common.run_out(["rpm", "-qi", pkg.strip()]) or \
            common.run_out(["dnf", "-q", "info", pkg.strip()])
        return text[:8000] or self.NOT_FOUND

    def updates(self) -> list[dict]:
        r = common.run(["dnf", "-q", "check-update"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 3 or "." not in parts[0]:
                continue
            name = parts[0].rsplit(".", 1)[0]
            rows.append({"name": name, "old": "", "new": parts[1]})
        return rows

    def upgrade(self) -> tuple[bool, str]:
        r = common.run(["dnf", "-y", "upgrade"], root=True, timeout=3600)
        return r.returncode == 0, self._tail(r, 6000)

    def cache_scan(self) -> tuple[int, str]:
        return common.dir_size(self.CACHE), "кэш метаданных и пакетов dnf"

    def cache_clean(self) -> tuple[int, str]:
        before = common.dir_size(self.CACHE)
        common.run(["dnf", "-y", "clean", "all"], root=True)
        return max(0, before - common.dir_size(self.CACHE)), "dnf clean all"

    def orphans_scan(self) -> tuple[int, str]:
        if not shutil.which("repoquery") and not shutil.which("dnf"):
            return 0, "не поддерживается"
        out = common.run_out(["dnf", "-q", "repoquery", "--unneeded"])
        names = [line.strip() for line in out.splitlines() if line.strip()]
        if not names:
            return 0, "нет сирот (нужен dnf-plugins-core для точного списка)"
        return 0, ", ".join(names)

    def orphans_clean(self) -> tuple[int, str]:
        r = common.run(["dnf", "-y", "autoremove"], root=True, timeout=1800)
        return 0, self._tail(r) or "готово"


# =========================================================================== #
#  zypper / rpm (openSUSE, SLES)
# =========================================================================== #
class ZypperPkg(PkgManager):
    key = "zypper"
    title = "Zypper"
    binary = "zypper"
    CACHE = Path("/var/cache/zypp/packages")

    def _table(self, args: list[str]) -> list[dict]:
        r = common.run(["zypper", "--no-refresh", "--quiet",
                        "--non-interactive", *args], timeout=300)
        header: list[str] | None = None
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if header is None:
                if "Name" in cells:
                    header = cells
                continue
            if all(set(c) <= set("-+ ") for c in cells):
                continue
            if len(cells) != len(header):
                continue
            rows.append(dict(zip(header, cells)))
        return rows

    def search(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        rows: list[dict] = []
        for row in self._table(["search", query]):
            if row.get("Type") and row["Type"] != "package":
                continue
            name = row.get("Name", "")
            if not name:
                continue
            status = row.get("S", "")
            rows.append({"repo": row.get("Repository", "zypper"),
                         "name": name,
                         "version": row.get("Version", ""),
                         "installed": ("i" in status) or ("v" in status),
                         "desc": ""})
            if len(rows) >= 150:
                break
        return rows

    def install(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["zypper", "--non-interactive", "install", *names],
                       root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def remove(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["zypper", "--non-interactive", "remove", *names],
                       root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["rpm", "-ql", pkg.strip()]) or self.NOT_FOUND

    def owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        return common.run_out(["rpm", "-qf", path.strip()]) or \
            "Файл не принадлежит ни одному пакету"

    def info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        text = common.run_out(["rpm", "-qi", pkg.strip()]) or \
            common.run_out(["zypper", "--no-refresh", "info", pkg.strip()])
        return text[:8000] or self.NOT_FOUND

    def updates(self) -> list[dict]:
        rows: list[dict] = []
        for row in self._table(["list-updates"]):
            name = row.get("Name", "")
            if not name:
                continue
            rows.append({"name": name,
                         "old": row.get("Current Version", ""),
                         "new": row.get("Available Version", "")})
        return rows

    def upgrade(self) -> tuple[bool, str]:
        r = common.run(["zypper", "--non-interactive", "update"],
                       root=True, timeout=3600)
        return r.returncode == 0, self._tail(r, 6000)

    def cache_scan(self) -> tuple[int, str]:
        return common.dir_size(self.CACHE), "кэш пакетов zypp"

    def cache_clean(self) -> tuple[int, str]:
        before = common.dir_size(self.CACHE)
        common.run(["zypper", "clean", "--all"], root=True)
        return max(0, before - common.dir_size(self.CACHE)), "zypper clean --all"

    def orphans_scan(self) -> tuple[int, str]:
        rows = self._table(["packages", "--orphaned"])
        names = [r.get("Name", "") for r in rows if r.get("Name")]
        return 0, (", ".join(names) if names else "нет сирот")

    def orphans_clean(self) -> tuple[int, str]:
        rows = self._table(["packages", "--orphaned"])
        names = [r.get("Name", "") for r in rows if r.get("Name")]
        if not names:
            return 0, "сирот нет"
        r = common.run(["zypper", "--non-interactive", "remove", "--clean-deps",
                        *names], root=True, timeout=1800)
        return 0, self._tail(r) or f"удалено {len(names)} пакетов"


# =========================================================================== #
#  apk (Alpine, postmarketOS)
# =========================================================================== #
class ApkPkg(PkgManager):
    key = "apk"
    title = "apk"
    binary = "apk"
    CACHE = Path("/var/cache/apk")

    _NAMEVER = re.compile(r"^(.+?)-(\d[^-]*(?:-r\d+)?)$")

    def _installed(self) -> set[str]:
        return {line.strip() for line in common.run_out(["apk", "info"]).splitlines()
                if line.strip()}

    def search(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        installed = self._installed()
        r = common.run(["apk", "search", "-v", query])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            left, sep, desc = line.partition(" - ")
            if not sep or not left:
                continue
            m = self._NAMEVER.match(left)
            name, version = (m.group(1), m.group(2)) if m else (left, "")
            rows.append({"repo": "apk", "name": name, "version": version,
                         "installed": name in installed, "desc": desc.strip()})
            if len(rows) >= 150:
                break
        return rows

    def install(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["apk", "add", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def remove(self, names: list[str]) -> tuple[bool, str]:
        r = common.run(["apk", "del", *names], root=True, timeout=1800)
        return r.returncode == 0, self._tail(r)

    def files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["apk", "info", "-L", pkg.strip()]) or self.NOT_FOUND

    def owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        return common.run_out(["apk", "info", "--who-owns", path.strip()]) or \
            "Файл не принадлежит ни одному пакету"

    def info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        return common.run_out(["apk", "info", "-a", pkg.strip()]) or self.NOT_FOUND

    def updates(self) -> list[dict]:
        r = common.run(["apk", "version", "-l", "<"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[0].endswith(":"):
                continue
            old_m = self._NAMEVER.match(parts[0])
            new_m = self._NAMEVER.match(parts[1])
            if not old_m or not new_m:
                continue
            rows.append({"name": old_m.group(1), "old": old_m.group(2),
                         "new": new_m.group(2)})
        return rows

    def upgrade(self) -> tuple[bool, str]:
        r = common.run(["apk", "upgrade", "--available"], root=True, timeout=3600)
        return r.returncode == 0, self._tail(r, 6000)

    def cache_scan(self) -> tuple[int, str]:
        n = len(list(self.CACHE.glob("*.apk"))) if self.CACHE.is_dir() else 0
        return common.dir_size(self.CACHE), f"{n} файлов .apk"

    def cache_clean(self) -> tuple[int, str]:
        before = common.dir_size(self.CACHE)
        common.run(["apk", "cache", "clean"], root=True)
        return max(0, before - common.dir_size(self.CACHE)), "apk cache clean"


# =========================================================================== #
#  Определение текущего менеджера
# =========================================================================== #
_MANAGERS = (PacmanPkg, AptPkg, DnfPkg, ZypperPkg, ApkPkg)

# Подсказки по ID/ID_LIKE из /etc/os-release (даже если бинарник нестандартный)
_HINTS: dict[str, set[str]] = {
    "pacman": {"arch", "archlinux", "manjaro", "endeavouros", "garuda", "artix",
               "cachyos", "arcolinux", "blackarch", "parabola", "archarm"},
    "apt": {"debian", "ubuntu", "linuxmint", "mint", "pop", "elementary", "kali",
            "raspbian", "raspberrypi", "devuan", "mx", "zorin", "neon", "deepin",
            "pureos", "parrot", "lmde", "ubuntu-core"},
    "dnf": {"fedora", "rhel", "centos", "rocky", "almalinux", "oracle", "ol",
            "amzn", "amazon", "scientific", "nobara", "bazzite", "azurelinux"},
    "zypper": {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse", "sles",
               "sled", "sle-micro", "microos"},
    "apk": {"alpine", "postmarketos", "chimera"},
}

_cached: PkgManager | None = None


def detect(force: bool = False) -> PkgManager:
    """Возвращает менеджер пакетов текущего дистрибутива."""
    global _cached
    if _cached is not None and not force:
        return _cached

    ids = _os_ids()
    ordered: list[type[PkgManager]] = []
    for cls in _MANAGERS:
        if ids & _HINTS.get(cls.key, set()):
            ordered.append(cls)
    for cls in _MANAGERS:
        if cls not in ordered:
            ordered.append(cls)

    for cls in ordered:
        if cls.available():
            _cached = cls()
            return _cached
    _cached = PkgManager()
    return _cached
