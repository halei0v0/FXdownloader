# 配置文件
import os

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
DATABASE_DIR = os.path.join(BASE_DIR, 'database')

# 创建必要的目录
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)

# 数据库配置
DATABASE_PATH = os.path.join(DATABASE_DIR, 'fanqie_novels.db')

# 番茄小说API配置
FANQIE_BASE_URL = "https://fanqienovel.com"
FANQIE_API_BASE = "https://api.fanqienovel.com"

# 请求配置
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
REQUEST_DELAY = 1  # 请求间隔，避免被封

# 输出格式配置
OUTPUT_FORMAT = 'txt'  # txt 或 epub

# Cookie 配置（用于访问需要登录权限的内容）
COOKIE_FILE = os.path.join(BASE_DIR, 'cookies.txt')

def load_cookies():
    """从 cookies.txt 文件加载 Cookie"""
    cookies = {}
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    # 支持两种格式：
                    # 1. JSON 格式: {"key1": "value1", "key2": "value2"}
                    # 2. 纯文本格式: key1=value1; key2=value2
                    if content.startswith('{'):
                        import json
                        cookies = json.loads(content)
                    else:
                        # 解析纯文本格式
                        for item in content.split(';'):
                            item = item.strip()
                            if '=' in item:
                                key, value = item.split('=', 1)
                                cookies[key.strip()] = value.strip()
            print(f"已加载 {len(cookies)} 个 Cookie")
        except Exception as e:
            print(f"加载 Cookie 失败: {e}")
    return cookies

def save_cookies(cookies):
    """保存 Cookie 到 cookies.txt 文件"""
    try:
        import json
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"已保存 {len(cookies)} 个 Cookie 到 {COOKIE_FILE}")
        return True
    except Exception as e:
        print(f"保存 Cookie 失败: {e}")
        return False

def clear_cookies():
    """清除保存的 Cookie"""
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
            print("已清除 Cookie")
            return True
    except Exception as e:
        print(f"清除 Cookie 失败: {e}")
        return False

# 全局加载 Cookie
COOKIES = load_cookies()