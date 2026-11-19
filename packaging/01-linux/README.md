# 01 — Linux (AppImage, .deb, .rpm)

SkayClearTux собирается в один переносимый файл
`SkayClearTux-1.5.3.1-x86_64.AppImage`, а также в пакеты `.deb` и `.rpm`.
Работает на большинстве современных дистрибутивов (glibc 2.35+): Arch,
Ubuntu 22.04+, Fedora, Debian 12 и др.

Менеджер пакетов определяется автоматически: **pacman, apt, dnf, zypper, apk**.

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
chmod +x SkayClearTux-1.5.3.1-x86_64.AppImage
./SkayClearTux-1.5.3.1-x86_64.AppImage
```

Если FUSE не установлен (частая ситуация в контейнерах):

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./SkayClearTux-1.5.3.1-x86_64.AppImage
```

## Установка из пакетов .deb / .rpm

```bash
# Debian, Ubuntu, Mint и производные:
sudo apt install ./SkayClearTux-1.5.3.1-amd64.deb

# Fedora, RHEL, openSUSE и производные:
sudo dnf install ./SkayClearTux-1.5.3.1-x86_64.rpm
```

После установки программа появляется в меню приложений и запускается командой
`skaycleartux`.

## Что внутри

* Python 3 + PySide6 (Qt 6), собран в один AppImage через PyInstaller.
* Ничего доустанавливать не нужно — все библиотеки внутри.

## Сборка с нуля

```bash
cd /path/to/SkayClearTux
python -m venv .venv && . .venv/bin/activate
pip install PySide6 pyinstaller
pyinstaller --noconfirm --clean --windowed \
    --name SkayClearTux \
    --add-data "skaycleartux/assets:skaycleartux/assets" \
    --icon skaycleartux/assets/tux.png \
    --exclude-module tkinter SkayClearTux.py
VERSION=1.5.3.1 bash packaging/01-linux/make_appimage.sh   # AppImage
VERSION=1.5.3.1 bash packaging/01-linux/make_deb.sh        # .deb (нужен dpkg-deb)
VERSION=1.5.3.1 bash packaging/01-linux/make_rpm.sh        # .rpm (нужен rpmbuild)
```

`make_appimage.sh` сам скачает `appimagetool`, если его нет, и соберёт
`build/SkayClearTux-1.5.3.1-x86_64.AppImage`. Скрипты `make_deb.sh` и
`make_rpm.sh` используют общий `stage_tree.sh`. Тот же сценарий использует CI.
