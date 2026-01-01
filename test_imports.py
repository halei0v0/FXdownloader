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

    if failed_imports:
        print(f"\nFailed imports: {failed_imports}")
        return False
    else:
        print("\nAll imports successful!")
        return True


def test_pywebview():
    """测试pywebview功能"""
    try:
        import pywebview
        print(f"\nPyWebView version: {pywebview.__version__}")

        # 测试是否可以创建窗口
        print("Testing window creation...")

        def create_test_window():
            window = pywebview.create_window(
                'Test Window',
                html='<h1>Test Window</h1>',
                width=400,
                height=300
            )
            pywebview.start()

        # 在新线程中测试，避免阻塞
        import threading
        test_thread = threading.Thread(target=create_test_window)
        test_thread.daemon = True
        test_thread.start()

        import time
        time.sleep(2)  # 等待窗口创建

        print("PyWebView test completed")
        return True

    except Exception as e:
        print(f"PyWebView test failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=== Import Test ===")
    imports_ok = test_imports()

    print("\n=== PyWebView Test ===")
    pywebview_ok = test_pywebview()

    if imports_ok and pywebview_ok:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed!")

    input("\nPress Enter to exit...")
