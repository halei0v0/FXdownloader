# -*- coding: utf-8 -*-
"""多源管理器

实现：
1. 多源自动搜索：并发调用 Bing 搜索 + 各源自身搜索，聚合去重给出多源可用结果
2. 多源分工加速下载：按章节把任务分配给多个源/线程并发下载
3. 失败自动重试：主源下载失败时，自动尝试其他源

搜索时无需手动切换源，直接给出所有源的可用结果。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from . import get_source, SOURCE_REGISTRY, SEARCHABLE_SOURCES, NovelInfo
from .bing_search import search_via_bing
from .base import SourceError


# 源显示名映射
SOURCE_DISPLAY_NAMES = {
    'biquge': '蚂蚁文学',
    'dingdian': '顶点小说',
    'bxwx': '笔下文学',
    'qianbi': '铅笔小说',
    'haitang': '海棠文学',
    'fanqie': '番茄小说',
}


def search_all_sources(keyword: str, include_fanqie: bool = True) -> List[dict]:
    """多源并发搜索，聚合所有源的可用结果

    搜索策略：
    1. 各源自身搜索接口（主要方式）—— 蚂蚁文学、铅笔小说、海棠文学等
    2. Bing 搜索（补充）—— 在中国网络环境下常被重定向到 cn.bing.com，结果不可靠

    不需要手动切换源，直接返回所有源中能找到的结果。

    Args:
        keyword: 搜索关键词或URL
        include_fanqie: 是否包含番茄源

    Returns:
        [{novel_id, title, author, source, source_name, ...}, ...]
    """
    results = {}  # key=(source, novel_id) 去重

    # 1. 各源自身搜索（并发，主要搜索方式）
    search_sources = list(SEARCHABLE_SOURCES)
    if include_fanqie:
        search_sources.append('fanqie')

    def _source_search(source_key):
        try:
            source = get_source(source_key)
            if not getattr(source, 'supports_search', False):
                return []
            return source.search_novel(keyword)
        except Exception as e:
            print(f'[多源搜索] {source_key} 搜索失败: {e}')
            return []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_source = {
            executor.submit(_source_search, sk): sk
            for sk in search_sources
        }
        for future in as_completed(future_to_source):
            sk = future_to_source[future]
            try:
                novels = future.result()
                for n in novels:
                    key = (sk, str(n.novel_id))
                    if key not in results:
                        results[key] = {
                            'novel_id': str(n.novel_id),
                            'title': n.title or '',
                            'author': n.author or '',
                            'description': n.description or '',
                            'cover_url': n.cover_url or '',
                            'word_count': n.word_count or 0,
                            'chapter_count': n.chapter_count or 0,
                            'source': sk,
                            'source_key': sk,
                            'source_name': SOURCE_DISPLAY_NAMES.get(sk, sk),
                            'extra': n.extra or {},
                        }
            except Exception:
                pass

    # 2. Bing 搜索作为补充（如果各源搜索结果不足）
    if len(results) < 3:
        try:
            bing_results = search_via_bing(keyword)
            for r in bing_results:
                src = r.get('source', '')
                nid = str(r.get('novel_id', ''))
                if not src or not nid:
                    continue
                key = (src, nid)
                if key not in results:
                    results[key] = {
                        'novel_id': nid,
                        'title': r.get('title', ''),
                        'author': '',
                        'description': '',
                        'cover_url': '',
                        'word_count': 0,
                        'chapter_count': 0,
                        'source': src,
                        'source_key': src,
                        'source_name': SOURCE_DISPLAY_NAMES.get(src, src),
                        'extra': {'_search_url': r.get('url', '')},
                    }
        except Exception as e:
            print(f'[多源搜索] Bing 补充搜索失败: {e}')

    return list(results.values())


def find_novel_in_all_sources(title: str, author: str = '', exclude_source: str = '') -> Dict[str, str]:
    """在各源搜索同一本书（用于多源分工下载）

    按书名+作者匹配，返回 {source_key: novel_id}

    Args:
        title: 书名
        author: 作者
        exclude_source: 排除的源（主源）

    Returns:
        {source_key: novel_id} 匹配到的各源 novel_id
    """
    matches = {}
    if not title:
        return matches

    search_sources = [s for s in SEARCHABLE_SOURCES if s != exclude_source]

    def _match_in_source(source_key):
        try:
            source = get_source(source_key)
            results = source.search_novel(title)
            for n in results:
                # 标题包含匹配 + 作者匹配（如果有）
                if title.lower() in (n.title or '').lower() or (n.title or '').lower() in title.lower():
                    if author and n.author and author not in n.author and n.author not in author:
                        continue
                    return (source_key, str(n.novel_id))
            return None
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_match_in_source, sk) for sk in search_sources]
        for future in as_completed(futures):
            result = future.result()
            if result:
                matches[result[0]] = result[1]

    return matches


def get_all_rankings(category: str = 'all', page: int = 1) -> List[dict]:
    """获取排行榜数据（来源：速读谷 sudugu.org，按天缓存）

    排行榜数据统一从速读谷获取，每日只请求一次后缓存到本地。
    排行榜中的小说封面和书名已缓存，点击后用书名在各源搜索。

    Returns:
        [{novel_id, title, author, source, source_name, cover_url, category, status, ...}]
    """
    try:
        from sources.sudugu_rankings import get_sudugu_rankings
        ranker = get_sudugu_rankings()
        novels = ranker.get_rankings(category, use_cache=True)
        if not novels:
            return []

        # 转换为统一格式
        results = []
        for n in novels:
            results.append({
                'novel_id': n.get('title', ''),  # 用书名作为标识（点击后搜索书名）
                'title': n.get('title', ''),
                'author': n.get('author', ''),
                'description': '',
                'cover_url': n.get('cover_url', ''),
                'word_count': 0,
                'chapter_count': 0,
                'source': 'sudugu',
                'source_name': n.get('source_name', '速读谷排行'),
                'source_key': 'sudugu',
                'category': n.get('category', ''),
                'status': n.get('status', ''),
                'rank': n.get('rank', 0),
                'extra': {},
            })
        return results
    except Exception as e:
        print(f'[多源排行] 获取速读谷排行榜失败: {e}')
        return []


def get_all_categories() -> List[dict]:
    """获取分类列表（来源：速读谷 sudugu.org 静态分类）

    Returns:
        [{'source': 'sudugu', 'source_name': '速读谷', 'categories': [{key, name}, ...]}]
    """
    try:
        from sources.sudugu_rankings import SUDUGU_CATEGORIES
        return [{
            'source': 'sudugu',
            'source_name': '速读谷',
            'categories': SUDUGU_CATEGORIES,
        }]
    except Exception as e:
        print(f'[多源分类] 获取分类列表失败: {e}')
        return []


def get_category_novels(category_key: str, page: int = 1) -> List[dict]:
    """获取分类下的小说列表（来源：速读谷 sudugu.org，按天缓存）

    点击分类后调用，返回该分类最新小说（带封面，已按天缓存）。
    点击具体小说后用书名在各源搜索。

    Args:
        category_key: 分类 key（如 'xuanhuan'）
        page: 页码（暂只支持第 1 页）

    Returns:
        [{novel_id, title, author, source, source_name, cover_url, category, status, ...}]
    """
    try:
        from sources.sudugu_rankings import get_sudugu_categories
        cats = get_sudugu_categories()
        novels = cats.get_category_novels(category_key, use_cache=True)
        if not novels:
            return []

        results = []
        for n in novels:
            results.append({
                'novel_id': n.get('title', ''),  # 用书名作为标识（点击后搜索书名）
                'title': n.get('title', ''),
                'author': n.get('author', ''),
                'description': '',
                'cover_url': n.get('cover_url', ''),
                'word_count': 0,
                'chapter_count': 0,
                'source': 'sudugu',
                'source_name': n.get('source_name', '速读谷分类'),
                'source_key': 'sudugu',
                'category': n.get('category', ''),
                'status': n.get('status', ''),
                'extra': {},
            })
        return results
    except Exception as e:
        print(f'[多源分类] 获取分类 {category_key} 小说失败: {e}')
        return []
