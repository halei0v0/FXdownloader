# -*- coding: utf-8 -*-
"""可配置的通用小说源

支持通过类属性配置不同的小说网站，封装通用的：
- Scrapling HTTP 请求（使用 Bing 作为 referer）
- og:meta 书籍信息解析
- 章节列表提取（含倒序/重复章节剔除）
- 章节正文提取（兼容 Scrapling 的 .get_all_text()）

子类只需配置类属性即可适配大多数同类网站。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, quote
from typing import Optional, List

from .base import BaseSource, NovelInfo, ChapterInfo, SourceError


class ConfigurableSource(BaseSource):
    """可配置的通用小说源基类"""

    # ====== 子类需配置的属性 ======
    name: str = 'generic'
    display_name: str = '通用源'
    MIRRORS: List[str] = ['https://example.com']
    ENCODING: str = 'utf-8'  # 'utf-8' 或 'gbk'

    # URL 模式（用于 parse_novel_url 识别 URL）
    URL_PATTERN: re.Pattern = re.compile(r'/book/(\d+)')

    # URL 模板（{novel_id} / {chapter_id}）
    BOOK_URL_TEMPLATE: str = '/book/{novel_id}/'
    CHAPTER_URL_TEMPLATE: str = '/book/{novel_id}/{chapter_id}.html'
    # 章节列表页 URL（None 表示与书籍页相同）
    CHAPTER_LIST_URL_TEMPLATE: Optional[str] = None

    # 选择器
    CHAPTER_LIST_SELECTOR: str = 'dd a'  # 章节列表链接选择器
    CHAPTER_LINK_PATTERN: re.Pattern = re.compile(r'.*?(\d+)\.html')  # 章节链接过滤+ID提取
    CONTENT_SELECTOR: str = '#content'  # 章节正文选择器
    TITLE_SELECTOR: str = 'h1::text'  # 章节标题选择器
    USE_OG_META: bool = True  # 是否使用 og:meta 解析书籍信息

    # 搜索（None 表示不支持自身搜索，依赖 Bing）
    SEARCH_URL: Optional[str] = None
    SEARCH_METHOD: str = 'GET'
    SEARCH_PARAM: str = 'searchkey'

    # 请求参数
    TIMEOUT: int = 20
    RETRIES: int = 2
    RETRY_DELAY: int = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_mirror = self.MIRRORS[0]
        # 根据 SEARCH_URL 自动设置 supports_search
        if self.SEARCH_URL:
            self.supports_search = True

    # ===================== URL 解析 =====================

    @classmethod
    def parse_novel_url(cls, url_or_id: str) -> Optional[str]:
        """从 URL 中解析小说 ID（子类覆盖 URL_PATTERN 即可）

        返回的 novel_id 用于 BOOK_URL_TEMPLATE。
        """
        if not url_or_id:
            return None
        s = str(url_or_id).strip()

        # 如果是纯数字，直接返回
        if re.match(r'^\d+$', s):
            return s

        # 如果是 cat/book 格式（笔下文学）
        if re.match(r'^\d+/\d+$', s):
            return s

        # 从 URL 中提取
        m = cls.URL_PATTERN.search(s)
        if m:
            return m.group(1)
        return None

    def _extract_novel_id_from_url(self, url: str) -> Optional[str]:
        """子类可覆盖：从 URL 提取 novel_id"""
        m = self.URL_PATTERN.search(url)
        if m:
            return m.group(1)
        return None

    # ===================== 内部请求方法 =====================

    def _build_url(self, path: str) -> str:
        """拼接完整 URL"""
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

    def _post(self, url: str, data: dict, **kwargs):
        """使用 Scrapling Fetcher 发起 POST 请求"""
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
            resp = Fetcher.post(full_url, data=data, **request_kwargs)
            if resp is None:
                raise SourceError('请求返回 None', error_type='NETWORK')
            return resp
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'POST 请求失败: {e}', error_type='NETWORK') from e

    def _parse_html(self, resp):
        """将 Scrapling 响应解析为 Selector，处理编码"""
        if not resp.body:
            raise SourceError('响应内容为空', error_type='NETWORK')
        from scrapling import Selector
        # 优先用 resp.text，如果乱码则按配置编码解码
        text = resp.text
        if not text or self.ENCODING == 'gbk':
            try:
                text = resp.body.decode(self.ENCODING, errors='replace')
            except Exception:
                text = resp.text or ''
        return Selector(text, adaptive=True)

    # ===================== BaseSource 接口实现 =====================

    def get_novel_info(self, novel_id: str) -> NovelInfo:
        """获取小说信息"""
        try:
            novel_id = str(novel_id).strip()
            book_url = self.BOOK_URL_TEMPLATE.format(novel_id=novel_id)
            if novel_id.startswith('http'):
                book_url = novel_id

            resp = self._fetch(book_url)
            page = self._parse_html(resp)

            title = ''
            author = ''
            description = ''
            cover_url = ''
            category = ''
            status_text = ''

            if self.USE_OG_META:
                title = page.css('meta[property="og:novel:book_name"]::attr(content)').get('') or \
                       page.css('meta[property="og:title"]::attr(content)').get('')
                author = page.css('meta[property="og:novel:author"]::attr(content)').get('')
                description = page.css('meta[property="og:description"]::attr(content)').get('')
                cover_url = page.css('meta[property="og:image"]::attr(content)').get('')
                category = page.css('meta[property="og:novel:category"]::attr(content)').get('')
                status_text = page.css('meta[property="og:novel:status"]::attr(content)').get('')

            # 备选解析（og:meta 不可用或为空时）
            if not title:
                title = page.css('h1::text').get('') or \
                       page.css('.book-title::text, .info h1::text, .title::text').get('') or '未知书名'
            if not author:
                author = page.css('.author::text, .info p::text').get('') or ''
                # 从文本中提取 "作者：xxx"
                if not author:
                    m = re.search(r'作者[：:]\s*([^\s<]+)', page.css('body::text').get('') or '')
                    if m:
                        author = m.group(1)
            if not description:
                description = page.css('meta[name="description"]::attr(content)').get('')

            # 章节数
            chapter_links = page.css(self.CHAPTER_LIST_SELECTOR)
            chapter_count = len(chapter_links)

            return NovelInfo(
                novel_id=novel_id,
                title=title or '未知书名',
                author=author or '未知',
                description=description,
                cover_url=cover_url,
                word_count=0,
                chapter_count=chapter_count,
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
        """获取章节列表（自动剔除倒序/重复章节）"""
        try:
            novel_id = str(novel_id).strip()
            # 章节列表页 URL
            if self.CHAPTER_LIST_URL_TEMPLATE:
                list_url = self.CHAPTER_LIST_URL_TEMPLATE.format(novel_id=novel_id)
            else:
                list_url = self.BOOK_URL_TEMPLATE.format(novel_id=novel_id)

            resp = self._fetch(list_url)
            page = self._parse_html(resp)

            # 提取章节链接
            links = page.css(self.CHAPTER_LIST_SELECTOR)
            if not links:
                links = page.css('dd a, .listmain a, .chapter a, ul.list a, .module-row-text')

            raw_chapters = []
            for i, link in enumerate(links):
                href = link.attrib.get('href', '')
                title = self._get_link_text(link)

                # 用 CHAPTER_LINK_PATTERN 过滤+提取章节ID
                m = self.CHAPTER_LINK_PATTERN.search(href)
                if not m:
                    continue
                chapter_id = m.group(1) if m.groups() else str(i + 1)

                raw_chapters.append((chapter_id, title or f'第{i + 1}章', i))

            # 剔除倒序/重复章节
            chapters = self._dedup_and_sort_chapters(raw_chapters)

            return chapters
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f'获取章节列表失败: {e}', error_type='UNKNOWN') from e

    @staticmethod
    def _dedup_and_sort_chapters(raw_chapters: list) -> list[ChapterInfo]:
        """剔除倒序和重复章节，正确排序（staticmethod，可被其他源复用）

        很多小说网站章节列表开头会有几章"最新章节"的倒序排列，
        后面才是正序的完整列表。本方法：
        1. 检测开头是否有倒序段（章节序号递减）
        2. 跳过倒序段，对正序主体去重（按 chapter_id 首次出现）

        注意：必须先跳过倒序段再去重。如果先去重（保留首次出现），
        倒序段的章节会被保留，正序主体中的同名章节被丢弃，
        随后剔除倒序段会导致这些章节彻底丢失。
        """
        if not raw_chapters:
            return []

        # 尝试将 chapter_id 转为数字用于排序判断
        def to_num(cid):
            try:
                return int(cid)
            except (ValueError, TypeError):
                return None

        numeric_ids = [(to_num(c[0]), c) for c in raw_chapters]

        # 检测开头的倒序段
        # 典型模式：[最新N章倒序] [完整正序列表]
        # 倒序段特征：开头几章 ID 递减，然后突然出现小 ID 开始正序递增
        main_start = 0
        if numeric_ids and numeric_ids[0][0] is not None:
            nums = [n for n, _ in numeric_ids if n is not None]
            if len(nums) >= 4:
                # 找到正序主体起点：第一个 nums[i] < nums[i+1] < nums[i+2] 的位置
                for i in range(len(numeric_ids) - 2):
                    n0 = numeric_ids[i][0]
                    n1 = numeric_ids[i + 1][0]
                    n2 = numeric_ids[i + 2][0]
                    if n0 is not None and n1 is not None and n2 is not None:
                        if n0 < n1 < n2:
                            main_start = i
                            break
                # 如果找到了正序起点，且起点之前有内容（倒序段）
                if main_start > 0:
                    # 只有当倒序段的 ID 都 >= 正序段起点 ID 时，才确认是倒序段
                    main_min = numeric_ids[main_start][0]
                    reversed_part = numeric_ids[:main_start]
                    if not all(n is None or n >= main_min for n, _ in reversed_part):
                        # 不是真正的倒序段，不跳过
                        main_start = 0

        # 先跳过倒序段，再对剩余正序主体去重
        effective = [c for _, c in numeric_ids[main_start:]] if main_start > 0 else raw_chapters
        seen_ids = set()
        deduped = []
        for cid, title, idx in effective:
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            deduped.append((cid, title, idx))

        return [
            ChapterInfo(
                chapter_id=cid,
                chapter_title=title,
                chapter_index=i + 1,
            )
            for i, (cid, title, _) in enumerate(deduped)
        ]

    def _get_link_text(self, link) -> str:
        """安全获取链接文本"""
        try:
            t = link.text
            if t:
                # TextHandler 可能需要 str()
                s = str(t).strip()
                if s:
                    return s
        except Exception:
            pass
        # 兜底
        try:
            return link.get_all_text().strip()
        except Exception:
            return ''

    def get_chapter_content(self, novel_id: str, chapter_id: str) -> dict:
        """获取章节内容"""
        try:
            novel_id = str(novel_id).strip()
            chapter_id = str(chapter_id).strip()
            chapter_url = self.CHAPTER_URL_TEMPLATE.format(
                novel_id=novel_id, chapter_id=chapter_id
            )

            resp = self._fetch(chapter_url)
            page = self._parse_html(resp)

            # 章节标题
            title = page.css(self.TITLE_SELECTOR).get('')

            # 章节正文
            content_el = page.css(self.CONTENT_SELECTOR)
            if not content_el:
                content_el = page.css(f'div{self.CONTENT_SELECTOR}, .content, .chapter-content, .article-content, #acontent')

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
                if '_' in page_title:
                    title = page_title.split('_')[0].strip()
                elif '-' in page_title:
                    title = page_title.split('-')[0].strip()

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
            r'最新网址[：:].*?www\.\S+',
            r'牢记网址[：:].*?www\.\S+',
            r'请刷新页面.*?获取最新更新',
            r'正在手打中.*?请稍等片刻',
            r'本章未完.*?点击下一页继续',
            r'内容更新后.*?请重新刷新页面.*?即可获取最新更新',
            r'www\.\S+\s*全文字更新',
        ]
        for pattern in ad_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ===================== 搜索 =====================

    def search_novel(self, keyword: str) -> list[NovelInfo]:
        """搜索小说（如果配置了 SEARCH_URL）"""
        if not self.SEARCH_URL:
            return []
        try:
            encoded = quote(keyword)
            if self.SEARCH_METHOD == 'GET':
                resp = self._fetch(f'{self.SEARCH_URL}?{self.SEARCH_PARAM}={encoded}')
            else:
                resp = self._post(self.SEARCH_URL, {self.SEARCH_PARAM: keyword})
            page = self._parse_html(resp)

            results = []
            seen_ids = set()
            # 搜索结果中的书籍链接
            links = page.css('a[href]')
            for link in links:
                href = link.attrib.get('href', '')
                nid = self._extract_novel_id_from_url(href)
                if not nid or nid in seen_ids:
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

    # ===================== 排行榜/分类 =====================

    # 子类可覆盖：排行榜页面 URL（{page} 占位）
    RANKING_URL: Optional[str] = None
    # 子类可覆盖：排行榜条目选择器
    RANKING_ITEM_SELECTOR: str = '.rank-list a, .rank a, .hot-list a, .book-list a, ul.list a'
    # 子类可覆盖：分类列表
    CATEGORIES: list = []

    def get_rankings(self, category: str = 'all', page: int = 1) -> list[NovelInfo]:
        """获取排行榜小说（如果配置了 RANKING_URL）"""
        if not self.RANKING_URL:
            return []
        try:
            url = self.RANKING_URL.format(page=page, category=category)
            resp = self._fetch(url)
            page_sel = self._parse_html(resp)

            results = []
            seen_ids = set()
            links = page_sel.css(self.RANKING_ITEM_SELECTOR)
            for link in links:
                href = link.attrib.get('href', '')
                nid = self._extract_novel_id_from_url(href)
                if not nid or nid in seen_ids:
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
                if len(results) >= 30:
                    break
            return results
        except Exception as e:
            print(f'[{self.display_name}] 获取排行榜出错: {e}')
            return []

    def get_categories(self) -> list[dict]:
        """返回支持的分类列表"""
        return [{'key': c[0], 'name': c[1]} for c in self.CATEGORIES] if self.CATEGORIES else []


# ============================================================
# 顶点小说 (23wxx.net)
# ============================================================

class DingdianSource(ConfigurableSource):
    """顶点小说源 (23wxx.net)"""

    name = 'dingdian'
    display_name = '顶点小说'
    MIRRORS = ['https://www.23wxx.net']
    ENCODING = 'utf-8'

    URL_PATTERN = re.compile(r'/xs/(\d+)')
    BOOK_URL_TEMPLATE = '/xs/{novel_id}/'
    CHAPTER_URL_TEMPLATE = '/xs/{novel_id}/{chapter_id}.html'
    CHAPTER_LIST_URL_TEMPLATE = None  # 与书籍页相同

    CHAPTER_LIST_SELECTOR = '#list dd a, .box_con dd a, dd a'
    CHAPTER_LINK_PATTERN = re.compile(r'/xs/\d+/(\d+)\.html')
    CONTENT_SELECTOR = '#content'
    TITLE_SELECTOR = 'h1::text'
    USE_OG_META = True

    # 搜索接口参数名是反爬的 369koolearn，实测无效，置 None 依赖 Bing
    SEARCH_URL = None


# ============================================================
# 笔下文学 (bxwxber.cc) - GBK 编码
# ============================================================

class BxwxSource(ConfigurableSource):
    """笔下文学源 (bxwxber.cc) - GBK 编码"""

    name = 'bxwx'
    display_name = '笔下文学'
    MIRRORS = ['https://www.bxwxber.cc']
    ENCODING = 'gbk'

    # URL: /book/{cat}/{id}/  -> novel_id = "cat/id"
    URL_PATTERN = re.compile(r'/book/(\d+/\d+)')
    BOOK_URL_TEMPLATE = '/book/{novel_id}/'
    CHAPTER_URL_TEMPLATE = '/book/{novel_id}/{chapter_id}.html'
    CHAPTER_LIST_URL_TEMPLATE = None

    CHAPTER_LIST_SELECTOR = '.listmain dd a, dd a'
    CHAPTER_LINK_PATTERN = re.compile(r'/book/\d+/\d+/(\d+)\.html')
    CONTENT_SELECTOR = '#content'
    TITLE_SELECTOR = 'h1::text'
    USE_OG_META = True

    SEARCH_URL = None  # 未确认可用搜索接口

    @staticmethod
    def parse_novel_url(url_or_id: str) -> Optional[str]:
        """笔下文学 URL: /book/{cat}/{id}/ -> "cat/id" """
        if not url_or_id:
            return None
        s = str(url_or_id).strip()
        if re.match(r'^\d+/\d+$', s):
            return s
        m = re.search(r'/book/(\d+/\d+)', s)
        if m:
            return m.group(1)
        return None


# ============================================================
# 铅笔小说 (23qb.net)
# ============================================================

class QianbiSource(ConfigurableSource):
    """铅笔小说源 (23qb.net) - 章节列表在 /catalog 独立页面"""

    name = 'qianbi'
    display_name = '铅笔小说'
    MIRRORS = ['https://www.23qb.net']
    ENCODING = 'utf-8'

    URL_PATTERN = re.compile(r'/book/(\d+)')
    BOOK_URL_TEMPLATE = '/book/{novel_id}/'
    CHAPTER_URL_TEMPLATE = '/book/{novel_id}/{chapter_id}.html'
    # 章节列表在独立页面
    CHAPTER_LIST_URL_TEMPLATE = '/book/{novel_id}/catalog'

    CHAPTER_LIST_SELECTOR = '.module-row-text, .module-row-info a'
    CHAPTER_LINK_PATTERN = re.compile(r'/book/\d+/(\d+)\.html')
    CONTENT_SELECTOR = '.article-content'
    TITLE_SELECTOR = 'h1::text'
    USE_OG_META = True

    # 铅笔小说搜索可用
    SEARCH_URL = '/search.html'
    SEARCH_METHOD = 'GET'
    SEARCH_PARAM = 'searchkey'

    @staticmethod
    def parse_novel_url(url_or_id: str) -> Optional[str]:
        if not url_or_id:
            return None
        s = str(url_or_id).strip()
        if re.match(r'^\d+$', s):
            return s
        m = re.search(r'/book/(\d+)', s)
        if m:
            return m.group(1)
        return None


# ============================================================
# 海棠文学 (htwenxe.com) - 杰奇 CMS，无 og:meta
# ============================================================

class HaitangSource(ConfigurableSource):
    """海棠文学源 (htwenxe.com) - 杰奇 CMS"""

    name = 'haitang'
    display_name = '海棠文学'
    MIRRORS = ['https://m.htwenxe.com', 'https://www.htwenxe.com']
    ENCODING = 'utf-8'

    URL_PATTERN = re.compile(r'/book/(\d+)')
    BOOK_URL_TEMPLATE = '/book/{novel_id}'
    CHAPTER_URL_TEMPLATE = '/book/{novel_id}/{chapter_id}.html'
    CHAPTER_LIST_URL_TEMPLATE = '/index/{novel_id}/asc/1.html'

    CHAPTER_LIST_SELECTOR = '.main a, dd a, li a'
    CHAPTER_LINK_PATTERN = re.compile(r'/book/\d+/(\d+)\.html')
    CONTENT_SELECTOR = '#acontent'
    TITLE_SELECTOR = 'h1::text'
    USE_OG_META = False  # 杰奇 CMS 无 og:meta

    SEARCH_URL = '/modules/article/search.php'
    SEARCH_METHOD = 'GET'
    SEARCH_PARAM = 'searchkey'

    @staticmethod
    def parse_novel_url(url_or_id: str) -> Optional[str]:
        if not url_or_id:
            return None
        s = str(url_or_id).strip()
        if re.match(r'^\d+$', s):
            return s
        m = re.search(r'/book/(\d+)', s)
        if m:
            return m.group(1)
        return None
