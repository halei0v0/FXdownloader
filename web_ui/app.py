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
import uuid
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
    get_all_rankings,
    get_all_categories,
    get_category_novels,
    SOURCE_DISPLAY_NAMES,
)  # noqa: E402
from database import NovelDatabase  # noqa: E402
import config as app_config  # noqa: E402


class Api:
    """暴露给 JavaScript 前端的 Python API 类"""

    def __init__(self, window=None):
        self._window = window
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()  # 暂停事件（set=暂停中）
        self._download_thread = None
        self._source_cache = {}  # 缓存源实例 {source_key: source_instance}
        self._db = NovelDatabase()
        self._current_task_id = None  # 当前下载任务 ID
        self._download_start_time = None  # 下载开始时间（ETA计算）
        self._download_done_count = 0  # 已完成章节数

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
        elif source_key in ('biquge', 'sto66', 'dingdian', 'bxwx', 'qianbi', 'haitang'):
            source = get_source(source_key)
        else:
            return None

        self._source_cache[source_key] = source
        return source

    def list_sources(self):
        """返回可用的源名称列表（前端格式）"""
        return [
            {'key': 'biquge', 'name': '蚂蚁文学'},
            {'key': 'sto66', 'name': '思兔阅读'},
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
        source_keys = ['biquge', 'sto66', 'dingdian', 'bxwx', 'qianbi', 'haitang', 'fanqie_api', 'fanqie_official']
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
                        # 缓存封面
                        if d.get('cover_url'):
                            try:
                                self._db.set_cover(str(novel_id), sk, d['cover_url'], d.get('title'))
                            except Exception:
                                pass
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

            result = self._novel_info_to_dict(info)
            # 缓存封面到数据库，避免下次重复获取
            if result.get('cover_url'):
                try:
                    sk = result.get('source_key') or source_key
                    self._db.set_cover(str(novel_id), sk, result['cover_url'], result.get('title'))
                except Exception:
                    pass
            return result

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

    def download(self, novel_id, chapter_ids, save_dir, source_key='biquge', append_mode=False):
        """在后台线程中下载章节（多源分工 + 失败重试 + 暂停/续传 + ETA）

        下载流程：
        1. 创建任务记录到数据库（支持暂停/续传）
        2. 主源并发下载所有章节（单章失败同源重试）
        3. 统计失败/缺失章节
        4. 自动用其他源重新下载失败章节
        5. 写入输出文件（append_mode=True 时追加到已有文件，用于补全内容）

        Args:
            append_mode: True 表示追加到已有输出文件（更新小说补全缺失内容时使用）
        """
        if self._download_thread and self._download_thread.is_alive():
            return {'error': '已有下载任务正在进行中'}

        self._cancel_event.clear()
        self._pause_event.clear()
        self._download_done_count = 0
        self._download_start_time = time.time()

        self._download_thread = threading.Thread(
            target=self._download_worker,
            args=(str(novel_id), chapter_ids, save_dir, source_key, append_mode),
            daemon=True,
        )
        self._download_thread.start()

        return {'status': 'started'}

    def _download_worker(self, novel_id, chapter_ids, save_dir, source_key, append_mode=False):
        """后台下载工作线程：多源并发 + 同源重试 + 跨源重试 + 暂停/续传 + ETA"""
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

            # 创建任务记录（支持暂停/续传）
            task_id = str(uuid.uuid4())
            self._current_task_id = task_id
            self._db.create_task(
                task_id=task_id,
                novel_id=novel_id,
                title=novel_title,
                source_key=source_key,
                save_dir=save_dir,
                output_file=output_file,
                chapter_ids=chapter_ids,
                total=total,
            )

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
            completed_ids = []  # 已完成的章节ID

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

                    # 暂停检测：如果 pause_event 被 set，则等待
                    while self._pause_event.is_set() and not self._cancel_event.is_set():
                        time.sleep(0.5)
                    if self._cancel_event.is_set():
                        break

                    cid = future_to_chapter[future]
                    done_count += 1
                    self._download_done_count = done_count
                    try:
                        data = future.result()
                        if data and data.get('content'):
                            results[cid] = data
                            completed_ids.append(cid)
                        else:
                            failed_ids.append(cid)
                    except Exception as e:
                        failed_ids.append(cid)
                        with lock:
                            self._push_log(f'章节 {cid} 下载失败: {e}', 'error')

                    # 推送进度 + ETA
                    self._push_progress_with_eta(done_count, total)

                    # 更新任务进度
                    try:
                        self._db.update_task_progress(
                            task_id, completed_ids, failed_ids,
                            status='paused' if self._pause_event.is_set() else 'running',
                        )
                    except Exception:
                        pass

            if self._cancel_event.is_set():
                self._push_log('下载已被用户取消', 'warning')
                if append_mode:
                    self._append_output(output_file, novel_info, results)
                else:
                    self._write_output(output_file, novel_info, chapter_ids, results)
                try:
                    self._db.set_task_status(task_id, 'cancelled')
                except Exception:
                    pass
                # 记录历史
                self._db.add_history(
                    novel_id, novel_title, novel_info.author if novel_info else '',
                    novel_info.source if novel_info else '', source_key,
                    total, len(results), output_file, status='cancelled',
                )
                self._current_task_id = None
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

            # 写入文件（append_mode 下追加到已有文件，用于补全缺失内容）
            if append_mode:
                self._append_output(output_file, novel_info, results)
            else:
                self._write_output(output_file, novel_info, chapter_ids, results)

            success_count = len(results)
            failed_count = total - success_count

            # 更新任务状态为完成
            try:
                self._db.set_task_status(task_id, 'completed')
            except Exception:
                pass

            # 记录历史
            status = 'completed' if failed_count == 0 else 'partial'
            self._db.add_history(
                novel_id, novel_title, novel_info.author if novel_info else '',
                novel_info.source if novel_info else '', source_key,
                total, success_count, output_file, status=status,
            )

            if failed_count > 0:
                self._push_log(
                    f'下载完成! 成功 {success_count}/{total} 章，失败 {failed_count} 章 -> {output_file}',
                    'warning'
                )
                # 指出彻底失败的章节并通知前端自动选中
                self._push_failed_chapters(novel_id, chapter_ids, results, chapter_id_to_title)
            else:
                self._push_log(f'下载完成! 成功 {success_count}/{total} 章 -> {output_file}', 'success')

            self._current_task_id = None

        except Exception as e:
            self._push_error(f'下载过程中出现严重错误: {e}')
            self._current_task_id = None

    def _download_one(self, source, novel_id, chapter_id, lock):
        """下载单个章节（同源重试 + 暂停/取消检测）

        失败时在相同源重试，最多 MAX_RETRIES 次，每次间隔小幅延迟。
        所有重试均失败才返回 None（交给跨源重试流程）。
        """
        max_retries = max(1, getattr(app_config, 'MAX_RETRIES', 3))
        last_err = None
        for attempt in range(1, max_retries + 1):
            # 暂停检测：每次尝试前都等待恢复
            while self._pause_event.is_set() and not self._cancel_event.is_set():
                time.sleep(0.5)
            if self._cancel_event.is_set():
                return None

            try:
                data = source.get_chapter_content(novel_id, str(chapter_id))
                if data and data.get('content'):
                    if lock:
                        with lock:
                            if attempt > 1:
                                self._push_log(
                                    f'同源重试成功（第{attempt}次）: {data.get("title", chapter_id)}',
                                    'success',
                                )
                            else:
                                self._push_log(f'下载成功: {data.get("title", chapter_id)}', 'success')
                    return data
            except Exception as e:
                last_err = e

            # 本次尝试失败，准备下一次重试（最后一次不再等待）
            if attempt < max_retries:
                if self._cancel_event.is_set():
                    return None
                time.sleep(1.0 * attempt)  # 简单退避：1s, 2s ...
                if lock:
                    with lock:
                        title_hint = ''
                        try:
                            title_hint = f' ({chapter_id})'
                        except Exception:
                            pass
                        self._push_log(
                            f'章节{title_hint} 下载失败，准备同源第{attempt + 1}次重试...',
                            'warning',
                        )

        # 所有同源重试均失败
        if lock:
            with lock:
                err_msg = f'（{last_err}）' if last_err else ''
                self._push_log(f'章节 {chapter_id} 同源重试 {max_retries} 次仍失败{err_msg}', 'error')
        return None

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

    @staticmethod
    def _clean_empty_lines(text):
        """去除多余空行，只保留段落间必要的单个换行

        规则：
        - 去除每行首尾空白
        - 去除连续空行（多个空行压缩为0个）
        - 去除开头和结尾的空行
        """
        if not text:
            return ''
        lines = text.split('\n')
        # 去除每行首尾空白，过滤掉空行
        cleaned = [line.strip() for line in lines]
        cleaned = [line for line in cleaned if line]
        return '\n'.join(cleaned)

    def _write_output(self, output_file, novel_info, chapter_ids, results):
        """按章节顺序写入输出文件

        根据配置 remove_empty_lines 决定是否去除空行（默认不去除）。
        """
        remove_empty = app_config.get_remove_empty_lines()

        def _clean(text):
            """根据配置清理空行"""
            if not remove_empty:
                return text
            return self._clean_empty_lines(text)

        with open(output_file, 'w', encoding='utf-8') as f:
            if novel_info:
                f.write(f"{'=' * 50}\n")
                f.write(f"书名: {novel_info.title}\n")
                if novel_info.author:
                    f.write(f"作者: {novel_info.author}\n")
                if novel_info.description:
                    f.write(f"简介: {_clean(novel_info.description)}\n")
                if novel_info.word_count:
                    f.write(f"字数: {novel_info.word_count:,} 字\n")
                f.write(f"{'=' * 50}\n")

            for i, cid in enumerate(chapter_ids, 1):
                data = results.get(cid)
                if not data:
                    continue
                title = data.get('title', f'第{i}章')
                content = _clean(data.get('content', ''))
                if not content:
                    continue
                f.write(f"\n{'=' * 30}\n")
                f.write(f"{title}\n")
                f.write(f"{'=' * 30}\n")
                f.write(content)
                f.write("\n")

    def _append_output(self, output_file, novel_info, results):
        """追加章节到已有文件（用于续传）

        只写入新下载的章节，不重写已有内容。
        """
        remove_empty = app_config.get_remove_empty_lines()

        def _clean(text):
            if not remove_empty:
                return text
            return self._clean_empty_lines(text)

        # 如果文件不存在，创建并写入头部
        mode = 'a' if os.path.exists(output_file) else 'w'
        with open(output_file, mode, encoding='utf-8') as f:
            if mode == 'w' and novel_info:
                f.write(f"{'=' * 50}\n")
                f.write(f"书名: {novel_info.title}\n")
                if novel_info.author:
                    f.write(f"作者: {novel_info.author}\n")
                if novel_info.description:
                    f.write(f"简介: {_clean(novel_info.description)}\n")
                f.write(f"{'=' * 50}\n")

            for cid, data in results.items():
                if not data:
                    continue
                title = data.get('title', '')
                content = _clean(data.get('content', ''))
                if not content:
                    continue
                f.write(f"\n{'=' * 30}\n")
                f.write(f"{title}\n")
                f.write(f"{'=' * 30}\n")
                f.write(content)
                f.write("\n")

    def cancel_download(self):
        """取消当前下载"""
        self._cancel_event.set()
        self._pause_event.clear()  # 同时清除暂停状态
        return {'status': 'cancelled'}

    def pause_download(self):
        """暂停当前下载"""
        self._pause_event.set()
        self._push_log('下载已暂停', 'warning')
        # 更新任务状态
        if self._current_task_id:
            try:
                self._db.set_task_status(self._current_task_id, 'paused')
            except Exception:
                pass
        return {'status': 'paused'}

    def resume_download(self):
        """恢复当前下载"""
        self._pause_event.clear()
        self._push_log('下载已恢复', 'info')
        if self._current_task_id:
            try:
                self._db.set_task_status(self._current_task_id, 'running')
            except Exception:
                pass
        return {'status': 'resumed'}

    def is_paused(self):
        """检查当前是否暂停"""
        return {'paused': self._pause_event.is_set()}

    def get_download_status(self):
        """获取当前下载状态（供批量下载轮询使用）"""
        active = self._download_thread is not None and self._download_thread.is_alive()
        return {'active': active, 'task_id': self._current_task_id or ''}

    def get_paused_tasks(self):
        """获取所有暂停的任务"""
        try:
            tasks = self._db.get_paused_tasks()
            result = []
            for t in tasks:
                result.append({
                    'task_id': t['task_id'],
                    'novel_id': t['novel_id'],
                    'title': t['title'],
                    'source_key': t['source_key'],
                    'save_dir': t['save_dir'],
                    'output_file': t['output_file'],
                    'total': t['total'],
                    'completed': len(t.get('completed_ids', [])),
                    'failed': len(t.get('failed_ids', [])),
                    'chapter_ids': t.get('chapter_ids', []),
                    'completed_ids': t.get('completed_ids', []),
                    'failed_ids': t.get('failed_ids', []),
                    'created_at': str(t.get('created_at', '')),
                    'updated_at': str(t.get('updated_at', '')),
                })
            return result
        except Exception as e:
            return {'error': str(e)}

    def resume_task(self, task_id):
        """续传已暂停的任务（从断点继续下载）"""
        try:
            task = self._db.get_task(task_id)
            if not task:
                return {'error': '任务不存在'}
            if task['status'] != 'paused':
                return {'error': f"任务状态为 {task['status']}，无法续传"}

            # 已完成的章节ID集合
            completed_set = set(task.get('completed_ids', []))
            # 待下载章节ID（去掉已完成的）
            remaining = [cid for cid in task.get('chapter_ids', [])
                         if cid not in completed_set]
            if not remaining:
                return {'error': '任务已全部完成，无需续传'}

            # 启动新的下载线程
            self._cancel_event.clear()
            self._pause_event.clear()
            self._download_done_count = len(completed_set)
            self._download_start_time = time.time()
            self._current_task_id = task_id

            self._download_thread = threading.Thread(
                target=self._resume_worker,
                args=(task, remaining),
                daemon=True,
            )
            self._download_thread.start()
            return {'status': 'started', 'remaining': len(remaining)}
        except Exception as e:
            return {'error': str(e)}

    def _resume_worker(self, task, remaining_ids):
        """续传任务工作线程"""
        try:
            source = self._get_source(task['source_key'])
            if not source:
                self._push_error(f"未知源: {task['source_key']}")
                return

            novel_id = task['novel_id']
            novel_title = task['title']
            output_file = task['output_file']
            total = task['total']
            all_chapter_ids = task['chapter_ids']
            completed_ids = task.get('completed_ids', [])

            # 更新状态为运行中
            self._db.set_task_status(task['task_id'], 'running')

            self._push_log(f'续传任务: {novel_title}, 剩余 {len(remaining_ids)} 章', 'info')

            # 获取小说信息
            novel_info = None
            try:
                novel_info = source.get_novel_info(novel_id)
            except Exception:
                pass

            # 章节ID到标题映射
            chapter_id_to_title = {}
            try:
                all_chapters = source.get_chapter_list(novel_id)
                for ch in all_chapters:
                    chapter_id_to_title[str(ch.chapter_id)] = ch.chapter_title
            except Exception:
                pass

            # 下载剩余章节
            results = {}
            failed_ids = []
            max_workers = min(app_config.get_concurrent_downloads(), 4)
            lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chapter = {
                    executor.submit(self._download_one, source, novel_id, cid, lock): cid
                    for cid in remaining_ids
                }
                done_count = 0
                for future in as_completed(future_to_chapter):
                    if self._cancel_event.is_set():
                        for f in future_to_chapter:
                            f.cancel()
                        break
                    while self._pause_event.is_set() and not self._cancel_event.is_set():
                        time.sleep(0.5)
                    if self._cancel_event.is_set():
                        break

                    cid = future_to_chapter[future]
                    done_count += 1
                    try:
                        data = future.result()
                        if data and data.get('content'):
                            results[cid] = data
                            completed_ids.append(cid)
                        else:
                            failed_ids.append(cid)
                    except Exception as e:
                        failed_ids.append(cid)

                    # 推送进度（基于总数）
                    total_done = len(completed_ids)
                    self._push_progress_with_eta(total_done, total)

                    # 更新任务进度
                    try:
                        self._db.update_task_progress(
                            task['task_id'], completed_ids, failed_ids,
                            status='running',
                        )
                    except Exception:
                        pass

            # 重试失败章节
            if failed_ids and not self._cancel_event.is_set():
                self._push_log(f'检测到 {len(failed_ids)} 个失败章节，尝试用其他源...', 'warning')
                retry_ok = self._retry_failed_chapters(
                    failed_ids, chapter_id_to_title, novel_info,
                    task['source_key'], results, lock
                )
                if retry_ok > 0:
                    self._push_log(f'重试成功 {retry_ok} 章', 'success')

            # 只写入新下载的章节（追加模式，不重新下载已完成的章节）
            if results:
                self._append_output(output_file, novel_info, results)

            success_count = len(completed_ids) + len(results)
            self._push_log(f'续传完成! 共 {success_count}/{total} 章 -> {output_file}', 'success')
            self._db.set_task_status(task['task_id'], 'completed')

            # 记录历史
            self._db.add_history(
                novel_id, novel_title, novel_info.author if novel_info else '',
                novel_info.source if novel_info else '', task['source_key'],
                total, success_count, output_file, status='completed',
            )
            self._current_task_id = None

        except Exception as e:
            self._push_error(f'续传失败: {e}')
            self._current_task_id = None

    def delete_task(self, task_id):
        """删除任务"""
        try:
            self._db.delete_task(task_id)
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    # ============== 设置 ==============

    def get_settings(self):
        """获取当前设置"""
        try:
            config = app_config.load_config()
            return {
                'concurrent_downloads': config.get('concurrent_downloads', 3),
                'remove_empty_lines': config.get('remove_empty_lines', False),
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
            if 'remove_empty_lines' in config:
                current['remove_empty_lines'] = bool(config['remove_empty_lines'])

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
        # 从 extra 中提取状态字段，便于前端统一显示
        extra = info.extra or {}
        status = extra.get('status', '') or extra.get('novel_status', '')
        return {
            'novel_id': str(info.novel_id),
            'title': info.title or '',
            'author': info.author or '',
            'description': info.description or '',
            'cover_url': info.cover_url or '',
            'word_count': info.word_count or 0,
            'chapter_count': info.chapter_count or 0,
            'status': status,
            'source': info.source or '',
            'source_name': SOURCE_DISPLAY_NAMES.get(info.source or '', info.source or ''),
            'extra': extra,
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

    def _push_progress_with_eta(self, current, total):
        """推送进度 + ETA（剩余时间预估）"""
        if not self._window:
            return
        try:
            percent = round(current / total * 100, 1) if total > 0 else 0
            eta_seconds = 0
            speed = 0
            if self._download_start_time and current > 0:
                elapsed = time.time() - self._download_start_time
                speed = current / elapsed if elapsed > 0 else 0  # 章/秒
                remaining = total - current
                eta_seconds = remaining / speed if speed > 0 else 0

            # 格式化 ETA
            def _fmt_time(s):
                if s <= 0:
                    return '--:--'
                s = int(s)
                h, s = divmod(s, 3600)
                m, s = divmod(s, 60)
                if h > 0:
                    return f'{h}:{m:02d}:{s:02d}'
                return f'{m:02d}:{s:02d}'

            # 速度转换为 章/分
            speed_per_min = speed * 60 if speed > 0 else 0

            data = json.dumps({
                'current': current,
                'total': total,
                'percent': percent,
                'eta': _fmt_time(eta_seconds),
                'eta_seconds': round(eta_seconds, 1),
                'speed': round(speed, 2),
                'speed_text': f'{speed_per_min:.1f} 章/分' if speed_per_min > 0 else '--',
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

    def _push_failed_chapters(self, novel_id, chapter_ids, results, chapter_id_to_title):
        """收集彻底失败的章节并通知前端自动选中

        在所有重试（同源 + 跨源）结束后调用，将仍未成功下载的章节
        通过 evaluate_js(onFailedChapters) 推送到前端，前端会自动选中
        这些章节的复选框并高亮，方便用户手动重试。
        """
        if not self._window:
            return
        failed = []
        for cid in chapter_ids:
            if cid in results and results[cid].get('content'):
                continue
            failed.append({
                'chapter_id': str(cid),
                'chapter_title': chapter_id_to_title.get(cid, '') or str(cid),
            })
        if not failed:
            return
        try:
            data = json.dumps({
                'novel_id': str(novel_id),
                'count': len(failed),
                'chapters': failed,
            })
            self._window.evaluate_js(f'onFailedChapters({data})')
        except Exception:
            pass

    # ============== 历史记录 ==============

    def get_history(self, limit=100):
        """获取下载历史"""
        try:
            history = self._db.get_history(limit)
            result = []
            for h in history:
                d = dict(h)
                d['created_at'] = str(d.get('created_at', ''))
                result.append(d)
            return result
        except Exception as e:
            return {'error': str(e)}

    def delete_history(self, history_id):
        """删除单条历史记录"""
        try:
            self._db.delete_history(history_id)
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def clear_history(self):
        """清空所有历史记录"""
        try:
            self._db.clear_history()
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    # ============== 收藏 ==============

    def add_favorite(self, novel_json):
        """添加收藏"""
        try:
            novel = json.loads(novel_json)
            novel_id = novel.get('novel_id', '')
            source = novel.get('source', '')
            source_key = novel.get('source_key', novel.get('source', ''))
            cover_url = novel.get('cover_url', '')
            # 若未带封面，从本地缓存补全
            if not cover_url and novel_id:
                cached = self._db.get_cover(str(novel_id), source_key)
                if cached:
                    cover_url = cached
            self._db.add_favorite(
                novel_id=novel_id,
                title=novel.get('title', ''),
                author=novel.get('author', ''),
                cover_url=cover_url,
                description=novel.get('description', ''),
                source=source,
                source_key=source_key,
                extra_json=json.dumps(novel.get('extra', {}), ensure_ascii=False),
            )
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def remove_favorite(self, novel_id, source):
        """取消收藏"""
        try:
            self._db.remove_favorite(novel_id, source)
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def get_favorites(self):
        """获取所有收藏"""
        try:
            favs = self._db.get_favorites()
            result = []
            for f in favs:
                d = dict(f)
                d['created_at'] = str(d.get('created_at', ''))
                result.append(d)
            return result
        except Exception as e:
            return {'error': str(e)}

    def is_favorited(self, novel_id, source):
        """检查是否已收藏"""
        try:
            return {'favorited': self._db.is_favorited(novel_id, source)}
        except Exception as e:
            return {'error': str(e)}

    # ============== 阅读功能 ==============

    def get_reader_settings(self):
        """获取阅读器设置（字号、主题等）"""
        try:
            config = app_config.load_config()
            return {
                'font_size': config.get('reader_font_size', 18),
                'theme': config.get('reader_theme', 'eye-care'),
            }
        except Exception as e:
            return {'error': str(e)}

    def save_reader_settings(self, settings_json):
        """保存阅读器设置

        Args:
            settings_json: JSON 字符串 {font_size, theme}
        """
        try:
            s = json.loads(settings_json) if isinstance(settings_json, str) else settings_json
            current = app_config.load_config()
            if 'font_size' in s:
                # 字号范围 12-36
                current['reader_font_size'] = max(12, min(36, int(s['font_size'])))
            if 'theme' in s:
                if s['theme'] in ('eye-care', 'dark'):
                    current['reader_theme'] = s['theme']
            app_config.save_config(current)
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def read_chapter(self, novel_id, chapter_id, source_key='biquge'):
        """获取章节内容用于阅读"""
        try:
            source = self._get_source(source_key)
            if not source:
                return {'error': f'未知源: {source_key}'}
            data = source.get_chapter_content(str(novel_id), str(chapter_id))
            if data and data.get('content'):
                # 保存阅读进度
                title = data.get('title', '')
                # 尝试获取小说标题
                novel_title = ''
                try:
                    novel_info = source.get_novel_info(str(novel_id))
                    if novel_info:
                        novel_title = novel_info.title or ''
                except Exception:
                    pass
                self._db.save_reading_progress(
                    novel_id=str(novel_id), title=novel_title,
                    last_chapter_id=str(chapter_id),
                    last_chapter_title=title, chapter_index=0,
                )
                return {
                    'title': title,
                    'content': data['content'],
                    'chapter_id': str(chapter_id),
                }
            return {'error': '获取章节内容失败'}
        except Exception as e:
            return {'error': str(e)}

    def get_reading_progress(self, novel_id):
        """获取阅读进度"""
        try:
            progress = self._db.get_reading_progress(str(novel_id))
            if progress:
                d = dict(progress)
                d['updated_at'] = str(d.get('updated_at', ''))
                return d
            return None
        except Exception as e:
            return {'error': str(e)}

    def save_reading_progress(self, novel_id, title, chapter_id,
                               chapter_title, chapter_index, scroll_position=0):
        """保存阅读进度"""
        try:
            self._db.save_reading_progress(
                novel_id=str(novel_id), title=title,
                last_chapter_id=str(chapter_id),
                last_chapter_title=chapter_title,
                chapter_index=chapter_index,
                scroll_position=scroll_position,
            )
            return {'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def get_reading_list(self):
        """获取阅读书架（所有阅读过的小说）"""
        try:
            progress_list = self._db.get_all_reading_progress()
            result = []
            for p in progress_list:
                d = dict(p)
                d['updated_at'] = str(d.get('updated_at', ''))
                result.append(d)
            return result
        except Exception as e:
            return {'error': str(e)}

    # ============== 排行榜 ==============

    def get_rankings(self, category='all', page=1):
        """获取排行榜数据（来源：速读谷，按天缓存，封面已包含）

        排行榜数据每日从 sudugu.org 获取一次后缓存到本地，
        封面 URL 已包含在缓存中，无需额外 prefetch。
        """
        try:
            return get_all_rankings(category=category, page=page)
        except Exception as e:
            return {'error': str(e)}

    def prefetch_covers(self, novels_json, source_key='biquge'):
        """批量预获取小说封面并缓存到本地

        对没有缓存封面的小说，并发获取其封面 URL 并存入数据库。
        已有缓存的不重复获取。

        Args:
            novels_json: JSON 字符串，包含 [{novel_id, title, cover_url, source_key}]
            source_key: 默认源（当小说未指定 source_key 时使用）

        Returns:
            dict: {novel_id: cover_url}（包含已有缓存 + 新获取的）
        """
        try:
            novels = json.loads(novels_json) if isinstance(novels_json, str) else novels_json
            if not novels:
                return {}

            # 找出需要获取封面的小说（本地缓存中没有的）
            need_fetch = []
            result = {}
            for n in novels:
                nid = str(n.get('novel_id', ''))
                sk = n.get('source_key') or n.get('source') or source_key
                if not nid:
                    continue
                # 先查缓存
                cached = self._db.get_cover(nid, sk)
                if cached:
                    result[nid] = cached
                elif n.get('cover_url'):
                    # 列表里已带封面 URL，直接缓存
                    self._db.set_cover(nid, sk, n['cover_url'], n.get('title'))
                    result[nid] = n['cover_url']
                else:
                    need_fetch.append((nid, sk, n.get('title', '')))

            if not need_fetch:
                return result

            # 并发获取封面（限制并发数，避免请求过多）
            source_cache = {}

            def _fetch_one(item):
                nid, sk, title = item
                try:
                    if sk not in source_cache:
                        source_cache[sk] = self._get_source(sk)
                    source = source_cache[sk]
                    if not source:
                        return nid, sk, title, None
                    info = source.get_novel_info(nid)
                    if info and info.cover_url:
                        # 缓存到数据库
                        self._db.set_cover(nid, sk, info.cover_url, title or info.title)
                        return nid, sk, title, info.cover_url
                except Exception as e:
                    print(f'[WebUI] 获取封面失败 {nid}: {e}')
                return nid, sk, title, None

            max_workers = min(6, len(need_fetch))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_fetch_one, item): item for item in need_fetch}
                for future in as_completed(futures):
                    try:
                        nid, sk, title, cover_url = future.result()
                        if cover_url:
                            result[nid] = cover_url
                    except Exception:
                        pass

            return result
        except Exception as e:
            print(f'[WebUI] prefetch_covers 出错: {e}')
            return {}

    def get_cover_cache_info(self):
        """获取封面缓存信息（条目数 + 估算大小 KB）

        封面缓存表仅存储 URL 字符串，没有图片文件本体；
        缓存大小按各行的 novel_id+source+cover_url+title 字符串总字节数估算。
        """
        try:
            count = self._db.get_cover_cache_count()
            # 估算大小：按行累计字符串字节数
            size_bytes = 0
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT novel_id, source, cover_url, title FROM novel_covers
                ''')
                for row in cursor.fetchall():
                    nid = str(row['novel_id'] or '')
                    src = str(row['source'] or '')
                    url = str(row['cover_url'] or '')
                    title = str(row['title'] or '')
                    # UTF-8 字节数
                    size_bytes += len(nid.encode('utf-8')) + len(src.encode('utf-8'))
                    size_bytes += len(url.encode('utf-8')) + len(title.encode('utf-8'))
            size_kb = round(size_bytes / 1024, 2)
            return {'count': count, 'size_kb': size_kb}
        except Exception as e:
            return {'error': str(e)}

    def clear_cover_cache(self):
        """清空封面缓存表，返回被删除的条目数"""
        try:
            count = self._db.clear_cover_cache()
            return {'status': 'ok', 'cleared': count}
        except Exception as e:
            return {'error': str(e)}

    def get_categories(self):
        """获取所有源的分类列表"""
        try:
            return get_all_categories()
        except Exception as e:
            return {'error': str(e)}

    def get_category_novels(self, category_key, page=1):
        """获取分类下的小说列表（来源：速读谷，按天缓存，封面已包含）

        点击分类后调用，返回该分类最新小说。点击具体小说后用书名在各源搜索。
        """
        try:
            return get_category_novels(category_key, page)
        except Exception as e:
            return {'error': str(e)}

    # ============== 更新小说 ==============

    def update_novel(self, novel_id, source_key='biquge'):
        """更新小说：检测新章节 + 补全上次未完成的内容

        对比已下载任务的章节列表和当前章节列表：
        1. 新增章节：当前有、上次任务中没有的章节
        2. 缺失内容章节：上次任务中存在但因失败/中断未下载完成的章节
           （在 chapter_ids_json 中但不在 completed_ids_json 中，且当前仍存在）

        Returns:
            dict: 包含 new_chapters / incomplete_chapters 及各自计数
        """
        try:
            source = self._get_source(source_key)
            if not source:
                return {'error': f'未知源: {source_key}'}

            # 获取当前章节列表
            chapters = source.get_chapter_list(str(novel_id))
            if not chapters:
                return {'error': '获取章节列表失败'}

            # 从最近的下载任务中获取已记录的章节ID集合
            existing_ids = set()       # 上次任务记录的全部章节ID
            completed_ids = set()      # 上次任务实际下载完成的章节ID
            try:
                with self._db.get_connection() as conn:
                    cursor = conn.cursor()
                    # 包含 completed 和 partial 状态，以检测未完成内容
                    cursor.execute('''
                        SELECT chapter_ids_json, completed_ids_json
                        FROM download_tasks
                        WHERE novel_id = ? AND status IN ('completed', 'partial')
                        ORDER BY updated_at DESC LIMIT 1
                    ''', (str(novel_id),))
                    row = cursor.fetchone()
                    if row:
                        old_chapters = json.loads(row['chapter_ids_json'] or '[]')
                        existing_ids = set(old_chapters)
                        completed_ids = set(json.loads(row['completed_ids_json'] or '[]'))
            except Exception:
                pass

            # 缺失内容：上次任务中有但未完成的章节（当前仍存在）
            missing_content_ids = existing_ids - completed_ids

            new_chapters = []
            incomplete_chapters = []
            for ch in chapters:
                cid = str(ch.chapter_id)
                if cid not in existing_ids:
                    new_chapters.append(ch)
                elif cid in missing_content_ids:
                    incomplete_chapters.append(ch)

            new_count = len(new_chapters)
            incomplete_count = len(incomplete_chapters)

            if new_count == 0 and incomplete_count == 0:
                return {'status': 'ok', 'new_count': 0, 'incomplete_count': 0,
                        'message': '没有新章节，内容完整'}

            return {
                'status': 'ok',
                'new_count': new_count,
                'incomplete_count': incomplete_count,
                'new_chapters': [
                    {
                        'chapter_id': str(ch.chapter_id),
                        'chapter_title': ch.chapter_title,
                        'chapter_index': ch.chapter_index,
                    }
                    for ch in new_chapters
                ],
                'incomplete_chapters': [
                    {
                        'chapter_id': str(ch.chapter_id),
                        'chapter_title': ch.chapter_title,
                        'chapter_index': ch.chapter_index,
                    }
                    for ch in incomplete_chapters
                ],
                'novel_id': str(novel_id),
                'source_key': source_key,
            }
        except Exception as e:
            return {'error': str(e)}

    def download_new_chapters(self, novel_id, source_key, save_dir):
        """下载新增章节 + 补全上次未完成的内容，并合并到现有文件

        通过 update_novel 检测：
        - new_chapters: 上次任务没有的新章节
        - incomplete_chapters: 上次任务中未下载完成、当前仍存在的章节
        合并下载后以追加模式写入已有文件，避免覆盖已下载内容。
        """
        try:
            check = self.update_novel(novel_id, source_key)
            if check.get('error'):
                return check

            new_chapters = check.get('new_chapters', [])
            incomplete_chapters = check.get('incomplete_chapters', [])
            new_count = len(new_chapters)
            incomplete_count = len(incomplete_chapters)

            if new_count == 0 and incomplete_count == 0:
                return {'status': 'ok', 'message': check.get('message', '没有新章节，内容完整'),
                        'new_count': 0, 'incomplete_count': 0}

            # 合并新章节 + 缺失章节（去重，保持章节顺序）
            seen = set()
            chapter_ids = []
            for ch in (new_chapters + incomplete_chapters):
                cid = ch['chapter_id']
                if cid not in seen:
                    seen.add(cid)
                    chapter_ids.append(cid)

            if incomplete_count > 0:
                self._push_log(
                    f'检测到 {incomplete_count} 章内容缺失，将补全下载', 'warning'
                )

            # 追加模式：合并到已有文件，不覆盖已下载内容
            result = self.download(novel_id, chapter_ids, save_dir, source_key, append_mode=True)
            if isinstance(result, dict):
                result['new_count'] = new_count
                result['incomplete_count'] = incomplete_count
            return result
        except Exception as e:
            return {'error': str(e)}


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


def _get_icon_path():
    """获取应用图标路径（兼容 PyInstaller 打包）

    开发模式：从项目根目录的 assets/icon.ico 读取
    打包模式：图标已嵌入 exe 资源，返回 None 让系统使用 exe 图标
    """
    if getattr(sys, 'frozen', False):
        # 打包模式：图标已嵌入 exe PE 头，pywebview 会自动使用
        return None
    # 开发模式：从项目根目录读取
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = os.path.join(root, 'assets', 'icon.ico')
    return icon if os.path.exists(icon) else None


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

    # 创建 pywebview 窗口（兼容不支持 icon 参数的旧版本 pywebview）
    icon_path = _get_icon_path()
    window_kwargs = {
        'title': 'FXdownloader',
        'url': f'http://127.0.0.1:{port}/index.html',
        'js_api': api,
        'width': 1100,
        'height': 780,
        'min_size': (960, 680),
        'text_select': False,
    }
    if icon_path:
        window_kwargs['icon'] = icon_path
    try:
        window = webview.create_window(**window_kwargs)
    except TypeError:
        # 旧版 pywebview 不支持 icon 参数，移除后重试
        window_kwargs.pop('icon', None)
        window = webview.create_window(**window_kwargs)

    # 保存窗口引用到 API（延迟设置，因为创建时 api 还没有 window 引用）
    def on_loaded():
        api._window = window

    window.events.loaded += on_loaded

    # 启动 webview 事件循环
    webview.start(debug=False)


if __name__ == '__main__':
    main()
