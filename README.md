<div align="center">

<img src="skaycleartux/assets/tux.png" alt="SkayClearTux" width="128">

# SkayClearTux

**Кроссплатформенный системный помощник для ПК**

Очистка системы · мониторинг ресурсов · инструменты · шахматы с премувами · фокус

[![CI](https://github.com/skayinray/SkayClearTux/actions/workflows/ci.yml/badge.svg)](https://github.com/skayinray/SkayClearTux/actions/workflows/ci.yml)
[![Build](https://github.com/skayinray/SkayClearTux/actions/workflows/build.yml/badge.svg)](https://github.com/skayinray/SkayClearTux/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Qt](https://img.shields.io/badge/Qt-6-41CD52.svg?logo=qt&logoColor=white)](https://www.qt.io/)

[Возможности](#возможности) · [Установка](#установка) · [Сборка](#сборка) · [Скриншоты](#скриншоты) · [Разработка](#разработка) · [Сообщество](#сообщество)

</div>

---

**SkayClearTux** — настольное приложение для **Linux, macOS и Windows**: один и
тот же код и один и тот же интерфейс на всех трёх системах, а системные разделы
(процессы, службы, пакеты, датчики и т. д.) работают через родные для каждой ОС
инструменты. Написан на Python + PySide6 (Qt 6), логотип — **Tux**, талисман Linux.

**Создатель:** [t.me/imneedasleep](https://t.me/imneedasleep)

## Возможности

Всего **34 экрана** в **7 сворачиваемых разделах**. При наведении на пункт меню
появляется подсказка, полный каталог функций — на странице **Справка**, а палитра
команд по `Ctrl+K` позволяет перейти куда угодно за пару нажатий.

| Раздел | Что внутри |
|--------|------------|
| **Обзор** | Главная (ЦП, память, диск, uptime, температура, батарея, оценка здоровья и экспорт отчёта), Монитор (живые графики), Датчики, Загрузка |
| **Очистка** | Очистка мусора по категориям, Анализ диска, Большие файлы, Корзина |
| **Инструменты** | Процессы, Службы, Таймеры, Пакеты, Файлы пакетов, Обновления, Сеть, Порты, Автозапуск |
| **Система** | Железо, Диски и SMART, Модули ядра, Журнал, Файрвол, Диагностика, Твики |
| **Утилиты** | Заметки, Хэши, Текст, Бэкап, Пароли |
| **Развлечения** | Шахматы с ботом, премувами и рейтингом Эло |
| **Настройка** | Коллекция тем оформления, Настройки, Справка, О программе |

### Кроссплатформенность

| Раздел | Linux | macOS | Windows |
|--------|:-----:|:-----:|:-------:|
| Очистка (категории мусора) | ✅ pacman/apt/dnf/zypper/apk + systemd/Flatpak/Docker | ✅ Homebrew/кэши/Xcode | ✅ `%TEMP%`/кэши/корзина |
| Процессы, службы, автозапуск | ✅ | ✅ `launchctl` | ✅ службы Windows |
| Пакеты и обновления | ✅ `pacman`/`apt`/`dnf`/`zypper`/`apk` | ✅ `brew` | ✅ `winget`/`choco` |
| Сеть и порты | ✅ `ip`/`ss` | ✅ `ifconfig`/`lsof` | ✅ `ipconfig`/`netstat` |
| Датчики, батарея, железо | ✅ `lm-sensors` | ✅ `powermetrics` | ✅ WMI |
| Журнал, диагностика | ✅ `journalctl` | ✅ `log show` | ✅ Журнал событий |
| Модули ядра | ✅ `lsmod` | — | — |
| Твики ядра | ✅ | частично | частично |

Недоступные на конкретной ОС функции аккуратно сообщают об этом и не роняют
программу — за это отвечает слой `skaycleartux/backends/`.

### Полезные мелочи

- **Оценка здоровья и быстрые действия** — на главной видна оценка состояния
  системы с рекомендациями, доступна безопасная быстрая очистка и экспорт
  подробного HTML-отчёта в один клик.
- **Автообновления из коробки** — AppImage сам проверяет свежий релиз на GitHub,
  скачивает обновление по HTTPS, сверяет SHA-256 и перезапускается без ручной
  настройки ссылок.
- **Активность в Discord из коробки** — встроенный Rich Presence (Linux, macOS
  и Windows) с предустановленным Application ID показывает, что вы в SkayClearTux,
  пока приложение открыто (при необходимости ID можно переопределить).
- **Палитра команд** (`Ctrl+K`) — переход по разделам и запуск действий поиском.
- **Системный трей** — значок с меню и, при желании, сворачивание окна в трей.
- **Темы оформления** с градиентами (включая новые), применяются мгновенно.
- **Шахматы** — полные правила, 4 уровня, премувы, анимация фигур, подсказки,
  оптимизация высоких сложностей и рейтинг Эло.
- **Понятные недоступные функции** — то, чего нет на текущей ОС, показано
  неактивным с подсказкой, а не молча ломается.
- **Тихая работа на Windows** — системные команды выполняются скрытно, без
  всплывающих окон cmd/PowerShell.
- **Лог ошибок** — ошибки бэкендов пишутся в файл лога в стандартном каталоге ОС
  (с ротацией), чтобы их можно было приложить к Issue.

## Скриншоты

| Главная | Очистка | Процессы |
|:---:|:---:|:---:|
| ![Главная](screenshots/page_dash.png) | ![Очистка](screenshots/page_cleaner.png) | ![Процессы](screenshots/page_procs.png) |

| Датчики | Пакеты | Службы |
|:---:|:---:|:---:|
| ![Датчики](screenshots/page_sensors.png) | ![Пакеты](screenshots/page_packages.png) | ![Службы](screenshots/page_services.png) |

| Сеть | Темы | Шахматы |
|:---:|:---:|:---:|
| ![Сеть](screenshots/page_network.png) | ![Темы](screenshots/page_themes.png) | ![Шахматы](screenshots/page_chess.png) |

## Установка

### Готовые сборки

Скачайте последний релиз со страницы
[Releases](https://github.com/skayinray/SkayClearTux/releases):

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.4.0-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.4.0-amd64.deb` | `sudo apt install ./SkayClearTux-1.4.0-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.4.0-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.4.0-x86_64.rpm` |
| Windows | `SkayClearTux-windows.zip` | распаковать, запустить `SkayClearTux.exe` |
| macOS | `SkayClearTux.dmg` | открыть образ, перетащить в «Программы» |

На Linux пакеты и обновления работают с любым из менеджеров
**pacman / apt / dnf / zypper / apk** — нужный определяется автоматически.

### Первый запуск на macOS

macOS помечает скачанные приложения карантином, поэтому при первом запуске
может появиться предупреждение «Не удаётся открыть, так как Apple не может
проверить разработчика». Это ожидаемо для неподписанной сборки — приложение
работает, нужно лишь один раз подтвердить запуск:

1. Откройте `SkayClearTux.dmg` и перетащите `SkayClearTux.app` в «Программы».
2. В Finder щёлкните по приложению **правой кнопкой** (или Control + клик) →
   **Открыть**.
3. В появившемся диалоге нажмите **Открыть** ещё раз.

Дальше приложение запускается как обычно, двойным щелчком.

Если предпочитаете терминал, снимите карантин вручную:

```bash
xattr -dr com.apple.quarantine /Applications/SkayClearTux.app
```

![Первый запуск на macOS](docs/images/macos-first-run.png)

> Приложение уже показывает разовую подсказку об этом при первом старте на
> macOS. Подробности и варианты подписи/нотаризации — в
> [`packaging/03-macos/README.md`](packaging/03-macos/README.md).
> Скриншот `docs/images/macos-first-run.png` добавляет мейнтейнер при первой
> публикации.

### Из исходников

Нужен **Python 3.11+**.

```bash
git clone https://github.com/skayinray/SkayClearTux.git
cd SkayClearTux

python -m venv .venv
# Linux / macOS:
.venv/bin/pip install PySide6
.venv/bin/python SkayClearTux.py

# Windows (PowerShell):
py -m venv .venv
.venv\Scripts\pip install PySide6
.venv\Scripts\python SkayClearTux.py
```

Или установить как пакет:

```bash
pip install .
skaycleartux
```

## Сборка

Готовые скрипты и инструкции для каждой ОС — в папке [`packaging/`](packaging):

| Платформа | Как собрать |
|-----------|-------------|
| Linux (AppImage, `.deb`, `.rpm`) | `packaging/01-linux/` |
| Windows (`.exe`) | `packaging/02-windows/` |
| macOS (`.app` + `.dmg`) | `packaging/03-macos/` |

Готовый CI собирает все три платформы и публикует релиз вместе с `latest.json`
при пуше тега `v*` — см. [`.github/workflows/build.yml`](.github/workflows/build.yml).

## Проверки

```bash
# тесты (юнит + интерфейс, offscreen)
python -m pytest -q

# покрытие ядра (backends/ + cleaner.py), порог 60%
python -m pytest -q --cov=skaycleartux.backends --cov=skaycleartux.cleaner \
    --cov-report=term-missing --cov-fail-under=60

# линтер (блокирует CI)
python -m ruff check skaycleartux tests tools

# синтаксис и дымовой тест интерфейса
python -m compileall -q skaycleartux SkayClearTux.py tools tests
QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
```

`tools/smoke_test.py` поднимает интерфейс без экрана, обходит все страницы,
проверяет бэкенд текущей ОС и ищет символы, которые Qt рисует пустыми квадратами.
`black` и `mypy` подключены в мягком режиме — они подсказывают, но не блокируют
сборку.

## Разработка

- [docs/architecture.md](docs/architecture.md) — устройство проекта, слои, как
  добавить экран или функцию бэкенда.
- [docs/backends.md](docs/backends.md) — контракт `BaseBackend`, примеры для
  Linux/macOS/Windows, тестирование.
- [CONTRIBUTING.md](CONTRIBUTING.md) — как сообщить об ошибке и прислать
  изменения.

Ошибки бэкендов и необработанные исключения пишутся в файл лога в стандартном
каталоге ОС:

| ОС | Путь к логу |
|----|-------------|
| Linux | `~/.local/state/SkayClearTux/skaycleartux.log` (`$XDG_STATE_HOME`) |
| macOS | `~/Library/Logs/SkayClearTux/skaycleartux.log` |
| Windows | `%LOCALAPPDATA%\SkayClearTux\Logs\skaycleartux.log` |

## Сообщество

- **Вопросы и идеи** — [GitHub Discussions](https://github.com/skayinray/SkayClearTux/discussions).
- **Ошибки и предложения** — [Issues](https://github.com/skayinray/SkayClearTux/issues/new/choose)
  (есть готовые шаблоны).
- **Правила участия** — [CONTRIBUTING.md](CONTRIBUTING.md) и
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **Помощь и документация** — [SUPPORT.md](SUPPORT.md).
- **Безопасность** — об уязвимостях не в публичных Issues, см.
  [SECURITY.md](SECURITY.md).

Спасибо всем, кто сообщает об ошибках, предлагает идеи и присылает Pull
Request'ы.

## Структура

```
SkayClearTux.py              точка входа
skaycleartux/
  main_window.py             окно, разделы, переходы, палитра команд, трей
  backends/                  кроссплатформенное ядро
    common.py                общие утилиты (запуск команд, права, пути)
    base.py                  интерфейс бэкенда и безопасные заглушки
    linux.py  macos.py  windows.py
    linux_pkg.py             менеджеры пакетов Linux (pacman/apt/dnf/zypper/apk)
  system_tools.py            фасад над бэкендом (весь API страниц)
  cleaner.py                 движок очистки (категории по ОС)
  pages.py                   главная, очистка, анализ диска, темы, о программе
  extra_pages.py             монитор, обновления, железо, журнал, утилиты и т. д.
  tools_pages.py             процессы, службы, пакеты, сеть, датчики, автозапуск
  palette.py                 палитра команд (Ctrl+K)
  helptext.py                описания всех разделов
  logging_setup.py           лог ошибок в стандартный каталог ОС (с ротацией)
  ui_utils.py                пометка недоступных функций в интерфейсе
  settings.py, settings_page.py
  themes.py                  темы оформления
  chess_engine.py, chess_widget.py
  discord_rpc.py, updater.py
  assets/                    логотип и шахматные фигуры
packaging/                   сборка под Linux / Windows / macOS
docs/                        документация разработчика
tests/                       юнит- и UI-тесты (pytest + pytest-qt)
tools/smoke_test.py          дымовой тест интерфейса
tools/pkg_check.py           самопроверка менеджеров пакетов Linux
.github/workflows/           CI и сборка релизов
```

## Технологии

Python 3 · PySide6 (Qt 6) · собственный шахматный движок (негамакс + альфа-бета).
Шахматные фигуры — набор **Cburnett** (Wikimedia Commons, CC BY-SA 3.0 / GFDL).

## Лицензия

[MIT](LICENSE).
