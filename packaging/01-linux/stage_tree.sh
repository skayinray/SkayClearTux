#!/usr/bin/env bash
# Общий код упаковки Linux-дерева для .deb и .rpm.
#
# Подключается через `source`; задаёт ROOT/NAME/VER и функцию
# stage_linux_tree <каталог-назначение>. Требует собранный бандл
# dist/SkayClearTux (PyInstaller).
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
NAME="SkayClearTux"
if [ -z "${VERSION:-}" ] && [ -f "$ROOT/skaycleartux/__init__.py" ]; then
    VERSION="$(python3 -c 'import re, pathlib; t=pathlib.Path("'"$ROOT"'/skaycleartux/__init__.py").read_text(); m=re.search(r"__version__\s*=\s*\"([^\"]+)\"", t); print(m.group(1) if m else "1.3.2")' 2>/dev/null || true)"
fi
VER="${VERSION:-1.3.2}"

stage_linux_tree() {
    local STAGE="$1"
    rm -rf "$STAGE"
    mkdir -p "$STAGE/opt/$NAME" \
             "$STAGE/usr/bin" \
             "$STAGE/usr/share/applications" \
             "$STAGE/usr/share/icons/hicolor/256x256/apps"

    cp -r "$ROOT/dist/$NAME/." "$STAGE/opt/$NAME/"

    cat > "$STAGE/usr/bin/skaycleartux" <<EOF
#!/bin/sh
exec /opt/$NAME/$NAME "\$@"
EOF
    chmod 0755 "$STAGE/usr/bin/skaycleartux"

    sed 's|^Exec=.*|Exec=skaycleartux|' \
        "$ROOT/packaging/01-linux/skaycleartux.desktop" \
        > "$STAGE/usr/share/applications/skaycleartux.desktop"

    cp "$ROOT/skaycleartux/assets/tux.png" \
        "$STAGE/usr/share/icons/hicolor/256x256/apps/skaycleartux.png"
}
