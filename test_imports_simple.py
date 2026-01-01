#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试导入是否正常
"""

import sys
import traceback


def test_imports():
    """测试关键模块导入"""
    modules_to_test = [
        'flask',
        'flask_cors',
        'pywebview',
        'requests',
        'PIL',
        'beautifulsoup4',
        'ebooklib',
        'fake_useragent',
        'tqdm',
        'markdown',
        'aiohttp',
        'packaging',
        'pillow_heif'
    ]

    print("Python version:", sys.version)
    print("\nTesting imports...")

    failed_imports = []

    for module in modules_to_test:
        try:
            if module == 'beautifulsoup4':
                import bs4
                print(f"✓ {module} (bs4)")
            elif module == 'pillow_heif':
                import pillow_heif
                print(f"✓ {module}")
            else:
                __import__(module)
                print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: {e}")
            failed_imports.append(module)

    # 测试本地模块
    local_modules = [
        'config',
        'web_app',
        'novel_downloader',
        'locales',
        'platform_utils',
        'updater'
    ]

    print("\nTesting local modules...")

    for module in local_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: {e}")
            failed_imports.append(module)
        except Exception as e:
            print(f"✗ {module}: {e}")
            failed_imports.append(module)

    if failed_imports:
        print(f"\nFailed imports: {failed_imports}")
        return False
    else:
        print("\nAll imports successful!")
        return True


if __name__ == "__main__":
    print("=== Import Test ===")
    imports_ok = test_imports()

    if imports_ok:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed!")
