# 番茄小说爬虫模块
import requests
import time
import re
import json
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from config import (
    FANQIE_BASE_URL, 
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    REQUEST_DELAY
)
from font_decrypt import FontDecryptor


class FanqieSpider:
    def __init__(self):
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })
        self.decryptor = FontDecryptor()
        self.current_mapping = {}  # 按小说ID缓存字体映射

    def _request(self, url, method='GET', params=None, data=None, headers=None):
        """发送HTTP请求，带重试机制"""
        for attempt in range(MAX_RETRIES):
            try:
                if headers:
                    self.session.headers.update(headers)
                
                if method == 'GET':
                    response = self.session.get(
                        url, 
                        params=params, 
                        timeout=REQUEST_TIMEOUT
                    )
                else:
                    response = self.session.post(
                        url, 
                        json=data, 
                        timeout=REQUEST_TIMEOUT
                    )
                
                response.raise_for_status()
                time.sleep(REQUEST_DELAY)
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    if self.ua:
                        try:
                            self.session.headers['User-Agent'] = self.ua.random
                        except Exception:
                            self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                else:
                    raise

    def get_novel_info(self, novel_url):
        """获取小说基本信息"""
        try:
            # 从URL提取小说ID
            # 番茄小说URL格式: https://fanqienovel.com/page/小说ID
            novel_id = novel_url.strip().strip('/')
            if '/page/' in novel_id:
                novel_id = novel_id.split('/page/')[-1]
            
            print(f"正在获取小说信息: {novel_id}")
            
            # 直接访问小说页面
            page_url = f"{FANQIE_BASE_URL}/page/{novel_id}"
            response = self._request(page_url)
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 提取小说信息
            title = ''
            author = ''
            description = ''
            cover_url = ''
            word_count = 0
            chapter_count = 0
            
            # 尝试从页面提取数据
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'window.__INITIAL_STATE__' in script.string:
                    # 提取JSON数据
                    json_str = script.string.strip()
                    
                    # 处理可能存在的 IIFE 包装
                    if 'window.__INITIAL_STATE__=' in json_str:
                        # 提取等号后的内容
                        json_str = json_str.split('window.__INITIAL_STATE__=', 1)[1]
                    
                    # 使用栈结构找到完整的 JSON 对象
                    start_idx = json_str.find('{')
                    if start_idx != -1:
                        stack = 0
                        end_idx = -1
                        for i in range(start_idx, len(json_str)):
                            if json_str[i] == '{':
                                stack += 1
                            elif json_str[i] == '}':
                                stack -= 1
                                if stack == 0:
                                    end_idx = i
                                    break
                        
                        if end_idx != -1:
                            json_str = json_str[start_idx:end_idx + 1]
                    
                    try:
                        data = json.loads(json_str)
                        # 小说信息在 page 键中，而不是 book 键
                        if 'page' in data:
                            page_info = data['page']
                            title = page_info.get('bookName', '')
                            author = page_info.get('authorName', '')
                            description = page_info.get('abstract', '')
                            cover_url = page_info.get('thumbUri', '')
                            word_count = page_info.get('wordNumber', 0)
                            chapter_count = page_info.get('chapterTotal', 0)
                    except Exception as e:
                        print(f"JSON 解析失败: {e}")
                    break
            
            # 如果JSON提取失败，尝试HTML解析
            if not title:
                title_tag = soup.find('h1')
                if title_tag:
                    title = title_tag.get_text(strip=True)
            
            if not author:
                author_tag = soup.find('span', class_='author-name-text')
                if author_tag:
                    author = author_tag.get_text(strip=True)
            
            if not description:
                desc_tag = soup.find('div', class_='abstract')
                if desc_tag:
                    description = desc_tag.get_text(strip=True)
            
            if title:
                return {
                    'novel_id': novel_id,
                    'title': title,
                    'author': author,
                    'description': description,
                    'cover_url': cover_url,
                    'word_count': word_count,
                    'chapter_count': chapter_count
                }
            else:
                print(f"获取小说信息失败: 无法解析页面")
                return None
                
        except Exception as e:
            print(f"获取小说信息时出错: {e}")
            return None

    def get_chapter_list(self, novel_id):
        """获取章节列表（参考博客优化，使用正则表达式提取章节ID）"""
        try:
            print(f"正在获取章节列表: {novel_id}")
            
            page_url = f"{FANQIE_BASE_URL}/page/{novel_id}"
            response = self._request(page_url)
            
            link_data = response.text
            
            # 使用正则表达式提取章节ID列表（参考博客实现）
            chapter_id_list = re.findall(r'<a href="/reader/(\d+)" class="chapter-item-title"', link_data)[1:]
            
            chapters = []
            for idx, chapter_id in enumerate(chapter_id_list):
                chapters.append({
                    'chapter_id': chapter_id,
                    'chapter_title': f'第{idx+1}章',
                    'chapter_index': idx + 1
                })
            
            if chapters:
                print(f"获取到 {len(chapters)} 个章节")
            else:
                print(f"获取章节列表失败: 未找到章节")
            
            return chapters
            
        except Exception as e:
            print(f"获取章节列表时出错: {e}")
            return []

    def get_chapter_content(self, novel_id, chapter_id):
        """获取章节内容（参考博客优化，使用parsel库）"""
        try:
            import parsel
            
            url = f'https://fanqienovel.com/reader/{chapter_id}'
            
            try:
                response = self._request(url)
                response.raise_for_status()
                html = response.text
            except Exception as e:
                print(f"章节 {chapter_id} 获取失败: {str(e)}")
                return None
            
            # 使用parsel解析页面
            selector = parsel.Selector(html)
            
            # 解析章节标题
            title = selector.css('.muye-reader-title::text').get()
            if not title:
                print(f"章节 {chapter_id} 未找到标题，跳过...")
                return None
            
            # 生成或获取字体映射（按小说ID缓存）
            if novel_id not in self.current_mapping:
                self.current_mapping[novel_id] = self.decryptor.decrypt_from_html(html)
            
            # 解析正文内容
            content_list = selector.css('.muye-reader-content p::text').getall()
            # 确保所有元素都是字符串
            content_list = [str(c) if c is not None else '' for c in content_list]
            content = '\n\n'.join(content_list)
            
            # 解密内容
            new_content = self.decryptor.change(content, self.current_mapping[novel_id])
            # 确保返回的是字符串
            new_content = str(new_content) if new_content is not None else ''
            
            # 返回标题和内容
            return {
                'title': str(title) if title else '',
                'content': new_content
            }
                
        except Exception as e:
            print(f"获取章节内容时出错: {e}")
            return None

    def search_novel(self, keyword):
        """搜索小说"""
        try:
            print(f"正在搜索: {keyword}")
            
            search_url = f"{FANQIE_BASE_URL}/search?keyword={keyword}"
            response = self._request(search_url)
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            results = []
            
            # 尝试从JSON数据获取搜索结果
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'window.__INITIAL_STATE__' in script.string:
                    json_str = script.string.strip()
                    json_str = json_str.replace('window.__INITIAL_STATE__ = ', '')
                    json_str = json_str.rstrip(';')
                    try:
                        data = json.loads(json_str)
                        if 'search' in data and 'bookList' in data['search']:
                            book_list = data['search']['bookList']
                            for book in book_list:
                                results.append({
                                    'novel_id': book.get('bookId', ''),
                                    'title': book.get('bookName', ''),
                                    'author': book.get('authorName', ''),
                                    'description': book.get('abstract', ''),
                                    'cover_url': book.get('cover', ''),
                                    'word_count': book.get('wordCount', 0)
                                })
                    except:
                        pass
                    break
            
            # 如果JSON提取失败，尝试HTML解析
            if not results:
                book_items = soup.find_all('div', class_='book-item')
                for item in book_items:
                    title_tag = item.find('h3') or item.find('a', class_='book-title')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        author_tag = item.find('span', class_='author') or item.find('a', class_='author-name')
                        author = author_tag.get_text(strip=True) if author_tag else ''
                        link_tag = item.find('a', href=re.compile(r'/page/'))
                        novel_id = link_tag.get('href', '').split('/')[-1] if link_tag else ''
                        
                        if title and novel_id:
                            results.append({
                                'novel_id': novel_id,
                                'title': title,
                                'author': author,
                                'description': '',
                                'cover_url': '',
                                'word_count': 0
                            })
            
            return results
            
        except Exception as e:
            print(f"搜索小说时出错: {e}")
            return []


def parse_novel_url(url):
    """解析小说URL，提取小说ID"""
    url = url.strip()
    # 支持多种URL格式
    patterns = [
        r'/page/(\d+)',
        r'book_id=(\d+)',
        r'^(\d+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None