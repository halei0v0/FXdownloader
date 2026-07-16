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

    # ===================== 排行榜/推荐 =====================

    # 排行榜页面分类区块标题（<h3>）与 category key 的映射
    # 顺序即页面出现顺序
    _RANKING_CATEGORIES = [
        ('xuanhuan', '玄幻·奇幻'),
        ('xiuzhen', '修真·仙侠'),
        ('dushi', '都市·青春'),
        ('chuanyue', '历史·穿越'),
        ('wangyou', '网游·竞技'),
        ('kehuan', '科幻·灵异'),
        ('quanben', '全本小说'),
        ('all', '全部小说'),
    ]

    # 排名类型：总/周/月/日
    _RANKING_TYPES = ['total', 'week', 'month', 'day']
    _RANKING_TYPE_LABELS = {
        'total': '总榜',
        'week': '周榜',
        'month': '月榜',
        'day': '日榜',
    }

    def get_categories(self) -> list[dict]:
        """返回支持的排行榜分类列表"""
        return [
            {'key': 'xuanhuan', 'name': '玄幻·奇幻'},
            {'key': 'xiuzhen', 'name': '修真·仙侠'},
            {'key': 'dushi', 'name': '都市·青春'},
            {'key': 'chuanyue', 'name': '历史·穿越'},
            {'key': 'wangyou', 'name': '网游·竞技'},
            {'key': 'kehuan', 'name': '科幻·灵异'},
            {'key': 'quanben', 'name': '全本小说'},
            {'key': 'all', 'name': '全部小说'},
        ]

    def get_rankings(self, category: str = 'all', page: int = 1) -> list[NovelInfo]:
        """从蚂蚁文学排行榜页面抓取真实排行数据

        数据来源：https://www.mayiwsk.com/paihangbang/
        页面结构：
        - 8 个分类区块，每个以 <h3>分类名推荐排行榜</h3> 开头
        - 每个区块有 4 个排名类型：总排名/周排名/月排名/日排名
        - 每个排名下是 <li>序号<a href="书籍URL">书名</a></li>

        Args:
            category: 分类 key（见 get_categories），默认 'all'（全部小说）
                      支持复合 key：'xuanhuan:week' 表示玄幻分类的周榜
            page: 页码（排行榜只有一页，>1 返回空）

        Returns:
            list[NovelInfo]：按排名顺序排列
        """
        if page > 1:
            return []
        try:
            resp = self._fetch('/paihangbang/')
            html_text = resp.text or resp.body.decode('utf-8', errors='replace')

            # 解析复合 category：'xuanhuan:week' -> (category, ranking_type)
            cat_key = category or 'all'
            rank_type = 'total'  # 默认总榜
            if ':' in cat_key:
                cat_key, rank_type = cat_key.split(':', 1)

            # 定位分类区块
            section_html = self._extract_ranking_section(html_text, cat_key)
            if not section_html:
                return []

            # 在区块内定位排名类型
            ranked_html = self._extract_ranking_type(section_html, rank_type)
            if not ranked_html:
                return []

            # 提取 <li>序号<a href="书籍URL">书名</a></li>
            results = []
            seen = set()
            # 匹配 <li>数字<a href="...数字_数字/index.html">书名</a></li>
            pattern = re.compile(
                r'<li>\s*(\d+)\s*<a\s+[^>]*href="https?://[^/]*(/\d+_\d+/index\.html)"[^>]*>(.*?)</a>\s*</li>',
                re.DOTALL
            )
            for m in pattern.finditer(ranked_html):
                rank_num = int(m.group(1))
                novel_id = m.group(2).strip('/').replace('/index.html', '')
                if novel_id in seen:
                    continue
                seen.add(novel_id)
                # 清理标题中的 HTML 标签
                title = re.sub(r'<[^>]+>', '', m.group(3)).strip()
                if not title:
                    continue
                results.append(NovelInfo(
                    novel_id=novel_id,
                    title=title,
                    author='',
                    source=self.name,
                    extra={
                        'url': m.group(2),
                        'rank': rank_num,
                        'rank_type': rank_type,
                        'category': cat_key,
                    },
                ))

            return results
        except Exception as e:
            print(f'[{self.display_name}] 获取排行榜出错: {e}')
            return []

    def _extract_ranking_section(self, html_text: str, cat_key: str) -> str:
        """从完整 HTML 中提取指定分类区块的 HTML 片段

        分类区块以 <h3>分类名推荐排行榜</h3> 开头，到下一个 <h3> 或文件末尾结束。
        """
        # 找到分类对应的中文名
        target_name = None
        for ck, cn in self._RANKING_CATEGORIES:
            if ck == cat_key:
                target_name = cn
                break
        if not target_name:
            return ''

        # 找 <h3>包含分类名</h3> 的位置
        # 标题格式："玄幻·奇幻小说推荐排行榜"
        h3_pattern = re.compile(r'<h3[^>]*>(.*?)</h3>', re.DOTALL)
        matches = list(h3_pattern.finditer(html_text))
        section_start = -1
        for i, m in enumerate(matches):
            title_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if target_name in title_text:
                section_start = m.end()
                break
        if section_start < 0:
            return ''

        # 区块结束：下一个 <h3> 或文件末尾
        section_end = len(html_text)
        for m in matches:
            if m.start() > section_start:
                section_end = m.start()
                break

        return html_text[section_start:section_end]

    def _extract_ranking_type(self, section_html: str, rank_type: str) -> str:
        """从分类区块 HTML 中提取指定排名类型（总/周/月/日）的 HTML 片段

        排行榜页面结构：
        - "总排名" 后跟着 <li>序号<a>书名</a></li> 列表
        - 然后 "周排名"、"月排名"、"日排名" 各跟一组列表

        rank_type: 'total'/'week'/'month'/'day'
        """
        # 排名类型关键字
        type_markers = {
            'total': '总排名',
            'week': '周排名',
            'month': '月排名',
            'day': '日排名',
        }
        target_marker = type_markers.get(rank_type, '总排名')
        if target_marker not in section_html:
            return ''

        # 找目标排名类型的位置
        start = section_html.find(target_marker)
        if start < 0:
            return ''

        # 找下一个排名类型的位置作为结束
        end = len(section_html)
        for marker in type_markers.values():
            if marker == target_marker:
                continue
            pos = section_html.find(marker, start + len(target_marker))
            if 0 <= pos < end:
                end = pos

        return section_html[start:end]
