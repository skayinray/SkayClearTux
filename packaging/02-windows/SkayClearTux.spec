# -*- mode: python ; coding: utf-8 -*-
# SkayClearTux.spec — сборка для Windows (PyInstaller, onedir).
#
# Использование (в папке с SkayClearTux.py):
#   pyinstaller --noconfirm --clean SkayClearTux.spec
#
# Иконку .ico можно сгенерировать из PNG:
#   python -c "from PIL import Image; Image.open('skaycleartux/assets/tux.png').save('skaycleartux/assets/tux.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

a = Analysis(
    ['SkayClearTux.py'],
    pathex=[],
    binaries=[],
    datas=[('skaycleartux/assets', 'skaycleartux/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SkayClearTux',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='skaycleartux/assets/tux.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SkayClearTux',
)
