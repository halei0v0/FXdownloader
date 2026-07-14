# -*- coding: utf-8 -*-
"""
FXdownloader WebUI - pywebview 后端桥接模块

通过 pywebview 将 Python 后端方法暴露给 JavaScript 前端。
启动本地 HTTP 服务器提供 index.html，并在后台线程中运行下载任务。
"""
import os
import sys
import json
import time
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 确保能导入项目根目录的模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import webview  # noqa: E402
from sources import get_source, list_sources, NovelInfo, ChapterInfo  # noqa: E402
from sources.bing_search import search_via_bing  # noqa: E402
from sources.multi_source import (
    search_all_sources,
    find_novel_in_all_sources,
    SOURCE_DISPLAY_NAMES,
)  # noqa: E402
import config as app_config  # noqa: E402


class Api:
    """暴露给 JavaScript 前端的 Python API 类"""

    def __init__(self, window=None):
        self._window = window
        self._cancel_event = threading.Event()
        self._download_thread = None
        self._source_cache = {}  # 缓存源实例 {source_key: source_instance}

    # ============== 源管理 ==============

    def _get_source(self, source_key='biquge'):
        """根据前端 source_key 获取对应的源实例（带缓存）"""
        if source_key in self._source_cache:
            return self._source_cache[source_key]

        if source_key == 'fanqie_api':
            source = get_source('fanqie', use_api=True)
        elif source_key == 'fanqie_official':
            cookies = app_config.load_cookies()
            source = get_source('fanqie', use_api=False, cookies=cookies)
        elif source_key in ('biquge', 'dingdian', 'bxwx', 'qianbi', 'haitang'):
            source = get_source(source_key)
        else:
            return None

        self._source_cache[source_key] = source
        return source

    def list_sources(self):
        """返回可用的源名称列表（前端格式）"""
        return [
            {'key': 'biquge', 'name': '蚂蚁文学'},
            {'key': 'dingdian', 'name': '顶点小说'},
            {'key': 'bxwx', 'name': '笔下文学'},
            {'key': 'qianbi', 'name': '铅笔小说'},
            {'key': 'haitang', 'name': '海棠文学'},
            {'key': 'fanqie_api', 'name': '番茄小说 (API)'},
            {'key': 'fanqie_official', 'name': '番茄官网'},
        ]

    # ============== 搜索 ==============

    def search(self, keyword, source_key='biquge'):
        """多源自动搜索（不需要切换模式，直接给出所有可用结果）

        并发调用 Bing 搜索 + 各源自身搜索，聚合去重后返回多源结果。

        Args:
            keyword: 搜索关键词或URL
            source_key: 保留参数（多源搜索时忽略，自动选取所有源）

        Returns:
            list[dict] 或 dict with 'error' key
        """
        try:
            # 先尝试解析为 URL（如果是某源支持的 URL，直接解析）
            url_guess = self._try_parse_url(keyword)
            if url_guess:
                return [url_guess]

            # 多源自动搜索
            results = search_all_sources(keyword, include_fanqie=True)
            return results

        except Exception as e:
            print(f'[WebUI] 搜索失败: {e}')
            return {'error': str(e)}

    def _try_parse_url(self, url_or_id: str) -> Optional[dict]:
        """尝试用各源解析 URL，成功则返回小说信息字典

        仅对真正的 URL（含 http/路径）尝试解析，纯数字/纯文本交给搜索处理。
        """
        s = str(url_or_id).strip()
        if not s or not ('/' in s or s.startswith('http')):
            # 纯数字或纯文本不是 URL，交给搜索
            return None

        # 尝试每个源（URL 通常只匹配一个源的 URL_PATTERN）
        source_keys = ['biquge', 'dingdian', 'bxwx', 'qianbi', 'haitang', 'fanqie']
        for sk in source_keys:
            try:
                source = self._get_source(sk)
                if not source:
                    continue
                novel_id = source.parse_novel_url(s)
                if novel_id:
                    info = source.get_novel_info(novel_id)
                    if info:
                        d = self._novel_info_to_dict(info)
                        d['source_name'] = SOURCE_DISPLAY_NAMES.get(sk, sk)
                        return d
            except Exception:
                continue
        return None

    # ============== 解析小说 ==============

    def parse_novel(self, url_or_id, source_key='biquge'):
        """解析小说 URL/ID，返回小说详细信息

        source_key 可以是任意已注册源，会自动识别 URL 对应的源。
        """
        try:
            # 先尝试自动识别 URL 对应的源
            url_guess = self._try_parse_url(url_or_id)
            if url_guess:
                return url_guess

            # 回退到指定源
            source = self._get_source(source_key)
            if not source:
                return {'error': f'未知源: {source_key}'}

            novel_id = source.parse_novel_url(url_or_id)
            if not novel_id:
                novel_id = url_or_id

            info = source.get_novel_info(str(novel_id))
            if not info:
                return {'error': '获取小说信息失败，请检查URL或ID是否正确'}

            return self._novel_info_to_dict(info)

        except Exception as e:
            print(f'[WebUI] 解析小说失败: {e}')
            return {'error': str(e)}

    # ============== 获取章节列表 ==============

    def get_chapters(self, novel_id, source_key='biquge'):
        """获取小说的章节列表（自动按章节顺序去重排序）"""
        try:
            source = self._get_source(source_key)
            if not source:
                return {'error': f'未知源: {source_key}'}

            chapters = source.get_chapter_list(str(novel_id))
            return [
                {
                    'chapter_id': str(ch.chapter_id),
                    'chapter_title': ch.chapter_title,
                    'chapter_index': ch.chapter_index,
                }
                for ch in chapters
            ]

        except Exception as e:
            print(f'[WebUI] 获取章节列表失败: {e}')
            return {'error': str(e)}

    # ============== 下载 ==============

    def download(self, novel_id, chapter_ids, save_dir, source_key='biquge'):
        """在后台线程中下载章节（多源分工 + 失败重试）

        下载流程：
        1. 主源并发下载所有章节
        2. 统计失败/缺失章节
        3. 自动用其他源重新下载失败章节
        """
        if self._download_thread and self._download_thread.is_alive():
            return {'error': '已有下载任务正在进行中'}

        self._cancel_event.clear()

        self._download_thread = threading.Thread(
            target=self._download_worker,
            args=(str(novel_id), chapter_ids, save_dir, source_key),
            daemon=True,
        )
        self._download_thread.start()

        return {'status': 'started'}

    def _download_worker(self, novel_id, chapter_ids, save_dir, source_key):
        """后台下载工作线程：多源并发 + 失败重试"""
        try:
            source = self._get_source(source_key)
            if not source:
                self._push_error(f'未知源: {source_key}')
                return

            os.makedirs(save_dir, exist_ok=True)

            # 获取小说信息（用于文件命名 + 多源匹配）
            novel_info = None
            try:
                novel_info = source.get_novel_info(novel_id)
            except Exception as e:
                self._push_log(f'获取小说信息失败: {e}', 'warning')

            novel_title = novel_info.title if novel_info else novel_id
            total = len(chapter_ids)
            output_file = os.path.join(save_dir, f'{novel_title}.txt')

            # 建立章节ID到标题的映射（用于多源重试时按标题匹配）
            chapter_id_to_title = {}
            try:
                all_chapters = source.get_chapter_list(novel_id)
                for ch in all_chapters:
                    chapter_id_to_title[str(ch.chapter_id)] = ch.chapter_title
            except Exception:
                pass

            self._push_log(f'开始下载 {total} 个章节（源: {SOURCE_DISPLAY_NAMES.get(source_key, source_key)}）...', 'info')

            # 存储下载结果: {chapter_id: {'title': str, 'content': str}}
            results = {}
            failed_ids = []  # 失败的章节ID

            # ====== 第一轮：主源并发下载 ======
            max_workers = min(app_config.get_concurrent_downloads(), 4)
            lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chapter = {
                    executor.submit(self._download_one, source, novel_id, cid, lock): cid
                    for cid in chapter_ids
                }
                done_count = 0
                for future in as_completed(future_to_chapter):
                    if self._cancel_event.is_set():
                        for f in future_to_chapter:
                            f.cancel()
                        break
                    cid = future_to_chapter[future]
                    done_count += 1
                    try:
                        data = future.result()
                        if data and data.get('content'):
                            results[cid] = data
                        else:
                            failed_ids.append(cid)
                    except Exception as e:
                        failed_ids.append(cid)
                        with lock:
                            self._push_log(f'章节 {cid} 下载失败: {e}', 'error')
                    self._push_progress(done_count, total, percent=round(done_count / total * 100, 1))

            if self._cancel_event.is_set():
                self._push_log('下载已被用户取消', 'warning')
                self._write_output(output_file, novel_info, chapter_ids, results)
                return

            # ====== 第二轮：自动重试失败章节（用其他源，按标题匹配） ======
            if failed_ids:
                self._push_log(f'检测到 {len(failed_ids)} 个失败章节，尝试用其他源重新下载...', 'warning')
                retry_ok = self._retry_failed_chapters(
                    failed_ids, chapter_id_to_title, novel_info,
                    source_key, results, lock
                )
                if retry_ok > 0:
                    self._push_log(f'重试成功 {retry_ok} 章', 'success')

            # ====== 第三轮：检查缺失章节 ======
            missing = [cid for cid in chapter_ids if cid not in results]
            if missing:
                self._push_log(f'仍有 {len(missing)} 个章节缺失，再次尝试...', 'warning')
                retry_ok = self._retry_failed_chapters(
                    missing, chapter_id_to_title, novel_info,
                    source_key, results, lock
                )
                if retry_ok > 0:
                    self._push_log(f'补缺成功 {retry_ok} 章', 'success')

            # 写入文件
            self._write_output(output_file, novel_info, chapter_ids, results)

            success_count = len(results)
            failed_count = total - success_count
            if failed_count > 0:
                self._push_log(
                    f'下载完成! 成功 {success_count}/{total} 章，失败 {failed_count} 章 -> {output_file}',
                    'warning'
                )
            else:
                self._push_log(f'下载完成! 成功 {success_count}/{total} 章 -> {output_file}', 'success')

        except Exception as e:
            self._push_error(f'下载过程中出现严重错误: {e}')

    def _download_one(self, source, novel_id, chapter_id, lock):
        """下载单个章节"""
        data = source.get_chapter_content(novel_id, str(chapter_id))
        if data and lock:
            with lock:
                self._push_log(f'下载成功: {data.get("title", chapter_id)}', 'success')
        return data

    def _retry_failed_chapters(self, failed_ids, chapter_id_to_title, novel_info,
                                primary_source_key, results, lock):
        """用其他源重试失败章节（按章节标题在不同源间匹配）

        不同源的 chapter_id 格式不同，需要：
        1. 获取主源失败章节的标题
        2. 在备用源中按标题查找对应的 chapter_id
        3. 用备用源的 chapter_id 下载

        Returns:
            int: 重试成功的数量
        """
        if not failed_ids or not novel_info:
            return 0

        # 查找同一本书在其他源
        title = novel_info.title or ''
        author = novel_info.author or ''
        other_sources = find_novel_in_all_sources(title, author, exclude_source=primary_source_key)

        if not other_sources:
            self._push_log('未在其他源找到同一本书，无法重试', 'warning')
            return 0

        self._push_log(f'在其他源找到本书: {", ".join(other_sources.keys())}', 'info')

        # 对每个备用源，获取章节列表并建立 {标题: chapter_id} 映射
        fallback_sources = []  # [(src_key, instance, novel_id, {title: chapter_id})]
        for src_key, src_novel_id in other_sources.items():
            try:
                src_instance = self._get_source(src_key)
                if not src_instance:
                    continue
                # 获取备用源的章节列表
                src_chapters = src_instance.get_chapter_list(src_novel_id)
                title_to_cid = {}
                for ch in src_chapters:
                    # 用标题作为匹配键
                    title_to_cid[ch.chapter_title] = str(ch.chapter_id)
                fallback_sources.append((src_key, src_instance, src_novel_id, title_to_cid))
                self._push_log(f'  {src_key}: {len(src_chapters)} 章可匹配', 'info')
            except Exception as e:
                self._push_log(f'  {src_key} 获取章节列表失败: {e}', 'warning')
                continue

        if not fallback_sources:
            return 0

        success_count = 0
        remaining = [cid for cid in failed_ids if cid not in results]

        for cid in remaining:
            if self._cancel_event.is_set():
                break

            # 获取主源中该章节的标题
            ch_title = chapter_id_to_title.get(cid, '')
            if not ch_title:
                # 没有标题无法匹配，跳过
                continue

            # 在备用源中按标题查找
            downloaded = False
            for src_key, src_instance, src_novel_id, title_to_cid in fallback_sources:
                src_chapter_id = title_to_cid.get(ch_title)
                if not src_chapter_id:
                    # 尝试模糊匹配（去掉空格后比较）
                    for t, cid2 in title_to_cid.items():
                        if t.replace(' ', '') == ch_title.replace(' ', ''):
                            src_chapter_id = cid2
                            break
                if not src_chapter_id:
                    continue

                try:
                    data = src_instance.get_chapter_content(src_novel_id, src_chapter_id)
                    if data and data.get('content'):
                        results[cid] = data
                        success_count += 1
                        downloaded = True
                        with lock:
                            self._push_log(f'重试成功（{src_key}）: {data.get("title", ch_title)}', 'success')
                        break
                except Exception:
                    continue

            if not downloaded:
                with lock:
                    self._push_log(f'重试失败: {ch_title}', 'error')

        return success_count

    def _write_output(self, output_file, novel_info, chapter_ids, results):
        """按章节顺序写入输出文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            if novel_info:
                f.write(f"{'=' * 50}\n")
                f.write(f"书名: {novel_info.title}\n")
                if novel_info.author:
                    f.write(f"作者: {novel_info.author}\n")
                if novel_info.description:
                    f.write(f"简介: {novel_info.description}\n")
                if novel_info.word_count:
                    f.write(f"字数: {novel_info.word_count:,} 字\n")
                f.write(f"{'=' * 50}\n\n")

            for i, cid in enumerate(chapter_ids, 1):
                data = results.get(cid)
                if not data:
                    continue
                title = data.get('title', f'第{i}章')
                content = data.get('content', '')
                f.write(f"\n{'=' * 30}\n")
                f.write(f"{title}\n")
                f.write(f"{'=' * 30}\n\n")
                f.write(content)
                f.write("\n")

    def cancel_download(self):
        """取消当前下载"""
        self._cancel_event.set()
        return {'status': 'cancelled'}

    # ============== 设置 ==============

    def get_settings(self):
        """获取当前设置"""
        try:
            config = app_config.load_config()
            return {
                'concurrent_downloads': config.get('concurrent_downloads', 3),
                'download_speed': config.get('download_speed', 1.0),
            }
        except Exception as e:
            return {'error': str(e)}

    def save_settings(self, config_json):
        """
        保存设置

        Args:
            config_json: JSON 字符串
        """
        try:
            config = json.loads(config_json)
            current = app_config.load_config()

            if 'concurrent_downloads' in config:
                current['concurrent_downloads'] = int(config['concurrent_downloads'])
            if 'download_speed' in config:
                current['download_speed'] = float(config['download_speed'])

            result = app_config.save_config(current)
            if result:
                return {'status': 'ok'}
            else:
                return {'error': '保存配置失败'}
        except Exception as e:
            return {'error': str(e)}

    # ============== 登录 ==============

    def open_login(self):
        """打开番茄官网登录对话框"""
        try:
            from selenium_login import login_with_selenium
            # 在后台线程中运行 Selenium 登录（避免阻塞 UI）
            result = {'success': False}

            def login_task():
                try:
                    success = login_with_selenium(headless=False)
                    result['success'] = success
                    if success:
                        # 登录成功后刷新源缓存
                        self._source_cache.pop('fanqie_official', None)
                        self._push_log('番茄官网登录成功', 'success')
                except Exception as e:
                    result['error'] = str(e)
                    self._push_log(f'登录失败: {e}', 'error')

            thread = threading.Thread(target=login_task, daemon=True)
            thread.start()
            thread.join(timeout=300)  # 最长等待5分钟

            return result

        except ImportError as e:
            return {'error': f'Selenium 未安装: {e}'}
        except Exception as e:
            return {'error': str(e)}

    # ============== 文件选择 ==============

    def select_save_dir(self):
        """打开目录选择器"""
        try:
            # 优先使用上次保存的路径
            last_path = app_config.get_last_export_path()
            default_dir = last_path if last_path and os.path.isdir(last_path) else app_config.DOWNLOAD_DIR

            result = self._window.create_file_dialog(
                dialog_type=webview.FOLDER_DIALOG,
                directory=default_dir,
            )
            if result and len(result) > 0:
                selected = result[0]
                # 记住选择的路径
                app_config.set_last_export_path(selected)
                return selected
            return None

        except Exception as e:
            print(f'[WebUI] 选择目录失败: {e}')
            return None

    def get_download_dir(self):
        """返回默认下载目录"""
        return app_config.DOWNLOAD_DIR

    # ============== 内部辅助方法 ==============

    def _novel_info_to_dict(self, info):
        """将 NovelInfo 对象转换为字典"""
        return {
            'novel_id': str(info.novel_id),
            'title': info.title or '',
            'author': info.author or '',
            'description': info.description or '',
            'cover_url': info.cover_url or '',
            'word_count': info.word_count or 0,
            'chapter_count': info.chapter_count or 0,
            'source': info.source or '',
            'source_name': SOURCE_DISPLAY_NAMES.get(info.source or '', info.source or ''),
            'extra': info.extra or {},
        }

    def _push_progress(self, current, total, percent=0, chapter_title=''):
        """向前端推送下载进度"""
        if not self._window:
            return
        try:
            data = json.dumps({
                'current': current,
                'total': total,
                'percent': percent,
                'chapter_title': chapter_title,
            })
            self._window.evaluate_js(f'onProgress({data})')
        except Exception:
            pass

    def _push_log(self, message, level='info'):
        """向前端推送日志"""
        if not self._window:
            return
        try:
            data = json.dumps({
                'message': message,
                'level': level,
            })
            self._window.evaluate_js(f'onLog({data})')
        except Exception:
            pass

    def _push_error(self, message):
        """向前端推送错误日志"""
        self._push_log(message, 'error')


def find_free_port():
    """查找一个可用的随机端口"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _get_html_dir():
    """获取 index.html 所在目录（兼容 PyInstaller 打包）

    打包后主入口 app.py 在根目录，但 index.html 在 web_ui/ 子目录。
    开发模式下两者同目录。
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        # index.html 在 web_ui/ 子目录
        web_ui_dir = os.path.join(base, 'web_ui')
        if os.path.exists(os.path.join(web_ui_dir, 'index.html')):
            return web_ui_dir
        # 兜底：可能在根目录
        if os.path.exists(os.path.join(base, 'index.html')):
            return base
        return base
    else:
        # 开发模式：index.html 和 app.py 同目录
        return os.path.dirname(os.path.abspath(__file__))


def start_http_server(port):
    """启动本地 HTTP 服务器来提供 index.html"""
    html_dir = _get_html_dir()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=html_dir, **kwargs)

        def log_message(self, format, *args):
            # 抑制 HTTP 服务器日志输出
            pass

    server = HTTPServer(('127.0.0.1', port), Handler)
    server.serve_forever()


def main():
    """启动 WebUI"""
    port = find_free_port()

    # 启动 HTTP 服务器线程
    server_thread = threading.Thread(
        target=start_http_server,
        args=(port,),
        daemon=True,
    )
    server_thread.start()

    print(f'[WebUI] HTTP 服务器已启动: http://127.0.0.1:{port}')

    # 创建 API 实例
    api = Api()

    # 创建 pywebview 窗口
    window = webview.create_window(
        title='FXdownloader',
        url=f'http://127.0.0.1:{port}/index.html',
        js_api=api,
        width=1000,
        height=720,
        min_size=(860, 620),
        text_select=False,
    )

    # 保存窗口引用到 API（延迟设置，因为创建时 api 还没有 window 引用）
    def on_loaded():
        api._window = window

    window.events.loaded += on_loaded

    # 启动 webview 事件循环
    webview.start(debug=False)


if __name__ == '__main__':
    main()
