# -*- mode: python ; coding: utf-8 -*-
# SkayClearTux.spec — сборка для macOS (.app + .dmg).
#
#   pyinstaller --noconfirm --clean SkayClearTux-macos.spec
#
# Универсальный бинарник (Intel + Apple Silicon) требует universal2-сборки
# Python и PySide6; на обычной машине получится бинарник под её архитектуру.

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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='skaycleartux/assets/tux.icns',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SkayClearTux',
)

app = BUNDLE(
    coll,
    name='SkayClearTux.app',
    icon='skaycleartux/assets/tux.icns',
    bundle_identifier='ru.skaycleartux.app',
    info_plist={
        'CFBundleName': 'SkayClearTux',
        'CFBundleDisplayName': 'SkayClearTux',
        'CFBundleShortVersionString': '1.4.0',
        'CFBundleVersion': '1.4.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)
