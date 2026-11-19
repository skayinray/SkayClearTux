# SkayClearTux v1.5.2 — сборка Windows (PowerShell)
# Запуск из корня проекта:  powershell -ExecutionPolicy Bypass -File packaging\02-windows\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> Проверяю Python" -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python не найден. Установите Python 3.11+ с python.org (Add to PATH)."
}

Write-Host "==> Виртуальное окружение .venv-win" -ForegroundColor Cyan
if (-not (Test-Path ".venv-win")) { python -m venv .venv-win }

Write-Host "==> Зависимости" -ForegroundColor Cyan
& ".venv-win\Scripts\python.exe" -m pip install --upgrade pip
& ".venv-win\Scripts\python.exe" -m pip install PySide6 pyinstaller pillow

Write-Host "==> Иконка .ico" -ForegroundColor Cyan
& ".venv-win\Scripts\python.exe" -c "from PIL import Image; Image.open('skaycleartux/assets/tux.png').save('skaycleartux/assets/tux.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

Write-Host "==> Spec и сборка" -ForegroundColor Cyan
Copy-Item -Force "packaging\02-windows\SkayClearTux.spec" "SkayClearTux.spec"
& ".venv-win\Scripts\pyinstaller.exe" --noconfirm --clean SkayClearTux.spec

Write-Host "==> Готово: dist\SkayClearTux\SkayClearTux.exe" -ForegroundColor Green
