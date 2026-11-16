# 01 — Linux (AppImage)

SkayClearTux собирается в один переносимый файл
`SkayClearTux-1.2.0-x86_64.AppImage`. Работает на большинстве современных
дистрибутивов (glibc 2.35+): Arch, Ubuntu 22.04+, Fedora, Debian 12 и др.

## Установка из готовой сборки

Положите AppImage рядом с `install.sh` и запустите:

```bash
chmod +x install.sh
./install.sh
```

Скрипт положит AppImage в `~/.local/bin`, иконку — в `~/.local/share/icons`
и создаст пункт в меню приложений. После этого программа запускается из меню
или командой `SkayClearTux.AppImage`.

## Запуск без установки

```bash
chmod +x SkayClearTux-1.2.0-x86_64.AppImage
./SkayClearTux-1.2.0-x86_64.AppImage
```

Если FUSE не установлен (частая ситуация в контейнерах):

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./SkayClearTux-1.2.0-x86_64.AppImage
```

## Что внутри

* Python 3 + PySide6 (Qt 6), собран в один AppImage через PyInstaller.
* Ничего доустанавливать не нужно — все библиотеки внутри.

## Сборка AppImage с нуля

```bash
cd /path/to/SkayClearTux
python -m venv .venv && . .venv/bin/activate
pip install PySide6 pyinstaller
pyinstaller --noconfirm --clean --windowed \
    --name SkayClearTux \
    --add-data "skaycleartux/assets:skaycleartux/assets" \
    --icon skaycleartux/assets/tux.png \
    --exclude-module tkinter SkayClearTux.py
VERSION=1.2.0 bash packaging/01-linux/make_appimage.sh
```

Скрипт `make_appimage.sh` сам скачает `appimagetool`, если его нет, и соберёт
`build/SkayClearTux-1.2.0-x86_64.AppImage`. Тот же сценарий использует CI.
