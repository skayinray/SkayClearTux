@echo off
rem ============================================================
rem  SkayClearTux v1.5.0 - сборка Windows .exe (PyInstaller)
rem  Запускать из корня проекта (там, где SkayClearTux.py).
rem ============================================================
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python не найден в PATH. Установите Python 3.11+ с python.org
    echo     и отметьте "Add python.exe to PATH".
    pause
    exit /b 1
)

echo ==^> Создаю виртуальное окружение .venv-win
if not exist .venv-win (
    python -m venv .venv-win
)

echo ==^> Устанавливаю зависимости
call .venv-win\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install PySide6 pyinstaller pillow

echo ==^> Готовлю иконку .ico
python -c "from PIL import Image; Image.open('skaycleartux/assets/tux.png').save('skaycleartux/assets/tux.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo ==^> Копирую spec для Windows
copy /Y packaging\02-windows\SkayClearTux.spec SkayClearTux.spec >nul

echo ==^> Собираю
pyinstaller --noconfirm --clean SkayClearTux.spec

echo.
echo ==^> Готово: dist\SkayClearTux\SkayClearTux.exe
echo     (папку dist\SkayClearTux целиком можно архивировать и раздавать)
pause
endlocal
