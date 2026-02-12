# 数据库管理模块
import sqlite3
import os
from config import DATABASE_PATH


class NovelDatabase:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 章节表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    chapter_id TEXT UNIQUE NOT NULL,
                    chapter_title TEXT NOT NULL,
                    chapter_index INTEGER NOT NULL,
                    content TEXT,
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT '未下载',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_id ON chapters(novel_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapter_id ON chapters(chapter_id)')
            
            conn.commit()

    def save_novel(self, novel_id, title, author, description, cover_url, word_count=0, chapter_count=0):
        """保存小说信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO novels 
                (novel_id, title, author, description, cover_url, word_count, chapter_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (novel_id, title, author, description, cover_url, word_count, chapter_count))
            conn.commit()

    def save_chapter(self, novel_id, chapter_id, chapter_title, chapter_index, content, word_count=0):
        """保存章节内容"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chapters 
                (novel_id, chapter_id, chapter_title, chapter_index, content, word_count, status)
                VALUES (?, ?, ?, ?, ?, ?, '已下载')
            ''', (novel_id, chapter_id, chapter_title, chapter_index, content, word_count))
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