# -*- coding: utf-8 -*-
"""
番茄小说源

包装现有 spider.py 的 FanqieSpider，实现 BaseSource 接口。
支持两种模式：
- API 模式（默认，无需登录）：使用第三方 API
- 官网模式（需要登录 + 字体解密）：直接爬取 fanqienovel.com
"""
from __future__ import annotations

import re
from typing import Optional

from .base import BaseSource, NovelInfo, ChapterInfo, SourceError


class FanqieSource(BaseSource):
    """番茄小说源"""

    name = 'fanqie'
    display_name = '番茄小说'
    needs_login = False  # API 模式不需要登录；官网模式由 use_api=False 触发
    supports_search = True  # 两种模式都支持搜索（API 模式内部会切换到官网搜索）

    def __init__(self, use_api: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.use_api = use_api
        # 延迟导入避免循环依赖
        from spider import FanqieSpider
        self._spider = FanqieSpider(use_api=use_api)
        # 官网模式需要登录
        if not use_api:
            self.needs_login = True

    @staticmethod
    def parse_novel_url(url: str) -> Optional[str]:
        """解析番茄小说 URL 或纯 ID"""
        if not url:
            return None
        url = url.strip()
        patterns = [
            r'/page/(\d+)',
            r'book_id=(\d+)',
            r'^(\d+)$',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_novel_info(self, novel_id: str) -> Optional[NovelInfo]:
        try:
            info = self._spider.get_novel_info(novel_id)
            if not info:
                return None

            # 处理 API 返回的授权错误
            if isinstance(info, dict) and info.get('_error'):
                err_type = info.get('_error', 'UNKNOWN')
                err_msg = info.get('_message', '获取小说信息失败')
                if err_type == 'AUTH_FAILED':
                    raise SourceError(err_msg, error_type='AUTH_FAILED', recoverable=False)
                return None

            return NovelInfo(
                novel_id=str(info.get('novel_id', novel_id)),
                title=info.get('title', ''),
                author=info.get('author', ''),
                description=info.get('description', ''),
                cover_url=info.get('cover_url', ''),
                word_count=int(info.get('word_count', 0) or 0),
                chapter_count=int(info.get('chapter_count', 0) or 0),
                source=self.name,
            )
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f"获取番茄小说信息失败: {e}", error_type='NETWORK') from e

    def get_chapter_list(self, novel_id: str) -> list[ChapterInfo]:
        try:
            chapters = self._spider.get_chapter_list(novel_id)
            if not chapters:
                return []
            return [
                ChapterInfo(
                    chapter_id=str(c.get('chapter_id', '')),
                    chapter_title=c.get('chapter_title', f"第{i+1}章"),
                    chapter_index=c.get('chapter_index', i + 1),
                )
                for i, c in enumerate(chapters)
            ]
        except Exception as e:
            raise SourceError(f"获取章节列表失败: {e}", error_type='NETWORK') from e

    def get_chapter_content(self, novel_id: str, chapter_id: str) -> Optional[dict]:
        try:
            data = self._spider.get_chapter_content(novel_id, chapter_id)
            if not data:
                return None
            return {
                'title': data.get('title', ''),
                'content': data.get('content', ''),
            }
        except Exception as e:
            raise SourceError(f"获取章节内容失败: {e}", error_type='NETWORK') from e

    def search_novel(self, keyword: str) -> list[NovelInfo]:
        """搜索小说 - 两种模式都通过官网搜索接口实现"""
        try:
            # API 模式下创建临时官网 spider 进行搜索
            # 番茄搜索接口需要访问 fanqienovel.com/search 页面解析，API 接口不提供搜索
            if self.use_api:
                from spider import FanqieSpider
                search_spider = FanqieSpider(use_api=False)
            else:
                search_spider = self._spider

            results = search_spider.search_novel(keyword)
            return [
                NovelInfo(
                    novel_id=str(r.get('novel_id', '')),
                    title=r.get('title', ''),
                    author=r.get('author', ''),
                    description=r.get('description', ''),
                    cover_url=r.get('cover_url', ''),
                    word_count=int(r.get('word_count', 0) or 0),
                    source=self.name,
                )
                for r in (results or [])
            ]
        except Exception as e:
            raise SourceError(f"搜索失败: {e}", error_type='NETWORK') from e
