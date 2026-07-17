# -*- coding: utf-8 -*-
"""速读谷 (sudugu.org) 排行榜抓取模块

数据来源：https://www.sudugu.org/paihang/
反爬策略：按天缓存到本地数据库，每日只请求一次

HTML 结构：
<div class="item">
  <a href="/21/"><img alt="书名" src="封面URL" /></a>
  <div class="itemtxt">
    <h3><b class="rank1">01</b><a href="/21/">书名</a></h3>
    <p><span>连载中</span><span>玄幻小说</span></p>
    <p><a href="/21/">作者：XXX</a></p>
    ...
  </div>
</div>
"""
from __future__ import annotations

import re
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import NovelDatabase


class SuduguRankings:
    """速读谷排行榜抓取器（带按天缓存）

    支持多页抓取：sudugu.org 排行榜按 /paihang/{N}.html 分页，每页 10 本。
    默认抓取前 3 页（共 30 本）。
    """

    RANKING_URL = 'https://www.sudugu.org/paihang/'
    MAX_PAGES = 3  # 抓取页数（每页 10 本）

    def __init__(self):
        self._db = NovelDatabase()

    def _fetch_html(self, page: int = 1) -> str:
        """从 sudugu.org 抓取指定页的排行榜 HTML

        Args:
            page: 页码（1=第一页，2=/paihang/2.html，依此类推）
        """
        from scrapling.fetchers import Fetcher
        if page <= 1:
            url = self.RANKING_URL
        else:
            url = f'{self.RANKING_URL}{page}.html'
        resp = Fetcher.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bing.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
            timeout=20000,
        )
        return resp.text or resp.body.decode('utf-8', errors='replace')

    def _parse_rankings(self, html: str, rank_offset: int = 0) -> list[dict]:
        """解析排行榜 HTML，返回小说列表

        Args:
            html: 单页 HTML
            rank_offset: 排名偏移量（第 N 页的 rank 需加上 (N-1)*10）

        Returns:
            [{rank, title, author, cover_url, category, status, source_url}]
        """
        results = []
        # 匹配每个 .item 区块
        # 结构：<div class="item"><a href="..."><img alt="书名" src="封面" /></a>...<h3><b class="rank1">01</b><a href="...">书名</a></h3>...
        item_pattern = re.compile(
            r'<div class="item">\s*'
            r'<a href="([^"]*)"[^>]*>\s*<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"[^>]*/?\s*>\s*</a>\s*'
            r'<div class="itemtxt">\s*'
            r'<h3><b[^>]*>(\d+)</b><a[^>]*>[^<]*</a></h3>\s*'  # rank + title in h3
            r'<p><span>([^<]*)</span><span>([^<]*)</span></p>\s*'  # status + category
            r'<p><a[^>]*>作者[：:]\s*([^<]*)</a></p>',  # author
            re.DOTALL
        )

        for m in item_pattern.finditer(html):
            source_url = m.group(1)
            img_alt = m.group(2)
            cover_url = m.group(3)
            rank_in_page = int(m.group(4))
            status = m.group(5).strip()
            category = m.group(6).strip()
            author = m.group(7).strip()

            # 全局 rank = 页内 rank + 偏移量（避免多页 rank 冲突）
            global_rank = rank_in_page + rank_offset

            results.append({
                'rank': global_rank,
                'title': img_alt,
                'author': author,
                'cover_url': cover_url,
                'category': category,
                'status': status,
                'source_url': source_url,
            })

        # 如果精确匹配失败，尝试宽松匹配
        if not results:
            results = self._parse_rankings_loose(html, rank_offset)

        return results

    def _parse_rankings_loose(self, html: str, rank_offset: int = 0) -> list[dict]:
        """宽松匹配模式（备用）"""
        results = []
        # 匹配 <img alt="书名" src="封面URL" />
        img_pattern = re.compile(
            r'<img[^>]*alt="([^"]+)"[^>]*src="(http[^"]+)"',
            re.DOTALL
        )
        # 匹配排名 <b class="rank1">01</b> 或 <b>01</b>
        rank_pattern = re.compile(r'<b[^>]*>(\d+)</b>')
        # 匹配 <span>状态</span><span>分类</span>
        span_pattern = re.compile(r'<span>([^<]+)</span><span>([^<]+)</span>')
        # 匹配 作者：XXX
        author_pattern = re.compile(r'作者[：:]\s*([^<\s]+)')

        # 按 .item 分割
        items = re.split(r'<div class="item">', html)
        for item in items[1:]:  # 跳过第一段（item 之前的内容）
            # 截取到 </div> 结束
            item = item.split('</div>', 1)[0]

            img_m = img_pattern.search(item)
            rank_m = rank_pattern.search(item)
            span_m = span_pattern.search(item)
            author_m = author_pattern.search(item)

            if img_m and rank_m:
                rank_in_page = int(rank_m.group(1))
                results.append({
                    'rank': rank_in_page + rank_offset,
                    'title': img_m.group(1),
                    'author': author_m.group(1) if author_m else '',
                    'cover_url': img_m.group(2),
                    'category': span_m.group(2) if span_m else '',
                    'status': span_m.group(1) if span_m else '',
                    'source_url': '',
                })

        results.sort(key=lambda x: x['rank'])
        return results

    def get_rankings(self, category: str = 'all', use_cache: bool = True) -> list[dict]:
        """获取排行榜数据（带按天缓存，多页合并）

        Args:
            category: 分类（暂未使用，sudugu 排行榜不区分分类）
            use_cache: 是否使用缓存（True=优先缓存，每日只请求一次）

        Returns:
            [{rank, title, author, cover_url, category, status, source_url,
              source_name, source_key, novel_id}]
            novel_id 设为 title（因为点击后用书名搜索，不解析 sudugu URL）
        """
        # 1. 优先从缓存读取
        if use_cache:
            cached = self._db.get_rankings_cache(category)
            if cached:
                # 补充前端需要的字段
                for item in cached:
                    item['source_name'] = '速读谷排行'
                    item['source_key'] = 'sudugu'
                    item['novel_id'] = item.get('title', '')
                return cached

        # 2. 缓存不存在，从网络获取（多页合并）
        try:
            all_novels = []
            for page in range(1, self.MAX_PAGES + 1):
                try:
                    html = self._fetch_html(page)
                    # 第 N 页的 rank 偏移 = (N-1) * 10
                    rank_offset = (page - 1) * 10
                    novels = self._parse_rankings(html, rank_offset)
                    if not novels:
                        # 该页无数据，停止翻页
                        break
                    all_novels.extend(novels)
                except Exception as e:
                    print(f'[SuduguRankings] 第 {page} 页抓取失败: {e}')
                    break

            if not all_novels:
                return []

            # 3. 保存到缓存
            self._db.save_rankings_cache(all_novels)

            # 4. 返回（补充前端字段）
            for item in all_novels:
                item['source_name'] = '速读谷排行'
                item['source_key'] = 'sudugu'
                item['novel_id'] = item.get('title', '')

            return all_novels
        except Exception as e:
            print(f'[SuduguRankings] 获取排行榜失败: {e}')
            return []


