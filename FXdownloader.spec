# -*- mode: python ; coding: utf-8 -*-
"""
FXdownloader 打包配置文件
"""

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        ('msedgedriver.exe', '.'),
    ],
    datas=[
        ('config.py', '.'),
        ('database.py', '.'),
        ('downloader.py', '.'),
        ('spider.py', '.'),
        ('font_decrypt.py', '.'),
        ('login_helper.html', '.'),
        ('config.json', '.'),
        ('webdrivers', 'webdrivers'),
        ('Driver_Notes', 'Driver_Notes'),
        ('font_cache', 'font_cache'),
        ('database', 'database'),
    ],
    hiddenimports=[
        'requests',
        'bs4',
        'lxml',
        'fake_useragent',
        'fontTools',
        'PIL',
        'ddddocr',
        'parsel',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FXdownloader',
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
    icon=None,
)