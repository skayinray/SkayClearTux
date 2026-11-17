# Бэкенды: контракт и примеры

Слой `skaycleartux/backends/` — единственное место, где программа общается с
операционной системой. Интерфейс и `system_tools.py` не запускают команды
напрямую.

```
backends/
  __init__.py   get_backend() — выбирает реализацию по common.FAMILY
  common.py     запуск команд, права, пути, чистые утилиты (общее для всех ОС)
  base.py       BaseBackend — контракт и безопасные заглушки
  linux.py      LinuxBackend
  macos.py      MacOSBackend
  windows.py    WindowsBackend
  linux_pkg.py  менеджеры пакетов Linux (pacman/apt/dnf/zypper/apk)
```

## Контракт `BaseBackend`

Каждый метод, который может быть не реализован на конкретной ОС, объявлен в
`BaseBackend` и возвращает безопасную заглушку. Реализации переопределяют
только то, что умеют.

### Соглашения о возвращаемых значениях

| Тип метода | Успех | Недоступно / ошибка |
|------------|-------|---------------------|
| Список (`list_processes`, `list_services`, …) | `list[dict]` | `[]` |
| Действие (`kill_process`, `install_packages`, `service_action`, `system_update`, `empty_trash`) | `(True, "что сделано")` | `(False, "причина")` |
| Булево действие (`set_swappiness`, `set_cpu_governor`, `set_startup_enabled`) | `True` | `False` |
| Текст (`package_info`, `smart_health`, `journal_entries`, `disks_overview`) | строка с данными | `NOT_AVAILABLE` или `"—"` |
| Информация (`network_info`) | `dict` | словарь с пустыми полями |
| Датчики (`sensors_info`, `memory_info`, `load_avg`) | кортеж чисел | нули |
| `battery_info` | `dict` | `None` |

`NOT_AVAILABLE` (`base.py`) — строка «На этой системе функция недоступна.».
Интерфейс показывает её как есть и не считает ошибкой.

### Список основных методов

- **Процессы/службы:** `list_processes`, `kill_process`, `list_services`,
  `service_action`.
- **Пакеты:** `package_manager`, `search_packages`, `install_packages`,
  `remove_packages`, `package_files`, `file_owner`, `package_info`.
- **Обновления:** `check_updates`, `system_update`.
- **Сеть:** `network_info`, `ping_test`, `public_ip`, `listening_ports`,
  `established_connections`.
- **Датчики/железо:** `sensors_info`, `memory_info`, `load_avg`, `cpu_percent`,
  `cpu_model`, `uptime`, `battery_info`, `hardware_sections`, `disks_overview`,
  `smart_health`, `mounts`, `disk_usage`, `large_files`.
- **Автозапуск:** `list_startup`, `set_startup_enabled`.
- **Диагностика:** `diagnostics`, `boot_analysis`, `journal_entries`,
  `list_timers_raw`, `firewall_status`, `firewall_status_root`.
- **Модули ядра:** `list_modules`, `module_action`.
- **Твики:** `get_swappiness`, `set_swappiness`, `cpu_governor`,
  `cpu_governors`, `set_cpu_governor`, `thp_status`, `zram_status`.
- **Корзина:** `trash_items`, `empty_trash`.

## `common.py`: запуск команд

Все внешние команды идут через две функции:

```python
def run(cmd: list[str], root: bool = False, timeout: float | None = None,
        input_text: str | None = None,
        cwd: str | None = None) -> subprocess.CompletedProcess: ...

def run_out(cmd: list[str], root: bool = False, timeout: float | None = None) -> str: ...
```

Правила:

- **Только список аргументов**, никогда `shell=True`. Пользовательские строки
  не склеиваются в команду.
- **Всегда таймаут** для команд, которые могут зависнуть.
- `root=True` — запрос прав администратора средствами ОС (`pkexec`/`sudo` на
  Linux, `osascript` на macOS). На Windows повышение прав требует отдельного
  процесса, поэтому здесь не делается.
- `run` **не бросает** исключений из-за отсутствия программы: возвращает
  `CompletedProcess` с кодом `127`. Проверяйте `r.returncode` и `r.stdout`.
- `run_out` дополнительно вырезает служебные строки `sudo`/`pkexec`.

Пример — чтение списка процессов:

```python
r = common.run(["ps", "-eo", "pid,user,pcpu,pmem,rss,comm,args",
                "--sort=-pcpu", "--no-headers"])
for line in (r.stdout or "").splitlines():
    ...
```

## Примеры по ОС

### Linux (`linux.py`)

```python
def list_processes(self) -> list[dict]:
    r = common.run(["ps", "-eo", "pid,user,pcpu,pmem,rss,comm,args",
                    "--sort=-pcpu", "--no-headers"])
    ...

def set_cpu_governor(self, governor: str) -> bool:
    # значение приходит из интерфейса — валидируем и пишем без shell
    gov = str(governor).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", gov):
        return False
    ...
    r = common.run(["tee", str(path)], root=True, input_text=gov + "\n")
```

Менеджеры пакетов Linux вынесены в `linux_pkg.py`: он определяет дистрибутив
(pacman/apt/dnf/zypper/apk) и отдаёт объект с общим интерфейсом
(`cache_scan`, `installed`, `search`, `install`, `remove`, …).

### macOS (`macos.py`)

```python
def list_services(self) -> list[dict]:
    # launchctl list печатает «PID\tStatus\tLabel»; PID == "-" → не запущен.
    r = common.run(["launchctl", "list"], timeout=15)
    ...
```

### Windows (`windows.py`)

```python
def service_action(self, unit: str, action: str) -> tuple[bool, str]:
    name = (unit or "").strip()
    if not name:
        return False, "Укажи имя службы"

    def sc(*args: str) -> tuple[bool, str]:
        r = common.run(["sc", *args], timeout=40)
        return r.returncode == 0, (r.stdout or "").strip()
    ...
```

## Как добавить новую функцию

1. **Заглушка** в `BaseBackend`: что вернуть, если функция недоступна
   (`(False, NOT_AVAILABLE)`, `[]`, `""` и т. п.).
2. **Реализация** в нужных бэкендах. Обязательно:
   - список аргументов вместо строки команды;
   - таймаут;
   - `try/except` там, где возможны ошибки ОС;
   - валидация пользовательского ввода (см. `set_cpu_governor`).
3. **Проброс** в `system_tools.py` (одна строка-обёртка).
4. **Вызов** из страницы интерфейса с корректной обработкой «недоступно».
5. **Тесты** в `tests/test_backend_<os>.py` с подменой `common.run` (фикстура
   `fake_run` в `tests/conftest.py`).
6. **Документация**: при расширении контракта — этот файл и `CHANGELOG.md`.

## Тестирование бэкендов

`common.run` подменяется, поэтому реальные команды не запускаются:

```python
def test_list_processes(monkeypatch):
    from skaycleartux.backends import common
    from skaycleartux.backends.linux import LinuxBackend

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "1 root 0.0 0.1 100 init /sbin/init", "")

    monkeypatch.setattr(common, "run", fake_run)
    rows = LinuxBackend().list_processes()
    assert rows[0]["pid"] == 1
```

Доступна готовая фикстура `fake_run` (см. `tests/conftest.py`), возвращающая
настраиваемый «бегунок».
