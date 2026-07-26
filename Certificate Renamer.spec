# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('assets', 'assets')]
datas += collect_data_files('tzdata')


a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PySide6', 'plyer', 'plyer.platforms.win.notification', 'pystray', 'PIL', 'openpyxl', 'zoneinfo', 'tzdata'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'pytest', 'docutils'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Certificate Renamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='assets\\version_info.txt',
    icon=['assets\\favicon.ico'],
)
