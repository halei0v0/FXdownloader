# GUI界面模块 - 美化版
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import sys
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
        # 获取资源文件所在的目录
        if getattr(sys, 'frozen', False):
            # 打包模式：使用临时解压目录
            base_dir = sys._MEIPASS
        else:
            # 开发模式：使用脚本所在目录
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
        
        # 初始化爬虫（登录必须使用官网模式，因为第三方模式不需要登录）
        from spider import FanqieSpider
        self.spider = FanqieSpider(use_api=False)
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("账户登录")
        self.dialog.geometry("700x600")
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
            text="账户登录",
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='#FF6B6B',
            fg='white'
        )
        title_label.pack(pady=12)
        
        # 内容区域
        content_frame = tk.Frame(main_frame, bg='#FFFFFF', padx=30, pady=20)
        content_frame.pack(fill='both', expand=True)
        
        # 登录方式选择
        method_frame = tk.Frame(content_frame, bg='#FFFFFF')
        method_frame.pack(fill='x', pady=(0, 20))
        
        method_label = tk.Label(
            method_frame,
            text="选择登录方式:",
            font=('Microsoft YaHei UI', 10, 'bold'),
            bg='#FFFFFF',
            fg='#2D3436'
        )
        method_label.pack(anchor='w', pady=(0, 10))
        
        # 创建选项卡
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Tab 1: Selenium自动登录
        selenium_tab = tk.Frame(self.notebook, bg='#FFFFFF', padx=20, pady=20)
        self.notebook.add(selenium_tab, text=' Selenium自动登录 ')
        
        selenium_info = """推荐使用此方式！

特点：
✓ 完全自动化，只需在浏览器中完成登录
✓ 自动获取并保存Cookie
✓ 支持所有登录方式（手机号、微信、QQ等）
✓ 无需手动复制Cookie

使用步骤：
1. 点击下方"启动浏览器"按钮
2. 在打开的浏览器中完成登录
3. 登录成功后自动保存Cookie"""
        
        selenium_info_label = tk.Label(
            selenium_tab,
            text=selenium_info,
            font=('Microsoft YaHei UI', 9),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=15,
            pady=15
        )
        selenium_info_label.pack(fill='x', pady=(0, 15), anchor='w')
        
        # Selenium状态显示
        self.selenium_status_label = tk.Label(
            selenium_tab,
            text="准备就绪",
            font=('Microsoft YaHei UI', 10),
            bg='#FFFFFF',
            fg='#636E72'
        )
        self.selenium_status_label.pack(pady=(0, 15))
        
        # Selenium按钮
        self.selenium_btn = tk.Button(
            selenium_tab,
            text="🚀 启动浏览器登录",
            command=self.start_selenium_login,
            bg='#00B894',
            fg='white',
            borderwidth=0,
            padx=30,
            pady=15,
            font=('Microsoft YaHei UI', 11, 'bold'),
            cursor='hand2'
        )
        self.selenium_btn.pack(fill='x')
        
        # Tab 2: 网页助手登录
        web_tab = tk.Frame(self.notebook, bg='#FFFFFF', padx=20, pady=20)
        self.notebook.add(web_tab, text=' 网页助手登录 ')
        
        web_info = """手动输入Cookie方式

特点：
• 适合已有Cookie的用户
• 需要手动复制粘贴
• 步骤较多，容易出错

使用步骤：
1. 点击下方"打开登录助手"按钮
2. 在浏览器中完成登录
3. 按照提示复制Cookie
4. 粘贴到输入框中"""
        
        web_info_label = tk.Label(
            web_tab,
            text=web_info,
            font=('Microsoft YaHei UI', 9),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=15,
            pady=15
        )
        web_info_label.pack(fill='x', pady=(0, 15), anchor='w')
        
        # 网页状态显示
        self.web_status_label = tk.Label(
            web_tab,
            text="准备就绪",
            font=('Microsoft YaHei UI', 10),
            bg='#FFFFFF',
            fg='#636E72'
        )
        self.web_status_label.pack(pady=(0, 15))
        
        # 网页按钮
        self.web_btn = tk.Button(
            web_tab,
            text="打开登录助手",
            command=self.start_auto_login,
            bg='#0984E3',
            fg='white',
            borderwidth=0,
            padx=30,
            pady=15,
            font=('Microsoft YaHei UI', 11, 'bold'),
            cursor='hand2'
        )
        self.web_btn.pack(fill='x')
        
        # Tab 3: 手动输入Cookie
        manual_tab = tk.Frame(self.notebook, bg='#FFFFFF', padx=20, pady=20)
        self.notebook.add(manual_tab, text=' 手动输入Cookie ')
        
        manual_info = """直接粘贴Cookie字符串

格式示例：
sessionid=xxx; passport_csrf_token=xxx; passport_assist_user=xxx

获取方法：
在浏览器开发者工具中：
1. 按F12打开开发者工具
2. 点击"应用程序"(Application)标签
3. 点击"Cookies"
4. 右键选择"Copy all as HTTP header format"
5. 粘贴到下方输入框"""
        
        manual_info_label = tk.Label(
            manual_tab,
            text=manual_info,
            font=('Microsoft YaHei UI', 9),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=15,
            pady=15
        )
        manual_info_label.pack(fill='x', pady=(0, 15), anchor='w')
        
        # Cookie输入框
        cookie_label = tk.Label(
            manual_tab,
            text="Cookie字符串:",
            font=('Microsoft YaHei UI', 10),
            bg='#FFFFFF',
            fg='#2D3436'
        )
        cookie_label.pack(anchor='w', pady=(0, 5))
        
        self.cookie_text = scrolledtext.ScrolledText(
            manual_tab,
            height=8,
            font=('Consolas', 9),
            bg='#F8F9FA',
            fg='#2D3436',
            padx=10,
            pady=10
        )
        self.cookie_text.pack(fill='x', pady=(0, 15))
        
        # 手动保存按钮
        self.manual_save_btn = tk.Button(
            manual_tab,
            text="保存Cookie",
            command=self.save_manual_cookie,
            bg='#636E72',
            fg='white',
            borderwidth=0,
            padx=30,
            pady=12,
            font=('Microsoft YaHei UI', 10, 'bold'),
            cursor='hand2'
        )
        self.manual_save_btn.pack(fill='x')
    
    def start_selenium_login(self):
        """启动Selenium自动登录"""
        self.selenium_btn.config(state='disabled', bg='#DFE6E9', fg='#636E72')
        self.selenium_status_label.config(text="正在启动浏览器，请稍候...", fg='#00B894')
        self.dialog.update()
        
        # 在新线程中执行登录
        import threading
        thread = threading.Thread(target=self._selenium_login_thread, daemon=True)
        thread.start()
    
    def _selenium_login_thread(self):
        """Selenium登录线程"""
        try:
            from selenium_login import SeleniumLogin
            
            selenium_login = SeleniumLogin()
            success, cookies = selenium_login.login_with_selenium(headless=False)
            
            if success:
                self.dialog.after(0, lambda: self.selenium_status_label.config(
                    text="✓ 登录成功！Cookie已保存", fg='#00B894'
                ))
                self.dialog.after(2000, self.on_login_success)
            else:
                self.dialog.after(0, lambda: self.selenium_status_label.config(
                    text="✗ 登录失败，请重试", fg='#FF7675'
                ))
                self.dialog.after(0, lambda: self.selenium_btn.config(
                    state='normal', bg='#00B894', fg='white'
                ))
                
        except Exception as e:
            error_msg = f"Selenium登录出错: {str(e)}"
            self.dialog.after(0, lambda: self.selenium_status_label.config(text=error_msg, fg='#FF7675'))
            self.dialog.after(0, lambda: self.selenium_btn.config(
                state='normal', bg='#00B894', fg='white'
            ))
    
    def start_auto_login(self):
        """启动网页助手登录"""
        self.web_btn.config(state='disabled', bg='#DFE6E9', fg='#636E72')
        self.web_status_label.config(text="正在打开登录助手...", fg='#0984E3')
        self.dialog.update()
        
        # 启动本地服务器
        self.start_server()
        
        # 打开浏览器访问本地服务器
        import time
        time.sleep(0.5)  # 等待服务器启动
        
        login_url = f'http://127.0.0.1:{self.server_port}/login'
        webbrowser.open(login_url)
        
        self.web_status_label.config(text="请在打开的网页中完成登录\nCookie将自动获取", fg='#00B894')
    
    def save_manual_cookie(self):
        """保存手动输入的Cookie"""
        cookie_str = self.cookie_text.get('1.0', 'end-1c').strip()
        
        if not cookie_str:
            messagebox.showerror('错误', '请输入Cookie字符串')
            return
        
        # 解析Cookie
        cookies = {}
        try:
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
            
            # 验证Cookie
            if not cookies or not any(key in cookies for key in ['sessionid', 'passport_csrf_token', 'passport_assist_user']):
                messagebox.showerror('错误', 'Cookie格式无效或缺少登录凭证')
                return
            
            # 保存Cookie
            if save_cookies(cookies):
                messagebox.showinfo('成功', 'Cookie已保存！')
                self.on_login_success()
            else:
                messagebox.showerror('错误', 'Cookie保存失败！')
                
        except Exception as e:
            messagebox.showerror('错误', f'解析Cookie失败: {e}')
    
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
            anchor='w',
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
    def __init__(self, parent, on_save=None):
        self.parent = parent
        self.on_save = on_save  # 保存成功后的回调函数

        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.geometry("550x920")
        self.dialog.resizable(True, True)
        self.dialog.minsize(550, 800)
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
        
        # 内容区域（带滚动条）
        canvas = tk.Canvas(main_frame, bg=ModernStyle.COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        content_frame = tk.Frame(canvas, bg=ModernStyle.COLORS['bg'], padx=30, pady=20)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 布局滚动条和内容区域
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 创建窗口内容
        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass  # canvas 已被销毁，忽略错误
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._mousewheel_handler = _on_mousewheel  # 保存引用以便在关闭时解绑
        
        # 更新滚动区域和窗口宽度
        def _update_canvas(event=None):
            # 更新滚动区域
            canvas.config(scrollregion=canvas.bbox("all"))
            # 更新窗口宽度以适应对话框
            canvas.itemconfig(canvas_window, width=canvas.winfo_width() - 15)  # 减去滚动条宽度
        
        content_frame.bind("<Configure>", _update_canvas)
        canvas.bind("<Configure>", _update_canvas)
        
        # 更新滚动区域
        def _update_canvas(event=None):
            canvas.config(scrollregion=canvas.bbox("all"))
        
        content_frame.bind("<Configure>", _update_canvas)
        
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
            anchor='w',
            padx=15,
            pady=15,
            wraplength=380
        )
        info_label.pack(fill='x', pady=(0, 20))

        # 下载速度设置
        speed_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg'])
        speed_frame.pack(fill='x', pady=(0, 20))
        
        speed_label = tk.Label(
            speed_frame,
            text="下载速度调整:",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        speed_label.pack(anchor='w', pady=(0, 10))
        
        from config import get_download_speed, DEFAULT_DOWNLOAD_SPEED, MIN_DOWNLOAD_SPEED, MAX_DOWNLOAD_SPEED
        current_speed = get_download_speed()
        
        # 速度滑块
        speed_control_frame = tk.Frame(speed_frame, bg=ModernStyle.COLORS['bg'])
        speed_control_frame.pack(fill='x', pady=(0, 10))
        
        self.speed_var = tk.DoubleVar(value=current_speed)
        
        speed_scale = tk.Scale(
            speed_control_frame,
            from_=MIN_DOWNLOAD_SPEED,
            to=MAX_DOWNLOAD_SPEED,
            resolution=0.1,
            orient='horizontal',
            variable=self.speed_var,
            font=ModernStyle.FONTS['normal'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text'],
            highlightthickness=0,
            length=350,
            showvalue=True
        )
        speed_scale.pack(side='left', fill='x', expand=True)
        
        # 速度值显示
        self.speed_value_label = tk.Label(
            speed_control_frame,
            text=f"{current_speed:.1f}x",
            font=ModernStyle.FONTS['normal'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['primary'],
            width=8
        )
        self.speed_value_label.pack(side='right', padx=(10, 0))
        
        # 绑定滑块变化事件
        speed_scale.config(command=lambda v: self.speed_value_label.config(text=f"{float(v):.1f}x"))
        
        # 速度说明
        speed_info_text = """下载速度倍数控制下载延迟时间（默认：1.0x）
• 0.5x = 慢速（延迟时间加倍，适合网络不稳定）
• 1.0x = 正常速度（推荐，稳定性最好）
• 2.0x-4.0x = 快速（延迟时间大幅减少，可能触发人机验证）

⚠️ 警告：过快的下载速度（>2.0x）可能会触发官网的人机验证！
如测试出更稳定的速度，欢迎通过Issues反馈给作者"""
        
        speed_info_label = tk.Label(
            content_frame,
            text=speed_info_text,
            font=ModernStyle.FONTS['small'],
            bg='#FFF3CD',
            fg='#856404',
            anchor='w',
            padx=15,
            pady=15,
            wraplength=380,
            relief='solid',
            borderwidth=1
        )
        speed_info_label.pack(fill='x', pady=(0, 20))

        # API 说明
        api_frame = tk.Frame(content_frame, bg='#F8F9FA', padx=15, pady=12)
        api_frame.pack(fill='x', pady=(0, 15))
        
        api_title = tk.Label(
            api_frame,
            text="下载方式",
            font=ModernStyle.FONTS['header'],
            bg='#F8F9FA',
            fg=ModernStyle.COLORS['text']
        )
        api_title.pack(anchor='w', pady=(0, 10))
        
        api_info = tk.Label(
            api_frame,
            text="• 使用 API 模式下载\n• 无需登录，无需字体解密\n• 支持节点自动切换\n• 支持批量下载，速度快",
            font=ModernStyle.FONTS['normal'],
            bg='#F8F9FA',
            fg='#636E72',
            justify='left'
        )
        api_info.pack(anchor='w')

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
            text="作者: halei0v0\n项目: FXdownloader - 番茄小说下载器\n版本: v1.0.6\n\n感谢使用本软件！",
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
        
        # 恢复默认设置按钮
        reset_btn = ttk.Button(
            button_frame,
            text="恢复默认设置",
            command=self.reset_to_default,
            style='Primary.TButton'
        )
        reset_btn.pack(side='left', padx=(5, 0))
        
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
        from config import set_concurrent_downloads, set_download_speed

        # 保存并发设置
        concurrent = self.concurrent_var.get()
        if not set_concurrent_downloads(concurrent):
            messagebox.showerror('错误', '保存并发设置失败！')
            return

        # 保存下载速度设置
        speed = self.speed_var.get()
        if not set_download_speed(speed):
            messagebox.showerror('错误', '保存下载速度设置失败！')
            return

        messagebox.showinfo('成功', '设置已保存！')

        # 调用回调函数刷新软件设置
        if self.on_save:
            self.on_save()

        self.dialog.destroy()

    def reset_to_default(self):
        """恢复默认设置"""
        from config import DEFAULT_CONCURRENT_DOWNLOADS, DEFAULT_DOWNLOAD_SPEED

        if messagebox.askyesno('确认', '确定要恢复默认设置吗？'):
            # 恢复并发下载数
            self.concurrent_var.set(DEFAULT_CONCURRENT_DOWNLOADS)

            # 恢复下载速度
            self.speed_var.set(DEFAULT_DOWNLOAD_SPEED)
            self.speed_value_label.config(text=f"{DEFAULT_DOWNLOAD_SPEED:.1f}x")

            messagebox.showinfo('成功', '已恢复默认设置！')

    def on_close(self):
        """关闭对话框"""
        # 解绑鼠标滚轮事件
        if hasattr(self, '_mousewheel_handler'):
            self.dialog.unbind_all("<MouseWheel>")
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
            cursor='hand2'
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
            # 将Row对象转换为字典
            novel_dict = dict(novel)
            # 根据源类型决定是否显示字数和章节数
            is_official = novel_dict.get('source', 'official') == 'official'
            if is_official:
                word_count_str = f"{novel_dict['word_count']:,}"
                chapter_count_str = novel_dict['chapter_count']
            else:
                word_count_str = ''
                chapter_count_str = ''

            # updated_at 已经是字符串格式，直接使用
            updated_at_str = novel_dict['updated_at'] if novel_dict['updated_at'] else '未知'
            self.tree.insert('', 'end', values=(
                '☐',
                novel_dict['title'],
                novel_dict['author'],
                word_count_str,
                chapter_count_str,
                novel_dict['status'],
                updated_at_str
            ), tags=(novel_dict['novel_id'],))
    
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
            # 将Row对象转换为字典
            novel_dict = dict(novel)
            content += f"# 《{novel_dict['title']}》\n"
            content += f"{novel_dict['novel_id']}\n\n"
        
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
        progress_dialog.geometry("550x400")
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

        # 状态标签
        status_label = tk.Label(
            progress_frame,
            text="准备下载...",
            font=ModernStyle.FONTS['header'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        status_label.pack(pady=(0, 10))

        # 进度条
        progress_bar = ttk.Progressbar(
            progress_frame,
            orient='horizontal',
            length=0,
            mode='determinate'
        )
        progress_bar.pack(fill='x', pady=(0, 10))

        # 详细信息标签（包含进度、速度、预估时间）
        detail_label = tk.Label(
            progress_frame,
            text="",
            font=ModernStyle.FONTS['normal'],
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text_secondary']
        )
        detail_label.pack(pady=(0, 10))

        # 日志文本框
        progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=8,
            state='disabled',
            font=('Consolas', 8),
            bg=ModernStyle.COLORS['surface'],
            fg=ModernStyle.COLORS['text'],
            padx=10,
            pady=10,
            relief='solid',
            borderwidth=1
        )
        progress_text.pack(fill='both', expand=True)

        # 下载开始时间（用于计算速度和预估时间）
        import time
        download_start_time = [time.time()]  # 使用列表以便在闭包中修改
        
        # 在新线程中执行批量下载
        def do_batch_download():
            from spider import FanqieSpider
            from config import get_concurrent_downloads, SOURCE_OFFICIAL, SOURCE_THIRD_PARTY
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading

            if self.download_mode == SOURCE_THIRD_PARTY:
                progress_dialog.after(0, lambda: progress_dialog.destroy())
                self.root.after(100, self._launch_tomato_downloader)
                return

            use_api = self.download_mode != SOURCE_OFFICIAL

            spider = FanqieSpider(use_api=use_api)
            concurrent_downloads = get_concurrent_downloads()

            # 线程安全的结果统计
            result_lock = threading.Lock()
            success_count = 0
            failed_novels = []
            completed_count = 0
            total_count = len(novel_list)

            # 添加总体进度信息
            progress_dialog.after(0, lambda: progress_bar.config(value=0))
            progress_dialog.after(0, lambda: progress_bar.config(maximum=100))
            progress_dialog.after(0, lambda: detail_label.config(text="初始化中..."))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"开始批量下载，共 {total_count} 个小说\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"并发数: {concurrent_downloads}\n"))
            if use_api:
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"使用第三方源下载（API模式，无需字体解密，下载前会对API进行测试请耐心等待）\n"))
            else:
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"使用官网下载（需登录，需字体解密）\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n\n"))

            # 下载单个小说的函数
            def download_novel(novel_info):
                novel_id = novel_info['novel_id']
                title = novel_info['title']

                # 每个线程创建自己的spider实例
                thread_spider = FanqieSpider(use_api=use_api)
                
                # 添加开始日志
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"正在下载: {title}\n"))
                
                try:
                    # 获取小说信息
                    novel_data = thread_spider.get_novel_info(novel_id)
                    if not novel_data:
                        progress_dialog.after(0, lambda: self._add_log(progress_text, f"  ✗ 获取信息失败: {title}\n"))
                        return (False, f"{title} (获取信息失败)")
                    
                    # 保存小说信息
                    source = 'third_party' if use_api else 'official'
                    self.db.save_novel(
                        novel_id=novel_data['novel_id'],
                        title=novel_data['title'],
                        author=novel_data['author'],
                        description=novel_data['description'],
                        cover_url=novel_data['cover_url'],
                        word_count=novel_data['word_count'],
                        chapter_count=novel_data['chapter_count'],
                        source=source
                    )
                    
                    # 获取章节列表
                    chapters = thread_spider.get_chapter_list(novel_id)
                    if not chapters:
                        progress_dialog.after(0, lambda: self._add_log(progress_text, f"  ✗ 获取章节失败: {title}\n"))
                        return (False, f"{title} (获取章节失败)")

                    # 下载章节
                    chapter_success = 0
                    total_chapters = len(chapters)
                    db_lock = threading.Lock()

                    progress_dialog.after(0, lambda t=title, tc=total_chapters:
                        self._add_log(progress_text, f"  《{t}》共 {tc} 章\n"))

                    # 第三方模式：使用线程池并发下载章节
                    if use_api:
                        from config import MAX_CONCURRENT_DOWNLOADS

                        def download_single_chapter(idx, chapter):
                            nonlocal chapter_success
                            chapter_title = chapter['chapter_title']
                            chapter_data = thread_spider.get_chapter_content(novel_id, chapter['chapter_id'])

                            if chapter_data:
                                # 使用返回的真实标题，如果为空则使用章节列表中的标题
                                api_title = chapter_data.get('title', '')
                                real_title = api_title if api_title and api_title.strip() else chapter_title
                                content = chapter_data.get('content', '')
                                word_count = len(content)

                                # 使用锁保护数据库写入
                                with db_lock:
                                    self.db.save_chapter(
                                        novel_id=novel_id,
                                        chapter_id=chapter['chapter_id'],
                                        chapter_title=real_title,
                                        chapter_index=chapter['chapter_index'],
                                        content=content,
                                        word_count=word_count,
                                        original_title=chapter_title  # 保存章节列表中的原始标题
                                    )
                                    chapter_success += 1

                                progress_dialog.after(0, lambda t=title, i=idx, tc=total_chapters, wc=word_count:
                                    self._add_log(progress_text, f"    [{i}/{tc}] 第{i}章 ({wc}字)\n"))
                                return True
                            else:
                                progress_dialog.after(0, lambda t=title, i=idx:
                                    self._add_log(progress_text, f"    [{i}] ✗ 第{i}章 下载失败\n"))
                                return False

                        # 使用线程池并发下载章节
                        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
                            future_to_chapter = {
                                executor.submit(download_single_chapter, idx, chapter): idx
                                for idx, chapter in enumerate(chapters, 1)
                            }
                            # 等待所有任务完成
                            for future in as_completed(future_to_chapter):
                                pass

                    # 官网模式：顺序下载章节
                    else:
                        for idx, chapter in enumerate(chapters, 1):
                            # 更新章节下载进度
                            chapter_title = chapter['chapter_title']
                            chapter_data = thread_spider.get_chapter_content(novel_id, chapter['chapter_id'])

                            if chapter_data:
                                # 使用返回的真实标题，如果为空则使用章节列表中的标题
                                api_title = chapter_data.get('title', '')
                                real_title = api_title if api_title and api_title.strip() else chapter_title
                                content = chapter_data.get('content', '')
                                word_count = len(content)

                                self.db.save_chapter(
                                    novel_id=novel_id,
                                    chapter_id=chapter['chapter_id'],
                                    chapter_title=real_title,
                                    chapter_index=chapter['chapter_index'],
                                    content=content,
                                    word_count=word_count,
                                    original_title=chapter_title  # 保存章节列表中的原始标题
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
                            # 只有官网模式才显示字数和章节数
                            if not use_api:
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

                        # 计算进度百分比
                        progress_percent = (completed_count / total_count) * 100

                        # 计算已用时间
                        elapsed_time = time.time() - download_start_time[0]

                        # 计算下载速度（小说/秒）
                        if elapsed_time > 0:
                            speed = completed_count / elapsed_time
                        else:
                            speed = 0

                        # 计算预估剩余时间（秒）
                        if speed > 0:
                            remaining_novels = total_count - completed_count
                            estimated_remaining = remaining_novels / speed
                        else:
                            estimated_remaining = 0

                        # 格式化时间显示
                        def format_time(seconds):
                            if seconds < 60:
                                return f"{int(seconds)}秒"
                            elif seconds < 3600:
                                minutes = int(seconds / 60)
                                secs = int(seconds % 60)
                                return f"{minutes}分{secs}秒"
                            else:
                                hours = int(seconds / 3600)
                                minutes = int((seconds % 3600) / 60)
                                return f"{hours}小时{minutes}分"

                        elapsed_str = format_time(elapsed_time)
                        remaining_str = format_time(estimated_remaining) if estimated_remaining > 0 else "计算中..."

                        # 更新进度条
                        progress_dialog.after(0, lambda p=progress_percent: progress_bar.config(value=p))

                        # 更新状态标签
                        progress_dialog.after(0, lambda: self._safe_update_ui(
                            status_label,
                            lambda: status_label.config(text=f"正在下载 ({completed_count}/{total_count})")
                        ))

                        # 更新详细信息标签
                        progress_dialog.after(0, lambda e=elapsed_str, r=remaining_str, s=speed: self._safe_update_ui(
                            detail_label,
                            lambda: detail_label.config(
                                text=f"进度: {progress_percent:.1f}% | 速度: {s:.2f} 本/秒 | 已用时: {e} | 预计剩余: {r}"
                            )
                        ))
            
            # 刷新历史列表
            progress_dialog.after(0, lambda: self._safe_update_ui(
                progress_dialog,
                lambda: self.load_download_history()
            ))

            # 计算总用时
            total_time = time.time() - download_start_time[0]
            avg_speed = total_count / total_time if total_time > 0 else 0

            def format_time(seconds):
                if seconds < 60:
                    return f"{int(seconds)}秒"
                elif seconds < 3600:
                    minutes = int(seconds / 60)
                    secs = int(seconds % 60)
                    return f"{minutes}分{secs}秒"
                else:
                    hours = int(seconds / 3600)
                    minutes = int((seconds % 3600) / 60)
                    return f"{hours}小时{minutes}分"

            total_time_str = format_time(total_time)

            # 显示结果
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"\n{'='*50}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"批量下载完成！\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"成功: {success_count}/{total_count}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"总用时: {total_time_str}\n"))
            progress_dialog.after(0, lambda: self._add_log(progress_text, f"平均速度: {avg_speed:.2f} 本/秒\n"))

            if failed_novels:
                progress_dialog.after(0, lambda: self._add_log(progress_text, f"\n失败的小说 ({len(failed_novels)}个):\n"))
                for i, novel in enumerate(failed_novels[:5]):
                    progress_dialog.after(0, lambda n=novel: self._add_log(progress_text, f"  - {n}\n"))
                if len(failed_novels) > 5:
                    progress_dialog.after(0, lambda c=len(failed_novels):
                        self._add_log(progress_text, f"  ... 还有 {c - 5} 个\n"))

            progress_dialog.after(0, lambda: self._add_log(progress_text, f"{'='*50}\n"))

            # 更新进度条为100%
            progress_dialog.after(0, lambda: progress_bar.config(value=100))

            # 更新状态标签
            progress_dialog.after(0, lambda: self._safe_update_ui(
                status_label,
                lambda: status_label.config(text="下载完成")
            ))

            # 更新详细信息标签
            progress_dialog.after(0, lambda: self._safe_update_ui(
                detail_label,
                lambda: detail_label.config(text=f"完成！成功 {success_count}/{total_count} 本，总用时 {total_time_str}")
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

                # 将Row对象转换为字典
                novel_dict = dict(novel)

                chapters = self.db.get_chapters(novel_id)
                if not chapters:
                    failed_novels.append(f"{title} (没有可导出的章节)")
                    continue

                with open(output_path, 'w', encoding='utf-8') as f:
                    # 写入小说信息
                    f.write("=" * 50 + "\n")
                    f.write(f"书名: {novel_dict['title']}\n")
                    f.write(f"作者: {novel_dict['author']}\n")
                    f.write(f"简介: {novel_dict['description']}\n")
                    # 只有官网模式才显示字数和章节数
                    if novel_dict.get('source', 'official') == 'official':
                        f.write(f"字数: {novel_dict['word_count']:,} 字\n")
                        f.write(f"章节数: {novel_dict['chapter_count']} 章\n")
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
            self.root.geometry("950x800")
            self.root.resizable(True, True)
            self.root.minsize(800, 600)

            # 设置样式
            self.setup_styles()

            # 下载模式：'official' 或 'third_party'
            self.download_mode = None

            # 初始化爬虫和下载器
            self.spider = FanqieSpider(use_api=False)
            self.downloader = NovelDownloader()
            self.current_novel_id = None
            self.is_logged_in = False
            
            # 跟踪失败的章节信息
            self.failed_chapters = []  # 存储失败的章节信息 [(chapter_id, chapter_title, chapter_url), ...]
            self.current_chapter_url = None  # 当前正在下载的章节URL
            
            # 暂停/继续下载状态管理
            self.is_paused = False  # 是否暂停
            self.is_downloading = False  # 是否正在下载
            self.pause_event = threading.Event()  # 暂停事件对象
            self.pause_event.set()  # 初始状态为未暂停

            # 下载时间记录（用于改进的预估算法）
            self.recent_download_records = []  # 记录最近N章的下载记录 (字数, 下载时间秒, 延迟时间秒)
            self.MAX_RECENT_TIMES = 15  # 最多记录最近15章
            self.ewma_speed = None  # 指数加权移动平均速度 (字/秒)
            self.EWMA_ALPHA = 0.3  # EWMA平滑系数（新数据权重）
            
            # 继续下载时需要的上下文信息
            self.resume_context = {
                'start_chapter': None,
                'end_chapter': None,
                'total_chapters': None,
                'start_index': None,
                'end_index': None,
                'chapters': None,
                'current_spider': None,
                'success_count': None,
                'download_start_time': None,
                'use_official_mode': None
            }
    
            # 创建界面
            self.create_widgets()

            # 启动时询问下载模式
            self.root.after(100, self._ask_download_mode)

    def _ask_download_mode(self):
        """启动时询问用户选择下载模式"""
        from config import get_source_preference, set_source_preference, SOURCE_ASK, SOURCE_OFFICIAL, SOURCE_THIRD_PARTY

        saved = get_source_preference()
        if saved != SOURCE_ASK:
            self.download_mode = saved
            self._apply_download_mode()
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("选择下载模式")
        dialog.geometry("480x340")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 240
        y = (dialog.winfo_screenheight() // 2) - 170
        dialog.geometry(f'+{x}+{y}')

        main_frame = tk.Frame(dialog, bg='#FFFFFF')
        main_frame.pack(fill='both', expand=True)

        title_frame = tk.Frame(main_frame, bg='#FF6B6B', height=50)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="选择下载模式", font=('Microsoft YaHei UI', 14, 'bold'), bg='#FF6B6B', fg='white').pack(pady=10)

        content = tk.Frame(main_frame, bg='#FFFFFF', padx=30, pady=20)
        content.pack(fill='both', expand=True)

        tk.Label(content, text="请选择本次使用的下载模式：", font=('Microsoft YaHei UI', 10), bg='#FFFFFF', fg='#2D3436').pack(anchor='w', pady=(0, 15))

        remember_var = tk.BooleanVar(value=False)

        def choose(mode):
            self.download_mode = mode
            if remember_var.get():
                set_source_preference(mode)
            self._apply_download_mode()
            dialog.destroy()

        btn_frame = tk.Frame(content, bg='#FFFFFF')
        btn_frame.pack(fill='x', pady=(0, 15))

        tk.Button(
            btn_frame, text="📖 官网模式", font=('Microsoft YaHei UI', 11, 'bold'),
            bg='#0984E3', fg='white', borderwidth=0, padx=20, pady=12, cursor='hand2',
            command=lambda: choose(SOURCE_OFFICIAL)
        ).pack(side='left', expand=True, fill='x', padx=(0, 8))

        tk.Button(
            btn_frame, text="🚀 第三方模式", font=('Microsoft YaHei UI', 11, 'bold'),
            bg='#00B894', fg='white', borderwidth=0, padx=20, pady=12, cursor='hand2',
            command=lambda: choose(SOURCE_THIRD_PARTY)
        ).pack(side='right', expand=True, fill='x', padx=(8, 0))

        tk.Label(content, text="官网模式：需登录，需字体解密，更稳定\n第三方模式：启动 TomatoNovelDownloader，无需登录",
                 font=('Microsoft YaHei UI', 8), bg='#FFFFFF', fg='#636E72', justify='left').pack(anchor='w', pady=(0, 10))

        tk.Checkbutton(
            content, text="记住选择（下次不再询问）", variable=remember_var,
            font=('Microsoft YaHei UI', 9), bg='#FFFFFF', fg='#636E72',
            selectcolor='#FFFFFF', activebackground='#FFFFFF'
        ).pack(anchor='w')

    def _apply_download_mode(self):
        """应用下载模式设置"""
        from config import SOURCE_OFFICIAL

        if self.download_mode == SOURCE_OFFICIAL:
            self.spider = FanqieSpider(use_api=False)
            self.log("当前模式：官网下载（需登录，需字体解密）", 'info')
            # 官网模式需要登录，创建登录区域
            self._create_login_area()
        else:
            self.spider = FanqieSpider(use_api=True)
            self.log("当前模式：第三方下载（点击下载按钮将启动 TomatoNovelDownloader）", 'info')
            # 第三方模式不需要登录，不创建登录区域

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
                       padding=(20, 10),
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
        
        # Progressbar样式
        style.configure('Modern.Horizontal.TProgressbar',
                       background=colors['primary'],
                       troughcolor=colors['surface'],
                       bordercolor=colors['border'],
                       lightcolor=colors['primary'],
                       darkcolor=colors['primary'],
                       borderwidth=0,
                       thickness=8)

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
        
        # 右侧区域容器（登录区域 + 设置按钮）
        self.right_frame = tk.Frame(title_frame, bg=ModernStyle.COLORS['primary'])
        self.right_frame.pack(side='right', padx=20, pady=15)
        
        # 登录区域（初始为空，在模式确定后根据需要创建）
        self.login_frame = None
        self.login_status_label = None
        self.login_btn = None
        
        # 设置按钮（始终显示）
        settings_btn = tk.Button(
            self.right_frame,
            text="设置",
            command=self.show_settings,
            bg='#95A5A6',
            fg='white',
            borderwidth=0,
            padx=15,
            pady=6,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2'
        )
        settings_btn.pack(side='right', padx=(10, 0))
    
    def _create_login_area(self):
        """创建登录区域（仅官网模式需要）"""
        if self.login_frame is not None:
            return  # 已创建
        
        self.login_frame = tk.Frame(self.right_frame, bg=ModernStyle.COLORS['primary'])
        self.login_frame.pack(side='right', padx=(0, 10))
        
        # 检查是否已登录（检查是否有有效的session_id或passport_csrf_token等关键cookie）
        cookies = load_cookies()
        self.is_logged_in = len(cookies) > 0 and any(key in cookies for key in ['sessionid', 'passport_csrf_token', 'passport_assist_user'])

        # 登录状态标签
        self.login_status_label = tk.Label(
            self.login_frame,
            text=self._get_login_status_text(),
            font=('Microsoft YaHei UI', 9),
            bg=ModernStyle.COLORS['primary'],
            fg='white' if self.is_logged_in else '#FFEAA7'
        )
        self.login_status_label.pack(side='left', padx=(0, 10))
        
        # 登录按钮
        self.login_btn = tk.Button(
            self.login_frame,
            text="退出登录" if self.is_logged_in else "登录",
            command=self.on_login_click,
            bg='white',
            fg=ModernStyle.COLORS['primary'],
            borderwidth=0,
            padx=18,
            pady=6,
            font=('Microsoft YaHei UI', 9, 'bold'),
            cursor='hand2'
        )
        self.login_btn.pack(side='left', padx=(10, 0))
    
    def on_login_click(self):
        """点击登录/退出登录按钮"""
        if self.is_logged_in:
            # 退出登录
            from config import clear_cookies
            if messagebox.askyesno('确认', '确定要退出登录吗？'):
                clear_cookies()
                self.is_logged_in = False
                # 清除用户信息缓存
                try:
                    import config as _cfg
                    if _cfg.USER_INFO is not None and hasattr(_cfg.USER_INFO, 'clear'):
                        _cfg.USER_INFO.clear()
                except:
                    pass
                self.update_login_status()
                self.log("已退出登录", 'info')
        else:
            # 打开登录对话框
            LoginDialog(self.root, self.on_login_result)
    
    def on_login_result(self, success):
        """登录结果回调"""
        if success:
            self.is_logged_in = True
            # 刷新用户信息
            try:
                from config import refresh_user_info
                refresh_user_info()
            except:
                pass
            self.update_login_status()
            self.log("登录成功！", 'success')
        else:
            self.log("登录失败", 'error')
    
    def update_login_status(self):
        """更新登录状态显示"""
        self.login_status_label.config(
            text=self._get_login_status_text(),
            fg='white' if self.is_logged_in else '#FFEAA7'
        )
        self.login_btn.config(
            text="退出登录" if self.is_logged_in else "登录"
        )
    
    def _get_login_status_text(self):
        """获取登录状态文本"""
        if self.is_logged_in:
            try:
                from config import USER_INFO
                if USER_INFO and 'username' in USER_INFO:
                    username = USER_INFO['username']
                    return f"已登录: {username}"
                else:
                    return "已登录"
            except:
                return "已登录"
        else:
            return "未登录"

    def show_settings(self):
        """显示设置对话框"""
        SettingsDialog(self.root, on_save=self._refresh_settings)

    def _refresh_settings(self):
        """刷新设置，使配置更改生效"""
        # 刷新用户信息（如果已登录）
        if self.is_logged_in:
            from config import refresh_user_info
            refresh_user_info()
            self.update_login_status()

        # 显示刷新提示
        self.log("设置已更新", 'info')

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

        # 优先使用上次保存的导出路径
        try:
            from config import get_last_export_path
            last_export_path = get_last_export_path()

            if last_export_path and os.path.exists(os.path.dirname(last_export_path)):
                # 使用上次导出路径的目录
                export_dir = os.path.dirname(last_export_path)
                self.export_path_entry.insert(0, export_dir)
            else:
                # 使用默认的用户文档目录
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
        except Exception as e:
            print(f"加载上次导出路径失败: {e}")
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
        self.download_button.pack(side='left', padx=(0, 5))
        
        # 暂停/继续按钮（初始隐藏）
        self.pause_resume_button = ttk.Button(
            button_frame,
            text="暂停",
            command=self.toggle_pause_resume,
            style='Primary.TButton'
        )
        # 初始状态为隐藏
        
        # 人机验证按钮已隐藏
        # self.captcha_button = ttk.Button(
        #     button_frame,
        #     text="人机验证",
        #     command=self.open_captcha_page,
        #     style='Primary.TButton'
        # )
        # self.captcha_button.pack(side='left', padx=(0, 10))
        
        self.export_button = ttk.Button(
            button_frame,
            text="下载历史",
            command=self.show_download_history,
            style='Success.TButton'
        )
        self.export_button.pack(side='left', padx=(0, 5))

    def create_log_section(self, parent):
        """创建日志显示区域"""
        log_frame = ttk.LabelFrame(parent, text="下载日志", style='Modern.TLabelframe', padding=15)
        log_frame.pack(fill='both', expand=True)
        
        # 进度信息容器
        progress_info_frame = tk.Frame(log_frame, bg=ModernStyle.COLORS['bg'])
        progress_info_frame.pack(fill='x', pady=(0, 10))
        
        # 进度百分比标签
        self.progress_label = tk.Label(
            progress_info_frame,
            text="准备就绪",
            font=('Microsoft YaHei UI', 10),
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text']
        )
        self.progress_label.pack(anchor='w', pady=(0, 5))
        
        # 进度条
        self.progress_bar = ttk.Progressbar(
            progress_info_frame,
            style='Modern.Horizontal.TProgressbar',
            mode='determinate',
            maximum=100
        )
        self.progress_bar.pack(fill='x', pady=(0, 5))
        
        # 预估时间标签
        self.eta_label = tk.Label(
            progress_info_frame,
            text="",
            font=('Microsoft YaHei UI', 9),
            bg=ModernStyle.COLORS['bg'],
            fg=ModernStyle.COLORS['text_secondary']
        )
        self.eta_label.pack(anchor='w')
        
        # 日志文本框
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
            # 检查是否是授权验证错误
            if novel_info.get('_error') == 'AUTH_FAILED':
                error_msg = novel_info.get('_message', '第三方API授权验证失败')
                messagebox.showerror(
                    '授权验证失败',
                    f'{error_msg}\n\n'
                    f'建议解决方案：\n'
                    f'1. 打开"设置"，切换到"官网"模式\n'
                    f'2. 点击"登录Cookie"按钮获取Cookie\n'
                    f'3. 重新尝试下载\n\n'
                    f'注意：官网模式需要登录，但更稳定可靠。'
                )
                self.log("授权验证失败，建议切换到官网模式", 'error')
                return

            self.current_novel_id = novel_info['novel_id']
            self.novel_title.config(text=novel_info['title'])
            self.novel_author.config(text=novel_info['author'])
            # 只有官网模式才显示字数和章节数
            if self.spider.use_api:
                self.novel_word_count.config(text="")
                self.novel_chapter_count.config(text="")
            else:
                self.novel_word_count.config(text=f"{novel_info['word_count']:,}")
                self.novel_chapter_count.config(text=str(novel_info['chapter_count']))
            self.novel_description.config(text=novel_info['description'][:150] + '...' if len(novel_info['description']) > 150 else novel_info['description'])
            self.end_chapter.delete(0, tk.END)
            self.end_chapter.insert(0, str(novel_info['chapter_count']))
            self.log(f"获取成功: {novel_info['title']}", 'success')
        else:
            messagebox.showerror('错误', '获取小说信息失败')
            self.log("获取小说信息失败", 'error')

    def pause_download(self):
        """暂停下载"""
        if self.is_downloading and not self.is_paused:
            self.is_paused = True
            self.pause_event.clear()  # 设置暂停标志
            self.log("用户请求暂停下载...", 'warning')
            self.progress_label.config(text="下载已暂停")
            self.download_button.config(state='disabled')
            self.pause_resume_button.config(text="继续", style='Success.TButton')
    
    def resume_download(self):
        """继续下载"""
        if self.is_paused:
            self.is_paused = False
            self.pause_event.set()  # 清除暂停标志
            self.log("用户请求继续下载...", 'info')
            self.progress_label.config(text="继续下载...")
            self.download_button.config(state='disabled')
            self.pause_resume_button.config(text="暂停", style='Primary.TButton')
    
    def toggle_pause_resume(self):
        """切换暂停/继续状态"""
        if self.is_paused:
            self.resume_download()
        else:
            self.pause_download()
    
    def show_download_controls(self):
        """显示下载控制按钮（暂停/继续）"""
        self.pause_resume_button.pack(side='left', padx=(0, 5))
        self.pause_resume_button.config(text="暂停", style='Primary.TButton', state='normal')
    
    def hide_download_controls(self):
        """隐藏下载控制按钮"""
        self.pause_resume_button.pack_forget()
        self.pause_resume_button.config(text="暂停", style='Primary.TButton')
    
    def _find_tomato_downloader(self):
        """查找 TomatoNovelDownloader 可执行文件路径"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        candidates = [
            os.path.join(base_dir, 'TomatoNovelDownloader.exe'),
            os.path.join(base_dir, 'TomatoNovelDownloader-Win64-v2.4.0.exe'),
        ]

        if getattr(sys, 'frozen', False):
            candidates.append(os.path.join(sys._MEIPASS, 'TomatoNovelDownloader.exe'))
            candidates.append(os.path.join(sys._MEIPASS, 'TomatoNovelDownloader-Win64-v2.4.0.exe'))

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _launch_tomato_downloader(self):
        """启动 TomatoNovelDownloader 并关闭 FXdownloader"""
        exe_path = self._find_tomato_downloader()
        if not exe_path:
            messagebox.showerror(
                '错误',
                '未找到 TomatoNovelDownloader 可执行文件！\n\n'
                '请确保以下文件之一存在于程序目录中：\n'
                '• TomatoNovelDownloader.exe\n'
                '• TomatoNovelDownloader-Win64-v2.4.0.exe'
            )
            self.download_button.config(state='normal')
            self.export_button.config(state='normal')
            return

        confirm = messagebox.askyesno(
            '切换到第三方下载器',
            '第三方下载将使用 TomatoNovelDownloader 进行下载。\n\n'
            'FXdownloader 将自动关闭，由 TomatoNovelDownloader 接管下载任务。\n\n'
            '是否继续？'
        )
        if not confirm:
            self.download_button.config(state='normal')
            self.export_button.config(state='normal')
            return

        try:
            import subprocess
            subprocess.Popen([exe_path])
            self.root.after(500, self.root.destroy)
        except Exception as e:
            messagebox.showerror('错误', f'启动 TomatoNovelDownloader 失败：{e}')
            self.download_button.config(state='normal')
            self.export_button.config(state='normal')

    def start_download(self):
        """开始下载"""
        # 检查是否已经在下载中
        if self.download_button['state'] == 'disabled' and not self.is_paused:
            messagebox.showwarning('提示', '正在下载中，请等待当前下载完成')
            return

        if not self.current_novel_id:
            messagebox.showwarning('提示', '请先获取小说信息')
            return

        from config import SOURCE_THIRD_PARTY
        if self.download_mode == SOURCE_THIRD_PARTY:
            self._launch_tomato_downloader()
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
        import time  # 导入time模块
        try:
            # 设置下载状态
            self.is_downloading = True
            self.is_paused = False
            self.pause_event.set()
            
            # 显示下载控制按钮
            self.root.after(0, lambda: self.show_download_controls())
            
            # 更新按钮状态
            self.root.after(0, lambda: self.download_button.config(state='disabled'))
            self.root.after(0, lambda: self.export_button.config(state='disabled'))
            
            self.log("=" * 60)
            self.log(f"开始下载: {self.current_novel_id}", 'info')
            self.log("=" * 60)

            # 清空失败章节列表
            self.failed_chapters = []

            # 根据实际使用的模式显示信息
            from config import SOURCE_OFFICIAL
            use_official_mode = self.download_mode == SOURCE_OFFICIAL

            if use_official_mode:
                self.log("使用官网下载（需登录，需字体解密）", 'info')
            else:
                self.log("使用第三方源下载（API模式，无需字体解密，下载前会对API进行测试请耐心等待）", 'info')
            current_spider = self.spider

            # 清除所有旧数据
            self.log("正在清除旧数据...")
            self.downloader.db.delete_novel(self.current_novel_id)
            self.log("旧数据已清除", 'success')

            # 获取小说信息
            novel_info = current_spider.get_novel_info(self.current_novel_id)
            if not novel_info:
                self.log("获取小说信息失败！", 'error')
                return

            self.log(f"小说名称: {novel_info['title']}")
            self.log(f"作者: {novel_info['author']}")
            if use_official_mode:
                self.log(f"字数: {novel_info['word_count']:,}")
                self.log(f"章节数: {novel_info['chapter_count']}")

            # 保存小说信息
            source = 'official' if use_official_mode else 'third_party'
            self.downloader.db.save_novel(
                novel_id=novel_info['novel_id'],
                title=novel_info['title'],
                author=novel_info['author'],
                description=novel_info['description'],
                cover_url=novel_info['cover_url'],
                word_count=novel_info['word_count'],
                chapter_count=novel_info['chapter_count'],
                source=source
            )

            # 获取章节列表
            chapters = current_spider.get_chapter_list(self.current_novel_id)
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

            # 保存继续下载需要的上下文信息
            self.resume_context.update({
                'start_chapter': start_chapter,
                'end_chapter': end_chapter,
                'total_chapters': total_chapters,
                'start_index': start_index,
                'end_index': end_index,
                'chapters': chapters,
                'current_spider': current_spider,
                'success_count': 0,
                'download_start_time': time.time(),
                'use_official_mode': use_official_mode
            })

            # 下载章节
            success_count = 0
            consecutive_failures = 0  # 连续失败计数器
            max_consecutive_failures = 3  # 最大连续失败次数
            captcha_detected = False  # 是否检测到人机验证
            
            # 进度跟踪
            download_start_time = time.time()
            total_to_download = end_index - start_index

            # 清空下载时间记录（用于改进的预估算法）
            self.recent_download_records = []
            self.ewma_speed = None

            # 初始化进度条
            self.root.after(0, lambda: self.progress_bar.config(value=0))
            self.root.after(0, lambda: self.progress_label.config(text=f"准备下载: 0/{total_to_download} 章 (0%)"))
            self.root.after(0, lambda: self.eta_label.config(text=""))

            for idx in range(start_index, end_index):
                # 检查是否暂停
                if self.is_paused:
                    self.log("下载已暂停，等待用户继续...", 'warning')
                    # 等待用户继续
                    self.pause_event.wait()
                    self.log("继续下载...", 'info')
                    # 重置连续失败计数器（避免暂停后的连续失败判定）
                    consecutive_failures = 0
                    # 更新继续下载的上下文信息
                    self.resume_context['success_count'] = success_count
                    self.resume_context['download_start_time'] = download_start_time
                
                chapter = chapters[idx]
                chapter_id = chapter['chapter_id']
                chapter_title = chapter['chapter_title']

                # 构建章节URL（仅官网模式使用）
                chapter_url = f"https://fanqienovel.com/reader/{chapter_id}"
                self.current_chapter_url = chapter_url

                self.log(f"[{idx + 1}/{total_chapters}] 正在下载: {chapter_title}")

                # 记录开始下载时间（用于计算实际下载时间，不包括等待延迟）
                chapter_start_time = time.time()

                chapter_data = current_spider.get_chapter_content(self.current_novel_id, chapter_id)

                # 检查是否需要人机验证
                if chapter_data and chapter_data.get('captcha_required'):
                    self.log(f"  ⚠ 检测到人机验证页面", 'warning')
                    self.log(f"  验证页面: {chapter_url}", 'warning')
                    
                    # 记录需要验证的章节
                    self.failed_chapters.append((chapter_id, chapter_title, chapter_url))
                    
                    # 弹出提示而非打开浏览器
                    self.root.after(0, lambda: messagebox.showwarning(
                        '访问过多',
                        '访问过于频繁，触发了官网人机验证！\n\n'
                        '建议解决方案：\n'
                        '1. 等待一段时间（10-30分钟）后重试\n'
                        '2. 切换到第三方源模式（无需登录，无需字体解密）\n'
                        '3. 在设置中调整并发数或延迟时间\n\n'
                        '点击"确定"后，下载将自动停止。'
                    ))
                    
                    # 暂停下载，等待用户操作
                    self.log("=" * 60, 'warning')
                    self.log("下载已暂停：访问过多引起官网人机验证", 'warning')
                    self.log("=" * 60, 'warning')
                    self.log("请等待一段时间后重新下载", 'warning')
                    captcha_detected = True
                    
                    # 退出下载线程
                    break
                
                if chapter_data and not chapter_data.get('captcha_required'):
                    real_title = chapter_data.get('title', chapter_title)
                    content = chapter_data.get('content', '')
                    word_count = len(content)

                    self.downloader.db.save_chapter(
                        novel_id=self.current_novel_id,
                        chapter_id=chapter_id,
                        chapter_title=real_title,
                        chapter_index=chapter['chapter_index'],
                        content=content,
                        word_count=word_count,
                        original_title=chapter_title  # 保存章节列表中的原始标题
                    )

                    # 记录实际下载时间（不包括等待延迟）
                    chapter_download_time = time.time() - chapter_start_time

                    # 计算下载速度（字/秒）
                    download_speed_chars_per_sec = word_count / chapter_download_time if chapter_download_time > 0 else 0

                    # 更新指数加权移动平均速度
                    if self.ewma_speed is None:
                        self.ewma_speed = download_speed_chars_per_sec
                    else:
                        self.ewma_speed = self.EWMA_ALPHA * download_speed_chars_per_sec + (1 - self.EWMA_ALPHA) * self.ewma_speed

                    success_count += 1
                    consecutive_failures = 0  # 重置连续失败计数器
                    self.log(f"  ✓ 成功 - {real_title} ({word_count} 字)", 'success')

                    # 根据源类型应用不同的延迟策略
                    if use_official_mode:
                        # 官网模式：使用智能延迟策略，模拟正常用户阅读速度
                        from config import calculate_smart_delay, get_download_speed
                        download_speed = get_download_speed()
                        delay = calculate_smart_delay(word_count, apply_delay=True)
                        if delay >= 0.5:
                            self.log(f"等待 {delay:.1f} 秒后继续... (速度: {download_speed:.1f}x, 字数: {word_count})", 'info')
                    else:
                        # 第三方模式：极短延迟（0.1-0.3秒）
                        from config import calculate_smart_delay
                        delay = calculate_smart_delay(word_count, apply_delay=False)
                        if delay >= 0.2:  # 只在延迟较长时才打印
                            self.log(f"等待 {delay:.1f} 秒后继续...", 'info')

                    # 记录下载记录（字数, 下载时间, 延迟时间）
                    self.recent_download_records.append((word_count, chapter_download_time, delay))
                    # 只保留最近N章的记录
                    if len(self.recent_download_records) > self.MAX_RECENT_TIMES:
                        self.recent_download_records.pop(0)

                    time.sleep(delay)

                    # 更新进度条
                    progress_percent = (success_count / total_to_download) * 100
                    elapsed_time = time.time() - download_start_time

                    # 计算预估剩余时间（改进的多层预估算法）
                    eta_str = ""
                    if self.recent_download_records and self.ewma_speed and self.ewma_speed > 0:
                        # 1. 计算最近N章的平均速度（字/秒）
                        recent_speeds = []
                        recent_delays = []
                        for word_count, download_time, delay_time in self.recent_download_records:
                            if download_time > 0:
                                recent_speeds.append(word_count / download_time)
                            recent_delays.append(delay_time)

                        # 使用中位数减少异常值影响
                        if recent_speeds:
                            sorted_speeds = sorted(recent_speeds)
                            median_speed = sorted_speeds[len(sorted_speeds) // 2]
                            avg_delay = sum(recent_delays) / len(recent_delays)

                            # 2. 综合预估：结合短期中位数速度和长期EWMA速度
                            # 随着下载进度增加，逐渐增加EWMA的权重
                            if success_count < 5:
                                # 初始阶段：主要使用短期速度
                                effective_speed = median_speed * 0.7 + self.ewma_speed * 0.3
                            elif success_count < 15:
                                # 过渡阶段：平衡使用
                                effective_speed = median_speed * 0.5 + self.ewma_speed * 0.5
                            else:
                                # 稳定阶段：主要使用EWMA
                                effective_speed = median_speed * 0.3 + self.ewma_speed * 0.7

                            # 3. 计算剩余时间（包含下载时间和延迟）
                            # 估算剩余总字数
                            remaining_chapters = total_to_download - success_count
                            estimated_remaining_words = remaining_chapters * (sum([r[0] for r in self.recent_download_records]) / len(self.recent_download_records))

                            # 下载时间 = 剩余字数 / 有效速度
                            download_time = estimated_remaining_words / effective_speed if effective_speed > 0 else 0

                            # 延迟时间 = 剩余章数 * 平均延迟
                            delay_time = remaining_chapters * avg_delay

                            eta_seconds = download_time + delay_time

                            # 格式化预估时间
                            if eta_seconds < 60:
                                eta_str = f"预估剩余时间: {int(eta_seconds)} 秒"
                            elif eta_seconds < 3600:
                                eta_str = f"预估剩余时间: {int(eta_seconds // 60)} 分 {int(eta_seconds % 60)} 秒"
                            else:
                                eta_str = f"预估剩余时间: {int(eta_seconds // 3600)} 小时 {int((eta_seconds % 3600) // 60)} 分"

                            # 添加调试信息（每10章显示一次）
                            if success_count % 10 == 0:
                                print(f"[调试ETA] 中位数速度: {median_speed:.1f}字/s, EWMA速度: {self.ewma_speed:.1f}字/s, 有效速度: {effective_speed:.1f}字/s, 平均延迟: {avg_delay:.2f}s, 剩余: {remaining_chapters}章, 预估: {eta_str}")

                    # 更新进度显示
                    self.root.after(0, lambda: self.progress_bar.config(value=progress_percent))
                    self.root.after(0, lambda: self.progress_label.config(text=f"下载进度: {success_count}/{total_to_download} 章 ({progress_percent:.1f}%)"))
                    self.root.after(0, lambda: self.eta_label.config(text=eta_str))
                else:
                    consecutive_failures += 1
                    # 记录失败的章节信息
                    self.failed_chapters.append((chapter_id, chapter_title, chapter_url))
                    self.log(f"  ✗ 失败", 'error')
                    
                    # 只有在官网模式下才触发人机验证
                    if use_official_mode and consecutive_failures >= max_consecutive_failures:
                        self.log(f"检测到连续{max_consecutive_failures}次下载失败，可能需要人机验证", 'warning')
                        
                        # 弹出提示而非打开浏览器
                        self.root.after(0, lambda: messagebox.showwarning(
                            '访问过多',
                            '访问过于频繁，可能触发了官网人机验证！\n\n'
                            '建议解决方案：\n'
                            '1. 等待一段时间（10-30分钟）后重试\n'
                            '2. 切换到第三方源模式（无需登录，无需字体解密）\n'
                            '3. 在设置中调整并发数或延迟时间\n\n'
                            '点击"确定"后，下载将自动停止。'
                        ))
                        
                        # 暂停下载，等待用户操作
                        self.log("下载已暂停：访问过于频繁，可能触发人机验证", 'warning')
                        self.log("请等待一段时间后重新下载", 'warning')
                        
                        # 退出下载线程
                        break
                    elif not use_official_mode and consecutive_failures >= max_consecutive_failures:
                        # API模式下的处理
                        self.log(f"检测到连续{max_consecutive_failures}次下载失败（API模式）", 'warning')
                        self.log("第三方API节点可能暂时不可用，程序会自动尝试切换节点", 'warning')
                        self.log("如果问题持续，请稍后重试或切换到官网模式", 'warning')
                        
                        # 等待一段时间再继续，避免触发频率限制
                        import random
                        wait_time = 5 + random.uniform(2, 5)
                        self.log(f"等待 {wait_time:.1f} 秒后继续...", 'warning')
                        time.sleep(wait_time)
                        
                        # 继续尝试下载下一个章节
                        continue

            self.log("=" * 60)
            if captcha_detected:
                self.log(f"下载暂停：等待用户完成人机验证", 'warning')
                self.log(f"已下载 {success_count} 个章节", 'info')
                # 更新进度显示
                progress_percent = (success_count / total_to_download) * 100
                self.root.after(0, lambda: self.progress_bar.config(value=progress_percent))
                self.root.after(0, lambda: self.progress_label.config(text=f"下载暂停: {success_count}/{total_to_download} 章 ({progress_percent:.1f}%)"))
                self.root.after(0, lambda: self.eta_label.config(text=""))
            else:
                self.log(f"下载完成！成功下载 {success_count}/{end_index - start_index} 个章节", 'success')
                # 更新进度条到100%
                self.root.after(0, lambda: self.progress_bar.config(value=100))
                self.root.after(0, lambda: self.progress_label.config(text=f"下载完成: {success_count}/{total_to_download} 章 (100%)"))
                self.root.after(0, lambda: self.eta_label.config(text=""))
            self.log("=" * 60)

            # 更新状态
            if success_count == end_index - start_index:
                self.downloader.db.update_novel_status(self.current_novel_id, '下载完成')
            else:
                self.downloader.db.update_novel_status(self.current_novel_id, '部分下载')

            # 如果不是因为人机验证暂停，才自动导出
            if not captcha_detected:
                # 自动导出
                export_path = self.root.after(0, lambda: self.export_path_entry.get().strip())
                export_path = self.export_path_entry.get().strip()

                if export_path:
                    self.log("正在自动导出...", 'info')
                    self.root.update()

                    try:
                        if self.downloader.export_to_txt(self.current_novel_id, export_path):
                            # 保存导出路径
                            from config import set_last_export_path
                            set_last_export_path(export_path)

                            self.log(f"导出成功: {export_path}", 'success')

                            # 复制到downloads文件夹（备份）- 静默执行，失败不影响用户体验
                            try:
                                import shutil
                                from config import DOWNLOAD_DIR
                                os.makedirs(DOWNLOAD_DIR, exist_ok=True)

                                backup_path = os.path.join(DOWNLOAD_DIR, os.path.basename(export_path))
                                shutil.copy2(export_path, backup_path)
                                # 备份成功时不显示消息，避免混淆
                            except:
                                # 备份失败时静默处理，不显示任何消息
                                pass
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
            # 重置下载状态
            self.is_downloading = False
            self.is_paused = False
            self.pause_event.set()
            
            # 隐藏下载控制按钮
            self.root.after(0, lambda: self.hide_download_controls())
            
            # 重置按钮状态
            self.root.after(0, lambda: self.download_button.config(state='normal'))
            self.root.after(0, lambda: self.export_button.config(state='normal'))

    def export_novel(self):
        """导出小说"""
        if not self.current_novel_id:
            messagebox.showwarning('提示', '请先获取小说信息')
            return

        title = self.novel_title.cget('text')

        # 获取上次导出路径作为初始目录
        from config import get_last_export_path
        last_export_path = get_last_export_path()
        initial_dir = os.path.dirname(last_export_path) if last_export_path else None

        file_path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')],
            initialfile=f"{title}.txt",
            initialdir=initial_dir
        )

        if file_path:
            if self.downloader.export_to_txt(self.current_novel_id, file_path):
                # 保存导出路径
                from config import set_last_export_path
                set_last_export_path(file_path)

                messagebox.showinfo('成功', '导出成功！')
                self.log(f"导出成功: {file_path}", 'success')
            else:
                messagebox.showerror('错误', '导出失败！')
                self.log(f"导出失败: {file_path}", 'error')
    
    def show_download_history(self):
        """显示下载历史"""
        DownloadHistoryDialog(self.root)

    def open_captcha_page(self, chapter_url=None):
        """打开人机验证页面（仅适用于官网模式）

        Args:
            chapter_url: 可选的章节URL，如果未提供则使用最后一个失败的章节URL
        """
        from config import SOURCE_OFFICIAL
        if self.download_mode != SOURCE_OFFICIAL:
            messagebox.showwarning(
                '提示',
                '人机验证功能仅适用于官网模式。\n\n'
                '当前使用的是第三方模式，无需人机验证。'
            )
            return
        
        # 如果没有提供URL，使用最后一个失败的章节URL
        if not chapter_url:
            if self.failed_chapters:
                chapter_url = self.failed_chapters[-1][2]  # 获取最后一个失败章节的URL
            elif self.current_chapter_url:
                chapter_url = self.current_chapter_url
            else:
                messagebox.showwarning('提示', '没有可验证的章节URL')
                return

        if not chapter_url:
            messagebox.showwarning('提示', '没有可验证的章节URL')
            return

        try:
            self.log(f"正在打开人机验证页面: {chapter_url}", 'info')
            webbrowser.open(chapter_url)
            messagebox.showinfo('人机验证', f'已打开浏览器窗口，请在页面中完成人机验证。\n\n完成后点击"确定"，然后重新点击"开始下载"继续下载。')
            self.log("用户完成人机验证后，请重新点击'开始下载'继续下载", 'info')
        except Exception as e:
            messagebox.showerror('错误', f'打开浏览器失败: {e}')
            self.log(f'打开浏览器失败: {e}', 'error')


def main():
    root = tk.Tk()
    app = NovelDownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()