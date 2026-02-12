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