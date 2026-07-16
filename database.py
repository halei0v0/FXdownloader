# 数据库管理模块
import sqlite3
import os
import json
import threading
from config import DATABASE_PATH


class NovelDatabase:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self._lock = threading.Lock()
        self.init_database()
        # 启用 WAL 模式，提升并发读写性能（多线程下载时避免 database is locked）
        with self.get_connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')

    def get_connection(self):
        """获取数据库连接（支持多线程）"""
        # check_same_thread=False 允许在不同线程中使用连接
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 小说表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS novels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    description TEXT,
                    cover_url TEXT,
                    word_count INTEGER DEFAULT 0,
                    chapter_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT '未下载',
                    source TEXT DEFAULT 'official',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 为旧数据库添加 source 字段（如果不存在）
            cursor.execute('PRAGMA table_info(novels)')
            columns = [col[1] for col in cursor.fetchall()]
            if 'source' not in columns:
                cursor.execute('ALTER TABLE novels ADD COLUMN source TEXT DEFAULT "official"')
                conn.commit()
            
            # 章节表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    chapter_id TEXT UNIQUE NOT NULL,
                    chapter_title TEXT NOT NULL,
                    original_title TEXT,
                    chapter_index INTEGER NOT NULL,
                    content TEXT,
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT '未下载',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
                )
            ''')

            # 为旧数据库添加 original_title 字段（如果不存在）
            cursor.execute('PRAGMA table_info(chapters)')
            columns = [col[1] for col in cursor.fetchall()]
            if 'original_title' not in columns:
                cursor.execute('ALTER TABLE chapters ADD COLUMN original_title TEXT')
                conn.commit()
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_id ON chapters(novel_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapter_id ON chapters(chapter_id)')

            # 下载历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    source TEXT,
                    source_key TEXT,
                    chapter_total INTEGER DEFAULT 0,
                    chapter_success INTEGER DEFAULT 0,
                    save_path TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 收藏表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    cover_url TEXT,
                    description TEXT,
                    source TEXT,
                    source_key TEXT,
                    extra_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(novel_id, source)
                )
            ''')

            # 阅读进度表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reading_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT UNIQUE NOT NULL,
                    title TEXT,
                    last_chapter_id TEXT,
                    last_chapter_title TEXT,
                    chapter_index INTEGER DEFAULT 0,
                    scroll_position INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 下载任务表（暂停/续传）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    novel_id TEXT NOT NULL,
                    title TEXT,
                    source_key TEXT,
                    save_dir TEXT,
                    output_file TEXT,
                    chapter_ids_json TEXT,
                    completed_ids_json TEXT DEFAULT '[]',
                    failed_ids_json TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'running',
                    total INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 小说封面缓存表（novel_id + source 联合主键）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS novel_covers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    cover_url TEXT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(novel_id, source)
                )
            ''')

            # 排行榜缓存表（按天缓存，sudugu.org 数据）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rankings_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rank INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    cover_url TEXT,
                    category TEXT,
                    status TEXT,
                    source_url TEXT,
                    cached_date DATE NOT NULL,
                    UNIQUE(rank, title, cached_date)
                )
            ''')

            # 分类小说缓存表（按天缓存，sudugu.org 各分类页数据）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS category_novels_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    cover_url TEXT,
                    category TEXT,
                    status TEXT,
                    source_url TEXT,
                    cached_date DATE NOT NULL,
                    UNIQUE(category_key, title, cached_date)
                )
            ''')

            conn.commit()

    def save_novel(self, novel_id, title, author, description, cover_url, word_count=0, chapter_count=0, source='official'):
        """保存小说信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO novels 
                (novel_id, title, author, description, cover_url, word_count, chapter_count, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (novel_id, title, author, description, cover_url, word_count, chapter_count, source))
            conn.commit()

    def save_chapter(self, novel_id, chapter_id, chapter_title, chapter_index, content, word_count=0, original_title=None):
        """保存章节内容"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chapters 
                (novel_id, chapter_id, chapter_title, original_title, chapter_index, content, word_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, '已下载')
            ''', (novel_id, chapter_id, chapter_title, original_title, chapter_index, content, word_count))
            conn.commit()
            
            # 更新小说状态
            cursor.execute('''
                UPDATE novels SET status = '下载中', updated_at = CURRENT_TIMESTAMP
                WHERE novel_id = ?
            ''', (novel_id,))
            conn.commit()

    def update_novel_status(self, novel_id, status):
        """更新小说状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE novels SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE novel_id = ?
            ''', (status, novel_id))
            conn.commit()

    def get_novel(self, novel_id):
        """获取小说信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM novels WHERE novel_id = ?', (novel_id,))
            return cursor.fetchone()

    def get_all_novels(self):
        """获取所有小说"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM novels ORDER BY created_at DESC')
            return cursor.fetchall()

    def get_chapters(self, novel_id):
        """获取小说所有章节"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chapters 
                WHERE novel_id = ? 
                ORDER BY chapter_index ASC
            ''', (novel_id,))
            return cursor.fetchall()

    def get_chapters_range(self, novel_id, start_index, end_index):
        """获取指定范围的章节"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chapters 
                WHERE novel_id = ? AND chapter_index >= ? AND chapter_index <= ?
                ORDER BY chapter_index ASC
            ''', (novel_id, start_index, end_index))
            return cursor.fetchall()

    def delete_novel(self, novel_id):
        """删除小说及其章节"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM chapters WHERE novel_id = ?', (novel_id,))
            cursor.execute('DELETE FROM novels WHERE novel_id = ?', (novel_id,))
            conn.commit()

    def delete_chapters(self, novel_id):
        """只删除小说的所有章节，保留小说信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM chapters WHERE novel_id = ?', (novel_id,))
            conn.commit()

    # ============== 下载历史 ==============

    def add_history(self, novel_id, title, author, source, source_key,
                    chapter_total, chapter_success, save_path, status='completed'):
        """添加下载历史记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO download_history
                (novel_id, title, author, source, source_key, chapter_total,
                 chapter_success, save_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (novel_id, title, author, source, source_key,
                  chapter_total, chapter_success, save_path, status))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, limit=100):
        """获取下载历史记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM download_history
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()

    def delete_history(self, history_id):
        """删除单条历史记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM download_history WHERE id = ?', (history_id,))
            conn.commit()

    def clear_history(self):
        """清空所有历史记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM download_history')
            conn.commit()

    # ============== 收藏 ==============

    def add_favorite(self, novel_id, title, author, cover_url, description,
                     source, source_key, extra_json=None):
        """添加收藏"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO favorites
                (novel_id, title, author, cover_url, description, source,
                 source_key, extra_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (novel_id, title, author, cover_url, description,
                  source, source_key, extra_json))
            conn.commit()
            return cursor.lastrowid

    def remove_favorite(self, novel_id, source):
        """取消收藏"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM favorites WHERE novel_id = ? AND source = ?
            ''', (novel_id, source))
            conn.commit()
            return cursor.rowcount > 0

    def get_favorites(self):
        """获取所有收藏"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM favorites ORDER BY created_at DESC')
            return cursor.fetchall()

    def is_favorited(self, novel_id, source):
        """检查是否已收藏"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM favorites WHERE novel_id = ? AND source = ?
            ''', (novel_id, source))
            return cursor.fetchone() is not None

    # ============== 阅读进度 ==============

    def save_reading_progress(self, novel_id, title, last_chapter_id,
                              last_chapter_title, chapter_index, scroll_position=0):
        """保存阅读进度"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO reading_progress
                (novel_id, title, last_chapter_id, last_chapter_title,
                 chapter_index, scroll_position, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (novel_id, title, last_chapter_id, last_chapter_title,
                  chapter_index, scroll_position))
            conn.commit()

    def get_reading_progress(self, novel_id):
        """获取阅读进度"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM reading_progress WHERE novel_id = ?
            ''', (novel_id,))
            return cursor.fetchone()

    def get_all_reading_progress(self):
        """获取所有阅读进度（用于书架）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM reading_progress ORDER BY updated_at DESC
            ''')
            return cursor.fetchall()

    # ============== 下载任务（暂停/续传） ==============

    def create_task(self, task_id, novel_id, title, source_key, save_dir,
                    output_file, chapter_ids, total):
        """创建下载任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO download_tasks
                (task_id, novel_id, title, source_key, save_dir, output_file,
                 chapter_ids_json, completed_ids_json, failed_ids_json,
                 status, total, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '[]', 'running', ?,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (task_id, novel_id, title, source_key, save_dir, output_file,
                  json.dumps(chapter_ids), total))
            conn.commit()

    def update_task_progress(self, task_id, completed_ids, failed_ids, status='running'):
        """更新任务进度"""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE download_tasks
                    SET completed_ids_json = ?, failed_ids_json = ?,
                        status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                ''', (json.dumps(completed_ids), json.dumps(failed_ids),
                      status, task_id))
                conn.commit()

    def set_task_status(self, task_id, status):
        """设置任务状态"""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE download_tasks SET status = ?,
                        updated_at = CURRENT_TIMESTAMP WHERE task_id = ?
                ''', (status, task_id))
                conn.commit()

    def get_task(self, task_id):
        """获取任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM download_tasks WHERE task_id = ?',
                           (task_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d['chapter_ids'] = json.loads(d.get('chapter_ids_json', '[]'))
                d['completed_ids'] = json.loads(d.get('completed_ids_json', '[]'))
                d['failed_ids'] = json.loads(d.get('failed_ids_json', '[]'))
                return d
            return None

    def get_paused_tasks(self):
        """获取所有暂停的任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM download_tasks
                WHERE status = 'paused'
                ORDER BY updated_at DESC
            ''')
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d['chapter_ids'] = json.loads(d.get('chapter_ids_json', '[]'))
                d['completed_ids'] = json.loads(d.get('completed_ids_json', '[]'))
                d['failed_ids'] = json.loads(d.get('failed_ids_json', '[]'))
                result.append(d)
            return result

    def delete_task(self, task_id):
        """删除任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM download_tasks WHERE task_id = ?',
                           (task_id,))
            conn.commit()

    # ============== 封面缓存 ==============

    def get_cover(self, novel_id, source):
        """获取缓存的封面 URL，未缓存返回 None"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cover_url FROM novel_covers
                WHERE novel_id = ? AND source = ?
            ''', (str(novel_id), source))
            row = cursor.fetchone()
            return row['cover_url'] if row else None

    def set_cover(self, novel_id, source, cover_url, title=None):
        """缓存封面 URL（已存在则更新）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO novel_covers
                (novel_id, source, cover_url, title, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (str(novel_id), source, cover_url, title))
            conn.commit()

    def get_covers_batch(self, novel_ids, source):
        """批量获取缓存的封面 URL

        Returns:
            dict: {novel_id: cover_url}（仅包含已缓存的）
        """
        if not novel_ids:
            return {}
        placeholders = ','.join('?' * len(novel_ids))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT novel_id, cover_url FROM novel_covers
                WHERE source = ? AND novel_id IN ({placeholders})
            ''', [source] + [str(nid) for nid in novel_ids])
            return {row['novel_id']: row['cover_url'] for row in cursor.fetchall() if row['cover_url']}

    # ============== 排行榜缓存 ==============

    def get_rankings_cache(self, category='all'):
        """获取今日缓存的排行榜数据

        Returns:
            list[dict] 或 None（无缓存）：[{rank, title, author, cover_url, category, status, source_url}]
        """
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if category == 'all':
                cursor.execute('''
                    SELECT rank, title, author, cover_url, category, status, source_url
                    FROM rankings_cache
                    WHERE cached_date = ?
                    ORDER BY rank ASC
                ''', (today,))
            else:
                cursor.execute('''
                    SELECT rank, title, author, cover_url, category, status, source_url
                    FROM rankings_cache
                    WHERE cached_date = ? AND category = ?
                    ORDER BY rank ASC
                ''', (today, category))
            rows = cursor.fetchall()
            if not rows:
                return None
            return [dict(row) for row in rows]

    def save_rankings_cache(self, novels):
        """批量保存排行榜数据到缓存（先清除今日旧缓存再写入）

        Args:
            novels: [{rank, title, author, cover_url, category, status, source_url}]
        """
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 清除今日缓存
            cursor.execute('DELETE FROM rankings_cache WHERE cached_date = ?', (today,))
            # 批量插入
            for n in novels:
                cursor.execute('''
                    INSERT OR REPLACE INTO rankings_cache
                    (rank, title, author, cover_url, category, status, source_url, cached_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    n.get('rank', 0),
                    n.get('title', ''),
                    n.get('author', ''),
                    n.get('cover_url', ''),
                    n.get('category', ''),
                    n.get('status', ''),
                    n.get('source_url', ''),
                    today,
                ))
            conn.commit()

    def has_rankings_cache_today(self):
        """检查今日是否已有排行榜缓存"""
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as cnt FROM rankings_cache WHERE cached_date = ?', (today,))
            return cursor.fetchone()['cnt'] > 0

    # ============== 分类小说缓存 ==============

    def get_category_novels_cache(self, category_key: str):
        """获取今日缓存的分类小说数据

        Returns:
            list[dict] 或 None（无缓存）：[{title, author, cover_url, category, status, source_url}]
        """
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, author, cover_url, category, status, source_url
                FROM category_novels_cache
                WHERE cached_date = ? AND category_key = ?
                ORDER BY id ASC
            ''', (today, category_key))
            rows = cursor.fetchall()
            if not rows:
                return None
            return [dict(row) for row in rows]

    def save_category_novels_cache(self, category_key: str, novels: list):
        """批量保存分类小说数据到缓存（先清除今日该分类缓存再写入）

        Args:
            category_key: 分类 key（如 'xuanhuan'）
            novels: [{title, author, cover_url, category, status, source_url}]
        """
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM category_novels_cache WHERE cached_date = ? AND category_key = ?',
                (today, category_key)
            )
            for n in novels:
                cursor.execute('''
                    INSERT OR REPLACE INTO category_novels_cache
                    (category_key, title, author, cover_url, category, status, source_url, cached_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    category_key,
                    n.get('title', ''),
                    n.get('author', ''),
                    n.get('cover_url', ''),
                    n.get('category', ''),
                    n.get('status', ''),
                    n.get('source_url', ''),
                    today,
                ))
            conn.commit()

    def has_category_novels_cache_today(self, category_key: str) -> bool:
        """检查今日是否已有该分类的小说缓存"""
        import datetime
        today = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) as cnt FROM category_novels_cache WHERE cached_date = ? AND category_key = ?',
                (today, category_key)
            )
            return cursor.fetchone()['cnt'] > 0