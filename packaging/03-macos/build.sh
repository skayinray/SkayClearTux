#!/usr/bin/env bash
# SkayClearTux v1.3.2 — сборка для macOS (.app и .dmg).
# Запуск из корня проекта:  bash packaging/03-macos/build.sh
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Проверяю Python 3"
python3 --version

echo "==> Окружение .venv-mac"
[ -d .venv-mac ] || python3 -m venv .venv-mac
source .venv-mac/bin/activate
python -m pip install --upgrade pip
python -m pip install PySide6 pyinstaller pillow

echo "==> Иконка .icns"
mkdir -p skaycleartux/assets/tux.iconset
python - <<'PY'
from PIL import Image
src = Image.open("skaycleartux/assets/tux.png").convert("RGBA")
sizes = [16, 32, 64, 128, 256, 512, 1024]
for s in sizes:
    img = src.resize((s, s), Image.LANCZOS)
    img.save(f"skaycleartux/assets/tux.iconset/icon_{s}x{s}.png")
    img.resize((s*2, s*2), Image.LANCZOS).save(
        f"skaycleartux/assets/tux.iconset/icon_{s}x{s}@2x.png")
PY
iconutil -c icns skaycleartux/assets/tux.iconset -o skaycleartux/assets/tux.icns

echo "==> Сборка .app"
cp packaging/03-macos/SkayClearTux-macos.spec SkayClearTux-macos.spec
pyinstaller --noconfirm --clean SkayClearTux-macos.spec

echo "==> Сборка .dmg"
APP="dist/SkayClearTux.app"
DMG="dist/SkayClearTux-${VERSION:-1.3.2}.dmg"
if command -v hdiutil >/dev/null 2>&1; then
    rm -f "$DMG"
    hdiutil create -volname "SkayClearTux" -srcfolder "$APP" -ov -format UDZO "$DMG"
    echo "==> Готово: $DMG"
else
    echo "==> hdiutil не найден, .app лежит в $APP"
fi

echo
echo "Первый запуск: правый клик по SkayClearTux.app -> Открыть (снимает карантин)."
echo "Для распространения подпишите и нотаризуйте приложение (codesign/notarytool)."
