# -*- coding: utf-8 -*-
"""
笔趣阁/蚂蚁文学小说源

支持网站：蚂蚁文学 (mayiwsk.com)
- 书籍 URL 模式：/{数字}_{数字}/index.html
- 章节列表：在 <dd> 标签中
- 章节内容：在 #content 中
- 搜索接口：/modules/article/search.php?searchkey=关键词
- 使用 og:meta 标签提取小说信息
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, quote
from typing import Optional

from .base import BaseSource, NovelInfo, ChapterInfo, SourceError


class BiqugeSource(BaseSource):
    """蚂蚁文学源（mayiwsk.com）"""

    name = 'biquge'
    display_name = '蚂蚁文学'
    needs_login = False
    supports_search = True

    # 镜像列表（mayiwsk 为主，保留其他镜像作为后备）
    BIQUGE_MIRRORS = [
        'https://www.mayiwsk.com',
    ]

    TIMEOUT = 20
    RETRIES = 2
    RETRY_DELAY = 1

    # URL 模式：/数字_数字/ 或 /数字_数字/index.html
    URL_PATTERN = re.compile(r'/(\d+_\d+)(?:/index\.html)?/?')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_mirror = self.BIQUGE_MIRRORS[0]

    @staticmethod
    def parse_novel_url(url_or_id: str) -> Optional[str]:
        """从 URL 中解析小说 ID

        支持：
        - https://www.mayiwsk.com/34_34033/index.html -> 34_34033
        - https://www.mayiwsk.com/34_34033/ -> 34_34033
        - 34_34033（直接是 ID）
        """
        if not url_or_id:
            return None

        s = str(url_or_id).strip()

        # 如果已经是 ID 格式（数字_数字）
        if re.match(r'^\d+_\d+$', s):
            return s

        # 从 URL 中提取
        m = BiqugeSource.URL_PATTERN.search(s)
        if m:
            return m.group(1)

        # 尝试提取纯数字（某些镜像可能用纯数字）
        m = re.search(r'/(\d{3,})', s)
        if m:
            return m.group(1)

        return None

    # ===================== 内部请求方法 =====================

    def _fetch(self, url: str, **kwargs):
        """使用 Scrapling Fetcher 发起 GET 请求"""
        from scrapling.fetchers import Fetcher

        # 默认请求参数
        # 使用 Bing 作为 referer（覆盖 Scrapling 默认的 Google referer）
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

        # 完整 URL 或相对路径
        if url.startswith('http'):
            full_url = url
        else:
            full_url = urljoin(self._active_mirror + '/', url.lstrip('/'))

        try:
            resp = Fetcher.get(full_url, **request_kwargs)
            if resp is None:
                raise SourceError('请求返回 None', error_type='NETWORK')
            return resp
        except Exception as e:
            raise SourceError(f'请求失败: {e}', error_type='NETWORK') from e

    def _post(self, url: str, data: dict, **kwargs):
        """使用 Scrapling Fetcher 发起 POST 请求"""
        from scrapling.fetchers import Fetcher

        # 使用 Bing 作为 referer（覆盖 Scrapling 默认的 Google referer）
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

        if url.startswith('http'):
            full_url = url
        else:
            full_url = urljoin(self._active_mirror + '/', url.lstrip('/'))

        try:
            resp = Fetcher.post(full_url, data=data, **request_kwargs)
            if resp is None:
                raise SourceError('请求返回 None', error_type='NETWORK')
            return resp
        except Exception as e:
            raise SourceError(f'POST 请求失败: {e}', error_type='NETWORK') from e

    def _parse_html(self, resp):
        """将 Scrapling 响应解析为 Selector"""
        if not resp.body:
            raise SourceError('响应内容为空', error_type='NETWORK')
        from scrapling import Selector
        # mayiwsk.com 使用 UTF-8 编码
        text = resp.text or resp.body.decode('utf-8', errors='replace')
        return Selector(text, adaptive=True)

    # ===================== BaseSource 接口实现 =====================

    def get_novel_info(self, novel_id: str) -> NovelInfo:
        """获取小说信息"""
        try:
            # 构造书籍页面 URL
            novel_id = str(novel_id).strip()
            # 如果是纯数字，假设是 ID（mayiwsk 用 数字_数字 格式，但搜索可能返回这种）
            if re.match(r'^\d+_\d+$', novel_id):
                book_url = f'/{novel_id}/index.html'
            elif novel_id.startswith('http'):
                # 完整 URL
                book_url = novel_id
            else:
                book_url = f'/{novel_id}/index.html'

            resp = self._fetch(book_url)
            page = self._parse_html(resp)

            # 使用 og:meta 标签提取信息
            title = page.css('meta[property="og:novel:book_name"]::attr(content)').get()
            if not title:
                title = page.css('meta[property="og:title"]::attr(content)').get('')

            author = page.css('meta[property="og:novel:author"]::attr(content)').get('')
            description = page.css('meta[property="og:description"]::attr(content)').get('')
            cover_url = page.css('meta[property="og:image"]::attr(content)').get('')
            category = page.css('meta[property="og:novel:category"]::attr(content)').get('')
            status_text = page.css('meta[property="og:novel:status"]::attr(content)').get('')
            latest_chapter = page.css('meta[property="og:novel:latest_chapter_name"]::attr(content)').get('')

            # 提取真实 novel_id（从 URL）
            book_read_url = page.css('meta[property="og:novel:read_url"]::attr(content)').get('')
            if book_read_url:
                m = self.URL_PATTERN.search(book_read_url)
                if m:
                    novel_id = m.group(1)

            # 统计章节数
            chapter_links = page.css('dd a')
            chapter_count = len(chapter_links)

            # 提取字数（从页面文本）
            word_count = 0
            page_text = page.css('body::text').get('') or ''
            word_match = re.search(r'(\d+)\s*[Kk万字]?', page_text)
            if word_match:
                try:
                    word_count = int(word_match.group(1))
                    if word_count < 1000:
                        word_count = word_count * 10000  # K 单位
                except ValueError:
                    pass

            return NovelInfo(
                novel_id=novel_id,
                title=title or '未知书名',
                author=author or '未知',
                description=description,
                cover_url=cover_url,
                word_count=word_count,
                chapter_count=chapter_count,
                source=self.name,
                extra={
                    'category': category,
                    'status': status_text,
                    'latest_chapter': latest_chapter,
                    'url': book_read_url or f'{self._active_mirror}/{novel_id}/index.html',
                },
            )
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取小说信息失败: {e}', error_type='UNKNOWN') from e

    def get_chapter_list(self, novel_id: str) -> list[ChapterInfo]:
        """获取章节列表（自动剔除开头倒序/重复章节）"""
        try:
            novel_id = str(novel_id).strip()
            if re.match(r'^\d+_\d+$', novel_id):
                book_url = f'/{novel_id}/index.html'
            elif novel_id.startswith('http'):
                book_url = novel_id
            else:
                book_url = f'/{novel_id}/index.html'

            resp = self._fetch(book_url)
            page = self._parse_html(resp)

            # 章节在 dd > a 中
            chapter_links = page.css('dd a')

            if not chapter_links:
                # 尝试其他选择器
                chapter_links = page.css('div#list a, div.list a, ul.list a, li a')

            raw_chapters = []
            for i, link in enumerate(chapter_links):
                href = link.attrib.get('href', '')
                title = (link.text or '').strip()

                # 只保留章节链接（/数字_数字/数字.html 格式）
                if not href or not re.match(r'/\d+_\d+/\d+\.html', href):
                    continue

                # 提取章节 ID
                m = re.search(r'/(\d+)\.html', href)
                chapter_id = m.group(1) if m else str(i + 1)

                raw_chapters.append((chapter_id, title or f'第{i + 1}章', i))

            # 剔除开头倒序段和重复章节
            from .generic_source import ConfigurableSource
            chapters = ConfigurableSource._dedup_and_sort_chapters(raw_chapters)

            return chapters
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取章节列表失败: {e}', error_type='UNKNOWN') from e

    def get_chapter_content(self, novel_id: str, chapter_id: str) -> dict:
        """获取章节内容"""
        try:
            novel_id = str(novel_id).strip()
            chapter_id = str(chapter_id).strip()

            # 构造章节 URL：/数字_数字/数字.html
            if re.match(r'^\d+_\d+$', novel_id):
                chapter_url = f'/{novel_id}/{chapter_id}.html'
            else:
                # 如果 novel_id 不是标准格式，尝试直接组合
                chapter_url = f'/{novel_id}/{chapter_id}.html'

            resp = self._fetch(chapter_url)
            page = self._parse_html(resp)

            # 提取章节标题
            title = page.css('h1::text').get('')

            # 提取章节内容 - mayiwsk.com 使用 #content
            content_el = page.css('#content')
            if not content_el:
                content_el = page.css('div#content, div.content, .bookcontent, #booktxt')

            if not content_el:
                raise SourceError('未找到章节内容', error_type='PARSE')

            # 注意：Scrapling Selector 的 .text 属性在元素含有子节点时会返回空，
            # 需要使用 .get_all_text() 递归提取所有文本节点。
            content_node = content_el[0]
            try:
                content_text = content_node.get_all_text() or ''
            except Exception:
                # 兜底：用 ::text 选择器拼接
                text_nodes = content_node.css('::text')
                content_text = '\n'.join(str(t).strip() for t in text_nodes if str(t).strip())

            # 清理内容
            # 移除常见广告/提示文字
            ad_patterns = [
                r'最新网址：www\.mayiwsk\.com',
                r'蚂蚁文学全文字更新.*?www\.mayiwsk\.com',
                r'牢记网址：www\.mayiwsk\.com',
                r'请刷新页面.*?获取最新更新',
                r'正在手打中.*?请稍等片刻',
            ]
            for pattern in ad_patterns:
                content_text = re.sub(pattern, '', content_text, flags=re.DOTALL)

            # 清理多余空行
            content_text = re.sub(r'\n{3,}', '\n\n', content_text)
            content_text = content_text.strip()

            if not content_text:
                raise SourceError('章节内容为空', error_type='PARSE')

            # 如果标题为空，从页面 title 提取
            if not title:
                page_title = page.css('title::text').get('')
                if '_' in page_title:
                    title = page_title.split('_')[0].strip()

            return {
                'title': title or f'章节',
                'content': content_text,
            }
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取章节内容失败: {e}', error_type='UNKNOWN') from e

    # ===================== 搜索 =====================

    def search_novel(self, keyword: str) -> list[NovelInfo]:
        """搜索小说"""
        try:
            # mayiwsk.com 搜索接口：/modules/article/search.php?searchkey=关键词
            search_url = '/modules/article/search.php'
            encoded_keyword = quote(keyword)

            # 使用 GET 方式搜索
            resp = self._fetch(f'{search_url}?searchkey={encoded_keyword}')
            page = self._parse_html(resp)

            results = []

            # 搜索结果是表格形式，每行一本书
            # 提取所有指向书籍页面的链接
            seen_ids = set()
            links = page.css('a[href*="_"]')

            for link in links:
                href = link.attrib.get('href', '')
                text = (link.text or '').strip()

                # 匹配书籍 URL 模式：/数字_数字/
                m = re.match(r'/(\d+_\d+)/?(?:index\.html)?$', href)
                if not m:
                    continue

                novel_id = m.group(1)
                if novel_id in seen_ids:
                    continue
                seen_ids.add(novel_id)

                if not text or len(text) < 2:
                    continue

                results.append(NovelInfo(
                    novel_id=novel_id,
                    title=text,
                    author='',  # 搜索结果表格中可能没有作者
                    description='',
                    source=self.name,
                    extra={'url': href},
                ))

                if len(results) >= 20:
                    break

            return results
        except Exception as e:
            # 搜索失败不抛异常，返回空列表
            print(f'[{self.display_name}] 搜索出错: {e}')
            return []
