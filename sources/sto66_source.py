# -*- coding: utf-8 -*-
"""思兔阅读 (sto66.com) 小说源

网站结构：
- 书籍页：/book/{novel_id}.html（含最新3章 + 信息）
- 章节列表页：/chapter/{novel_id}.html（每页 500 章，分页 /chapter/{novel_id}/{page}.html）
- 章节内容：/chapter/{novel_id}/{chapter_id}.html（#content）
- 搜索：/search/{keyword}.html

novel_id 和 chapter_id 均为 22 位字符串（如 6Tyll06FRM6vWZgatDuIwl），
非数字格式，因此 _dedup_and_sort_chapters 的倒序段检测不适用，
本源使用自定义的章节列表抓取与去重逻辑。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, quote
from typing import Optional, List

from .base import BaseSource, NovelInfo, ChapterInfo, SourceError


class Sto66Source(BaseSource):
    """思兔阅读源 (sto66.com)"""

    name = 'sto66'
    display_name = '思兔阅读'
    needs_login = False
    supports_search = True

    MIRRORS = ['https://www.sto66.com']
    ENCODING = 'utf-8'

    # URL 模式：/book/{22位ID}.html
    URL_PATTERN = re.compile(r'/book/([A-Za-z0-9]{20,26})')

    TIMEOUT = 20
    RETRIES = 2
    RETRY_DELAY = 1

    # 章节列表每页条数
    CHAPTERS_PER_PAGE = 500
    MAX_CHAPTER_PAGES = 30  # 安全上限，最多抓 30 页（15000 章）

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_mirror = self.MIRRORS[0]

    # ===================== URL 解析 =====================

    @staticmethod
    def parse_novel_url(url_or_id: str) -> Optional[str]:
        """解析 URL 提取小说 ID

        支持：
        - https://www.sto66.com/book/6Tyll06FRM6vWZgatDuIwl.html -> 6Tyll06FRM6vWZgatDuIwl
        - 6Tyll06FRM6vWZgatDuIwl（直接是 ID）
        """
        if not url_or_id:
            return None
        s = str(url_or_id).strip()
        # 直接是 ID（20-26 位字母数字）
        if re.match(r'^[A-Za-z0-9]{20,26}$', s):
            return s
        # 从 URL 中提取
        m = Sto66Source.URL_PATTERN.search(s)
        if m:
            return m.group(1)
        return None

    # ===================== 内部请求 =====================

    def _build_url(self, path: str) -> str:
        if path.startswith('http'):
            return path
        return urljoin(self._active_mirror + '/', path.lstrip('/'))

    def _fetch(self, url: str, **kwargs):
        """使用 Scrapling Fetcher 发起 GET 请求"""
        from scrapling.fetchers import Fetcher

        custom_headers = kwargs.pop('headers', None) or {}
        if 'referer' not in {k.lower() for k in custom_headers}:
            custom_headers['referer'] = 'https://www.bing.com/'

        request_kwargs = {
            'timeout': self.TIMEOUT,
            'retries': self.RETRIES,
            'retry_delay': self.RETRY_DELAY,
            'impersonate': 'chrome',
            'stealthy_headers': True,
            'follow_redirects': True,
            'verify': False,
            'headers': custom_headers,
        }
        request_kwargs.update(kwargs)

        full_url = self._build_url(url)
        try:
            resp = Fetcher.get(full_url, **request_kwargs)
            if resp is None:
                raise SourceError('请求返回 None', error_type='NETWORK')
            return resp
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'请求失败: {e}', error_type='NETWORK') from e

    def _parse_html(self, resp):
        if not resp.body:
            raise SourceError('响应内容为空', error_type='NETWORK')
        from scrapling import Selector
        text = resp.text or resp.body.decode(self.ENCODING, errors='replace')
        return Selector(text, adaptive=True)

    def _get_link_text(self, link) -> str:
        """安全获取链接文本"""
        try:
            t = link.text
            if t:
                s = str(t).strip()
                if s:
                    return s
        except Exception:
            pass
        try:
            return link.get_all_text().strip()
        except Exception:
            return ''

    # ===================== BaseSource 接口实现 =====================

    def get_novel_info(self, novel_id: str) -> NovelInfo:
        """获取小说信息

        sto66.com 无 og:meta，从 .booktag 等结构化元素提取。
        """
        try:
            novel_id = str(novel_id).strip()
            book_url = f'/book/{novel_id}.html'
            if novel_id.startswith('http'):
                book_url = novel_id

            resp = self._fetch(book_url)
            page = self._parse_html(resp)

            # 标题
            title = page.css('h1.booktitle::text').get('') or page.css('h1::text').get('') or '未知书名'
            title = title.strip()

            # .booktag 内含 作者链接 / 分类链接 / 字数 / 阅读数 / 状态
            author = ''
            category = ''
            word_count = 0
            status_text = ''

            # 作者：.booktag a.red
            author_links = page.css('.booktag a.red')
            if author_links:
                author = self._get_link_text(author_links[0])

            # 分类：.booktag a.blue（第一个 blue 是分类，第二个可能是阅读数等）
            category_links = page.css('.booktag a.blue')
            if category_links:
                category = self._get_link_text(category_links[0])

            # 字数 / 状态在 span 中
            spans = page.css('.booktag span')
            for span in spans:
                cls = span.attrib.get('class', '')
                text = self._get_link_text(span)
                if '万字' in text or '字' in text:
                    m = re.search(r'([\d.]+)\s*万字', text)
                    if m:
                        try:
                            word_count = int(float(m.group(1)) * 10000)
                        except ValueError:
                            pass
                if 'red' in (cls or '').split() and text in ('连载', '全本', '完结', '连载中', '已完结'):
                    status_text = text

            # 封面
            cover_url = page.css('.bookcover img::attr(src)').get('') or \
                        page.css('.bookcover img::attr(data-src)').get('')

            # 简介
            description = page.css('.bookintro::text').get('') or ''
            if not description:
                description = page.css('meta[name="description"]::attr(content)').get('')

            # 章节数（从章节列表页获取更准确，这里先粗略计数最新章节区块）
            # 实际章节数在 get_chapter_list 时才能确定

            return NovelInfo(
                novel_id=novel_id,
                title=title,
                author=author or '未知',
                description=description,
                cover_url=cover_url,
                word_count=word_count,
                chapter_count=0,
                source=self.name,
                extra={
                    'category': category,
                    'status': status_text,
                    'url': self._build_url(book_url),
                },
            )
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取小说信息失败: {e}', error_type='UNKNOWN') from e

    def get_chapter_list(self, novel_id: str) -> list[ChapterInfo]:
        """获取章节列表（支持分页抓取）

        sto66.com 章节列表分页：/chapter/{id}.html, /chapter/{id}/2.html, ...
        每页 500 章。章节 ID 是 22 位字符串（非数字），无法用数值排序检测倒序段，
        因此直接按页面顺序拼接去重，依赖页面本身的正序排列。
        """
        try:
            novel_id = str(novel_id).strip()
            # 从 URL 提取真实 novel_id
            if novel_id.startswith('http'):
                m = self.URL_PATTERN.search(novel_id)
                if m:
                    novel_id = m.group(1)

            all_chapters = []  # [(chapter_id, title), ...]
            seen_ids = set()

            for page_num in range(1, self.MAX_CHAPTER_PAGES + 1):
                if page_num == 1:
                    list_url = f'/chapter/{novel_id}.html'
                else:
                    list_url = f'/chapter/{novel_id}/{page_num}.html'

                try:
                    resp = self._fetch(list_url)
                except SourceError as e:
                    if page_num == 1:
                        raise
                    # 第 2 页及之后失败视为正常结束
                    break

                page = self._parse_html(resp)

                # 章节在 dd > a 中，href=/chapter/{novel_id}/{chapter_id}.html
                links = page.css('dd a')
                if not links:
                    links = page.css('a[href*="/chapter/"]')

                page_chapter_count = 0
                has_next_page = False

                for link in links:
                    href = link.attrib.get('href', '')
                    title = self._get_link_text(link)

                    # 匹配章节链接：/chapter/{novel_id}/{chapter_id}.html
                    # 用 search 而非 match，兼容绝对 URL（https://www.sto66.com/chapter/...）
                    m = re.search(r'/chapter/[A-Za-z0-9]+/([A-Za-z0-9]+)\.html', href)
                    if not m:
                        # 检查是否是"下一页"链接：/chapter/{novel_id}/{N}.html
                        if re.search(r'/chapter/[A-Za-z0-9]+/\d+\.html', href) and \
                                ('下一页' in title or '下页' in title or 'next' in title.lower()):
                            has_next_page = True
                        continue

                    chapter_id = m.group(1)
                    if chapter_id in seen_ids:
                        continue
                    seen_ids.add(chapter_id)
                    all_chapters.append((chapter_id, title or f'第{len(all_chapters) + 1}章'))
                    page_chapter_count += 1

                # 本页无章节或不足 500 章，视为最后一页
                if page_chapter_count == 0:
                    break
                if not has_next_page and page_chapter_count < self.CHAPTERS_PER_PAGE:
                    break

            return [
                ChapterInfo(
                    chapter_id=cid,
                    chapter_title=title,
                    chapter_index=i + 1,
                )
                for i, (cid, title) in enumerate(all_chapters)
            ]
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取章节列表失败: {e}', error_type='UNKNOWN') from e

    def get_chapter_content(self, novel_id: str, chapter_id: str) -> dict:
        """获取章节内容

        章节URL：/chapter/{novel_id}/{chapter_id}.html
        正文在 #content
        """
        try:
            novel_id = str(novel_id).strip()
            chapter_id = str(chapter_id).strip()

            # 如果 novel_id 是 URL，提取真实 ID
            if novel_id.startswith('http'):
                m = self.URL_PATTERN.search(novel_id)
                if m:
                    novel_id = m.group(1)

            chapter_url = f'/chapter/{novel_id}/{chapter_id}.html'
            resp = self._fetch(chapter_url)
            page = self._parse_html(resp)

            # 标题
            title = page.css('h1::text').get('')

            # 正文
            content_el = page.css('#content')
            if not content_el:
                content_el = page.css('div#content, .content, .chapter-content, .article-content')

            if not content_el:
                raise SourceError('未找到章节内容', error_type='PARSE')

            content_node = content_el[0]
            try:
                content_text = content_node.get_all_text() or ''
            except Exception:
                text_nodes = content_node.css('::text')
                content_text = '\n'.join(str(t).strip() for t in text_nodes if str(t).strip())

            # 清理广告/提示文字
            content_text = self._clean_content(content_text)

            if not content_text:
                raise SourceError('章节内容为空', error_type='PARSE')

            if not title:
                page_title = page.css('title::text').get('')
                if '-' in page_title:
                    title = page_title.split('-')[0].strip()
                elif '_' in page_title:
                    title = page_title.split('_')[0].strip()

            return {
                'title': title or '章节',
                'content': content_text,
            }
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取章节内容失败: {e}', error_type='UNKNOWN') from e

    def _clean_content(self, text: str) -> str:
        """清理章节内容中的广告和提示文字"""
        ad_patterns = [
            r'思兔阅读.*?最新章节',
            r'思兔小说.*?为您呈现',
            r'请刷新页面.*?获取最新更新',
            r'正在手打中.*?请稍等片刻',
            r'本章未完.*?点击下一页继续',
            r'内容更新后.*?请重新刷新页面.*?即可获取最新更新',
        ]
        for pattern in ad_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ===================== 搜索 =====================

    def search_novel(self, keyword: str) -> list[NovelInfo]:
        """搜索小说

        搜索URL：/search/{keyword}.html
        搜索结果中书籍链接：/book/{id}.html
        """
        try:
            encoded = quote(keyword)
            search_url = f'/search/{encoded}.html'
            resp = self._fetch(search_url)
            page = self._parse_html(resp)

            results = []
            seen_ids = set()

            # 搜索结果中的书籍链接
            links = page.css('a[href*="/book/"]')
            for link in links:
                href = link.attrib.get('href', '')
                # 用 search 而非 match，兼容绝对 URL
                m = re.search(r'/book/([A-Za-z0-9]{20,26})\.html', href)
                if not m:
                    continue
                nid = m.group(1)
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)

                title = self._get_link_text(link)
                if not title or len(title) < 2:
                    continue

                results.append(NovelInfo(
                    novel_id=nid,
                    title=title,
                    author='',
                    source=self.name,
                    extra={'url': href},
                ))
                if len(results) >= 20:
                    break

            return results
        except Exception as e:
            print(f'[{self.display_name}] 搜索出错: {e}')
            return []
