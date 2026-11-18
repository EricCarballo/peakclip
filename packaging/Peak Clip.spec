# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path

root = Path(SPECPATH).resolve().parent
datas = [(str(root / 'ui'), 'ui'), (str(root / 'assets'), 'assets')]
datas += collect_data_files('googleapiclient')

a = Analysis(
    [str(root / 'src' / 'peakclip' / '__main__.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=['peakclip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Peak Clip',
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
    icon=[str(root / 'assets' / 'peak-clip.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Peak Clip',
)
