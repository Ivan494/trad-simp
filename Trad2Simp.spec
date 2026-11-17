# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import runpy
from pathlib import Path

version_file = str(Path(SPECPATH) / 'build' / 'version_info.txt')
runpy.run_path(str(Path(SPECPATH) / 'scripts' / 'version_info.py'))['write_version_info'](version_file)

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('opencc')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pystray')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


hiddenimports += [
    'trad2simp',
    'trad2simp.app',
    'trad2simp.config',
    'trad2simp.convert',
    'trad2simp.hotkeys',
    'trad2simp.instance',
    'trad2simp.win32',
    'trad2simp.__main__',
]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['keyboard', 'pyperclip'],
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
    name='Trad2Simp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
    version=version_file,
)
