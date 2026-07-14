# -*- coding: utf-8 -*-
"""
FXdownloader 主程序（CustomTkinter 版）

特性：
- 使用 CustomTkinter 提供现代化 UI
- 通过 sources/ 抽象统一支持笔趣阁（无需登录）和番茄小说
- 多源同时搜索（番茄 API + 笔趣阁），结果标注来源
- 支持源切换、小说解析、章节列表、批量下载、进度显示
- 修复了原 gui.py 中的登录逻辑 bug（Cookie 不刷新等）
"""
from __future__ import annotations

import os
import sys
import time
import threading
from collections import Counter
from tkinter import filedialog, messagebox

import customtkinter as ctk

# 确保 sources 模块可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import BaseSource, NovelInfo, SourceError
from sources.biquge_source import BiqugeSource
from sources.fanqie_source import FanqieSource
from sources.bing_search import search_via_bing
import config as app_config


# ===================== 全局配置 =====================
ctk.set_appearance_mode('System')
ctk.set_default_color_theme('blue')


# ===================== 源定义 =====================
# 统一的源 key 体系（与 SOURCE_REGISTRY 兼容）
SOURCE_KEYS = {
    'biquge': '笔趣阁（无需登录）',
    'fanqie_api': '番茄小说（API·免登录）',
    'fanqie_official': '番茄小说（官网·需登录）',
}

# 搜索结果显示用的源简称
SEARCH_SOURCE_LABEL = {
    'fanqie': '番茄',
    'biquge': '笔趣阁',
}


