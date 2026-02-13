# GUI界面模块 - 美化版
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from spider import FanqieSpider, parse_novel_url
from downloader import NovelDownloader
from config import save_cookies, load_cookies
import http.server
import socketserver
import json
import webbrowser
import os
import time


# 全局变量用于存储登录对话框实例
login_dialog_instance = None


class CookieHandler(http.server.SimpleHTTPRequestHandler):
    """Cookie请求处理器"""
    def __init__(self, *args, **kwargs):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=base_dir, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/login':
            self.path = '/login_helper.html'
        return super().do_GET()
    
    def do_POST(self):
        global login_dialog_instance
        if self.path == '/save_cookies':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                cookies = data.get('cookies', {})
                
                # 保存cookie
                save_cookies(cookies)
                
                # 通知主窗口
                if login_dialog_instance:
                    login_dialog_instance.cookies_received = True
                    # 延迟关闭对话框
                    login_dialog_instance.dialog.after(2000, login_dialog_instance.on_login_success)
                
                # 发送成功响应
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
                
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 禁用日志输出


class LoginDialog:
    """登录对话框"""
    def __init__(self, parent, callback):
        self.callback = callback
        self.server_thread = None
        self.server_port = 0
        self.cookies_received = False
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("账户登录")
        self.dialog.geometry("700x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        self.create_widgets()
        
        # 绑定关闭事件
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 启动本地服务器
        self.start_server()
    
    def create_widgets(self):
        """创建登录界面组件"""
        # 主容器
        main_frame = tk.Frame(self.dialog, bg='#FFFFFF')
        main_frame.pack(fill='both', expand=True)
        
        # 标题栏
        title_frame = tk.Frame(main_frame, bg='#FF6B6B', height=50)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📱 自动获取Cookie登录",
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='#FF6B6B',
            fg='white'
        )
        title_label.pack(pady=12)
        
        # 内容区域
        content_frame = tk.Frame(main_frame, bg='#FFFFFF', padx=30, pady=20)
        content_frame.pack(fill='both', expand=True)
        
        # 说明文本
        info_text = """点击下方按钮将打开一个本地网页，该页面会：
1. 自动打开番茄小说登录窗口
2. 您在登录窗口中完成登录（电脑仅支持手机号）
3. 登录成功后，网页会自动获取Cookie（用于SVIP账户身份验证以下载全本小说）
4. Cookie会自动保存到本地软件中

整个过程完全自动化！"""
        
        info_label = tk.Label(
            content_frame,
            text=info_text,
            font=('Microsoft YaHei UI', 10),
            bg='#F8F9FA',
            fg='#2D3436',
            justify='left',
            padx=20,
            pady=20
        )
        info_label.pack(fill='x', pady=(0, 20))
        
        # 状态显示
        self.status_label = tk.Label(
            content_frame,
            text="准备就绪",
            font=('Microsoft YaHei UI', 10),
            bg='#FFFFFF',
            fg='#636E72'
        )
        self.status_label.pack(pady=(0, 15))
        
        # 按钮
        self.start_btn = tk.Button(
            content_frame,
            text="🚀 开始自动获取Cookie",
            command=self.start_auto_login,
            bg='#00B894',
            fg='white',
            borderwidth=0,
            padx=30,
            pady=15,
            font=('Microsoft YaHei UI', 11, 'bold'),
            cursor='hand2',
            activebackground='#00A383',
            activeforeground='white'
        )
        self.start_btn.pack()
        
        # 手动方式按钮
        tk.Button(
            content_frame,
            text="📝 手动输入Cookie",
            command=self.show_manual_cookie_dialog,
            bg='#DFE6E9',
            fg='#636E72',
            borderwidth=0,
            padx=20,
            pady=10,
            font=('Microsoft YaHei UI', 9),
            cursor='hand2'
        ).pack(pady=(10, 0))
    
    def start_server(self):
        """启动本地HTTP服务器"""
        global login_dialog_instance
        login_dialog_instance = self
        
        # 查找可用端口
        with socketserver.TCPServer(("127.0.0.1", 0), CookieHandler) as httpd:
            self.server_port = httpd.server_address[1]
            httpd.server_close()
        
        # 启动服务器
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.server_port), CookieHandler)
        
        # 在新线程中运行服务器
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
    
    def start_auto_login(self):
        """启动自动登录流程"""
        self.start_btn.config(state='disabled', bg='#DFE6E9', fg='#636E72')
        self.status_label.config(text="正在打开登录助手网页...", fg='#667eea')
        self.dialog.update()
        
        # 打开浏览器访问本地服务器
        login_url = f'http://127.0.0.1:{self.server_port}/login'
        webbrowser.open(login_url)
        
        self.status_label.config(text="请在打开的网页中完成登录\nCookie将自动获取", fg='#00B894')
    
    def complete_login(self):
        """完成登录，获取Cookie"""
        # 直接显示手动获取Cookie的对话框
        self.show_manual_cookie_dialog()
    
    def show_manual_cookie_dialog(self):
        """显示手动输入Cookie的对话框"""
        cookie_dialog = tk.Toplevel(self.dialog)
        cookie_dialog.title("手动获取Cookie")
        cookie_dialog.geometry("600x400")
        cookie_dialog.transient(self.dialog)
        cookie_dialog.grab_set()
        
        # 居中显示
        cookie_dialog.update_idletasks()
        width = cookie_dialog.winfo_width()
        height = cookie_dialog.winfo_height()
        x = (self.dialog.winfo_rootx() + (self.dialog.winfo_width() // 2) - (width // 2))
        y = (self.dialog.winfo_rooty() + (self.dialog.winfo_height() // 2) - (height // 2))
        cookie_dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # 说明文本
        info_frame = tk.Frame(cookie_dialog, bg='#FFFFFF', padx=20, pady=20)
        info_frame.pack(fill='both', expand=True)
        
        info_text = """无法自动获取Cookie，请按以下步骤手动获取：

1. 在打开的登录页面或浏览器中完成登录
2. 按F12打开开发者工具
3. 点击 Network（网络）标签
4. 刷新页面，找到任意请求
5. 复制请求头中的 Cookie 值
6. 粘贴到下方文本框中"""
        
        info_label = tk.Label(
            info_frame,
            text=info_text,
            font=('Microsoft YaHei UI', 9),
            bg='#F8F9FA',
            fg='#636E72',
            justify='left',
            padx=15,
            pady=15
        )
        info_label.pack(fill='x', pady=(0, 10))
        
        # Cookie输入框
        cookie_text = scrolledtext.ScrolledText(
            info_frame,
            height=10,
            font=('Consolas', 8),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=8,
            pady=8,
            wrap='word'
        )
        cookie_text.pack(fill='both', expand=True)
        cookie_text.insert('1.0', '粘贴Cookie到这里...')
        cookie_text.bind('<FocusIn>', lambda e: self._clear_placeholder(cookie_text))
        
        def save_and_close():
            cookie_str = cookie_text.get('1.0', 'end-1c').strip()
            if cookie_str and cookie_str != '粘贴Cookie到这里...':
                cookies_dict = {}
                for item in cookie_str.split(';'):
                    item = item.strip()
                    if '=' in item:
                        key, value = item.split('=', 1)
                        cookies_dict[key.strip()] = value.strip()
                
                if cookies_dict and any(key in cookies_dict for key in ['sessionid', 'passport_csrf_token', 'passport_assist_user']):
                    save_cookies(cookies_dict)
                    cookie_dialog.destroy()
                    self.on_login_success()
                else:
                    messagebox.showerror('错误', 'Cookie格式无效或缺少登录凭证')
            else:
                messagebox.showwarning('提示', '请输入Cookie')
        
        btn_frame = tk.Frame(info_frame, bg='#FFFFFF')
        btn_frame.pack(fill='x', pady=(10, 0))
        
        tk.Button(
            btn_frame,
            text="取消",
            command=cookie_dialog.destroy,
            bg='#DFE6E9',
            fg='#636E72',
            borderwidth=0,
            padx=20,
            pady=8,
            font=('Microsoft YaHei UI', 9),
            cursor='hand2'
        ).pack(side='right', padx=(5, 0))
        
        tk.Button(
            btn_frame,
            text="保存Cookie",
            command=save_and_close,
            bg='#00B894',
            fg='white',
            borderwidth=0,
            padx=20,
            py=8,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2'
        ).pack(side='right')
    
    def _clear_placeholder(self, text_widget):
        """清除占位符文本"""
        if text_widget.get('1.0', 'end-1c') == '粘贴Cookie到这里...':
            text_widget.delete('1.0', 'end')
    
    def on_login_success(self):
        """登录成功回调"""
        self.dialog.destroy()
        if self.callback:
            self.callback(True)
    
    def on_close(self):
        """关闭对话框"""
        global login_dialog_instance
        login_dialog_instance = None
        
        # 停止服务器
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()
        
        self.dialog.destroy()
        if self.callback:
            self.callback(False)
    
    def send_verification_code(self):
        """发送验证码"""
        phone = self.phone_entry.get().strip()
        
        if not phone or phone == '请输入手机号':
            messagebox.showwarning('提示', '请输入手机号')
            return
        
        if len(phone) != 11 or not phone.isdigit():
            messagebox.showwarning('提示', '请输入正确的11位手机号')
            return
        
        self.status_label.config(text='正在发送验证码...', fg='#636E72')
        self.dialog.update()
        
        # 在新线程中发送验证码
        thread = threading.Thread(target=self._send_code_thread, args=(phone,))
        thread.daemon = True
        thread.start()
    
    def _send_code_thread(self, phone):
        """发送验证码线程"""
        result = self.spider.send_verification_code(phone)
        
        self.dialog.after(0, lambda: self._handle_send_result(result, phone))
    
    def _handle_send_result(self, result, phone):
        """处理发送验证码结果"""
        if result['success']:
            self.status_label.config(text='验证码已发送，请查收', fg='#00B894')
            self.start_countdown()
        else:
            self.status_label.config(text=result['message'], fg='#D63031')
    
    def start_countdown(self):
        """开始倒计时"""
        self.countdown = 60
        self.send_code_btn.config(state='disabled', bg='#DFE6E9', fg='#636E72')
        self.update_countdown()
    
    def update_countdown(self):
        """更新倒计时"""
        if self.countdown > 0:
            self.send_code_btn.config(text=f'{self.countdown}秒后重发')
            self.countdown -= 1
            self.dialog.after(1000, self.update_countdown)
        else:
            self.send_code_btn.config(
                state='normal',
                text='发送验证码',
                bg='#00B894',
                fg='white'
            )
    
    def login(self):
        """登录"""
        phone = self.phone_entry.get().strip()
        code = self.code_entry.get().strip()
        
        if not phone or phone == '请输入手机号':
            messagebox.showwarning('提示', '请输入手机号')
            return
        
        if len(phone) != 11 or not phone.isdigit():
            messagebox.showwarning('提示', '请输入正确的11位手机号')
            return
        
        if not code:
            messagebox.showwarning('提示', '请输入验证码')
            return
        
        self.status_label.config(text='正在登录...', fg='#636E72')
        self.login_btn.config(state='disabled', bg='#DFE6E9')
        self.dialog.update()
        
        # 在新线程中登录
        thread = threading.Thread(target=self._login_thread, args=(phone, code))
        thread.daemon = True
        thread.start()
    
    def _login_thread(self, phone, code):
        """登录线程"""
        result = self.spider.login_with_verification_code(phone, code)
        
        self.dialog.after(0, lambda: self._handle_login_result(result))
    
    def _handle_login_result(self, result):
        """处理登录结果"""
        if result['success']:
            # 保存Cookie
            save_cookies(result['cookies'])
            self.status_label.config(text='登录成功！', fg='#00B894')
            
            # 延迟关闭对话框
            self.dialog.after(1000, self.on_login_success)
        else:
            self.status_label.config(text=result['message'], fg='#D63031')
            self.login_btn.config(state='normal', bg='#FF6B6B')
    
    def on_login_success(self):
        """登录成功回调"""
        self.dialog.destroy()
        if self.callback:
            self.callback(result['success'])
    
    def on_close(self):
        """关闭对话框"""
        self.dialog.destroy()


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
        self.is_logged_in = False

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
        
        # 登录区域
        login_frame = tk.Frame(title_frame, bg=ModernStyle.COLORS['primary'])
        login_frame.pack(side='right', padx=20, pady=15)
        
        # 检查是否已登录（检查是否有有效的session_id或passport_csrf_token等关键cookie）
        cookies = load_cookies()
        self.is_logged_in = len(cookies) > 0 and any(key in cookies for key in ['sessionid', 'passport_csrf_token', 'passport_assist_user'])
        
        # 登录状态标签
        self.login_status_label = tk.Label(
            login_frame,
            text="✓ 已登录" if self.is_logged_in else "未登录",
            font=('Microsoft YaHei UI', 9),
            bg=ModernStyle.COLORS['primary'],
            fg='#00B894' if self.is_logged_in else '#FFEAA7'
        )
        self.login_status_label.pack(side='left', padx=(0, 10))
        
        # 登录按钮
        self.login_btn = tk.Button(
            login_frame,
            text="退出登录" if self.is_logged_in else "登录",
            command=self.on_login_click,
            bg='#FFFFFF',
            fg=ModernStyle.COLORS['primary'],
            borderwidth=0,
            padx=15,
            pady=5,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2',
            activebackground='#F8F9FA',
            activeforeground=ModernStyle.COLORS['primary']
        )
        self.login_btn.pack(side='left')
    
    def on_login_click(self):
        """点击登录/退出登录按钮"""
        if self.is_logged_in:
            # 退出登录
            from config import clear_cookies
            if messagebox.askyesno('确认', '确定要退出登录吗？'):
                clear_cookies()
                self.is_logged_in = False
                self.update_login_status()
                self.log("已退出登录", 'info')
        else:
            # 打开登录对话框
            LoginDialog(self.root, self.on_login_result)
    
    def on_login_result(self, success):
        """登录结果回调"""
        if success:
            self.is_logged_in = True
            self.update_login_status()
            self.log("登录成功！", 'success')
        else:
            self.log("登录失败", 'error')
    
    def update_login_status(self):
        """更新登录状态显示"""
        self.login_status_label.config(
            text="✓ 已登录" if self.is_logged_in else "未登录",
            fg='#00B894' if self.is_logged_in else '#FFEAA7'
        )
        self.login_btn.config(
            text="退出登录" if self.is_logged_in else "登录"
        )

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