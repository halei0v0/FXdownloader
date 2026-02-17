# 配置文件
import os
import sys

# 基础配置
# 检测是否在 PyInstaller 打包环境中运行
if getattr(sys, 'frozen', False):
    # 打包模式：使用用户目录保存配置和数据
    BASE_DIR = os.path.join(os.path.expanduser('~'), 'FXdownloader')
else:
    # 开发模式：使用脚本所在目录
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

# 基础请求延迟配置（模拟正常用户阅读速度）
REQUEST_DELAY_MIN = 3.0  # 最小延迟（秒）
REQUEST_DELAY_MAX = 5.0  # 最大延迟（秒）

# 下载速度配置（用户可调整）
DEFAULT_DOWNLOAD_SPEED = 1.0  # 默认下载速度（倍数，1.0表示正常速度）
MIN_DOWNLOAD_SPEED = 0.5  # 最小下载速度（0.5表示慢速）
MAX_DOWNLOAD_SPEED = 2.0  # 最大下载速度（2.0表示快速）

def get_download_speed():
    """获取下载速度配置"""
    config = load_config()
    return config.get('download_speed', DEFAULT_DOWNLOAD_SPEED)

def set_download_speed(speed):
    """设置下载速度配置"""
    config = load_config()
    config['download_speed'] = max(MIN_DOWNLOAD_SPEED, min(speed, MAX_DOWNLOAD_SPEED))
    return save_config(config)

# 基于章节字数的动态延迟配置
# 阅读速度：约 600-900 字/分钟（10-15 字/秒）
READ_SPEED_MIN = 10  # 最快阅读速度（字/秒）
READ_SPEED_MAX = 15  # 最慢阅读速度（字/秒）
BASE_DELAY = 1.5  # 基础延迟时间（秒），除了阅读时间外的额外延迟

# 并发请求限制
MAX_CONCURRENT_REQUESTS = 2  # 最大并发请求数，避免在同一IP下进行大量并发请求

# 输出格式配置
OUTPUT_FORMAT = 'txt'  # txt 或 epub

# 源选择配置
SOURCE_ASK = "ask"  # 每次询问
SOURCE_OFFICIAL = "official"  # 官网
SOURCE_THIRD_PARTY = "third_party"  # 第三方源

# Cookie 配置（用于访问需要登录权限的内容）
COOKIE_FILE = os.path.join(BASE_DIR, 'cookies.txt')

# 并发下载配置
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
DEFAULT_CONCURRENT_DOWNLOADS = 3
MAX_CONCURRENT_DOWNLOADS = 10

def load_config():
    """从配置文件加载配置"""
    config = {
        'concurrent_downloads': DEFAULT_CONCURRENT_DOWNLOADS,
        'source_preference': SOURCE_ASK,  # 源选择偏好
        'remember_source_choice': False  # 是否记住源选择
    }
    if os.path.exists(CONFIG_FILE):
        try:
            import json
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except Exception as e:
            print(f"加载配置失败: {e}")
    return config

def save_config(config):
    """保存配置到文件"""
    try:
        import json
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

def get_concurrent_downloads():
    """获取并发下载数"""
    config = load_config()
    concurrent = config.get('concurrent_downloads', DEFAULT_CONCURRENT_DOWNLOADS)
    return max(1, min(concurrent, MAX_CONCURRENT_DOWNLOADS))

def set_concurrent_downloads(count):
    """设置并发下载数"""
    config = load_config()
    config['concurrent_downloads'] = max(1, min(count, MAX_CONCURRENT_DOWNLOADS))
    return save_config(config)

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

# ===================== 源选择配置 =====================

def get_source_preference():
    """获取源选择偏好"""
    config = load_config()
    return config.get('source_preference', SOURCE_ASK)

def set_source_preference(preference):
    """设置源选择偏好"""
    config = load_config()
    config['source_preference'] = preference
    return save_config(config)

def is_remember_source_choice():
    """是否记住源选择"""
    config = load_config()
    return config.get('remember_source_choice', False)

def set_remember_source_choice(value):
    """设置是否记住源选择"""
    config = load_config()
    config['remember_source_choice'] = value
    return save_config(config)

# ===================== 导出路径记忆 =====================

def get_last_export_path():
    """获取上次导出路径"""
    config = load_config()
    return config.get('last_export_path', '')

def set_last_export_path(path):
    """设置上次导出路径"""
    config = load_config()
    config['last_export_path'] = path
    return save_config(config)

# ===================== 节点统计配置 =====================

def get_node_stats():
    """获取节点成功统计"""
    config = load_config()
    return config.get('node_stats', {})

def save_node_stats(stats):
    """保存节点成功统计"""
    config = load_config()
    config['node_stats'] = stats
    return save_config(config)

