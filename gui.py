# GUI界面模块 - 美化版
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from spider import FanqieSpider, parse_novel_url
from downloader import NovelDownloader


class ModernStyle:
    """现代化样式配置"""
    COLORS = {
        'primary': '#FF6B6B',
        'primary_hover': '#FF5252',
        'bg': '#F8F9FA',
        'surface': '#FFFFFF',
        'text': '#2D3436',
        'text_secondary': '#636E72',
        'border': '#DFE6E9',
        'success': '#00B894',
        'error': '#D63031',
        'warning': '#FD79A8',
    }
    
    FONTS = {
        'title': ('Microsoft YaHei UI', 14, 'bold'),
        'header': ('Microsoft YaHei UI', 11, 'bold'),
        'normal': ('Microsoft YaHei UI', 9),
        'small': ('Microsoft YaHei UI', 8),
    }


class NovelDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FXdownloader - 番茄小说下载器")
        self.root.geometry("850x700")
        self.root.resizable(True, True)
        self.root.minsize(700, 500)
        
        # 设置样式
        self.setup_styles()
        
        # 初始化爬虫和下载器
        self.spider = FanqieSpider()
        self.downloader = NovelDownloader()
        self.current_novel_id = None

        # 创建界面
        self.create_widgets()

    def setup_styles(self):
        """设置现代化样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        colors = ModernStyle.COLORS
        fonts = ModernStyle.FONTS
        
        # LabelFrame样式
        style.configure('Modern.TLabelframe',
                       background=colors['bg'],
                       bordercolor=colors['border'],
                       borderwidth=1)
        style.configure('Modern.TLabelframe.Label',
                       background=colors['bg'],
                       foreground=colors['text'],
                       font=fonts['header'],
                       padding=(10, 5))
        
        # Entry样式
        style.configure('Modern.TEntry',
                       fieldbackground=colors['surface'],
                       bordercolor=colors['border'],
                       lightcolor=colors['border'],
                       darkcolor=colors['border'],
                       padding=8,
                       font=fonts['normal'])
        
        # Button样式
        style.configure('Primary.TButton',
                       background=colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       padding=(20, 10),
                       font=fonts['header'])
        style.map('Primary.TButton',
                 background=[('active', colors['primary_hover']),
                           ('pressed', colors['primary_hover'])])
        
        style.configure('Success.TButton',
                       background=colors['success'],
                       foreground='white',
                       borderwidth=0,
                       padding=(15, 8),
                       font=fonts['header'])
        style.map('Success.TButton',
                 background=[('active', '#00A383'),
                           ('pressed', '#00A383')])
        
        # Label样式
        style.configure('Modern.TLabel',
                       background=colors['bg'],
                       foreground=colors['text'],
                       font=fonts['normal'])
        
        # ScrolledText样式
        style.configure('Modern.TText',
                       font=fonts['normal'],
                       padding=5)

    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_container = tk.Frame(self.root, bg=ModernStyle.COLORS['bg'])
        main_container.pack(fill='both', expand=True)
        
        # 创建标题栏
        self.create_title_bar(main_container)
        
        # 创建内容区域
        content_frame = tk.Frame(main_container, bg=ModernStyle.COLORS['bg'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 输入区域
        self.create_input_section(content_frame)
        
        # 小说信息显示
        self.create_info_section(content_frame)
        
        # 操作按钮
        self.create_button_section(content_frame)
        
        # 日志显示
        self.create_log_section(content_frame)

    def create_title_bar(self, parent):
        """创建标题栏"""
        title_frame = tk.Frame(parent, bg=ModernStyle.COLORS['primary'], height=60)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📚 FXdownloader",
            font=('Microsoft YaHei UI', 16, 'bold'),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        title_label.pack(side='left', padx=20, pady=15)
        
        subtitle_label = tk.Label(
            title_frame,
            text="番茄小说下载器",
            font=('Microsoft YaHei UI', 9),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        subtitle_label.pack(side='left', padx=5, pady=15)

    def create_input_section(self, parent):
        """创建输入区域"""
        input_frame = ttk.LabelFrame(parent, text="📖 小说信息", style='Modern.TLabelframe', padding=15)
        input_frame.pack(fill='x', pady=(0, 10))
        
        # 第一行：URL输入
        url_frame = tk.Frame(input_frame, bg=ModernStyle.COLORS['bg'])
        url_frame.pack(fill='x', pady=5)
        
        url_label = tk.Label(
            url_frame,
            text="小说URL或ID:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        url_label.pack(side='left', padx=(0, 10))
        
        self.url_entry = ttk.Entry(url_frame, style='Modern.TEntry')
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        get_info_btn = ttk.Button(
            url_frame,
            text="🔍 获取信息",
            command=self.get_novel_info,
            style='Primary.TButton'
        )
        get_info_btn.pack(side='left')
        
        # 第二行：章节范围
        chapter_frame = tk.Frame(input_frame, bg=ModernStyle.COLORS['bg'])
        chapter_frame.pack(fill='x', pady=5)
        
        start_label = tk.Label(
            chapter_frame,
            text="起始章节:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        start_label.pack(side='left', padx=(0, 10))
        
        self.start_chapter = ttk.Entry(chapter_frame, style='Modern.TEntry', width=10)
        self.start_chapter.insert(0, '1')
        self.start_chapter.pack(side='left', padx=(0, 20))
        
        end_label = tk.Label(
            chapter_frame,
            text="结束章节:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        end_label.pack(side='left', padx=(0, 10))
        
        self.end_chapter = ttk.Entry(chapter_frame, style='Modern.TEntry', width=10)
        self.end_chapter.pack(side='left', padx=(0, 10))
        
        tip_label = tk.Label(
            chapter_frame,
            text="(留空表示全部)",
            font=ModernStyle.FONTS['small'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text_secondary']
        )
        tip_label.pack(side='left')

    def create_info_section(self, parent):
        """创建小说信息显示区域"""
        info_frame = ttk.LabelFrame(parent, text="📋 小说详情", style='Modern.TLabelframe', padding=15)
        info_frame.pack(fill='x', pady=(0, 10))
        
        info_grid = tk.Frame(info_frame, bg=ModernStyle.COLORS['bg'])
        info_grid.pack(fill='x')
        
        # 创建两列布局
        for i, (label, attr) in enumerate([
            ("书名", 'novel_title'),
            ("作者", 'novel_author'),
            ("字数", 'novel_word_count'),
            ("章节数", 'novel_chapter_count')
        ]):
            row = i // 2
            col = (i % 2) * 2
            
            lbl = tk.Label(
                info_grid,
                text=f"{label}:",
                font=ModernStyle.FONTS['header'],
                bg=ModernStyle.COLORS['bg'],
                fg=ModernStyle.COLORS['text'],
                width=8,
                anchor='w'
            )
            lbl.grid(row=row, column=col, sticky='w', padx=(0, 10), pady=5)
            
            val = tk.Label(
                info_grid,
                text="暂无",
                font=ModernStyle.FONTS['normal'],
                bg=ModernStyle.COLORS['bg'],
                fg=ModernStyle.COLORS['text_secondary'],
                anchor='w'
            )
            val.grid(row=row, column=col+1, sticky='w', pady=5)
            
            setattr(self, attr, val)
        
        # 简介单独一行
        desc_frame = tk.Frame(info_grid, bg=ModernStyle.COLORS['bg'])
        desc_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=(10, 0))
        
        desc_label = tk.Label(
            desc_frame,
            text="简介:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text'],
            width=8,
            anchor='nw'
        )
        desc_label.pack(side='left')
        
        self.novel_description = tk.Label(
            desc_frame,
            text="暂无",
            font=ModernStyle.FONTS['normal'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text_secondary'],
            anchor='w',
            wraplength=600
        )
        self.novel_description.pack(side='left', fill='x', expand=True)

    def create_button_section(self, parent):
        """创建操作按钮区域"""
        button_frame = tk.Frame(parent, bg=ModernStyle.COLORS['bg'])
        button_frame.pack(fill='x', pady=(0, 10))
        
        self.download_button = ttk.Button(
            button_frame,
            text="⬇️  开始下载",
            command=self.start_download,
            style='Primary.TButton'
        )
        self.download_button.pack(side='left', padx=(0, 10))
        
        self.export_button = ttk.Button(
            button_frame,
            text="📝 导出TXT",
            command=self.export_novel,
            style='Success.TButton'
        )
        self.export_button.pack(side='left')

    def create_log_section(self, parent):
        """创建日志显示区域"""
        log_frame = ttk.LabelFrame(parent, text="📝 下载日志", style='Modern.TLabelframe', padding=15)
        log_frame.pack(fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            state='disabled',
            font=('Consolas', 9),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=10,
            pady=10,
            relief='flat'
        )
        self.log_text.pack(fill='both', expand=True)

    def log(self, message, level='info'):
        """添加日志"""
        colors = {
            'info': '#2D3436',
            'success': '#00B894',
            'error': '#D63031',
            'warning': '#FD79A8',
        }
        
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + '\n', (level,))
        self.log_text.tag_config(level, foreground=colors.get(level, colors['info']))
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.root.update()

    def get_novel_info(self):
        """获取小说信息"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning('提示', '请输入小说URL或ID')
            self.url_entry.focus()
            return

        novel_id = parse_novel_url(url)
        if not novel_id:
            messagebox.showerror('错误', '无效的小说URL或ID')
            return

        self.log(f"正在获取小说信息: {novel_id}")
        self.root.update()

        novel_info = self.spider.get_novel_info(novel_id)
        if novel_info:
            self.current_novel_id = novel_info['novel_id']
            self.novel_title.config(text=novel_info['title'])
            self.novel_author.config(text=novel_info['author'])
            self.novel_word_count.config(text=f"{novel_info['word_count']:,}")
            self.novel_chapter_count.config(text=str(novel_info['chapter_count']))
            self.novel_description.config(text=novel_info['description'][:150] + '...' if len(novel_info['description']) > 150 else novel_info['description'])
            self.end_chapter.delete(0, tk.END)
            self.end_chapter.insert(0, str(novel_info['chapter_count']))
            self.log(f"获取成功: {novel_info['title']}", 'success')
        else:
            messagebox.showerror('错误', '获取小说信息失败')
            self.log("获取小说信息失败", 'error')

    def start_download(self):
        """开始下载"""
        if not self.current_novel_id:
            messagebox.showwarning('提示', '请先获取小说信息')
            return

        try:
            start_chapter = int(self.start_chapter.get())
        except ValueError:
            messagebox.showerror('错误', '起始章节必须是数字')
            return

        end_chapter = self.end_chapter.get().strip()
        end_chapter = int(end_chapter) if end_chapter else None

        # 禁用按钮
        self.download_button.config(state='disabled')
        self.export_button.config(state='disabled')

        # 在新线程中下载
        thread = threading.Thread(target=self._download_thread, args=(start_chapter, end_chapter))
        thread.daemon = True
        thread.start()

    def _download_thread(self, start_chapter, end_chapter):
        """下载线程"""
        try:
            self.log("=" * 60)
            self.log(f"开始下载: {self.current_novel_id}", 'info')
            self.log("=" * 60)

            # 清除所有旧数据
            self.log("正在清除旧数据...")
            self.downloader.db.delete_novel(self.current_novel_id)
            self.log("旧数据已清除", 'success')

            # 获取小说信息
            novel_info = self.spider.get_novel_info(self.current_novel_id)
            if not novel_info:
                self.log("获取小说信息失败！", 'error')
                return

            self.log(f"小说名称: {novel_info['title']}")
            self.log(f"作者: {novel_info['author']}")
            self.log(f"字数: {novel_info['word_count']:,}")
            self.log(f"章节数: {novel_info['chapter_count']}")

            # 保存小说信息
            self.downloader.db.save_novel(
                novel_id=novel_info['novel_id'],
                title=novel_info['title'],
                author=novel_info['author'],
                description=novel_info['description'],
                cover_url=novel_info['cover_url'],
                word_count=novel_info['word_count'],
                chapter_count=novel_info['chapter_count']
            )

            # 获取章节列表
            chapters = self.spider.get_chapter_list(self.current_novel_id)
            if not chapters:
                self.log("获取章节列表失败！", 'error')
                return

            total_chapters = len(chapters)
            self.log(f"共获取到 {total_chapters} 个章节", 'success')

            # 确定下载范围
            start_index = max(1, start_chapter) - 1
            end_index = min(total_chapters, end_chapter) if end_chapter else total_chapters

            self.log(f"下载范围: 第 {start_index + 1} 章到第 {end_index} 章")
            self.log("=" * 60)

            # 下载章节
            success_count = 0
            for idx in range(start_index, end_index):
                chapter = chapters[idx]
                self.log(f"[{idx + 1}/{total_chapters}] 正在下载: {chapter['chapter_title']}")

                chapter_data = self.spider.get_chapter_content(self.current_novel_id, chapter['chapter_id'])

                if chapter_data:
                    real_title = chapter_data.get('title', chapter['chapter_title'])
                    content = chapter_data.get('content', '')
                    word_count = len(content)
                    
                    self.downloader.db.save_chapter(
                        novel_id=self.current_novel_id,
                        chapter_id=chapter['chapter_id'],
                        chapter_title=real_title,
                        chapter_index=chapter['chapter_index'],
                        content=content,
                        word_count=word_count
                    )
                    success_count += 1
                    self.log(f"  ✓ 成功 - {real_title} ({word_count} 字)", 'success')
                else:
                    self.log(f"  ✗ 失败", 'error')

            self.log("=" * 60)
            self.log(f"下载完成！成功下载 {success_count}/{end_index - start_index} 个章节", 'success')
            self.log("=" * 60)

            # 更新状态
            if success_count == end_index - start_index:
                self.downloader.db.update_novel_status(self.current_novel_id, '下载完成')
            else:
                self.downloader.db.update_novel_status(self.current_novel_id, '部分下载')

            messagebox.showinfo('完成', f'下载完成！\n成功下载 {success_count} 个章节')

        except Exception as e:
            self.log(f"下载出错: {e}", 'error')
            messagebox.showerror('错误', f'下载出错: {e}')
        finally:
            self.root.after(0, lambda: self.download_button.config(state='normal'))
            self.root.after(0, lambda: self.export_button.config(state='normal'))

    def export_novel(self):
        """导出小说"""
        if not self.current_novel_id:
            messagebox.showwarning('提示', '请先获取小说信息')
            return

        title = self.novel_title.cget('text')
        file_path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')],
            initialfile=f"{title}.txt"
        )

        if file_path:
            if self.downloader.export_to_txt(self.current_novel_id, file_path):
                messagebox.showinfo('成功', '导出成功！')
                self.log(f"导出成功: {file_path}", 'success')
            else:
                messagebox.showerror('错误', '导出失败！')
                self.log(f"导出失败: {file_path}", 'error')


def main():
    root = tk.Tk()
    app = NovelDownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()