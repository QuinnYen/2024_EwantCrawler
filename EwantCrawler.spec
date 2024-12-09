# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('resources', 'resources'), ('venv/Lib/site-packages/PyQt6', 'PyQt6')]
binaries = [('venv/Lib/site-packages/selenium', 'selenium'), ('dependencies\\dlls\\ffi.dll', '.'), ('dependencies\\dlls\\libbz2.dll', '.'), ('dependencies\\dlls\\libcrypto-3-x64.dll', '.'), ('dependencies\\dlls\\libexpat.dll', '.'), ('dependencies\\dlls\\liblzma.dll', '.'), ('dependencies\\dlls\\libssl-3-x64.dll', '.')]
hiddenimports = ['PyQt6', 'selenium', 'xml.parsers.expat', 'pkg_resources.py2_warn', 'pkg_resources']
tmp_ret = collect_all('selenium')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='EwantCrawler',
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
    icon=['resources\\icon.ico'],
)