def increment_node_success(node_url, endpoint):
    """增加节点成功计数"""
    stats = get_node_stats()

    # 如果节点不存在，初始化
    if node_url not in stats:
        stats[node_url] = {
            'total_success': 0,
            'endpoints': {}
        }

    # 增加总成功计数
    stats[node_url]['total_success'] += 1

    # 增加接口成功计数
    if endpoint not in stats[node_url]['endpoints']:
        stats[node_url]['endpoints'][endpoint] = 0
    stats[node_url]['endpoints'][endpoint] += 1

    # 保存
    return save_node_stats(stats)

def get_best_node_for_endpoint(endpoint, candidate_nodes):
    """
    根据成功统计获取指定接口的最优节点

    Args:
        endpoint: 接口名称（如 'detail', 'book', 'chapter'）
        candidate_nodes: 候选节点列表

    Returns:
        最优节点的 URL，如果没有统计则返回第一个候选节点
    """
    stats = get_node_stats()

    if not stats or not candidate_nodes:
        return candidate_nodes[0] if candidate_nodes else None

    # 找出候选节点中该接口成功次数最多的节点
    best_node = None
    max_success = -1

    for node in candidate_nodes:
        node_stat = stats.get(node, {})
        endpoint_success = node_stat.get('endpoints', {}).get(endpoint, 0)

        if endpoint_success > max_success:
            max_success = endpoint_success
            best_node = node

    # 如果所有节点都没有统计，返回总成功次数最多的节点
    if max_success == 0:
        for node in candidate_nodes:
            node_stat = stats.get(node, {})
            total_success = node_stat.get('total_success', 0)

            if total_success > max_success:
                max_success = total_success
                best_node = node

    # 如果还是没有，返回第一个候选节点
    return best_node if best_node else (candidate_nodes[0] if candidate_nodes else None)

def reset_node_stats():
    """重置节点统计"""
    return save_node_stats({})

# ===================== 动态延迟计算 =====================

def calculate_smart_delay(word_count):
    """
    计算智能延迟时间，基于章节字数模拟用户阅读速度
    
    Args:
        word_count: 章节字数
        
    Returns:
        延迟时间（秒）
    """
    import random
    
    # 获取用户配置的下载速度
    download_speed = get_download_speed()
    
    # 如果没有字数，使用基础延迟
    if not word_count or word_count <= 0:
        base_delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        return base_delay / download_speed
    
    # 根据阅读速度计算阅读时间
    # 随机选择一个阅读速度（5-8 字/秒）
    read_speed = random.uniform(READ_SPEED_MIN, READ_SPEED_MAX)
    read_time = word_count / read_speed
    
    # 添加基础延迟
    total_delay = read_time + BASE_DELAY
    
    # 添加随机波动（±20%）
    random_factor = random.uniform(0.8, 1.2)
    total_delay *= random_factor
    
    # 应用下载速度调整（速度越快，延迟越短）
    total_delay /= download_speed
    
    # 确保延迟在合理范围内（最小 1.5 秒，最大 30 秒）
    total_delay = max(1.5, min(total_delay, 30.0))
    
    return total_delay

# ===================== 用户信息 =====================

def get_user_info():
    """获取用户信息"""
    cookies = load_cookies()
    if not cookies or 'sessionid' not in cookies:
        return None
    
    try:
        import requests
        from fake_useragent import UserAgent
        
        # 构造请求
        ua = UserAgent()
        headers = {
            'User-Agent': ua.random,
            'Cookie': '; '.join([f"{k}={v}" for k, v in cookies.items()])
        }
        
        # 尝试访问用户信息页面
        response = requests.get(
            'https://fanqienovel.com/page/user/center',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            # 简单的用户名提取（从页面中查找用户名）
            import re
            # 尝试匹配页面中的用户名
            patterns = [
                r'"nick_name":"([^"]+)"',
                r'"nickname":"([^"]+)"',
                r'<span[^>]*class="user-name"[^>]*>([^<]+)</span>',
                r'"user_name":"([^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    return {
                        'username': match.group(1),
                        'uid': cookies.get('serial_webid', 'unknown')
                    }
            
            # 如果找不到用户名，返回 UID
            return {
                'username': '用户',
                'uid': cookies.get('serial_webid', 'unknown')
            }
        else:
            # 如果请求失败，返回 UID
            return {
                'username': '用户',
                'uid': cookies.get('serial_webid', 'unknown')
            }
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        # 返回 UID
        return {
            'username': '用户',
            'uid': cookies.get('serial_webid', 'unknown')
        }

# 全局缓存用户信息
USER_INFO = get_user_info()

def refresh_user_info():
    """刷新用户信息"""
    global USER_INFO
    USER_INFO = get_user_info()
    return USER_INFO