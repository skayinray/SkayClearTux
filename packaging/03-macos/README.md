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
* упаковывает в `dist/SkayClearTux-1.2.0.dmg`.

## Первый запуск

macOS помечает скачанные приложения карантином. Один раз:
правый клик по `SkayClearTux.app` → **Открыть** → **Открыть**.

## Универсальный бинарник (Intel + Apple Silicon)

Чтобы приложение шло и на Intel, и на M-чипах, соберите на universal2-Python:

```bash
pip install "PySide6" pyinstaller
pyinstaller --target-arch universal2 --noconfirm --clean SkayClearTux-macos.spec
```

## Подпись и нотаризация (для раздачи без предупреждений)

```bash
codesign --deep --force --options runtime \
    --sign "Developer ID Application: ВАШЕ ИМЯ (TEAMID)" dist/SkayClearTux.app
xcrun notarytool submit dist/SkayClearTux-1.2.0.dmg \
    --apple-id "you@example.com" --team-id TEAMID --password "app-specific-pw" --wait
xcrun stapler staple dist/SkayClearTux-1.2.0.dmg
```

Для нотаризации нужен платный Apple Developer аккаунт. Без него приложение
работает, но при первом запуске macOS попросит подтверждение.
