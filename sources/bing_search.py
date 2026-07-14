# -*- coding: utf-8 -*-
"""通用小说搜索模块

使用多策略搜索：
1. 各源自身搜索接口（铅笔小说、海棠文学等支持搜索的源）
2. Bing 站内搜索（site:mayiwsk.com 等）精准匹配
3. Bing 通用搜索作为兜底

聚合所有源的可用结果，无需手动切换源。
"""
from __future__ import annotations

import re
from urllib.parse import quote, urljoin
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup


# 各源的站点域名和 URL 模式
# (source_key, 域名, URL正则, novel_id 取 group(1))
SOURCE_SITES = [
    ('fanqie', 'fanqienovel.com', re.compile(r'https?://fanqienovel\.com/page/(\d+)')),
    ('biquge', 'mayiwsk.com', re.compile(r'https?://(?:www\.)?mayiwsk\.com/(\d+_\d+)/')),
    ('dingdian', '23wxx.net', re.compile(r'https?://(?:www\.|m\.)?23wxx\.(?:net|com)/xs/(\d+)')),
    ('bxwx', 'bxwxber.cc', re.compile(r'https?://(?:www\.|wap\.)?bxwx(?:ber)?\.(?:cc|org|tv)/book/(\d+/\d+)')),
    ('qianbi', '23qb.net', re.compile(r'https?://(?:www\.)?23qb\.net/book/(\d+)')),
    ('haitang', 'htwenxe.com', re.compile(r'https?://(?:www\.|m\.)?htwenxe\.com/book/(\d+)')),
]

# 向后兼容
FANQIE_URL_PATTERN = SOURCE_SITES[0][2]
BIQUGE_URL_PATTERN = SOURCE_SITES[1][2]

# 源 URL 模式列表（用于从搜索结果中识别）
SOURCE_URL_PATTERNS = [(sk, pat) for sk, _, pat in SOURCE_SITES]

# 请求头
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def _bing_search(query: str, timeout: int = 15) -> List[Tuple[str, str]]:
    """用 Bing 搜索，返回 [(标题, URL), ...]

    使用国际版 Bing（不强制中国区），避免被重定向到 cn.bing.com 导致结果质量差。
    """
    # 不使用 setlang/cc 参数，避免被强制到中国版 Bing
    url = f'https://www.bing.com/search?q={quote(query)}'
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'lxml')
        results = []
        for item in soup.find_all('li', class_='b_algo'):
            h2 = item.find('h2')
            if h2:
                a = h2.find('a')
                if a:
                    href = a.get('href', '')
                    text = a.get_text(strip=True)
                    if href and text:
                        results.append((text, href))
        return results
    except Exception:
        return []


def _bing_site_search(keyword: str, site: str, timeout: int = 15) -> List[Tuple[str, str]]:
    """Bing 站内搜索：site:domain 关键词

    精准搜索特定小说网站的结果。
    """
    query = f'site:{site} {keyword}'
    return _bing_search(query, timeout)


def search_via_bing(keyword: str) -> List[dict]:
    """通过 Bing 搜索小说，返回所有源的聚合结果

    搜索策略：
    1. 对每个支持的源站点，用 site: 搜索精准匹配
    2. 通用 Bing 搜索作为补充

    返回: [{source, novel_id, title, url}, ...]
    """
    found = {}  # 用 (source, novel_id) 作 key 去重

    # 1. 对每个源站点做 site: 搜索（精准）
    for src_key, domain, pattern in SOURCE_SITES:
        try:
            results = _bing_site_search(keyword, domain)
            for title, url in results:
                m = pattern.search(url)
                if m:
                    book_id = m.group(1)
                    key = (src_key, book_id)
                    if key not in found:
                        found[key] = {
                            'source': src_key,
                            'novel_id': book_id,
                            'title': title,
                            'url': url,
                        }
        except Exception:
            continue

    # 2. 通用搜索作为补充（可能找到未被 site: 搜索覆盖的源）
    for query in [f'{keyword} 小说', f'{keyword} 阅读']:
        results = _bing_search(query)
        for title, url in results:
            for src_key, _, pattern in SOURCE_SITES:
                m = pattern.search(url)
                if m:
                    book_id = m.group(1)
                    key = (src_key, book_id)
                    if key not in found:
                        found[key] = {
                            'source': src_key,
                            'novel_id': book_id,
                            'title': title,
                            'url': url,
                        }
                    break

    return list(found.values())
