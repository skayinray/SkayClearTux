# 02 — Windows

Тот же Python-код собирается в обычное приложение `SkayClearTux.exe`.
Нужен Windows-компьютер с Python 3.11+.

**Готовая сборка** публикуется в релизах как `SkayClearTux-windows.zip`.
Распакуйте архив и запустите `SkayClearTux.exe`.

> Все системные разделы на Windows работают через родные средства:
> `winget`/`choco` (пакеты и обновления), службы Windows, `ipconfig`/`netstat`
> (сеть и порты), WMI (железо, температура, батарея), Планировщик заданий и
> Журнал событий. Отдельные функции (например, модули ядра) недоступны и
> аккуратно сообщают об этом.

## Быстрая сборка

1. Скопируйте всю папку проекта `SkayClearTux` на Windows-машину.
2. Установите Python 3.11+ (python.org), отметив **Add python.exe to PATH**.
3. Запустите скрипт сборки:

   ```bat
   packaging\02-windows\build.bat
   ```

   или через PowerShell:

   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging\02-windows\build.ps1
   ```

4. Результат: `dist\SkayClearTux\SkayClearTux.exe`.
   Папку `dist\SkayClearTux` целиком архивируйте в `.zip` — это и есть сборка.

## Что делает скрипт

* создаёт окружение `.venv-win`;
* ставит `PySide6`, `pyinstaller`, `pillow`;
* делает `tux.ico` из `tux.png`;
* собирает программу по `SkayClearTux.spec` (onedir — быстрый запуск).

## Опционально: один файл .exe

В `SkayClearTux.spec` замените блок `COLLECT` на `onefile`, либо соберите так:

```bat
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name SkayClearTux ^
    --add-data "skaycleartux/assets;skaycleartux/assets" ^
    --icon skaycleartux/assets/tux.ico ^
    --exclude-module tkinter SkayClearTux.py
```

> `--add-data` в Windows использует разделитель `;` (в Linux — `:`).

## Опционально: установщик

Готовый `dist\SkayClearTux` можно завернуть в установщик
[Inno Setup](https://jrsoftware.org/isinfo.php) — 10 строк в `.iss`-скрипте.

## Обновления

Файлы `latest.json` и новые сборки можно публиковать на GitHub Releases —
см. общий [`README.md`](../README.md) и workflow
[`.github/workflows/build.yml`](../../.github/workflows/build.yml).
