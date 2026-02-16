# GUI界面模块 - 美化版
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from spider import FanqieSpider, parse_novel_url
from downloader import NovelDownloader
from database import NovelDatabase
from config import save_cookies, load_cookies
import http.server
import socketserver
import json
import webbrowser
import os
import time
import shutil


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
            text="自动获取Cookie登录",
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
            text="开始自动获取Cookie",
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
            text="手动输入Cookie",
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
            pady=8,
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
        'primary': '#4A90E2',
        'primary_hover': '#357ABD',
        'primary_light': '#E3F2FD',
        'bg': '#F5F7FA',
        'surface': '#FFFFFF',
        'text': '#2C3E50',
        'text_secondary': '#7F8C8D',
        'border': '#E0E6ED',
        'success': '#27AE60',
        'error': '#E74C3C',
        'warning': '#F39C12',
        'info': '#3498DB',
    }
    
    FONTS = {
        'title': ('Microsoft YaHei UI', 14, 'bold'),
        'header': ('Microsoft YaHei UI', 11, 'bold'),
        'normal': ('Microsoft YaHei UI', 9),
        'small': ('Microsoft YaHei UI', 8),
    }


class SettingsDialog:
    """设置对话框"""
    def __init__(self, parent):
        self.parent = parent
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.geometry("450x550")
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
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = tk.Frame(self.dialog, bg=ModernStyle.COLORS['bg'])
        main_frame.pack(fill='both', expand=True)
        
        # 标题栏
        title_frame = tk.Frame(main_frame, bg=ModernStyle.COLORS['primary'], height=50)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="设置",
            font=('Microsoft YaHei UI', 14, 'bold'),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        title_label.pack(side='left', padx=20, pady=12)
        
        # 内容区域
        content_frame = tk.Frame(main_frame, bg=ModernStyle.COLORS['bg'], padx=30, pady=20)
        content_frame.pack(fill='both', expand=True)
        
        # 并发下载设置
        concurrent_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg'])
        concurrent_frame.pack(fill='x', pady=(0, 20))
        
        concurrent_label = tk.Label(
            concurrent_frame,
            text="并发下载数:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        concurrent_label.pack(side='left', padx=(0, 15))
        
        from config import get_concurrent_downloads
        current_value = get_concurrent_downloads()
        
        self.concurrent_var = tk.IntVar(value=current_value)
        
        concurrent_spinbox = tk.Spinbox(
            concurrent_frame,
            from_=1,
            to=10,
            textvariable=self.concurrent_var,
            width=10,
            font=ModernStyle.FONTS['normal'],
            bg=ModernStyle.COLORS['surface'],
            fg=ModernStyle.COLORS['text'],
            relief='solid',
            borderwidth=1
        )
        concurrent_spinbox.pack(side='left', padx=(0, 10))
        
        concurrent_tip = tk.Label(
            concurrent_frame,
            text="(1-10，建议3-5)",
            font=ModernStyle.FONTS['small'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text_secondary']
        )
        concurrent_tip.pack(side='left')
        
        # 说明文字
        info_text = """并发下载数表示同时下载的小说数量。
数值越大下载速度越快，但可能增加服务器压力。
建议设置为3-5以获得最佳效果。"""
        
        info_label = tk.Label(
            content_frame,
            text=info_text,
            font=ModernStyle.FONTS['small'],
            bg='#F8F9FA',
            fg='#636E72',
            justify='left',
            padx=15,
            pady=15,
            wraplength=380
        )
        info_label.pack(fill='x', pady=(0, 15))
        
        # 作者信息区域
        author_frame = tk.Frame(content_frame, bg='#F8F9FA', padx=15, pady=12)
        author_frame.pack(fill='x', pady=(0, 15))
        
        author_title = tk.Label(
            author_frame,
            text="关于作者",
            font=ModernStyle.FONTS['header'],
            bg='#F8F9FA',
            fg=ModernStyle.COLORS['text']
        )
        author_title.pack(anchor='w', pady=(0, 10))
        
        author_info = tk.Label(
            author_frame,
            text="作者: halei0v0\n项目: FXdownloader - 番茄小说下载器\n版本: v1.0.2\n\n感谢使用本软件！",
            font=ModernStyle.FONTS['normal'],
            bg='#F8F9FA',
            fg='#636E72',
            justify='left'
        )
        author_info.pack(anchor='w')
        
        # 底部按钮区域
        button_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg'])
        button_frame.pack(fill='x', pady=(15, 0))
        
        # 保存按钮
        save_btn = ttk.Button(
            button_frame,
            text="保存",
            command=self.save_settings,
            style='Success.TButton'
        )
        save_btn.pack(side='left')
        
        # 取消按钮
        cancel_btn = ttk.Button(
            button_frame,
            text="取消",
            command=self.on_close,
            style='Primary.TButton'
        )
        cancel_btn.pack(side='right')
    
    def save_settings(self):
        """保存设置"""
        from config import set_concurrent_downloads
        
        concurrent = self.concurrent_var.get()
        
        if set_concurrent_downloads(concurrent):
            messagebox.showinfo('成功', '设置已保存！')
            self.dialog.destroy()
        else:
            messagebox.showerror('错误', '保存设置失败！')
    
    def on_close(self):
        """关闭对话框"""
        self.dialog.destroy()


class DownloadHistoryDialog:
    """下载历史对话框"""
    def __init__(self, parent):
        self.parent = parent
        self.db = NovelDatabase()
        self.selected_novels = []
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("下载历史")
        self.dialog.geometry("900x600")
        self.dialog.resizable(True, True)
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
        
        # 加载下载历史
        self.load_download_history()
        
        # 绑定关闭事件
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = tk.Frame(self.dialog, bg=ModernStyle.COLORS['bg'])
        main_frame.pack(fill='both', expand=True)
        
        # 标题栏
        title_frame = tk.Frame(main_frame, bg=ModernStyle.COLORS['primary'], height=50)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="下载历史",
            font=('Microsoft YaHei UI', 14, 'bold'),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        title_label.pack(side='left', padx=20, pady=12)
        
        # 刷新按钮
        refresh_btn = tk.Button(
            title_frame,
            text="刷新",
            command=self.load_download_history,
            bg='white',
            fg=ModernStyle.COLORS['primary'],
            borderwidth=0,
            padx=15,
            pady=5,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2',
            activebackground=ModernStyle.COLORS['primary_light'],
            activeforeground=ModernStyle.COLORS['primary']
        )
        refresh_btn.pack(side='right', padx=20, pady=12)
        
        # 内容区域
        content_frame = tk.Frame(main_frame, bg=ModernStyle.COLORS['bg'], padx=20, pady=20)
        content_frame.pack(fill='both', expand=True)
        
        # 小说列表框架
        list_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg'])
        list_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # 创建Treeview
        tree_frame = tk.Frame(list_frame, bg=ModernStyle.COLORS['bg'])
        tree_frame.pack(fill='both', expand=True)
        
        columns = ('select', 'title', 'author', 'word_count', 'chapter_count', 'status', 'updated_at')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='extended')
        
        self.tree.heading('select', text='选择')
        self.tree.heading('title', text='书名')
        self.tree.heading('author', text='作者')
        self.tree.heading('word_count', text='字数')
        self.tree.heading('chapter_count', text='章节数')
        self.tree.heading('status', text='状态')
        self.tree.heading('updated_at', text='更新时间')
        
        self.tree.column('select', width=50, anchor='center')
        self.tree.column('title', width=250, anchor='w')
        self.tree.column('author', width=120, anchor='w')
        self.tree.column('word_count', width=100, anchor='e')
        self.tree.column('chapter_count', width=80, anchor='center')
        self.tree.column('status', width=100, anchor='center')
        self.tree.column('updated_at', width=150, anchor='w')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 绑定点击事件
        self.tree.bind('<Button-1>', self.on_tree_click)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 底部按钮区域
        button_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg'])
        button_frame.pack(fill='x')
        
        # 全选/取消全选按钮
        self.select_all_var = tk.BooleanVar(value=False)
        select_all_btn = tk.Checkbutton(
            button_frame,
            text="全选",
            variable=self.select_all_var,
            command=self.toggle_select_all,
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text'],
            font=ModernStyle.FONTS['normal'],
            activebackground=ModernStyle.COLORS['bg'],
            activeforeground=ModernStyle.COLORS['text'],
            selectcolor=ModernStyle.COLORS['bg']
        )
        select_all_btn.pack(side='left', padx=(0, 20))
        
        # 导出列表按钮
        export_list_btn = ttk.Button(
            button_frame,
            text="导出列表",
            command=self.export_novel_list,
            style='Primary.TButton'
        )
        export_list_btn.pack(side='left')
        
        # 导入列表按钮
        import_list_btn = ttk.Button(
            button_frame,
            text="导入列表",
            command=self.import_novel_list,
            style='Primary.TButton'
        )
        import_list_btn.pack(side='left', padx=(5, 0))
        
        # 批量下载按钮
        batch_download_btn = ttk.Button(
            button_frame,
            text="批量下载",
            command=self.batch_download,
            style='Success.TButton'
        )
        batch_download_btn.pack(side='left', padx=(10, 0))
        
        # 关闭按钮
        close_btn = ttk.Button(
            button_frame,
            text="关闭",
            command=self.on_close,
            style='Primary.TButton'
        )
        close_btn.pack(side='right', padx=(10, 0))
        
        # 删除按钮
        delete_btn = ttk.Button(
            button_frame,
            text="删除选中",
            command=self.delete_selected_novels,
            style='Primary.TButton'
        )
        delete_btn.pack(side='right', padx=(10, 0))
    
    def load_download_history(self):
        """加载下载历史"""
        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 从数据库获取所有小说
        novels = self.db.get_all_novels()
        
        # 添加到列表
        for novel in novels:
            word_count_str = f"{novel['word_count']:,}"
            # updated_at 已经是字符串格式，直接使用
            updated_at_str = novel['updated_at'] if novel['updated_at'] else '未知'
            self.tree.insert('', 'end', values=(
                '☐',
                novel['title'],
                novel['author'],
                word_count_str,
                novel['chapter_count'],
                novel['status'],
                updated_at_str
            ), tags=(novel['novel_id'],))
    
    def on_tree_click(self, event):
        """处理Treeview点击事件"""
        # 获取点击的项
        item = self.tree.identify_row(event.y)
        if item:
            # 获取点击的列
            column = self.tree.identify_column(event.x)
            # 如果点击的是选择列，切换选择状态
            if column == '#1':
                current_value = self.tree.set(item, 'select')
                new_value = '☑' if current_value == '☐' else '☐'
                self.tree.set(item, 'select', new_value)
    
    def toggle_select_all(self):
        """全选/取消全选"""
        select_all = self.select_all_var.get()
        for item in self.tree.get_children():
            self.tree.set(item, 'select', '☑' if select_all else '☐')
    
    def export_novel_list(self):
        """导出小说列表"""
        # 获取所有小说
        novels = self.db.get_all_novels()
        
        if not novels:
            messagebox.showwarning('提示', '暂无小说可导出')
            return
        
        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title="保存小说列表",
            defaultextension=".txt",
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')],
            initialfile="小说列表.txt"
        )
        
        if not file_path:
            return
        
        # 生成列表内容
        content = ""
        for novel in novels:
            content += f"# 《{novel['title']}》\n"
            content += f"{novel['novel_id']}\n\n"
        
        # 保存文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo('成功', f'成功导出 {len(novels)} 个小说到：\n{file_path}')
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{e}')
    
    def import_novel_list(self):
        """导入小说列表并批量下载"""
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择小说列表文件",
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')]
        )
        
        if not file_path:
            return
        
        # 解析文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror('错误', f'无法读取文件：{e}')
                return
        except Exception as e:
            messagebox.showerror('错误', f'无法读取文件：{e}')
            return
        
        # 解析小说列表
        lines = content.strip().split('\n')
        novel_list = []
        current_title = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # 提取标题（格式：# 《小说标题》）
                if '《' in line and '》' in line:
                    start = line.find('《') + 1
                    end = line.find('》')
                    current_title = line[start:end]
            elif line and line.isdigit():
                # 小说ID
                novel_id = line
                if current_title:
                    novel_list.append({'title': current_title, 'novel_id': novel_id})
                current_title = None
        
        if not novel_list:
            messagebox.showwarning('提示', '未找到有效的小说列表')
            return
        
        # 确认导入
        confirm_msg = f"找到 {len(novel_list)} 个小说：\n\n"
        for novel in novel_list[:5]:  # 只显示前5个
            confirm_msg += f"《{novel['title']}》 - {novel['novel_id']}\n"
        if len(novel_list) > 5:
            confirm_msg += f"... 还有 {len(novel_list) - 5} 个小说\n"
        confirm_msg += f"\n是否开始批量下载？"
        
        if not messagebox.askyesno('确认', confirm_msg):
            return
        
        # 选择导出路径
        export_path = filedialog.askdirectory(title="选择导出文件夹")
        if not export_path:
            return
        
        # 检查文件夹是否可写
        try:
            test_file = os.path.join(export_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except PermissionError:
            messagebox.showerror(
                '权限错误',
                f'无法写入该文件夹：\n{export_path}\n\n请选择其他有写入权限的文件夹。'
            )
            return
        except Exception as e:
            messagebox.showerror(
                '路径错误',
                f'无法使用该路径：\n{export_path}\n\n错误信息：{e}'
            )
            return
        
        # 创建批量下载进度对话框
        progress_dialog = tk.Toplevel(self.dialog)
        progress_dialog.title("批量下载")
        progress_dialog.geometry("500x300")
        progress_dialog.resizable(False, False)
        progress_dialog.transient(self.dialog)
        progress_dialog.grab_set()
        
        # 居中显示
        progress_dialog.update_idletasks()
        width = progress_dialog.winfo_width()
        height = progress_dialog.winfo_height()
        x = self.dialog.winfo_rootx() + (self.dialog.winfo_width() // 2) - (width // 2)
        y = self.dialog.winfo_rooty() + (self.dialog.winfo_height() // 2) - (height // 2)
        progress_dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # 创建进度界面
        progress_frame = tk.Frame(progress_dialog, bg=ModernStyle.COLORS['bg'], padx=20, pady=20)
        progress_frame.pack(fill='both', expand=True)
        
        status_label = tk.Label(
            progress_frame,
            text="准备下载...",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        status_label.pack(pady=(0, 20))
        
        progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=10,
            state='disabled',
            font=('Consolas', 9),
            bg=ModernStyle.COLORS['surface'],
            fg=ModernStyle.COLORS['text'],
            padx=10,
            pady=10,
            relief='solid',
            borderwidth=1
        )
        progress_text.pack(fill='both', expand=True)
        
        # 在新线程中执行批量下载
        def do_batch_download():
            from spider import FanqieSpider
            from config import get_concurrent_downloads
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            spider = FanqieSpider()
            concurrent_downloads = get_concurrent_downloads()
            
            # 线程安全的结果统计
            result_lock = threading.Lock()
            success_count = 0
            failed_novels = []
            completed_count = 0
            total_count = len(novel_list)
            
            # 添加总体进度信息
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"开始批量下载，共 {total_count} 个小说\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"并发数: {concurrent_downloads}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n\n"))
            
            # 下载单个小说的函数
            def download_novel(novel_info):
                novel_id = novel_info['novel_id']
                title = novel_info['title']
                
                # 每个线程创建自己的spider实例
                thread_spider = FanqieSpider()
                
                # 添加开始日志
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"正在下载: {title}\n"))
                
                try:
                    # 获取小说信息
                    novel_data = thread_spider.get_novel_info(novel_id)
                    if not novel_data:
                        progress_dialog.after(0, lambda: self._add_log(progress_text, f"  ✗ 获取信息失败: {title}\n"))
                        return (False, f"{title} (获取信息失败)")
                    
                    # 保存小说信息
                    self.db.save_novel(
                        novel_id=novel_data['novel_id'],
                        title=novel_data['title'],
                        author=novel_data['author'],
                        description=novel_data['description'],
                        cover_url=novel_data['cover_url'],
                        word_count=novel_data['word_count'],
                        chapter_count=novel_data['chapter_count']
                    )
                    
                    # 获取章节列表
                    chapters = thread_spider.get_chapter_list(novel_id)
                    if not chapters:
                        progress_dialog.after(0, lambda: self._add_log(progress_text, f"  ✗ 获取章节失败: {title}\n"))
                        return (False, f"{title} (获取章节失败)")
                    
                    # 下载章节
                    chapter_success = 0
                    total_chapters = len(chapters)
                    
                    progress_dialog.after(0, lambda t=title, tc=total_chapters: 
                        self._add_log(progress_text, f"  《{t}》共 {tc} 章\n"))
                    
                    for idx, chapter in enumerate(chapters, 1):
                        # 更新章节下载进度
                        chapter_title = chapter['chapter_title']
                        chapter_data = thread_spider.get_chapter_content(novel_id, chapter['chapter_id'])
                        
                        if chapter_data:
                            real_title = chapter_data.get('title', chapter_title)
                            content = chapter_data.get('content', '')
                            word_count = len(content)
                            
                            self.db.save_chapter(
                                novel_id=novel_id,
                                chapter_id=chapter['chapter_id'],
                                chapter_title=real_title,
                                chapter_index=chapter['chapter_index'],
                                content=content,
                                word_count=word_count
                            )
                            chapter_success += 1
                            
                            progress_dialog.after(0, lambda t=title, i=idx, tc=total_chapters, wc=word_count: 
                                self._add_log(progress_text, f"    [{i}/{tc}] 第{i}章 ({wc}字)\n"))
                        else:
                            progress_dialog.after(0, lambda t=title, i=idx: 
                                self._add_log(progress_text, f"    [{i}] ✗ 第{i}章 下载失败\n"))
                    
                    if chapter_success == total_chapters:
                        self.db.update_novel_status(novel_id, '下载完成')
                        
                        # 导出文件
                        filename = f"{novel_data['title']}.txt"
                        output_path = os.path.join(export_path, filename)
                        
                        downloaded_chapters = self.db.get_chapters(novel_id)
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write("=" * 50 + "\n")
                            f.write(f"书名: {novel_data['title']}\n")
                            f.write(f"作者: {novel_data['author']}\n")
                            f.write(f"简介: {novel_data['description']}\n")
                            f.write(f"字数: {novel_data['word_count']:,} 字\n")
                            f.write(f"章节数: {novel_data['chapter_count']} 章\n")
                            f.write("=" * 50 + "\n\n")
                            
                            for chapter in downloaded_chapters:
                                f.write(f"\n{'='*30}\n")
                                f.write(f"{chapter['chapter_title']}\n")
                                f.write(f"{'='*30}\n\n")
                                f.write(chapter['content'])
                                f.write("\n")
                        
                        progress_dialog.after(0, lambda t=title, cs=chapter_success: 
                            self._add_log(progress_text, f"  ✓ 《{t}》下载完成 ({cs}章)\n\n"))
                        return (True, None)
                    else:
                        self.db.update_novel_status(novel_id, '部分下载')
                        progress_dialog.after(0, lambda t=title, cs=chapter_success, tc=total_chapters: 
                            self._add_log(progress_text, f"  ⚠ 《{t}》部分完成 ({cs}/{tc}章)\n\n"))
                        return (False, f"{title} (部分下载: {chapter_success}/{total_chapters})")
                        
                except Exception as e:
                    progress_dialog.after(0, lambda t=title, err=str(e): 
                        self._add_log(progress_text, f"  ✗ 《{t}》下载出错: {err}\n\n"))
                    return (False, f"{title} (出错: {str(e)})")
            
            # 使用线程池并发下载
            with ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
                # 提交所有下载任务
                future_to_novel = {
                    executor.submit(download_novel, novel_info): novel_info
                    for novel_info in novel_list
                }
                
                # 等待任务完成
                for future in as_completed(future_to_novel):
                    success, error = future.result()
                    
                    with result_lock:
                        completed_count += 1
                        if success:
                            success_count += 1
                        else:
                            failed_novels.append(error)
                        
                        # 更新状态标签
                        progress_dialog.after(0, lambda: self._safe_update_ui(
                            status_label,
                            lambda: status_label.config(text=f"正在下载 ({completed_count}/{total_count})")
                        ))
            
            # 刷新历史列表
            progress_dialog.after(0, lambda: self._safe_update_ui(
                progress_dialog,
                lambda: self.load_download_history()
            ))
            
            # 显示结果
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"\n{'='*50}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"批量下载完成！\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"成功: {success_count}/{total_count}\n"))
            
            if failed_novels:
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"\n失败的小说 ({len(failed_novels)}个):\n"))
                for i, novel in enumerate(failed_novels[:5]):
                    progress_dialog.after(0, lambda n=novel: self._add_log(progress_text, f"  - {n}\n"))
                if len(failed_novels) > 5:
                    progress_dialog.after(0, lambda c=len(failed_novels): 
                        self._add_log(progress_text, f"  ... 还有 {c - 5} 个\n"))
            
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n"))
            
            # 更新状态标签
            progress_dialog.after(0, lambda: self._safe_update_ui(
                status_label,
                lambda: status_label.config(text="下载完成")
            ))
            
            # 显示结果对话框
            result_msg = f'批量下载完成！\n\n成功: {success_count}/{total_count}'
            if failed_novels:
                result_msg += f'\n失败: {len(failed_novels)}个'
            progress_dialog.after(0, lambda: self._safe_update_ui(
                progress_dialog,
                lambda: messagebox.showinfo('完成', result_msg)
            ))
        
        import threading
        thread = threading.Thread(target=do_batch_download, daemon=True)
        thread.start()
    
    def _safe_update_ui(self, widget, func):
        """安全地更新UI控件"""
        try:
            if widget.winfo_exists():
                func()
        except Exception:
            # 窗口已关闭，忽略错误
            pass
    
    def _add_log(self, text_widget, message):
        """添加日志"""
        try:
            # 检查窗口和控件是否还存在
            if text_widget.winfo_exists():
                text_widget.config(state='normal')
                text_widget.insert('end', message)
                text_widget.see('end')
                text_widget.config(state='disabled')
        except Exception:
            # 窗口已关闭，忽略错误
            pass
    
    def batch_download(self):
        """批量下载选中的小说"""
        # 获取选中的小说
        selected_novels = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values[0] == '☑':
                tags = self.tree.item(item, 'tags')
                if tags:
                    novel_id = tags[0]
                    selected_novels.append((novel_id, values[1]))
        
        if not selected_novels:
            messagebox.showwarning('提示', '请至少选择一个小说')
            return
        
        # 选择导出路径
        export_path = filedialog.askdirectory(title="选择导出文件夹")
        if not export_path:
            return
        
        # 检查文件夹是否可写
        try:
            test_file = os.path.join(export_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except PermissionError:
            messagebox.showerror(
                '权限错误',
                f'无法写入该文件夹：\n{export_path}\n\n请选择其他有写入权限的文件夹。\n\n建议：\n- 不要选择系统受保护文件夹（如C盘根目录、Program Files等）\n- 选择用户的Documents或Desktop文件夹\n- 或在D盘、E盘等其他分区创建文件夹'
            )
            return
        except Exception as e:
            messagebox.showerror(
                '路径错误',
                f'无法使用该路径：\n{export_path}\n\n错误信息：{e}\n\n请选择其他有效路径。'
            )
            return
        
        # 导出小说
        success_count = 0
        failed_novels = []
        
        for novel_id, title in selected_novels:
            try:
                filename = f"{title}.txt"
                output_path = os.path.join(export_path, filename)
                
                novel = self.db.get_novel(novel_id)
                if not novel:
                    failed_novels.append(f"{title} (小说不存在)")
                    continue
                
                chapters = self.db.get_chapters(novel_id)
                if not chapters:
                    failed_novels.append(f"{title} (没有可导出的章节)")
                    continue
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    # 写入小说信息
                    f.write("=" * 50 + "\n")
                    f.write(f"书名: {novel['title']}\n")
                    f.write(f"作者: {novel['author']}\n")
                    f.write(f"简介: {novel['description']}\n")
                    f.write(f"字数: {novel['word_count']:,} 字\n")
                    f.write(f"章节数: {novel['chapter_count']} 章\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # 写入章节内容
                    for chapter in chapters:
                        f.write(f"\n{'='*30}\n")
                        f.write(f"{chapter['chapter_title']}\n")
                        f.write(f"{'='*30}\n\n")
                        f.write(chapter['content'])
                        f.write("\n")
                
                success_count += 1
            except Exception as e:
                failed_novels.append(f"{title} ({str(e)})")
        
        if failed_novels:
            error_msg = f"部分小说导出失败：\n\n" + "\n".join(failed_novels)
            messagebox.showwarning('部分失败', error_msg)
        
        messagebox.showinfo('完成', f'成功导出 {success_count}/{len(selected_novels)} 个小说')
    
    def delete_selected_novels(self):
        """删除选中的小说"""
        # 获取选中的小说
        selected_novels = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values[0] == '☑':
                tags = self.tree.item(item, 'tags')
                if tags:
                    novel_id = tags[0]
                    selected_novels.append((novel_id, values[1]))
        
        if not selected_novels:
            messagebox.showwarning('提示', '请至少选择一个小说')
            return
        
        if not messagebox.askyesno('确认', f'确定要删除选中的 {len(selected_novels)} 个小说吗？'):
            return
        
        # 删除小说
        success_count = 0
        for novel_id, title in selected_novels:
            try:
                self.db.delete_novel(novel_id)
                success_count += 1
            except Exception as e:
                messagebox.showerror('错误', f'删除小说 {title} 失败: {e}')
        
        messagebox.showinfo('完成', f'成功删除 {success_count}/{len(selected_novels)} 个小说')
        self.load_download_history()
    
    def on_close(self):
        """关闭对话框"""
        self.dialog.destroy()


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
                       borderwidth=1,
                       relief='solid')
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
                       font=fonts['normal'],
                       relief='solid')
        style.map('Modern.TEntry',
                 bordercolor=[('focus', colors['primary'])])
        
        # Button样式
        style.configure('Primary.TButton',
                       background=colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       padding=(20, 10),
                       font=fonts['header'],
                       relief='flat')
        style.map('Primary.TButton',
                 background=[('active', colors['primary_hover']),
                           ('pressed', colors['primary_hover']),
                           ('focus', colors['primary'])],
                 relief=[('pressed', 'sunken')])
        
        style.configure('Success.TButton',
                       background=colors['success'],
                       foreground='white',
                       borderwidth=0,
                       padding=(15, 8),
                       font=fonts['header'],
                       relief='flat')
        style.map('Success.TButton',
                 background=[('active', '#229954'),
                           ('pressed', '#229954'),
                           ('focus', colors['success'])],
                 relief=[('pressed', 'sunken')])
        
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
            text="FXdownloader",
            font=('Microsoft YaHei UI', 18, 'bold'),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        title_label.pack(side='left', padx=25, pady=15)
        
        subtitle_label = tk.Label(
            title_frame,
            text="番茄小说下载器",
            font=('Microsoft YaHei UI', 10),
            bg=ModernStyle.COLORS['primary'],
            fg='white'
        )
        subtitle_label.pack(side='left', padx=8, pady=15)
        
        # 登录区域
        login_frame = tk.Frame(title_frame, bg=ModernStyle.COLORS['primary'])
        login_frame.pack(side='right', padx=20, pady=15)
        
        # 检查是否已登录（检查是否有有效的session_id或passport_csrf_token等关键cookie）
        cookies = load_cookies()
        self.is_logged_in = len(cookies) > 0 and any(key in cookies for key in ['sessionid', 'passport_csrf_token', 'passport_assist_user'])
        
        # 登录状态标签
        self.login_status_label = tk.Label(
            login_frame,
            text="已登录" if self.is_logged_in else "未登录",
            font=('Microsoft YaHei UI', 9),
            bg=ModernStyle.COLORS['primary'],
            fg='white' if self.is_logged_in else '#FFEAA7'
        )
        self.login_status_label.pack(side='left', padx=(0, 10))
        
        # 登录按钮
        self.login_btn = tk.Button(
            login_frame,
            text="退出登录" if self.is_logged_in else "登录",
            command=self.on_login_click,
            bg='white',
            fg=ModernStyle.COLORS['primary'],
            borderwidth=0,
            padx=18,
            pady=6,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2',
            activebackground=ModernStyle.COLORS['primary_light'],
            activeforeground=ModernStyle.COLORS['primary']
        )
        self.login_btn.pack(side='left', padx=(10, 0))
        
        # 设置按钮
        settings_btn = tk.Button(
            login_frame,
            text="设置",
            command=self.show_settings,
            bg='#95A5A6',
            fg='white',
            borderwidth=0,
            padx=15,
            pady=6,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2',
            activebackground='#7F8C8D',
            activeforeground='white'
        )
        settings_btn.pack(side='left', padx=(10, 0))
    
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
            text="已登录" if self.is_logged_in else "未登录",
            fg='white' if self.is_logged_in else '#FFEAA7'
        )
        self.login_btn.config(
            text="退出登录" if self.is_logged_in else "登录"
        )
    
    def show_settings(self):
        """显示设置对话框"""
        SettingsDialog(self.root)

    def create_input_section(self, parent):
        """创建输入区域"""
        input_frame = ttk.LabelFrame(parent, text="小说信息", style='Modern.TLabelframe', padding=15)
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
        url_label.pack(side='left', padx=(0, 12))
        
        self.url_entry = ttk.Entry(url_frame, style='Modern.TEntry')
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 12))
        
        get_info_btn = ttk.Button(
            url_frame,
            text="获取信息",
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
        
        # 第三行：导出路径
        export_path_frame = tk.Frame(input_frame, bg=ModernStyle.COLORS['bg'])
        export_path_frame.pack(fill='x', pady=5)
        
        export_label = tk.Label(
            export_path_frame,
            text="导出路径:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        export_label.pack(side='left', padx=(0, 10))
        
        self.export_path_entry = ttk.Entry(export_path_frame, style='Modern.TEntry')
        self.export_path_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        # 设置默认导出路径到用户的文档目录
        try:
            import os
            # 优先使用用户文档目录，如果失败则使用桌面目录
            if os.name == 'nt':  # Windows
                user_docs = os.path.join(os.path.expanduser('~'), 'Documents')
                if not os.path.exists(user_docs):
                    user_docs = os.path.join(os.path.expanduser('~'), 'Desktop')
            else:  # Linux/Mac
                user_docs = os.path.join(os.path.expanduser('~'), 'Documents')
                if not os.path.exists(user_docs):
                    user_docs = os.path.expanduser('~')
            
            if os.path.exists(user_docs):
                self.export_path_entry.insert(0, user_docs)
        except Exception:
            pass  # 如果设置失败就留空
        
        select_path_btn = ttk.Button(
            export_path_frame,
            text="选择路径",
            command=self.select_export_path,
            style='Primary.TButton'
        )
        select_path_btn.pack(side='left')

    def create_info_section(self, parent):
        """创建小说信息显示区域"""
        info_frame = ttk.LabelFrame(parent, text="小说详情", style='Modern.TLabelframe', padding=15)
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
            text="开始下载",
            command=self.start_download,
            style='Primary.TButton'
        )
        self.download_button.pack(side='left', padx=(0, 10))
        
        self.export_button = ttk.Button(
            button_frame,
            text="下载历史",
            command=self.show_download_history,
            style='Success.TButton'
        )
        self.export_button.pack(side='left')

    def create_log_section(self, parent):
        """创建日志显示区域"""
        log_frame = ttk.LabelFrame(parent, text="下载日志", style='Modern.TLabelframe', padding=15)
        log_frame.pack(fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            state='disabled',
            font=('Consolas', 9),
            bg=ModernStyle.COLORS['surface'],
            fg=ModernStyle.COLORS['text'],
            padx=12,
            pady=12,
            relief='solid',
            borderwidth=1
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

    def select_export_path(self):
        """选择导出路径"""
        path = filedialog.askdirectory(title="选择导出文件夹")
        if path:
            # 检查文件夹是否可写
            try:
                test_file = os.path.join(path, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)

                # 验证通过，设置路径
                self.export_path_entry.delete(0, tk.END)
                self.export_path_entry.insert(0, path)
                self.log(f"已选择导出路径: {path}", 'info')
            except PermissionError:
                messagebox.showerror(
                    '权限错误',
                    f'无法写入该文件夹：\n{path}\n\n请选择其他有写入权限的文件夹。\n\n建议：\n- 不要选择系统受保护文件夹（如C盘根目录、Program Files等）\n- 选择用户的Documents或Desktop文件夹\n- 或在D盘、E盘等其他分区创建文件夹'
                )
            except Exception as e:
                messagebox.showerror(
                    '路径错误',
                    f'无法使用该路径：\n{path}\n\n错误信息：{e}\n\n请选择其他有效路径。'
                )
    
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

            # 自动导出
            export_path = self.root.after(0, lambda: self.export_path_entry.get().strip())
            export_path = self.export_path_entry.get().strip()
            
            if export_path:
                self.log("正在自动导出...", 'info')
                self.root.update()
                
                try:
                    if self.downloader.export_to_txt(self.current_novel_id, export_path):
                        self.log(f"导出成功: {export_path}", 'success')
                        
                        # 复制到downloads文件夹
                        import shutil
                        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
                        os.makedirs(downloads_dir, exist_ok=True)
                        
                        backup_path = os.path.join(downloads_dir, os.path.basename(export_path))
                        shutil.copy2(export_path, backup_path)
                        self.log(f"已备份到: {backup_path}", 'success')
                    else:
                        self.log("导出失败", 'error')
                except PermissionError:
                    error_msg = f"权限不足，无法写入文件: {export_path}\n\n建议：\n1. 选择其他有写入权限的文件夹\n2. 以管理员身份运行程序\n3. 检查文件是否被其他程序占用"
                    self.log(error_msg, 'error')
                    self.root.after(0, lambda: messagebox.showerror('权限错误', error_msg))
                except OSError as e:
                    error_msg = f"写入文件失败: {e}\n\n建议：\n1. 检查路径是否有效\n2. 检查磁盘空间是否充足\n3. 选择其他保存位置"
                    self.log(error_msg, 'error')
                    self.root.after(0, lambda: messagebox.showerror('写入错误', error_msg))
                except Exception as e:
                    error_msg = f"导出过程发生未知错误: {e}"
                    self.log(error_msg, 'error')
                    self.root.after(0, lambda: messagebox.showerror('导出错误', error_msg))
            else:
                self.log("未设置导出路径，跳过自动导出", 'warning')

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
    
    def show_download_history(self):
        """显示下载历史"""
        DownloadHistoryDialog(self.root)


def main():
    root = tk.Tk()
    app = NovelDownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()