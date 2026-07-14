# -*- coding: utf-8 -*-
"""小说源抽象基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class SourceError(Exception):
    """源错误基类"""

    def __init__(self, message: str, error_type: str = 'UNKNOWN', recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.recoverable = recoverable


@dataclass
class NovelInfo:
    """小说信息"""
    novel_id: str
    title: str = ''
    author: str = ''
    description: str = ''
    cover_url: str = ''
    word_count: int = 0
    chapter_count: int = 0
    source: str = ''
    extra: dict = field(default_factory=dict)


@dataclass
class ChapterInfo:
    """章节信息"""
    chapter_id: str
    chapter_title: str
    chapter_index: int


class BaseSource(ABC):
    """小说源抽象基类"""

    # 子类需覆盖以下类属性
    name: str = 'base'              # 源唯一标识（如 'fanqie', 'biquge'）
    display_name: str = '基础源'   # 用户可见名称
    needs_login: bool = False      # 是否需要登录
    supports_search: bool = False  # 是否支持搜索

    def __init__(self, **kwargs):
        # 子类可读取 kwargs 中的 cookies / config
        self.cookies = kwargs.get('cookies', {}) or {}

    # ============== 核心接口 ==============

    @abstractmethod
    def get_novel_info(self, novel_id: str) -> Optional[NovelInfo]:
        """获取小说基本信息"""
        raise NotImplementedError

    @abstractmethod
    def get_chapter_list(self, novel_id: str) -> list[ChapterInfo]:
        """获取章节列表"""
        raise NotImplementedError

    @abstractmethod
    def get_chapter_content(self, novel_id: str, chapter_id: str) -> Optional[dict]:
        """
        获取章节内容

        Returns:
            dict: {'title': str, 'content': str}
            None: 失败
        """
        raise NotImplementedError

    # ============== 可选接口 ==============

    def search_novel(self, keyword: str) -> list[NovelInfo]:
        """搜索小说（默认不支持）"""
        if not self.supports_search:
            return []
        raise NotImplementedError

    @staticmethod
    def parse_novel_url(url: str) -> Optional[str]:
        """解析 URL 提取小说 ID（默认返回原值）"""
        return url.strip() if url and url.strip() else None

    # ============== 通用辅助 ==============

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} needs_login={self.needs_login}>"
