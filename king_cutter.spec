# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec file for King Video Cutter (ស្ដេចកាត់វីដេអូ).
Packages Python runtime, PySide6 GUI, Khmer fonts, locales, and bundled FFmpeg/FFprobe binaries.
"""

import sys
import os

block_cipher = None

BASE_DIR = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(BASE_DIR, 'locales'), 'locales'),
    (os.path.join(BASE_DIR, 'assets', 'fonts'), os.path.join('assets', 'fonts')),
    (os.path.join(BASE_DIR, 'assets', 'icons'), os.path.join('assets', 'icons')),
    (os.path.join(BASE_DIR, 'assets', 'bin', 'ffmpeg.exe'), os.path.join('assets', 'bin')),
    (os.path.join(BASE_DIR, 'assets', 'bin', 'ffprobe.exe'), os.path.join('assets', 'bin')),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'ctypes',
    'shutil',
    'subprocess',
    'json',
    're',
    'time',
]

a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
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
    name='KingVideoCutter',
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
    icon=os.path.join(BASE_DIR, 'assets', 'icons', 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KingVideoCutter',
)