# 模块级单例
_rankings = None


def get_sudugu_rankings() -> SuduguRankings:
    """获取 SuduguRankings 单例"""
    global _rankings
    if _rankings is None:
        _rankings = SuduguRankings()
    return _rankings


# ============================================================
# 速读谷分类小说 (sudugu.org/{category}/)
# ============================================================

# 静态分类列表（从 sudugu.org 导航菜单）
SUDUGU_CATEGORIES = [
    {'key': 'xuanhuan', 'name': '玄幻小说'},
    {'key': 'xianxia', 'name': '仙侠小说'},
    {'key': 'dushi', 'name': '都市小说'},
    {'key': 'lishi', 'name': '历史小说'},
    {'key': 'junshi', 'name': '军事小说'},
    {'key': 'kehuan', 'name': '科幻小说'},
    {'key': 'yanqing', 'name': '言情小说'},
]


class SuduguCategories:
    """速读谷分类小说抓取器（带按天缓存）

    数据来源：https://www.sudugu.org/{category_key}/
    每个分类页主体为 .item 区块（10 本最新小说，结构同排行榜但无 rank）。
    反爬策略：按天缓存到本地数据库，每日每个分类只请求一次。
    """

    BASE_URL = 'https://www.sudugu.org'

    def __init__(self):
        self._db = NovelDatabase()

    def _fetch_html(self, category_key: str) -> str:
        """从 sudugu.org 抓取分类页 HTML"""
        from scrapling.fetchers import Fetcher
        url = f'{self.BASE_URL}/{category_key}/'
        resp = Fetcher.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bing.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
            timeout=20000,
        )
        return resp.text or resp.body.decode('utf-8', errors='replace')

    def _parse_category_novels(self, html: str) -> list[dict]:
        """解析分类页 HTML，返回小说列表

        分类页 .item 结构（无 rank，与排行榜 .item 相同但 h3 内无 <b>排名</b>）：
        <div class="item"><a href="/6471/"><img alt="书名" src="封面" /></a>
          <div class="itemtxt"><h3><a href="/6471/">书名</a></h3>
          <p><span>连载中</span><span>玄幻小说</span></p>
          <p><a href="/6471/">作者：XXX</a></p>...</div></div>

        Returns:
            [{title, author, cover_url, category, status, source_url}]
        """
        results = []
        # 匹配每个 .item 区块（分类页结构，h3 内无 <b>排名</b>）
        item_pattern = re.compile(
            r'<div class="item">\s*'
            r'<a href="([^"]*)"[^>]*>\s*<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"[^>]*/?\s*>\s*</a>\s*'
            r'<div class="itemtxt">\s*'
            r'<h3><a[^>]*>[^<]*</a></h3>\s*'  # 标题在 h3>a
            r'<p><span>([^<]*)</span><span>([^<]*)</span></p>\s*'  # status + category
            r'<p><a[^>]*>作者[：:]\s*([^<]*)</a></p>',  # author
            re.DOTALL
        )

        for m in item_pattern.finditer(html):
            source_url = m.group(1)
            title = m.group(2)
            cover_url = m.group(3)
            status = m.group(4).strip()
            category = m.group(5).strip()
            author = m.group(6).strip()

            results.append({
                'title': title,
                'author': author,
                'cover_url': cover_url,
                'category': category,
                'status': status,
                'source_url': source_url,
            })

        # 宽松匹配备用
        if not results:
            results = self._parse_category_loose(html)
        return results

    def _parse_category_loose(self, html: str) -> list[dict]:
        """宽松匹配（备用）"""
        results = []
        img_pattern = re.compile(
            r'<img[^>]*alt="([^"]+)"[^>]*src="(http[^"]+)"',
            re.DOTALL
        )
        span_pattern = re.compile(r'<span>([^<]+)</span><span>([^<]+)</span>')
        author_pattern = re.compile(r'作者[：:]\s*([^<\s]+)')
        link_pattern = re.compile(r'<a href="(/?\d+/)"')

        items = re.split(r'<div class="item">', html)
        for item in items[1:]:
            item = item.split('</div>', 1)[0]
            img_m = img_pattern.search(item)
            span_m = span_pattern.search(item)
            author_m = author_pattern.search(item)
            link_m = link_pattern.search(item)

            if img_m:
                results.append({
                    'title': img_m.group(1),
                    'author': author_m.group(1) if author_m else '',
                    'cover_url': img_m.group(2),
                    'category': span_m.group(2) if span_m else '',
                    'status': span_m.group(1) if span_m else '',
                    'source_url': link_m.group(1) if link_m else '',
                })
        return results

    def get_category_novels(self, category_key: str, use_cache: bool = True) -> list[dict]:
        """获取分类小说数据（带按天缓存）

        Args:
            category_key: 分类 key（如 'xuanhuan'）
            use_cache: 是否使用缓存（True=优先缓存，每日只请求一次）

        Returns:
            [{title, author, cover_url, category, status, source_url,
              source_name, source_key, novel_id}]
            novel_id 设为 title（点击后用书名搜索）
        """
        # 1. 优先从缓存读取
        if use_cache:
            cached = self._db.get_category_novels_cache(category_key)
            if cached:
                for item in cached:
                    item['source_name'] = '速读谷分类'
                    item['source_key'] = 'sudugu'
                    item['source'] = 'sudugu'
                    item['novel_id'] = item.get('title', '')
                return cached

        # 2. 缓存不存在，从网络获取
        try:
            html = self._fetch_html(category_key)
            novels = self._parse_category_novels(html)
            if not novels:
                return []

            # 3. 保存到缓存
            self._db.save_category_novels_cache(category_key, novels)

            # 4. 返回（补充前端字段）
            for item in novels:
                item['source_name'] = '速读谷分类'
                item['source_key'] = 'sudugu'
                item['source'] = 'sudugu'
                item['novel_id'] = item.get('title', '')

            return novels
        except Exception as e:
            print(f'[SuduguCategories] 获取分类 {category_key} 失败: {e}')
            # 尝试返回旧缓存（即使过期）
            cached = self._db.get_category_novels_cache(category_key)
            if cached:
                for item in cached:
                    item['source_name'] = '速读谷分类'
                    item['source_key'] = 'sudugu'
                    item['source'] = 'sudugu'
                    item['novel_id'] = item.get('title', '')
                return cached
            return []


_categories = None


def get_sudugu_categories() -> SuduguCategories:
    """获取 SuduguCategories 单例"""
    global _categories
    if _categories is None:
        _categories = SuduguCategories()
    return _categories
