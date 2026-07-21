# -*- coding: utf-8 -*-
"""小说源统一接口模块

每个小说源实现 BaseSource 接口，提供：
- get_novel_info(novel_id) -> dict
- get_chapter_list(novel_id) -> list[dict]
- get_chapter_content(novel_id, chapter_id) -> dict
- search_novel(keyword) -> list[dict]
- parse_novel_url(url) -> str | None  （可选）
"""

from .base import BaseSource, SourceError, NovelInfo, ChapterInfo
from .fanqie_source import FanqieSource
from .biquge_source import BiqugeSource
from .sto66_source import Sto66Source
from .generic_source import (
    ConfigurableSource,
    DingdianSource,
    BxwxSource,
    QianbiSource,
    HaitangSource,
)

# 源注册表
SOURCE_REGISTRY = {
    'fanqie': FanqieSource,
    'biquge': BiqugeSource,
    'sto66': Sto66Source,
    'dingdian': DingdianSource,
    'bxwx': BxwxSource,
    'qianbi': QianbiSource,
    'haitang': HaitangSource,
}

# 可搜索的源（用于多源自动搜索，无需登录的源）
SEARCHABLE_SOURCES = ['biquge', 'sto66', 'dingdian', 'bxwx', 'qianbi', 'haitang']


def get_source(name, **kwargs):
    """获取源实例"""
    if name not in SOURCE_REGISTRY:
        raise ValueError(f"未知源: {name}, 可用源: {list(SOURCE_REGISTRY.keys())}")
    return SOURCE_REGISTRY[name](**kwargs)


def list_sources():
    """列出所有可用源"""
    return list(SOURCE_REGISTRY.keys())


__all__ = [
    'BaseSource', 'SourceError', 'NovelInfo', 'ChapterInfo',
    'FanqieSource', 'BiqugeSource', 'Sto66Source',
    'ConfigurableSource', 'DingdianSource', 'BxwxSource', 'QianbiSource', 'HaitangSource',
    'SOURCE_REGISTRY', 'SEARCHABLE_SOURCES', 'get_source', 'list_sources',
]
