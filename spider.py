# -*- coding: utf-8 -*-
"""
番茄小说爬虫模块 - 整合 NovelAPIManager
支持通过 API 下载小说，无需字体解密
"""

import requests
import time
import re
import json
import uuid
import random
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from config import (
    FANQIE_BASE_URL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    COOKIES,
    BASE_DIR
)
from font_decrypt import FontDecryptor
import urllib3
from typing import Optional, Dict, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 禁用 urllib3 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API 配置
API_CONFIG = {
    "endpoints": {
        "search": "/api/search",
        "detail": "/api/detail",
        "book": "/api/book",
        "directory": "/api/directory",
        "content": "/api/content",
        "chapter": "/api/chapter",
    },
    "api_sources": [
        {"base_url": "https://qkfqapi.vv9v.cn", "supports_full_download": True},
        {"base_url": "http://49.232.137.12", "supports_full_download": True},
        {"base_url": "https://bk.yydjtc.cn", "supports_full_download": True},
        {"base_url": "http://103.236.91.147:9999", "supports_full_download": False},
        {"base_url": "http://43.248.77.205:22222", "supports_full_download": True},
        {"base_url": "http://47.108.80.161:5005", "supports_full_download": True},
        {"base_url": "https://fq.shusan.cn", "supports_full_download": True},
        {"base_url": "http://101.35.133.34:5000", "supports_full_download": True}
    ],
    "max_retries": 3,
    "request_timeout": 30,
    "connection_pool_size": 10,
}


