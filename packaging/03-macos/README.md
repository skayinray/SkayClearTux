# 03 — macOS

Тот же код собирается в нативное приложение `.app` и образ `.dmg`.

**Готовая сборка** публикуется в релизах как `SkayClearTux.dmg` — откройте
образ и перетащите приложение в «Программы».

> Системные разделы на macOS работают через родные средства: Homebrew (пакеты
> и обновления), `launchctl` (службы и автозапуск), `diskutil`/`system_profiler`
> (диски и железо), `pmset`/`ioreg` (батарея), `log show` (журнал),
> `lsof` (порты), корзина `~/.Trash`. Отдельные функции (модули ядра, твики
> ядра) недоступны и аккуратно сообщают об этом.

## Сборка

Нужен Mac с Xcode Command Line Tools (`xcode-select --install`) и Python 3.11+.

```bash
cd SkayClearTux
bash packaging/03-macos/build.sh
```

Скрипт:
* создаёт окружение `.venv-mac`, ставит `PySide6`, `pyinstaller`, `pillow`;
* делает иконку `.icns`;
* собирает `dist/SkayClearTux.app`;
* упаковывает в `dist/SkayClearTux-1.4.0.dmg`.

## Первый запуск

macOS помечает скачанные приложения карантином, поэтому при первом запуске
появится предупреждение «Не удаётся открыть, так как Apple не может проверить
разработчика». Это ожидаемо для неподписанной сборки — есть два пути.

**Способ 1 — через Finder (рекомендуется):**

1. Откройте образ `SkayClearTux.dmg` и перетащите `SkayClearTux.app`
   в папку «Программы».
2. В Finder щёлкните по приложению **правой кнопкой** (или Control + клик) →
   **Открыть**.
3. В диалоге нажмите **Открыть** ещё раз. Дальше приложение запускается как
   обычно, двойным щелчком.

**Способ 2 — снять карантин из терминала:**

```bash
xattr -dr com.apple.quarantine /Applications/SkayClearTux.app
```

**Способ 3 — Системные настройки:** «Конфиденциальность и безопасность» →
в разделе «Безопасность» нажмите **Всё равно открыть** после первой попытки
запуска.

> Скриншот диалога первого запуска — `docs/images/macos-first-run.png`
> (добавляется мейнтейнером при первой публикации).

## Подпись и нотаризация (для раздачи без предупреждений)

Без подписи приложение работает, но при первом запуске macOS просит
подтверждение. Чтобы предупреждений не было, сборку подписывают и нотаризуют.

Готовый скрипт делает всё сам:

```bash
# Ad-hoc подпись + снятие карантина (без аккаунта Apple Developer):
bash packaging/03-macos/sign-and-notarize.sh

# Полная подпись Developer ID + нотаризация (нужен платный аккаунт):
export IDENTITY="Developer ID Application: ВАШЕ ИМЯ (TEAMID)"
export APPLE_ID="you@example.com"
export TEAM_ID="TEAMID"
export APP_PASSWORD="app-specific-password"   # не обычный пароль!
bash packaging/03-macos/sign-and-notarize.sh
```

Скрипт использует `packaging/03-macos/entitlements.plist` (исключения для
dylib Python/PySide6, нужны для нотаризации).

Вручную то же самое выглядит так:

```bash
codesign --deep --force --options runtime --timestamp \
    --entitlements packaging/03-macos/entitlements.plist \
    --sign "Developer ID Application: ВАШЕ ИМЯ (TEAMID)" dist/SkayClearTux.app
xcrun notarytool submit dist/SkayClearTux-1.4.0.dmg \
    --apple-id "you@example.com" --team-id TEAMID --password "app-specific-pw" --wait
xcrun stapler staple dist/SkayClearTux-1.4.0.dmg
```

> **Требует действий мейнтейнера.** Сертификат Developer ID и учётные данные
> Apple Developer не хранятся в репозитории. Пока их нет, релиз публикуется
> ad-hoc-подписанным, а пользователю достаточно способа 1 из раздела
> «Первый запуск».

## Универсальный бинарник (Intel + Apple Silicon)

Чтобы приложение шло и на Intel, и на M-чипах, соберите на universal2-Python:

```bash
pip install "PySide6" pyinstaller
pyinstaller --target-arch universal2 --noconfirm --clean SkayClearTux-macos.spec
```
