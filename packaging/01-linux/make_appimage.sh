#!/usr/bin/env bash
# Сборка AppImage SkayClearTux.
#
# Требуется: собранный бандл PyInstaller в dist/SkayClearTux и appimagetool.
#   VERSION=1.5.3.1 bash packaging/01-linux/make_appimage.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUILD="$ROOT/build"
APPDIR="$BUILD/SkayClearTux.AppDir"
NAME="SkayClearTux"

if [ -z "${VERSION:-}" ] && [ -f "$ROOT/skaycleartux/__init__.py" ]; then
    VERSION="$(python3 -c 'import re, pathlib; t=pathlib.Path("'"$ROOT"'/skaycleartux/__init__.py").read_text(); m=re.search(r"__version__\s*=\s*\"([^\"]+)\"", t); print(m.group(1) if m else "1.5.3.1")' 2>/dev/null || true)"
fi
VER="${VERSION:-1.5.3.1}"

if [ ! -d "$ROOT/dist/$NAME" ]; then
    echo "Нет dist/$NAME — сначала соберите бандл PyInstaller."
    exit 1
fi

if [ ! -x "$BUILD/appimagetool-x86_64.AppImage" ]; then
    echo "==> Скачиваю appimagetool"
    curl -L -o "$BUILD/appimagetool-x86_64.AppImage" \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$BUILD/appimagetool-x86_64.AppImage"
fi

echo "==> Очищаю AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

echo "==> Копирую бандл"
cp -r "$ROOT/dist/$NAME/." "$APPDIR/usr/bin/"

echo "==> AppRun"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/SkayClearTux" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> desktop-файл и иконка"
cat > "$APPDIR/skaycleartux.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SkayClearTux
GenericName=Системный помощник
Comment=Очистка, монитор, процессы, службы, пакеты, обновления, сеть, порты, железо, диски, журнал, файрвол, твики, хэши, бэкап, темы и шахматы с ботом
Exec=SkayClearTux
Icon=skaycleartux
Terminal=false
Categories=Utility;System;Game;
Keywords=cleaner;system;chess;themes;tux;
Version=1.0
X-AppVersion=$VER
EOF

cp "$ROOT/skaycleartux/assets/tux.png" "$APPDIR/skaycleartux.png"
cp "$APPDIR/skaycleartux.png" "$APPDIR/.DirIcon"

echo "==> Собираю AppImage"
cd "$BUILD"
ARCH=x86_64 ./appimagetool-x86_64.AppImage --no-appstream \
    "$APPDIR" "$BUILD/$NAME-$VER-x86_64.AppImage"

echo "==> Готово:"
ls -la "$BUILD/$NAME-$VER-x86_64.AppImage"
