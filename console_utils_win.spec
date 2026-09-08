# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Console Utilities Windows executable

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the directory containing the spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# retro_roster_patcher populates its game registry by importing every game
# package for the side effect of @register. PyInstaller's static analysis
# follows those, but the games are only reachable through that one import, so
# collect the whole tree rather than trusting the graph. collect_data_files
# picks up the WE2002 .ppf, which is read via importlib.resources and would
# otherwise be absent from the bundle.
_rrp_hiddenimports = collect_submodules('retro_roster_patcher')
_rrp_datas = collect_data_files('retro_roster_patcher')

a = Analysis(
    ['src/app.py'],
    pathex=[os.path.join(spec_dir, 'src')],
    binaries=[],
    datas=[
        ('assets', 'assets'),
    ] + _rrp_datas,
    hiddenimports=[
        'pygame',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'rarfile',
        'zstandard',
        'Crypto',
        'Crypto.Cipher',
        'Crypto.Cipher.AES',
        'Crypto.Util',
        'Crypto.Util.Padding',
    ] + _rrp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Console Utilities',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Console Utilities',
)
