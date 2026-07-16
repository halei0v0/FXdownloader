# -*- mode: python ; coding: utf-8 -*-
"""
FXdownloader 打包配置文件

主入口：web_ui/app.py（pywebview + HTML/CSS/JS WebUI）
源抽象：sources/ 模块（蚂蚁文学 + 顶点 + 笔下 + 铅笔 + 海棠 + 番茄）
依赖：pywebview, scrapling, curl_cffi, bs4, requests, lxml
"""

import os
import glob
import sys

# PyInstaller hook 工具
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

tomato_exe = 'TomatoNovelDownloader-Win64-v2.4.0.exe'
tomato_binaries = []
if os.path.exists(tomato_exe):
    tomato_binaries.append((tomato_exe, '.'))

# 构建需要打包的数据文件列表
datas_list = [
    # Python 模块文件
    ('config.py', '.'),
    ('database.py', '.'),
    ('downloader.py', '.'),
    ('spider.py', '.'),
    ('font_decrypt.py', '.'),
    ('selenium_login.py', '.'),
    ('gui.py', '.'),  # 兼容旧入口 + 登录对话框复用
    # HTML 模板文件
    ('login_helper.html', '.'),
    # WebUI 文件
    ('web_ui/app.py', 'web_ui'),
    ('web_ui/index.html', 'web_ui'),
]

# sources 模块：仅作为 Python 包通过 hiddenimports 打包（编译进 PYZ），
# 不需要再作为 DATA 文件重复打包
# （之前 glob.glob('sources/*.py') 作为 data 是冗余的）

# 可选配置文件
if os.path.exists('config.json'):
    datas_list.append(('config.json', '.'))

# 静态资源目录
if os.path.exists('webdrivers'):
    datas_list.append(('webdrivers', 'webdrivers'))
if os.path.exists('Driver_Notes'):
    datas_list.append(('Driver_Notes', 'Driver_Notes'))

# ====== scrapling 及其依赖完整收集 ======
# scrapling 是 editable 安装，PyInstaller 静态分析无法解析其子模块。
# browserforge/apify_fingerprint_datapoints 有数据文件（.zip）需要收集。
scrapling_hidden = []
scrapling_datas = []
try:
    scrapling_hidden = collect_submodules('scrapling')
    scrapling_datas = collect_data_files('scrapling')
    print(f'[spec] scrapling 子模块数: {len(scrapling_hidden)}')
    print(f'[spec] scrapling 数据文件数: {len(scrapling_datas)}')
except Exception as e:
    print(f'[spec] 警告: collect_submodules("scrapling") 失败: {e}')
    scrapling_hidden = [
        'scrapling', 'scrapling.__init__', 'scrapling.parser',
        'scrapling.fetchers', 'scrapling.fetchers.__init__',
        'scrapling.fetchers.requests', 'scrapling.fetchers.async_fetcher',
        'scrapling.fetchers.sync_fetcher', 'scrapling.fetchers.web_driver',
        'scrapling.fetchers.firefox', 'scrapling.fetchers.stealthy',
        'scrapling.fetchers.chrome', 'scrapling.fetchers.stealth_chrome',
        'scrapling.core', 'scrapling.core.__init__',
        'scrapling.core.custom_types', 'scrapling.core._types',
        'scrapling.core._html_callbacks', 'scrapling.core._matcher',
        'scrapling.core._verifiers',
        'scrapling.engines', 'scrapling.engines.__init__',
        'scrapling.engines.static', 'scrapling.engines.toolbelt',
        'scrapling.engines.toolbelt.custom',
    ]

# browserforge + apify_fingerprint_datapoints 的数据文件（.zip）必须打包
browserforge_datas = []
apify_datas = []
browserforge_hidden = []
try:
    browserforge_hidden = collect_submodules('browserforge')
    browserforge_datas = collect_data_files('browserforge')
    print(f'[spec] browserforge 子模块数: {len(browserforge_hidden)}, 数据文件数: {len(browserforge_datas)}')
except Exception as e:
    print(f'[spec] 警告: collect("browserforge") 失败: {e}')

try:
    apify_datas = collect_data_files('apify_fingerprint_datapoints')
    print(f'[spec] apify_fingerprint_datapoints 数据文件数: {len(apify_datas)}')
except Exception as e:
    print(f'[spec] 警告: collect("apify_fingerprint_datapoints") 失败: {e}')

# curl_cffi 也需要完整收集（scrapling 依赖）
curl_hidden = []
try:
    curl_hidden = collect_submodules('curl_cffi')
except Exception:
    curl_hidden = ['curl_cffi', 'curl_cffi.requests', 'curl_cffi._wrapper']

# 注意：font_cache 和 database 是运行时动态生成的目录，不需要打包

a = Analysis(
    ['web_ui/app.py'],
    pathex=['.', 'Scrapling-main'],
    binaries=[
        ('msedgedriver.exe', '.'),
    ] + tomato_binaries,
    datas=datas_list + scrapling_datas + browserforge_datas + apify_datas,
    hiddenimports=[
        'requests',
        'bs4',
        'lxml',
        'fake_useragent',
        'fontTools',
        'PIL',
        'ddddocr',
        'parsel',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        # pywebview 相关
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'webview.platforms.gtk',
        'webview.platforms.cocoa',
        'webview.platforms.qt',
        'clr_loader',
        'pythonnet',
        # Scrapling / curl_cffi / browserforge 完整收集
    ] + scrapling_hidden + curl_hidden + browserforge_hidden + [
        'apify_fingerprint_datapoints',
        'playwright',
        'w3lib',
        'cssselect',
        'orjson',
        'tld',
        # 本项目 sources 模块
        'sources',
        'sources.base',
        'sources.biquge_source',
        'sources.fanqie_source',
        'sources.bing_search',
        'sources.generic_source',
        'sources.multi_source',
        'sources.sudugu_rankings',
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
