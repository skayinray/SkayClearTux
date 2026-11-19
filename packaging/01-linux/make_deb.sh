#!/usr/bin/env bash
# Сборка .deb-пакета SkayClearTux (Debian, Ubuntu, Mint и др.).
#
# Требуется: собранный бандл PyInstaller в dist/SkayClearTux и dpkg-deb.
#   VERSION=1.5.3.1 bash packaging/01-linux/make_deb.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=stage_tree.sh
source "$HERE/stage_tree.sh"

BUILD="$ROOT/build"
STAGE="$BUILD/deb/$NAME"

if [ ! -d "$ROOT/dist/$NAME" ]; then
    echo "Нет dist/$NAME — сначала соберите бандл PyInstaller."
    exit 1
fi
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Нужен dpkg-deb (пакеты dpkg / dpkg-dev)."
    exit 1
fi

echo "==> Готовлю дерево файлов"
stage_linux_tree "$STAGE"

echo "==> Управляющие файлы пакета"
mkdir -p "$STAGE/DEBIAN"
SIZE_KB=$(du -sk "$STAGE/opt/$NAME" | cut -f1)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: skaycleartux
Version: $VER
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: $SIZE_KB
Depends: libc6 (>= 2.35), libgl1, libegl1, libxkbcommon0, libdbus-1-3, libfontconfig1, libglib2.0-0
Maintainer: SkayClearTux <t.me/imneedasleep>
Homepage: https://github.com/skayinray/SkayClearTux
Description: Универсальный помощник для Linux
 Очистка системы, мониторинг, процессы и службы, пакеты и обновления,
 сеть и порты, железо и диски, журнал, файрвол, твики, хэши, бэкап,
 темы и шахматы с ботом.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
update-desktop-database -q /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
exit 0
EOF
chmod 0755 "$STAGE/DEBIAN/postinst"

echo "==> Собираю .deb"
mkdir -p "$BUILD"
dpkg-deb --build --root-owner-group "$STAGE" "$BUILD/$NAME-$VER-amd64.deb"

echo "==> Готово:"
ls -la "$BUILD/$NAME-$VER-amd64.deb"
