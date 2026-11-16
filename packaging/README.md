# SkayClearTux v1.2 — сборка под Linux, macOS и Windows

Здесь лежит всё, чтобы собрать **SkayClearTux** под каждую настольную систему.
Проект теперь **только для ПК** — один и тот же Python-код собирается в
AppImage (Linux), `.zip` с `.exe` (Windows) и `.dmg` (macOS). Мобильные порты
(Android/iOS/PWA) удалены.

Готовые сборки публикуются автоматически на странице
[Releases](https://github.com/skayinray/SkayClearTux/releases) при пуше тега
`v*` — см. [`.github/workflows/build.yml`](../.github/workflows/build.yml).

| Платформа | Файл релиза | Как запустить |
|-----------|-------------|---------------|
| Linux | `SkayClearTux-1.2.0-x86_64.AppImage` | `chmod +x` и запустить |
| Windows | `SkayClearTux-windows.zip` | распаковать, запустить `SkayClearTux.exe` |
| macOS | `SkayClearTux.dmg` | открыть образ, перетащить в «Программы» |

> **Первый запуск на macOS.** Приложение не подписано — щёлкните по нему правой
> кнопкой → **Открыть** → **Открыть**.

---

## Что где лежит

```
packaging/
├── 01-linux/            AppImage: make_appimage.sh + install.sh + ярлык
├── 02-windows/          build.bat / build.ps1 + SkayClearTux.spec
├── 03-macos/            build.sh + SkayClearTux-macos.spec
├── latest.json.example  пример манифеста дистанционных обновлений
└── README.md            этот файл
```

| № | Папка | Платформа | Что нужно |
|---|-------|-----------|-----------|
| 01 | [`01-linux`](01-linux) | Linux | Python 3.11+ (сборка) или готовый AppImage |
| 02 | [`02-windows`](02-windows) | Windows 10/11 | Windows + Python 3.11+ |
| 03 | [`03-macos`](03-macos) | macOS | Mac + Xcode Command Line Tools |

---

## Быстрая сборка

### Linux — AppImage

```bash
python -m venv .venv && . .venv/bin/activate
pip install PySide6 pyinstaller
pyinstaller --noconfirm --clean --windowed \
    --name SkayClearTux \
    --add-data "skaycleartux/assets:skaycleartux/assets" \
    --icon skaycleartux/assets/tux.png \
    --exclude-module tkinter SkayClearTux.py
VERSION=1.2.0 bash packaging/01-linux/make_appimage.sh
```

Готовый файл: `build/SkayClearTux-1.2.0-x86_64.AppImage`.

### Windows — `.zip` с `.exe`

```powershell
powershell -ExecutionPolicy Bypass -File packaging\02-windows\build.ps1
```

Готово: `dist\SkayClearTux\SkayClearTux.exe` (папку `dist\SkayClearTux` целиком
архивируйте в `.zip`).

### macOS — `.app` и `.dmg`

```bash
bash packaging/03-macos/build.sh
```

Готово: `dist/SkayClearTux.app` и `dist/SkayClearTux-1.2.0.dmg`.

---

## Дистанционные обновления

Программа умеет сама проверять обновления: читает JSON-манифест по адресу
из «Настройки → Обновление программы», показывает баннер «Доступно
обновление», скачивает новый файл, проверяет SHA-256, подменяет его и
перезапускается.

Формат манифеста (`latest.json`):

```json
{
  "version": "1.2.0",
  "url": "https://github.com/skayinray/SkayClearTux/releases/download/v1.2.0/SkayClearTux-1.2.0-x86_64.AppImage",
  "sha256": "....",
  "notes": "Что нового в этой версии",
  "published": "2026-11-16"
}
```

Полный пример — в [`latest.json.example`](latest.json.example). Получите
`sha256` так:

```bash
sha256sum SkayClearTux-1.2.0-x86_64.AppImage
```

CI из [`.github/workflows/build.yml`](../.github/workflows/build.yml) собирает
все три сборки, публикует их в GitHub Releases и **автоматически создаёт
`latest.json`** — достаточно указать ссылку на него в настройках приложения.

> Релиз запускается по тегу: `git tag v1.2.0 && git push --tags`.

---

Создатель: **t.me/imneedasleep**
