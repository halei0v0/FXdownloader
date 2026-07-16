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

    def get_rankings(self, category: str = 'all', page: int = 1) -> list[NovelInfo]:
        """获取排行榜/分类推荐小说（默认不支持，子类可覆盖）

        Args:
            category: 分类名（'all'-总榜, 'hot'-人气, 'new'-新作, 'finish'-完结）
            page: 页码（从 1 开始）

        Returns:
            list[NovelInfo]
        """
        return []

    def get_categories(self) -> list[dict]:
        """获取支持的分类列表（子类可覆盖）

        Returns:
            list[dict]: [{'key': str, 'name': str}, ...]
        """
        return []

    @staticmethod
    def parse_novel_url(url: str) -> Optional[str]:
        """解析 URL 提取小说 ID（默认返回原值）"""
        return url.strip() if url and url.strip() else None

    # ============== 通用辅助 ==============

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} needs_login={self.needs_login}>"
