#!/usr/bin/env bash
# SkayClearTux — подпись и нотаризация сборки macOS.
#
# Два режима:
#
# 1. Ad-hoc подпись (без Apple Developer аккаунта).
#    Достаточно, чтобы приложение запускалось локально и не пугало карантином
#    при передаче «из рук в руки»:
#
#        bash packaging/03-macos/sign-and-notarize.sh
#
# 2. Полная подпись + нотаризация (нужен платный Apple Developer аккаунт).
#    Задайте переменные окружения и запустите скрипт:
#
#        export IDENTITY="Developer ID Application: ИМЯ (TEAMID)"
#        export APPLE_ID="you@example.com"
#        export TEAM_ID="TEAMID"
#        export APP_PASSWORD="app-specific-password"   # не обычный пароль!
#        bash packaging/03-macos/sign-and-notarize.sh
#
# Подробности — в packaging/03-macos/README.md и SECURITY.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

APP="${1:-dist/SkayClearTux.app}"
ENTITLEMENTS="packaging/03-macos/entitlements.plist"

if [ ! -d "$APP" ]; then
    echo "Не найден $APP — сначала соберите приложение: bash packaging/03-macos/build.sh" >&2
    exit 1
fi

if [ -n "${IDENTITY:-}" ]; then
    echo "==> Подпись Developer ID: $IDENTITY"
    codesign --deep --force --options runtime --timestamp \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" "$APP"
    codesign --verify --deep --strict --verbose=2 "$APP"
else
    echo "==> Ad-hoc подпись (без Developer ID)"
    codesign --deep --force --sign - "$APP"
    codesign --verify --deep --strict --verbose=2 "$APP"
fi

# Снимаем карантин, чтобы приложение открывалось без диалога Gatekeeper.
echo "==> Снятие карантина"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

# Нотаризация — только если заданы все параметры Apple Developer.
if [ -n "${APPLE_ID:-}" ] && [ -n "${TEAM_ID:-}" ] && [ -n "${APP_PASSWORD:-}" ]; then
    DMG="${2:-$(ls dist/SkayClearTux-*.dmg 2>/dev/null | head -n1 || true)}"
    TARGET="${DMG:-$APP}"
    echo "==> Нотаризация $TARGET (может занять несколько минут)"
    xcrun notarytool submit "$TARGET" \
        --apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$APP_PASSWORD" --wait
    echo "==> Прикрепление тикета"
    xcrun stapler staple "$TARGET" || xcrun stapler staple "$APP"
    echo "==> Готово: подписано и нотаризовано"
else
    cat <<'NOTE'

Готово (ad-hoc). Для раздачи без предупреждений Gatekeeper нужен платный
Apple Developer аккаунт и повторный запуск с переменными IDENTITY, APPLE_ID,
TEAM_ID и APP_PASSWORD (см. packaging/03-macos/README.md).

Этот пункт требует действий мейнтейнера: сертификат и учётные данные Apple
Developer не хранятся в репозитории.
NOTE
fi