def get_api_headers():
    """获取 API 请求头（模拟真实客户端）"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://fanqienovel.com/',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }


class NovelAPIManager:
    """小说 API 管理器"""

    def __init__(self):
        self.endpoints = API_CONFIG["endpoints"]
        self._session = None
        # 选择最优节点（优先使用支持批量下载的节点）
        self.base_url = self._get_optimal_node()

    def _get_optimal_node(self) -> str:
        """自动选择支持批量下载的节点"""
        full_nodes = []
        other_nodes = []
        for source in API_CONFIG.get("api_sources", []):
            if isinstance(source, dict):
                base = (source.get("base_url") or "").strip().rstrip('/')
                supports_full = source.get("supports_full_download", True)
                if base:
                    (full_nodes if supports_full else other_nodes).append(base)
            elif isinstance(source, str):
                base = str(source).strip().rstrip('/')
                if base:
                    other_nodes.append(base)
        
        if full_nodes:
            return full_nodes[0]
        if other_nodes:
            return other_nodes[0]
        return ""

    def _build_candidate_list(self, full_nodes: list, other_nodes: list) -> List[str]:
        """将分类后的节点列表组装为候选列表"""
        candidates = []
        current = (self.base_url or "").strip().rstrip('/')
        if current:
            if current in full_nodes:
                candidates.append(current)
                full_nodes.remove(current)
            elif current in other_nodes:
                candidates.append(current)
                other_nodes.remove(current)
        candidates.extend(full_nodes)
        candidates.extend(other_nodes)
        return candidates

    def _candidate_base_urls(self) -> List[str]:
        """返回候选 API 节点列表"""
        full_nodes = []
        other_nodes = []
        for source in API_CONFIG.get("api_sources", []):
            if isinstance(source, dict):
                base = (source.get("base_url") or "").strip().rstrip('/')
                supports_full = source.get("supports_full_download", True)
                if base:
                    (full_nodes if supports_full else other_nodes).append(base)
            elif isinstance(source, str):
                base = str(source).strip().rstrip('/')
                if base:
                    other_nodes.append(base)
        
        return self._build_candidate_list(full_nodes, other_nodes)

    def _switch_base_url(self, base_url: str):
        """切换当前生效节点"""
        normalized = (base_url or "").strip().rstrip('/')
        if not normalized:
            return
        self.base_url = normalized

    def _request_with_failover(self, endpoint: str, params: Dict) -> Optional[requests.Response]:
        """同步请求（自动故障切换 API 节点）"""
        last_exception = None
        timeout = API_CONFIG["request_timeout"]
        candidates = self._candidate_base_urls()

        for index, base in enumerate(candidates, start=1):
            url = f"{base}{endpoint}"
            try:
                response = self._get_session().get(
                    url,
                    params=params,
                    headers=get_api_headers(),
                    timeout=timeout
                )

                # 成功返回时，记住该可用节点
                if response.status_code == 200:
                    if base != self.base_url:
                        self._switch_base_url(base)
                    return response

                # 5xx 视为节点故障，尝试下一个
                if response.status_code >= 500:
                    continue

                # 4xx 等业务错误直接返回，避免误切换
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                continue
            except requests.RequestException as e:
                last_exception = e
                continue

        if last_exception:
            raise last_exception
        return None

    def _get_session(self) -> requests.Session:
        """获取同步HTTP会话"""
        if self._session is None:
            self._session = requests.Session()
            retries = Retry(
                total=API_CONFIG.get("max_retries", 3),
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "POST"),
                raise_on_status=False,
            )
            pool_size = API_CONFIG.get("connection_pool_size", 10)
            adapter = HTTPAdapter(
                pool_connections=pool_size,
                pool_maxsize=pool_size,
                max_retries=retries,
                pool_block=False
            )
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            self._session.headers.update({'Connection': 'keep-alive'})
        return self._session

    def get_book_detail(self, book_id: str) -> Optional[Dict]:
        """获取书籍详情"""
        try:
            params = {"book_id": book_id}
            response = self._request_with_failover(self.endpoints['detail'], params)
            if response is None:
                return None

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    level1_data = data["data"]
                    # 检查是否有错误信息（如书籍下架）
                    if isinstance(level1_data, dict):
                        inner_msg = level1_data.get("message", "")
                        inner_code = level1_data.get("code")
                        if inner_msg == "BOOK_REMOVE" or inner_code == 101109:
                            return {"_error": "BOOK_REMOVE", "_message": "书籍已下架"}
                        if "data" in level1_data:
                            inner_data = level1_data["data"]
                            if isinstance(inner_data, dict) and not inner_data and inner_msg:
                                return {"_error": inner_msg, "_message": inner_msg}
                            return inner_data
                    return level1_data
        except Exception as e:
            print(f"获取书籍详情失败: {str(e)}")
        return None

    def get_chapter_list(self, book_id: str) -> Optional[List[Dict]]:
        """获取章节列表"""
        try:
            params = {"book_id": book_id}
            response = self._request_with_failover(self.endpoints['book'], params)
            if response is None:
                return None

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    level1_data = data["data"]
                    if isinstance(level1_data, dict) and "data" in level1_data:
                        return level1_data["data"]
                    return level1_data
        except Exception as e:
            print(f"获取章节列表失败: {str(e)}")
        return None

    def get_chapter_content(self, item_id: str) -> Optional[Dict]:
        """获取章节内容（无水印）"""
        try:
            # 优先使用简化的 /api/chapter 接口
            chapter_endpoint = self.endpoints.get('chapter', '/api/chapter')
            params = {"item_id": item_id}
            response = self._request_with_failover(chapter_endpoint, params)
            if response is None:
                return None

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    # 返回原始内容，不添加水印
                    return data["data"]

            # 回退到 /api/content 接口
            params = {"tab": "小说", "item_id": item_id}
            response = self._request_with_failover(self.endpoints['content'], params)
            if response is None:
                return None

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    # 返回原始内容，不添加水印
                    return data["data"]
        except Exception as e:
            print(f"获取章节内容失败: {str(e)}")
        return None


class FanqieSpider:
    def __init__(self, use_api=True):
        """
        初始化爬虫
        
        Args:
            use_api: 是否使用 API 下载（默认 True）
        """
        self.use_api = use_api
        
        if self.use_api:
            # 使用 API 下载
            self.api_manager = NovelAPIManager()
            print("✓ 使用 API 模式下载（无需字体解密）")
        else:
            # 使用官网爬取
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
            import os
            font_cache_dir = os.path.join(BASE_DIR, 'font_cache')
            self.decryptor = FontDecryptor(font_cache_dir)
            self.current_mapping = {}  # 按小说ID缓存字体映射
            self.login_aid = '1768'  # 默认aid
            self.login_device_id = ''  # 默认device_id
            print("✓ 使用官网爬取模式")

    def _request(self, url, method='GET', params=None, data=None, headers=None):
        """发送HTTP请求，带重试机制和随机延迟"""
        for attempt in range(MAX_RETRIES):
            try:
                if headers:
                    self.session.headers.update(headers)

                if method == 'GET':
                    response = self.session.get(
                        url,
                        params=params,
                        cookies=COOKIES,
                        timeout=REQUEST_TIMEOUT
                    )
                else:
                    response = self.session.post(
                        url,
                        json=data,
                        cookies=COOKIES,
                        timeout=REQUEST_TIMEOUT
                    )
                
                response.raise_for_status()
                
                # 使用随机延迟，避免固定间隔被检测为爬虫
                import random
                delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                time.sleep(delay)
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    # 重试时使用指数退避策略
                    backoff_delay = (2 ** attempt) + random.uniform(0.5, 1.5)
                    print(f"等待 {backoff_delay:.1f} 秒后重试...")
                    time.sleep(backoff_delay)
                    if self.ua:
                        try:
                            self.session.headers['User-Agent'] = self.ua.random
                        except Exception:
                            self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                else:
                    raise

    def get_novel_info(self, novel_url):
        """获取小说基本信息"""
        if self.use_api:
            # 使用 API 获取
            return self._get_novel_info_api(novel_url)
        else:
            # 使用官网爬取
            return self._get_novel_info_web(novel_url)

    def _get_novel_info_api(self, novel_url):
        """通过 API 获取小说信息"""
        try:
            # 从URL提取小说ID
            novel_id = novel_url.strip().strip('/')
            if '/page/' in novel_url:
                novel_id = novel_url.split('/page/')[-1]
            
            print(f"正在获取小说信息（API）: {novel_id}")
            
            result = self.api_manager.get_book_detail(novel_id)
            if not result or result.get('_error'):
                print(f"获取小说信息失败: {result.get('_message', '未知错误') if result else '返回为空'}")
                return None
            
            return {
                'novel_id': str(result.get('book_id', novel_id)),
                'title': result.get('book_name', ''),
                'author': result.get('author', ''),
                'description': result.get('abstract', ''),
                'cover_url': result.get('thumb_url', ''),
                'word_count': int(result.get('word_count', 0)),
                'chapter_count': int(result.get('chapter_count', 0))
            }
        except Exception as e:
            print(f"获取小说信息时出错: {e}")
            return None

    def _get_novel_info_web(self, novel_url):
        """通过官网爬取获取小说信息"""
        try:
            # 从URL提取小说ID
            novel_id = novel_url.strip().strip('/')
            if '/page/' in novel_url:
                novel_id = novel_url.split('/page/')[-1]
            
            print(f"正在获取小说信息（官网）: {novel_id}")
            
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
        """获取章节列表"""
        if self.use_api:
            # 使用 API 获取
            return self._get_chapter_list_api(novel_id)
        else:
            # 使用官网爬取
            return self._get_chapter_list_web(novel_id)

    def _get_chapter_list_api(self, novel_id):
        """通过 API 获取章节列表"""
        try:
            print(f"正在获取章节列表（API）: {novel_id}")
            
            result = self.api_manager.get_chapter_list(novel_id)
            if not result:
                print(f"获取章节列表失败: 返回为空")
                return None
            
            chapters = []
            if isinstance(result, dict):
                all_item_ids = result.get("allItemIds", [])
                chapter_list = result.get("chapterListWithVolume", [])
                
                if chapter_list:
                    idx = 1
                    for volume in chapter_list:
                        if isinstance(volume, list):
                            for ch in volume:
                                if isinstance(ch, dict):
                                    item_id = ch.get("itemId") or ch.get("item_id")
                                    title = ch.get("title", f"第{idx}章")
                                    if item_id:
                                        chapters.append({
                                            'chapter_id': str(item_id),
                                            'chapter_title': title,
                                            'chapter_index': idx
                                        })
                                        idx += 1
                elif all_item_ids:
                    for idx, item_id in enumerate(all_item_ids, 1):
                        chapters.append({
                            'chapter_id': str(item_id),
                            'chapter_title': f'第{idx}章',
                            'chapter_index': idx
                        })
            elif isinstance(result, list):
                for idx, ch in enumerate(result, 1):
                    item_id = ch.get("item_id") or ch.get("chapter_id")
                    title = ch.get("title", f"第{idx}章")
                    if item_id:
                        chapters.append({
                            'chapter_id': str(item_id),
                            'chapter_title': title,
                            'chapter_index': idx
                        })
            
            if chapters:
                print(f"获取章节列表成功: {len(chapters)} 个章节")
            else:
                print(f"获取章节列表失败: 未找到章节")
            
            return chapters
        except Exception as e:
            print(f"获取章节列表时出错: {e}")
            return None

    def _get_chapter_list_web(self, novel_id):
        """通过官网爬取获取章节列表（参考博客优化，使用正则表达式提取章节ID）"""
        try:
            print(f"正在获取章节列表（官网）: {novel_id}")
            
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
        """获取章节内容"""
        if self.use_api:
            # 使用 API 获取（无需字体解密）
            return self._get_chapter_content_api(novel_id, chapter_id)
        else:
            # 使用官网爬取（需要字体解密）
            return self._get_chapter_content_web(novel_id, chapter_id)

    def _get_chapter_content_api(self, novel_id, chapter_id):
        """通过 API 获取章节内容（无需字体解密）"""
        try:
            result = self.api_manager.get_chapter_content(chapter_id)
            if not result:
                return None
            
            return {
                'title': result.get('title', ''),
                'content': result.get('content', '')
            }
        except Exception as e:
            print(f"获取章节内容失败: {e}")
            return None

    def _get_chapter_content_web(self, novel_id, chapter_id):
        """通过官网爬取获取章节内容（参考博客优化，使用parsel库）"""
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
            
            # 如果没有找到标题，检查是什么情况
            if not title:
                # 检查页面是否包含人机验证的特征
                page_text = html.lower()
                page_title = selector.css('title::text').get() or ''
                
                # 保存HTML用于调试
                debug_file = f'debug_chapter_{chapter_id}.html'
                try:
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                    print(f"章节 {chapter_id} 调试信息已保存到: {debug_file}")
                except:
                    pass
                
                # 检查是否可能是人机验证或拦截页面
                captcha_keywords = ['验证', '安全', '人机', 'captcha', 'verify', 'security', 'robot', '拦截', '禁止访问']
                is_intercepted = any(keyword in page_text for keyword in captcha_keywords) or \
                                any(keyword in page_title.lower() for keyword in captcha_keywords) or \
                                '验证' in html or '安全验证' in html or '人机验证' in html or \
                                '访问被拒绝' in html or 'Access Denied' in html
                
                # 检查页面长度是否过短（可能是错误页面）
                page_too_short = len(html) < 1000
                
                if is_intercepted:
                    print(f"章节 {chapter_id} 检测到拦截页面（可能需要人机验证或Cookie失效）")
                    print(f"  页面标题: {page_title}")
                    return {
                        'captcha_required': True,
                        'captcha_url': url,
                        'message': '请求被拦截，可能需要人机验证或Cookie已失效',
                        'debug_file': debug_file
                    }
                elif page_too_short:
                    print(f"章节 {chapter_id} 返回页面内容过短（可能请求失败）")
                    print(f"  页面长度: {len(html)} 字符")
                    print(f"  页面内容: {html[:200]}")
                    return {
                        'error': '页面内容过短',
                        'page_length': len(html),
                        'debug_file': debug_file
                    }
                else:
                    print(f"章节 {chapter_id} 未找到标题（页面结构可能已改变）")
                    print(f"  页面标题: {page_title}")
                    print(f"  页面长度: {len(html)} 字符")
                    return {
                        'error': '未找到章节标题',
                        'page_title': page_title,
                        'debug_file': debug_file
                    }
            
            # 生成或获取字体映射（按小说ID缓存）
            if novel_id not in self.current_mapping:
                self.current_mapping[novel_id] = self.decryptor.decrypt_from_html(html)
            
            # 解析正文内容
            content_list = selector.css('.muye-reader-content p::text').getall()
            # 确保所有元素都是字符串
            content_list = [str(c) if c is not None else '' for c in content_list]
            content = '\n\n'.join(content_list)
            
            # 检查内容是否为空
            if not content or len(content.strip()) < 50:
                print(f"章节 {chapter_id} 内容为空或过短")
                return {
                    'error': '章节内容为空或过短',
                    'content_length': len(content)
                }
            
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
            import traceback
            traceback.print_exc()
            return None

    def send_verification_code(self, phone):
        """发送验证码（仅官网模式）"""
        if self.use_api:
            print("API 模式不支持发送验证码")
            return {'success': False, 'message': 'API 模式不支持此功能'}
        
        try:
            # 番茄小说验证码发送API - 尝试多种aid值
            aid_list = ['1768', '6383', '1128', '2904']
            
            import uuid
            device_id = str(uuid.uuid4())
            
            headers = {
                'Content-Type': 'application/json',
                'Referer': 'https://fanqienovel.com/',
                'Origin': 'https://fanqienovel.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            for aid in aid_list:
                url = f"https://novel.snssdk.com/passport/account/send_sms_code/?aid={aid}"
                
                data = {
                    'mobile': phone,
                    'device_id': device_id,
                    'os': 'web',
                    'type': 'login',
                }
                
                print(f"尝试 aid={aid}, 发送验证码请求: {data}")
                response = self.session.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
                print(f"响应状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        print(f"解析结果: {result}")
                        
                        # 检查是否成功
                        error_code = result.get('data', {}).get('error_code', -1)
                        description = result.get('data', {}).get('description', '')
                        
                        if error_code == 0:
                            # 成功，保存aid用于后续登录
                            self.login_aid = aid
                            self.login_device_id = device_id
                            return {'success': True, 'message': '验证码已发送'}
                        elif '非法应用' not in description:
                            # 不是非法应用错误，可能是其他错误，直接返回
                            return {'success': False, 'message': description}
                    except:
                        pass
                
                # 继续尝试下一个aid
            
            return {'success': False, 'message': '所有aid都返回错误，请使用Cookie登录方式'}
                
        except Exception as e:
            print(f"发送验证码时出错: {e}")
            return {'success': False, 'message': f'网络错误: {str(e)}'}

    def login_with_verification_code(self, phone, code):
        """使用验证码登录（仅官网模式）"""
        if self.use_api:
            print("API 模式不支持验证码登录")
            return {'success': False, 'message': 'API 模式不支持此功能'}
        
        try:
            # 获取之前保存的aid和device_id
            aid = getattr(self, 'login_aid', '1768')
            device_id = getattr(self, 'login_device_id', str(uuid.uuid4()))
            
            url = f"https://novel.snssdk.com/passport/account/login/?aid={aid}"
            headers = {
                'Content-Type': 'application/json',
                'Referer': 'https://fanqienovel.com/',
                'Origin': 'https://fanqienovel.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            data = {
                'mobile': phone,
                'code': code,
                'device_id': device_id,
                'os': 'web',
            }
            
            print(f"登录请求: {data}, aid={aid}")
            response = self.session.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
            print(f"登录响应状态码: {response.status_code}")
            print(f"登录响应内容: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            print(f"登录解析结果: {result}")
            
            if result.get('errno', -1) == 0 or result.get('code', -1) == 0 or result.get('data', {}).get('error_code') == 0:
                # 提取Cookie
                cookies_dict = {}
                for cookie in self.session.cookies:
                    cookies_dict[cookie.name] = cookie.value
                
                return {
                    'success': True,
                    'message': '登录成功',
                    'cookies': cookies_dict,
                    'user_info': result.get('data', {})
                }
            else:
                error_msg = result.get('data', {}).get('description', result.get('errmsg', result.get('message', '登录失败')))
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            print(f"验证码登录时出错: {e}")
            return {'success': False, 'message': f'网络错误: {str(e)}'}

    def search_novel(self, keyword):
        """搜索小说（仅官网模式）"""
        if self.use_api:
            print("API 模式不支持搜索功能")
            return []
        
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
