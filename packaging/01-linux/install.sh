#!/usr/bin/env bash
# Установка SkayClearTux v1.5.2 из AppImage (любой современный Linux).
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
APPIMAGE="$(ls "$HERE"/SkayClearTux-*.AppImage 2>/dev/null | head -n1 || true)"

if [ -z "$APPIMAGE" ]; then
    echo "Не найден файл SkayClearTux-*.AppImage рядом со скриптом."
    exit 1
fi

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"

echo "==> Копирую AppImage в $BIN_DIR"
install -m 0755 "$APPIMAGE" "$BIN_DIR/SkayClearTux.AppImage"

echo "==> Иконка"
# вытаскиваем иконку из AppImage, если есть; иначе пропускаем
if [ -f "$HERE/skaycleartux.png" ]; then
    install -m 0644 "$HERE/skaycleartux.png" "$ICON_DIR/skaycleartux.png"
fi

echo "==> Пункт меню"
cat > "$APPS_DIR/skaycleartux.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SkayClearTux
GenericName=Системный помощник
Comment=Очистка, монитор, процессы, службы, пакеты, обновления, сеть, порты, железо, диски, журнал, файрвол, твики, хэши, бэкап, темы и шахматы с ботом и рейтингом Эло
Exec=$BIN_DIR/SkayClearTux.AppImage
Icon=skaycleartux
Terminal=false
Categories=Utility;System;Game;
Keywords=cleaner;system;chess;themes;tux;
StartupNotify=true
EOF

update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "==> Готово."
echo "Запуск: SkayClearTux.AppImage  (или из меню приложений)"
echo "Если команды нет в PATH — добавьте в ~/.bashrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