class FXDownloaderApp(ctk.CTk):
    """主应用窗口"""

    def __init__(self):
        super().__init__()

        self.title('FXdownloader - 小说下载器')
        self.geometry('1040x740')
        self.minsize(880, 640)

        # 状态变量
        self.current_source: BaseSource | None = None
        self.current_source_key: str = ''
        self.current_novel_info: NovelInfo | None = None
        self.current_chapters: list = []
        self.chapter_vars: list[ctk.BooleanVar] = []
        self.is_downloading = False
        self.download_thread: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.login_dlg = None

        # 构建 UI
        self._build_ui()

        # 默认选择笔趣阁源（无需登录，立即可用）
        self._switch_source('biquge')

        # 窗口关闭处理
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ===================== UI 构建 =====================

    def _build_ui(self):
        # 顶部工具栏
        self._build_topbar()

        # 主体：左右分栏
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1, uniform='col')
        body.grid_columnconfigure(1, weight=1, uniform='col')
        body.grid_rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)

        # 底部日志 + 进度
        self._build_bottom_panel()

    def _build_topbar(self):
        topbar = ctk.CTkFrame(self, height=54, corner_radius=0, fg_color=('#EAEAEA', '#2B2B2B'))
        topbar.pack(fill='x', side='top')
        topbar.pack_propagate(False)

        # 标题
        ctk.CTkLabel(
            topbar, text='FXdownloader',
            font=ctk.CTkFont(size=20, weight='bold'),
        ).pack(side='left', padx=(16, 0))

        # 源选择
        ctk.CTkLabel(topbar, text='小说源：').pack(side='left', padx=(24, 4))

        # 用 key 作为下拉值，避免字符串匹配脆弱
        self.source_var = ctk.StringVar(value='biquge')
        source_menu = ctk.CTkOptionMenu(
            topbar,
            variable=self.source_var,
            values=list(SOURCE_KEYS.values()),
            command=self._on_source_menu_change,
            width=200,
        )
        source_menu.pack(side='left', padx=(0, 16))

        # 登录状态指示（仅番茄官网模式显示）
        self.login_status_label = ctk.CTkLabel(topbar, text='', font=ctk.CTkFont(size=12))
        self.login_status_label.pack(side='left', padx=(0, 8))

        # 登录按钮（番茄官网模式）
        self.login_btn = ctk.CTkButton(
            topbar, text='登录', width=72, height=30,
            command=self._on_login_click,
        )
        # 默认隐藏（笔趣阁模式）；通过 _switch_source 控制显示

        # 右侧：状态指示 + 设置
        self.status_label = ctk.CTkLabel(
            topbar, text='就绪',
            font=ctk.CTkFont(size=12),
            text_color=('gray40', 'gray60'),
        )
        self.status_label.pack(side='right', padx=(0, 12))

        ctk.CTkButton(
            topbar, text='设置', width=72, height=30,
            command=self._on_settings_click,
        ).pack(side='right', padx=(0, 16))

    def _build_left_panel(self, parent):
        panel = ctk.CTkFrame(parent)
        panel.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # URL 输入区
        url_frame = ctk.CTkFrame(panel, fg_color='transparent')
        url_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 4))
        url_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            url_frame, text='小说 URL 或 ID：',
            font=ctk.CTkFont(size=13, weight='bold'),
        ).pack(anchor='w', pady=(0, 4))

        input_row = ctk.CTkFrame(url_frame, fg_color='transparent')
        input_row.pack(fill='x')
        input_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text='输入小说 URL 或 ID（如 11331 或 fanqienovel.com/page/123）',
        )
        self.url_entry.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.url_entry.bind('<Return>', lambda e: self._on_parse_click())

        self.parse_btn = ctk.CTkButton(
            input_row, text='解析', width=80, command=self._on_parse_click,
        )
        self.parse_btn.grid(row=0, column=1)

        # 搜索区（始终显示，使用 Bing 搜索引擎）
        search_frame = ctk.CTkFrame(panel, fg_color='transparent')
        search_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 4))
        search_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            search_frame,
            text='搜索（Bing 搜索引擎，结果可能不全）',
            font=ctk.CTkFont(size=12),
        ).pack(anchor='w', pady=(0, 2))

        search_row = ctk.CTkFrame(search_frame, fg_color='transparent')
        search_row.pack(fill='x')
        search_row.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(search_row, placeholder_text='输入书名/作者...')
        self.search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.search_entry.bind('<Return>', lambda e: self._on_search_click())

        self.search_btn = ctk.CTkButton(
            search_row, text='搜索', width=80, command=self._on_search_click,
        )
        self.search_btn.grid(row=0, column=1)

        # 搜索结果列表
        self.search_results_box = ctk.CTkScrollableFrame(search_frame, height=120)
        self.search_results_box.pack(fill='both', expand=True, pady=(4, 0))
        self._show_search_placeholder('输入关键词搜索小说')

        # 小说信息区
        ctk.CTkLabel(
            panel, text='小说信息',
            font=ctk.CTkFont(size=14, weight='bold'),
        ).grid(row=2, column=0, sticky='w', padx=10, pady=(8, 4))

        self.info_box = ctk.CTkScrollableFrame(panel, label_text='')
        self.info_box.grid(row=3, column=0, sticky='nsew', padx=10, pady=(0, 10))

        self.info_title = ctk.CTkLabel(
            self.info_box, text='（等待解析）',
            font=ctk.CTkFont(size=16, weight='bold'),
        )
        self.info_title.pack(anchor='w', pady=(4, 4))

        self.info_author = ctk.CTkLabel(
            self.info_box, text='',
            text_color=('gray40', 'gray60'),
        )
        self.info_author.pack(anchor='w', pady=(0, 4))

        self.info_desc = ctk.CTkLabel(
            self.info_box, text='', wraplength=380, justify='left',
        )
        self.info_desc.pack(anchor='w', pady=(0, 4))

        self.info_meta = ctk.CTkLabel(
            self.info_box, text='',
            text_color=('gray40', 'gray60'),
            font=ctk.CTkFont(size=12),
        )
        self.info_meta.pack(anchor='w')

    def _build_right_panel(self, parent):
        panel = ctk.CTkFrame(parent)
        panel.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # 章节列表头
        header = ctk.CTkFrame(panel, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 4))

        ctk.CTkLabel(
            header, text='章节列表',
            font=ctk.CTkFont(size=14, weight='bold'),
        ).pack(side='left')

        ctrl = ctk.CTkFrame(header, fg_color='transparent')
        ctrl.pack(side='right')
        ctk.CTkButton(ctrl, text='全选', width=56, height=26, command=self._select_all) \
            .pack(side='left', padx=(0, 4))
        ctk.CTkButton(ctrl, text='反选', width=56, height=26, command=self._invert_selection) \
            .pack(side='left', padx=(0, 4))
        ctk.CTkButton(ctrl, text='清空', width=56, height=26, command=self._clear_selection) \
            .pack(side='left')

        # 章节列表（可滚动）
        self.chapter_box = ctk.CTkScrollableFrame(panel, label_text='')
        self.chapter_box.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 4))

        self._show_chapter_placeholder('请先解析小说以获取章节列表')

        # 下载控制
        dl_frame = ctk.CTkFrame(panel, fg_color='transparent')
        dl_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(4, 10))

        self.start_btn = ctk.CTkButton(
            dl_frame, text='开始下载', height=34, command=self._on_download_click,
        )
        self.start_btn.pack(side='left', fill='x', expand=True, padx=(0, 6))

        self.cancel_btn = ctk.CTkButton(
            dl_frame, text='取消', height=34,
            fg_color='#C0392B', hover_color='#922B21',
            command=self._on_cancel_click, state='disabled',
        )
        self.cancel_btn.pack(side='left')

    def _build_bottom_panel(self):
        bottom = ctk.CTkFrame(self, fg_color='transparent')
        bottom.pack(fill='x', side='bottom', padx=12, pady=(0, 8))

        # 进度条
        self.progress = ctk.CTkProgressBar(bottom, height=14)
        self.progress.pack(fill='x', pady=(0, 4))
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(
            bottom, text='就绪',
            font=ctk.CTkFont(size=11),
            text_color=('gray40', 'gray60'),
        )
        self.progress_label.pack(anchor='w', pady=(0, 4))

        # 日志框
        self.log_box = ctk.CTkTextbox(bottom, height=120, font=ctk.CTkFont(size=12))
        self.log_box.pack(fill='both', expand=True)
        self.log_box.configure(state='disabled')

    # ===================== 占位符 =====================

    def _show_chapter_placeholder(self, text: str):
        """显示章节列表占位符（清空后重建）"""
        for widget in self.chapter_box.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.chapter_box, text=text,
            text_color=('gray50', 'gray50'),
        ).pack(pady=40)

    def _show_search_placeholder(self, text: str):
        """显示搜索结果占位符"""
        for widget in self.search_results_box.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.search_results_box, text=text,
            text_color=('gray50', 'gray50'),
        ).pack(pady=10)

    # ===================== 源切换 =====================

    def _on_source_menu_change(self, choice: str):
        """下拉菜单切换源（choice 是显示标签）"""
        # 反查 key
        for key, label in SOURCE_KEYS.items():
            if label == choice:
                self._switch_source(key)
                return
        self.log(f'未知源选项: {choice}', 'error')

    def _switch_source(self, source_key: str):
        """切换源，并同步下拉菜单显示"""
        try:
            if source_key == 'biquge':
                self.current_source = BiqugeSource()
                self.current_source_key = 'biquge'
                self.login_btn.pack_forget()
                self.login_status_label.configure(text='')
            elif source_key == 'fanqie_api':
                self.current_source = FanqieSource(use_api=True)
                self.current_source_key = 'fanqie_api'
                self.login_btn.pack_forget()
                self.login_status_label.configure(text='')
            elif source_key == 'fanqie_official':
                self.current_source = FanqieSource(use_api=False)
                self.current_source_key = 'fanqie_official'
                self.login_btn.pack(side='left', padx=(0, 4))
                self._update_login_status()
            else:
                self.log(f'未知源: {source_key}', 'error')
                return

            # 同步下拉菜单显示
            self.source_var.set(SOURCE_KEYS.get(source_key, source_key))
            self.log(f'已切换到源：{SOURCE_KEYS.get(source_key, source_key)}', 'info')
        except Exception as e:
            self.log(f'切换源失败: {e}', 'error')

    # ===================== 解析小说 =====================

    def _on_parse_click(self):
        if not self.current_source:
            self.log('请先选择小说源', 'warning')
            return

        raw = self.url_entry.get().strip()
        if not raw:
            self.log('请输入小说 URL 或 ID', 'warning')
            return

        # 清除旧状态，避免残留
        self.current_novel_info = None
        self.current_chapters = []
        self.chapter_vars = []
        self._show_chapter_placeholder('正在解析...')

        # 捕获当前源引用，避免线程竞态
        source = self.current_source

        # 解析 ID
        novel_id = type(source).parse_novel_url(raw)
        if not novel_id:
            # 无法解析为 ID，尝试作为关键词搜索
            self.log(f'无法解析为小说 ID，尝试搜索: {raw}', 'info')
            self.search_entry.delete(0, 'end')
            self.search_entry.insert(0, raw)
            self._on_search_click()
            return

        self.parse_btn.configure(state='disabled', text='解析中...')
        self.log(f'正在解析小说: {novel_id}', 'info')

        def worker():
            try:
                info = source.get_novel_info(novel_id)
                self.after(0, lambda: self._handle_parse_result(info, None))
            except SourceError as e:
                self.after(0, lambda: self._handle_parse_result(None, e))
            except Exception as e:
                err = SourceError(str(e), error_type='UNKNOWN')
                self.after(0, lambda: self._handle_parse_result(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_parse_result(self, info: NovelInfo | None, error: SourceError | None):
        self.parse_btn.configure(state='normal', text='解析')

        if error:
            self.log(f'解析失败: {error.message} (类型: {error.error_type})', 'error')
            self._show_chapter_placeholder('解析失败，请重试')
            return

        if not info:
            self.log('解析失败：未获取到小说信息', 'error')
            self._show_chapter_placeholder('解析失败，请重试')
            return

        self.current_novel_info = info
        # 显示小说信息
        self.info_title.configure(text=info.title or '未知书名')
        self.info_author.configure(text=f'作者：{info.author or "未知"}')
        self.info_desc.configure(text=info.description or '（无简介）')
        meta_parts = []
        if info.chapter_count:
            meta_parts.append(f'章节 {info.chapter_count}')
        if info.word_count:
            meta_parts.append(f'字数 {info.word_count}')
        if info.extra:
            if info.extra.get('category'):
                meta_parts.append(info.extra['category'])
            if info.extra.get('status'):
                meta_parts.append(info.extra['status'])
        self.info_meta.configure(text=' | '.join(meta_parts) if meta_parts else '')

        self.log(f'解析成功：{info.title} - {info.author}', 'success')

        # 获取章节列表
        self._fetch_chapters(info.novel_id)

    def _fetch_chapters(self, novel_id: str):
        # 捕获源引用
        source = self.current_source
        if not source:
            return
        self.log('正在获取章节列表...', 'info')

        def worker():
            try:
                chapters = source.get_chapter_list(novel_id)
                self.after(0, lambda: self._handle_chapters_result(chapters, None))
            except SourceError as e:
                self.after(0, lambda: self._handle_chapters_result(None, e))
            except Exception as e:
                err = SourceError(str(e), error_type='UNKNOWN')
                self.after(0, lambda: self._handle_chapters_result(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_chapters_result(self, chapters, error):
        if error:
            self.log(f'获取章节列表失败: {error.message}', 'error')
            self._show_chapter_placeholder('获取章节失败，请重试')
            return

        if not chapters:
            self.log('章节列表为空', 'warning')
            self._show_chapter_placeholder('未获取到章节')
            return

        self.current_chapters = chapters
        self._render_chapter_list(chapters)
        self.log(f'共获取 {len(chapters)} 章', 'success')

    def _render_chapter_list(self, chapters):
        # 清空旧列表（包括占位符）
        for widget in self.chapter_box.winfo_children():
            widget.destroy()

        self.chapter_vars = []
        for ch in chapters:
            var = ctk.BooleanVar(value=True)
            row = ctk.CTkFrame(self.chapter_box, fg_color='transparent')
            row.pack(fill='x', pady=1)

            ctk.CTkCheckBox(row, text=ch.chapter_title, variable=var) \
                .pack(side='left', fill='x', expand=True)
            self.chapter_vars.append(var)

    # ===================== 搜索（Bing 后备） =====================

    def _on_search_click(self):
        """搜索：用 Bing 搜索引擎查找小说，从结果中提取番茄/笔趣阁链接"""
        keyword = self.search_entry.get().strip()
        if not keyword:
            self.log('请输入搜索关键词', 'warning')
            return

        self.search_btn.configure(state='disabled', text='搜索中...')
        self._show_search_placeholder('正在通过 Bing 搜索...')
        self.log(f'搜索: {keyword}（使用 Bing 搜索引擎）', 'info')

        def worker():
            try:
                results = search_via_bing(keyword)
                self.after(0, lambda: self._handle_search_result(results, None))
            except Exception as e:
                err = SourceError(f'搜索失败: {e}', error_type='NETWORK')
                self.after(0, lambda: self._handle_search_result(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_search_result(self, results, error):
        self.search_btn.configure(state='normal', text='搜索')

        # 清空旧结果
        for widget in self.search_results_box.winfo_children():
            widget.destroy()

        if error:
            self.log(f'搜索失败: {error.message}', 'error')
            self._show_search_placeholder('搜索失败')
            return

        if not results:
            self.log('无搜索结果（Bing 未找到番茄/笔趣阁链接）', 'info')
            self._show_search_placeholder('无结果，请尝试其他关键词或直接输入小说 URL')
            return

        # 按来源分组统计
        source_counts = Counter(r.get('source', '') for r in results)
        stat_text = ' | '.join(
            f'{SEARCH_SOURCE_LABEL.get(s, s)} {n} 条'
            for s, n in source_counts.items() if s
        )
        self.log(f'搜索到 {len(results)} 条结果 ({stat_text})', 'success')

        for r in results:
            src_key = r.get('source', '')
            src_label = SEARCH_SOURCE_LABEL.get(src_key, src_key)
            title = r.get('title', '')[:60]
            novel_id = r.get('novel_id', '')

            row = ctk.CTkFrame(self.search_results_box, fg_color='transparent')
            row.pack(fill='x', pady=2)

            text = f'[{src_label}] {title}'
            ctk.CTkButton(
                row, text=text, anchor='w', height=28,
                fg_color='transparent',
                hover_color=('#D6D6D6', '#3A3A3A'),
                command=lambda r=r: self._on_search_pick(r),
            ).pack(fill='x')

    def _on_search_pick(self, result: dict):
        """点击搜索结果：切换到对应源并解析"""
        src_key = result.get('source', '')
        novel_id = str(result.get('novel_id', ''))
        title = result.get('title', '')

        # 根据搜索结果来源切换源
        if src_key == 'biquge':
            if self.current_source_key != 'biquge':
                self._switch_source('biquge')
        elif src_key == 'fanqie':
            # 番茄搜索结果使用 API 模式下载（免登录）
            if self.current_source_key != 'fanqie_api':
                self._switch_source('fanqie_api')

        # 填入 novel_id 并触发解析
        self.url_entry.delete(0, 'end')
        self.url_entry.insert(0, novel_id)
        self.log(
            f'已选择 [{SEARCH_SOURCE_LABEL.get(src_key, src_key)}]: {title}，开始解析...',
            'info',
        )
        self._on_parse_click()

    # ===================== 选择控制 =====================

    def _select_all(self):
        for v in self.chapter_vars:
            v.set(True)

    def _invert_selection(self):
        for v in self.chapter_vars:
            v.set(not v.get())

    def _clear_selection(self):
        for v in self.chapter_vars:
            v.set(False)

    # ===================== 下载 =====================

    def _on_download_click(self):
        if not self.current_novel_info or not self.current_chapters:
            self.log('请先解析小说', 'warning')
            return

        if self.is_downloading:
            self.log('正在下载中，请先取消', 'warning')
            return

        # 收集选中章节
        selected = []
        for i, var in enumerate(self.chapter_vars):
            if var.get():
                selected.append(self.current_chapters[i])

        if not selected:
            self.log('请选择至少一个章节', 'warning')
            return

        # 选择输出目录
        default_dir = app_config.DOWNLOAD_DIR
        out_dir = filedialog.askdirectory(
            title='选择保存目录', initialdir=default_dir,
        )
        if not out_dir:
            self.log('已取消下载', 'info')
            return

        # 捕获源引用，避免线程竞态
        source = self.current_source
        if not source:
            self.log('源未初始化', 'error')
            return

        # 开始下载
        self.is_downloading = True
        self.cancel_event.clear()
        self.start_btn.configure(state='disabled')
        self.cancel_btn.configure(state='normal')
        self.progress.set(0)

        self.download_thread = threading.Thread(
            target=self._download_worker,
            args=(source, self.current_novel_info, selected, out_dir),
            daemon=True,
        )
        self.download_thread.start()

    def _on_cancel_click(self):
        if self.is_downloading:
            self.cancel_event.set()
            self.log('正在取消下载...', 'warning')

    def _download_worker(self, source: BaseSource, novel_info: NovelInfo, chapters, out_dir: str):
        total = len(chapters)
        success = 0
        failed = 0
        all_content = []
        cancelled = False

        safe_title = self._safe_filename(novel_info.title)

        for i, ch in enumerate(chapters, 1):
            if self.cancel_event.is_set():
                cancelled = True
                break

            self.after(0, lambda i=i, t=ch.chapter_title: self._update_progress(
                i, total, f'下载中: {t}'))

            try:
                result = source.get_chapter_content(novel_info.novel_id, ch.chapter_id)
                if result and result.get('content'):
                    all_content.append({
                        'title': result.get('title', ch.chapter_title),
                        'content': result['content'],
                        'index': ch.chapter_index,
                    })
                    success += 1
                    self.after(0, lambda i=i: self._update_progress(
                        i, total, f'已完成 {i}/{total}'))
                else:
                    failed += 1
                    self.after(0, lambda t=ch.chapter_title: self.log(
                        f'章节获取失败: {t}', 'error'))
            except Exception as e:
                failed += 1
                self.after(0, lambda t=ch.chapter_title, e=e: self.log(
                    f'章节异常 [{t}]: {e}', 'error'))

        # 保存文件（仅在有内容时）
        saved_path = None
        if all_content:
            try:
                # 按章节顺序排序，防御 index 为 None 的情况
                all_content.sort(key=lambda x: x['index'] if x['index'] is not None else 0)
                out_path = os.path.join(out_dir, f'{safe_title}.txt')
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(f'《{novel_info.title}》\n')
                    f.write(f'作者：{novel_info.author}\n')
                    f.write(f'来源：{source.display_name}\n')
                    f.write(f'章节数：{success}\n')
                    if cancelled:
                        f.write(f'（已取消，未完成全部章节）\n')
                    f.write('=' * 50 + '\n\n')
                    for item in all_content:
                        f.write(item['title'] + '\n\n')
                        f.write(item['content'] + '\n\n\n')
                saved_path = out_path
            except Exception as e:
                self.after(0, lambda e=e: self.log(f'保存文件失败: {e}', 'error'))

        # 完成回调
        self.after(0, lambda: self._on_download_complete(success, failed, total, cancelled, saved_path))

    def _on_download_complete(self, success: int, failed: int, total: int,
                               cancelled: bool, saved_path: str | None):
        self.is_downloading = False
        self.start_btn.configure(state='normal')
        self.cancel_btn.configure(state='disabled')

        if cancelled:
            self.progress.set(success / total if total > 0 else 0)
            msg = f'下载已取消：已完成 {success}，失败 {failed}，共 {total}'
            level = 'warning'
        else:
            self.progress.set(1.0 if success else 0)
            msg = f'下载完成：成功 {success}，失败 {failed}，共 {total}'
            level = 'success' if failed == 0 else 'warning'

        self.progress_label.configure(text=msg)
        self.log(msg, level)
        if saved_path:
            self.log(f'已保存到: {saved_path}', 'success')

    # ===================== 登录（番茄官网模式） =====================

    def _on_login_click(self):
        if self.current_source_key != 'fanqie_official':
            return

        # 检查是否已登录 → 退出登录
        cookies = app_config.load_cookies()
        logged_in = len(cookies) > 0 and any(
            k in cookies for k in ['sessionid', 'passport_csrf_token', 'passport_assist_user']
        )
        if logged_in:
            if messagebox.askyesno('确认', '确定要退出登录吗？'):
                app_config.clear_cookies()
                self._update_login_status()
                self.log('已退出登录', 'info')
            return

        # 打开登录对话框（复用原 gui.py 的 LoginDialog）
        try:
            import gui as _gui
            self.login_dlg = _gui.LoginDialog(self, self._on_login_result)
            _gui.login_dialog_instance = self.login_dlg
        except Exception as e:
            self.log(f'打开登录对话框失败: {e}', 'error')

    def _on_login_result(self, success: bool):
        if success:
            self.log('登录成功', 'success')
        else:
            self.log('登录失败或已取消', 'warning')
        self._update_login_status()

    def _update_login_status(self):
        try:
            cookies = app_config.load_cookies()
            logged_in = len(cookies) > 0 and any(
                k in cookies for k in ['sessionid', 'passport_csrf_token', 'passport_assist_user']
            )
            self.login_status_label.configure(text='已登录' if logged_in else '未登录')
            self.login_btn.configure(text='退出登录' if logged_in else '登录')
        except Exception:
            self.login_status_label.configure(text='')

    # ===================== 设置 =====================

    def _on_settings_click(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title('设置')
        dlg.geometry('460x340')
        dlg.transient(self)
        dlg.grab_set()

        # 窗口关闭时按取消处理
        dlg.protocol('WM_DELETE_WINDOW', lambda: dlg.destroy())

        ctk.CTkLabel(
            dlg, text='设置',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).pack(pady=(16, 8))

        # 并发数
        conc_frame = ctk.CTkFrame(dlg, fg_color='transparent')
        conc_frame.pack(fill='x', padx=20, pady=8)
        cur_conc = app_config.get_concurrent_downloads()
        conc_var = ctk.IntVar(value=cur_conc)
        ctk.CTkLabel(conc_frame, text='并发下载数：').pack(side='left')
        ctk.CTkOptionMenu(
            conc_frame, variable=conc_var, values=[str(i) for i in range(1, 6)],
        ).pack(side='right')

        # 下载速度
        speed_frame = ctk.CTkFrame(dlg, fg_color='transparent')
        speed_frame.pack(fill='x', padx=20, pady=8)
        cur_speed = app_config.get_download_speed()
        speed_var = ctk.DoubleVar(value=cur_speed)
        ctk.CTkLabel(speed_frame, text='下载速度倍数：').pack(side='left')
        ctk.CTkOptionMenu(
            speed_frame, variable=speed_var, values=['0.5', '1.0', '2.0', '3.0', '4.0'],
        ).pack(side='right')

        # 按钮区
        btn_frame = ctk.CTkFrame(dlg, fg_color='transparent')
        btn_frame.pack(fill='x', padx=20, pady=(8, 16))

        def save():
            app_config.set_concurrent_downloads(conc_var.get())
            app_config.set_download_speed(float(speed_var.get()))
            self.log('设置已保存', 'success')
            dlg.destroy()

        ctk.CTkButton(btn_frame, text='保存', command=save) \
            .pack(side='right', padx=(4, 0))
        ctk.CTkButton(
            btn_frame, text='取消', fg_color='transparent',
            border_width=1, command=lambda: dlg.destroy(),
        ).pack(side='right')

    # ===================== 工具方法 =====================

    def _update_progress(self, current: int, total: int, label: str):
        self.progress.set(current / total if total > 0 else 0)
        self.progress_label.configure(text=f'{label} ({current}/{total})')

    # Windows 保留文件名
    _WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | \
        {f'COM{i}' for i in range(1, 10)} | {f'LPT{i}' for i in range(1, 10)}

    def _safe_filename(self, name: str) -> str:
        if not name:
            return 'novel'
        for ch in '\\/:*?"<>|':
            name = name.replace(ch, '_')
        name = name.strip().strip('.')
        # 处理 Windows 保留名
        base = name.split('.')[0].upper()
        if base in self._WINDOWS_RESERVED:
            name = '_' + name
        return name or 'novel'

    def log(self, message: str, level: str = 'info'):
        """输出日志到底部日志框"""
        prefix = {
            'info': '[INFO]',
            'success': '[OK]',
            'warning': '[WARN]',
            'error': '[ERR]',
        }.get(level, '[INFO]')
        ts = time.strftime('%H:%M:%S')
        line = f'{ts} {prefix} {message}\n'

        self.log_box.configure(state='normal')
        self.log_box.insert('end', line)
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def _on_close(self):
        """窗口关闭处理：取消下载后退出"""
        if self.is_downloading:
            if not messagebox.askyesno('确认退出', '正在下载中，确定要退出吗？'):
                return
            self.cancel_event.set()
            # 给下载线程一点时间清理
            if self.download_thread and self.download_thread.is_alive():
                self.download_thread.join(timeout=2.0)
        self.destroy()


def main():
    app = FXDownloaderApp()
    app.mainloop()


if __name__ == '__main__':
    main()
