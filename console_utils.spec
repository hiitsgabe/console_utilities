# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Console Utilities macOS app

import os
import sys

block_cipher = None

# Get the directory containing the spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))

_binaries = []

a = Analysis(
    ['src/app.py'],
    pathex=[os.path.join(spec_dir, 'src')],
    binaries=_binaries,
    datas=[
        ('assets', 'assets'),
    ],
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
    ],
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
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS argv emulation
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

app = BUNDLE(
    coll,
    name='Console Utilities.app',
    bundle_identifier='com.consoleutilities.app',
    info_plist={
        'CFBundleName': 'Console Utilities',
        'CFBundleDisplayName': 'Console Utilities',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
    },
)
