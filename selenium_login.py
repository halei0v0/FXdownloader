# -*- coding: utf-8 -*-
"""
Selenium自动化登录模块
"""
import os
import sys
import json
import time
import re
import ssl
import urllib.request
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import COOKIE_FILE, save_cookies


class SeleniumLogin:
    """Selenium自动化登录类"""

    def __init__(self):
        self.driver = None
        self.login_url = "https://fanqienovel.com/main/writer/login"
        
        # 获取脚本/程序所在目录
        if getattr(sys, 'frozen', False):
            # 打包模式：使用临时解压目录
            self.base_dir = sys._MEIPASS
        else:
            # 开发模式：使用脚本所在目录
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.driver_dir = os.path.join(self.base_dir, "webdrivers")
        self.driver_path = os.path.join(self.driver_dir, "msedgedriver.exe")
        
        # 检查多个可能的驱动位置
        possible_paths = [
            self.driver_path,  # webdrivers 目录
            os.path.join(self.base_dir, "msedgedriver.exe"),  # 项目根目录或打包根目录
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.driver_path = path
                print(f"找到 EdgeDriver: {path}")
                break

    def get_edge_version(self):
        """获取 Edge 浏览器版本"""
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        
        for path in edge_paths:
            if os.path.exists(path):
                try:
                    # 使用 powershell 获取文件版本信息
                    import subprocess
                    cmd = f'(Get-Item "{path}").VersionInfo.FileVersion'
                    result = subprocess.run(
                        ["powershell", "-Command", cmd],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        print(f"找到 Edge 浏览器版本: {version}")
                        return version
                except Exception as e:
                    print(f"获取 Edge 版本失败: {e}")
                    continue
        
        return None

    def download_edgedriver(self, version):
        """下载对应版本的 EdgeDriver"""
        try:
            # 创建驱动目录
            os.makedirs(self.driver_dir, exist_ok=True)
            
            # 如果驱动已存在，先删除
            if os.path.exists(self.driver_path):
                try:
                    os.remove(self.driver_path)
                    print("删除旧的驱动文件")
                except Exception as e:
                    print(f"删除旧驱动失败: {e}")
            
            # 生成多个可能的下载 URL
            major_version = version.split('.')[0]
            minor_version = version.split('.')[1]
            patch_version = version.split('.')[2]
            
            download_urls = [
                f"https://msedgedriver.azureedge.net/{major_version}.{minor_version}.{patch_version}/edgedriver_win64.zip",
                f"https://msedgedriver.azureedge.net/{major_version}.{minor_version}.{patch_version}.{version.split('.')[3]}/edgedriver_win64.zip",
                f"https://msedgedriver.azureedge.net/{major_version}.{minor_version}/edgedriver_win64.zip",
            ]
            
            print(f"正在下载 EdgeDriver")
            print(f"目标版本: {version}")
            print(f"主版本号: {major_version}.{minor_version}.{patch_version}")
            
            # 创建临时目录
            temp_dir = os.path.join(self.driver_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            zip_path = os.path.join(temp_dir, "edgedriver.zip")
            
            # 优先使用 PowerShell 脚本下载（更可靠）
            ps_script = os.path.join(base_dir, "手动下载驱动.ps1")
            if os.path.exists(ps_script):
                print("\n尝试使用 PowerShell 下载驱动...")
                try:
                    import subprocess
                    result = subprocess.run(
                        ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if os.path.exists(self.driver_path):
                        print("使用 PowerShell 下载成功！")
                        return True
                    else:
                        print(f"PowerShell 下载失败: {result.stderr}")
                except Exception as e:
                    print(f"使用 PowerShell 下载失败: {e}")
            
            # 尝试使用 curl 脚本
            curl_script = os.path.join(base_dir, "下载驱动.bat")
            if os.path.exists(curl_script):
                print("\n尝试使用 curl 下载驱动...")
                try:
                    import subprocess
                    result = subprocess.run(
                        [curl_script],
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if os.path.exists(self.driver_path):
                        print("使用 curl 下载成功！")
                        return True
                    else:
                        print(f"curl 下载失败: {result.stderr}")
                except Exception as e:
                    print(f"使用 curl 下载失败: {e}")
            
            # 尝试多个下载源
            success = False
            for i, url in enumerate(download_urls):
                try:
                    print(f"\n尝试下载源 {i+1}/{len(download_urls)}: {url}")
                    
                    # 下载文件（忽略 SSL 证书验证）
                    context = ssl._create_unverified_context()
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    # 使用 urlopen 而不是 urlretrieve
                    with urllib.request.urlopen(req, context=context, timeout=60) as response:
                        with open(zip_path, 'wb') as f:
                            f.write(response.read())
                    print("下载完成")
                    success = True
                    break
                except Exception as e:
                    print(f"下载源 {i+1} 失败: {e}")
                    if os.path.exists(zip_path):
                        try:
                            os.remove(zip_path)
                        except:
                            pass
                    continue
            
            if not success:
                print("\n所有下载源都失败了")
                return False
            
            # 解压文件
            import zipfile
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                print("解压完成")
            except Exception as e:
                print(f"解压失败: {e}")
                return False
            
            # 查找并移动驱动文件
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == "msedgedriver.exe":
                        src = os.path.join(root, file)
                        try:
                            os.rename(src, self.driver_path)
                            print(f"驱动已安装到: {self.driver_path}")
                            return True
                        except Exception as e:
                            print(f"移动驱动文件失败: {e}")
                            try:
                                import shutil
                                shutil.copy2(src, self.driver_path)
                                print(f"驱动已复制到: {self.driver_path}")
                                return True
                            except Exception as e2:
                                print(f"复制驱动文件也失败: {e2}")
            
            print("未找到 msedgedriver.exe 文件")
            return False
            
        except Exception as e:
            print(f"下载驱动时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def init_driver(self, headless=False):
        """初始化浏览器驱动"""
        edge_options = Options()
        
        if headless:
            edge_options.add_argument('--headless')
        
        # 常用配置
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        # 禁用图片加载，提高速度
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.managed_default_content_settings.javascript': 1
        }
        edge_options.add_experimental_option('prefs', prefs)
        
        # 查找 Edge 浏览器
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        
        edge_binary = None
        for path in edge_paths:
            if os.path.exists(path):
                edge_binary = path
                edge_options.binary_location = edge_binary
                print(f"找到 Edge 浏览器: {edge_binary}")
                break
        
        if not edge_binary:
            raise Exception("未找到 Edge 浏览器，请确保已安装 Microsoft Edge 浏览器")
        
        # 获取 Edge 版本
        edge_version = self.get_edge_version()
        if not edge_version:
            raise Exception("无法获取 Edge 浏览器版本")
        
        # 检查驱动是否存在
        if not os.path.exists(self.driver_path):
            print("EdgeDriver 未找到，正在自动下载...")
            if not self.download_edgedriver(edge_version):
                major_version = edge_version.split('.')[0]
                minor_version = edge_version.split('.')[1]
                patch_version = edge_version.split('.')[2]
                
                error_msg = f"""
========================================
EdgeDriver 自动下载失败
========================================

您的 Edge 浏览器版本: {edge_version}

请手动下载 EdgeDriver：

方法 1: 官方网站下载
-------------------
1. 访问: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
2. 找到版本 {major_version}.{minor_version}.{patch_version}
3. 下载 "edgedriver_win64.zip"
4. 解压后将 msedgedriver.exe 放到以下目录:
   {self.driver_dir}

方法 2: 直接下载链接
-------------------
访问以下链接下载:
https://msedgedriver.azureedge.net/{major_version}.{minor_version}.{patch_version}/edgedriver_win64.zip

========================================
"""
                raise Exception(error_msg)
        
        # 检查驱动版本是否匹配
        try:
            import subprocess
            result = subprocess.run(
                [self.driver_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                driver_version = result.stdout.strip()
                print(f"EdgeDriver 版本: {driver_version}")
                
                # 提取驱动的主版本号
                driver_major = driver_version.split()[3].split('.')[0]
                edge_major = edge_version.split('.')[0]
                
                if driver_major != edge_major:
                    print(f"版本不匹配！")
                    print(f"  Edge 浏览器: {edge_version}")
                    print(f"  EdgeDriver: {driver_version}")
                    print(f"正在重新下载匹配版本的驱动...")
                    
                    # 删除旧驱动并重新下载
                    try:
                        os.remove(self.driver_path)
                        print("已删除旧驱动")
                    except Exception as e:
                        print(f"删除旧驱动失败: {e}")
                    
                    # 重新检查驱动路径
                    possible_paths = [
                        os.path.join(self.base_dir, "webdrivers", "msedgedriver.exe"),
                        os.path.join(self.base_dir, "msedgedriver.exe"),
                    ]
                    
                    self.driver_path = None
                    for path in possible_paths:
                        if os.path.exists(path):
                            self.driver_path = path
                            break
                    
                    if not self.driver_path:
                        print("驱动已删除，开始下载新驱动...")
                        if not self.download_edgedriver(edge_version):
                            raise Exception(f"无法下载匹配的 EdgeDriver 版本 {edge_version}")
                        
                        # 重新设置驱动路径
                        for path in possible_paths:
                            if os.path.exists(path):
                                self.driver_path = path
                                break
                        else:
                            raise Exception(f"驱动下载后未找到文件")
        except Exception as e:
            print(f"检查驱动版本时出错: {e}")
            print("继续使用现有驱动...")
        
        # 使用本地驱动
        print(f"使用本地驱动: {self.driver_path}")
        service = Service(executable_path=self.driver_path)
        
        try:
            self.driver = webdriver.Edge(service=service, options=edge_options)
            print("Edge 浏览器启动成功")
        except Exception as e:
            error_msg = str(e)
            print(f"启动 Edge 浏览器失败: {e}")
            
            # 检查是否是版本不匹配错误或驱动找不到错误
            if "version" in error_msg.lower() or "145" in error_msg or "144" in error_msg or "Unable to locate" in error_msg:
                print("\n检测到驱动问题，尝试重新下载驱动...")
                
                # 删除旧驱动
                try:
                    if os.path.exists(self.driver_path):
                        os.remove(self.driver_path)
                        print("已删除旧驱动")
                except Exception as e2:
                    print(f"删除旧驱动失败: {e2}")
                
                # 重新下载
                if self.download_edgedriver(edge_version):
                    print("驱动下载成功，重新启动浏览器...")
                    
                    # 重新检测驱动路径
                    possible_paths = [
                        os.path.join(self.base_dir, "webdrivers", "msedgedriver.exe"),
                        os.path.join(self.base_dir, "msedgedriver.exe"),
                    ]
                    
                    self.driver_path = None
                    for path in possible_paths:
                        if os.path.exists(path):
                            self.driver_path = path
                            break
                    
                    if not self.driver_path:
                        raise Exception("驱动下载后未找到文件")
                    
                    try:
                        service = Service(executable_path=self.driver_path)
                        self.driver = webdriver.Edge(service=service, options=edge_options)
                        print("Edge 浏览器启动成功")
                    except Exception as e3:
                        raise Exception(f"Edge 浏览器启动失败（重试后）: {e3}\n\n驱动文件可能已损坏，请手动下载正确版本的 EdgeDriver ({edge_version})")
                else:
                    raise Exception(f"Edge 浏览器启动失败且无法重新下载驱动: {e}\n\n请手动下载正确版本的 EdgeDriver ({edge_version})")
            else:
                raise Exception(f"Edge 浏览器启动失败: {e}\n\n驱动文件可能已损坏，请删除 {self.driver_path} 后重新下载")
        
        # 隐藏自动化特征
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        return self.driver

    def get_cookies(self):
        """获取当前页面的所有Cookie"""
        cookies = {}
        try:
            cookie_list = self.driver.get_cookies()
            for cookie in cookie_list:
                cookies[cookie['name']] = cookie['value']
            
            print(f"获取到 {len(cookies)} 个Cookie")
            return cookies
        except Exception as e:
            print(f"获取Cookie失败: {e}")
            return {}

    def save_cookies_to_file(self, cookies):
        """保存Cookie到文件"""
        return save_cookies(cookies)

    def check_login_status(self):
        """检查是否已登录"""
        cookies = self.get_cookies()
        
        # 检查关键Cookie - 必须有 sessionid 且值不为空
        required_cookies = ['sessionid', 'passport_csrf_token', 'passport_assist_user']
        
        # 检查是否有至少一个关键 Cookie，并且其值有效
        has_valid_cookie = False
        for cookie_name in required_cookies:
            if cookie_name in cookies:
                cookie_value = cookies[cookie_name]
                # 检查 Cookie 值是否有效（长度大于 10，且不包含空格）
                if cookie_value and len(cookie_value) > 10 and ' ' not in cookie_value:
                    has_valid_cookie = True
                    break
        
        # 如果有有效 Cookie，还需要检查 Cookie 数量（登录后通常会有更多 Cookie）
        if has_valid_cookie and len(cookies) >= 5:
            return True, cookies
        
        return False, cookies

    def wait_for_login(self, timeout=300):
        """等待用户完成登录"""
        print("请在浏览器中完成登录...")
        print("登录方式：手机号验证码、微信、QQ等")
        print(f"最长等待时间：{timeout}秒")
        print("提示：登录完成后请稍等几秒...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查是否已登录
            is_logged_in, cookies = self.check_login_status()
            
            if is_logged_in:
                print("检测到登录成功！")
                return True, cookies
            
            time.sleep(2)
        
        print("登录超时！")
        return False, None

    def login_with_selenium(self, headless=False):
        """
        使用Selenium自动登录

        Args:
            headless: 是否使用无头模式（不显示浏览器窗口）

        Returns:
            tuple: (是否成功, cookies字典)
        """
        try:
            # 初始化浏览器
            self.init_driver(headless=headless)
            
            # 访问登录页面
            print(f"正在打开登录页面: {self.login_url}")
            self.driver.get(self.login_url)
            
            # 等待用户完成登录
            success, cookies = self.wait_for_login()
            
            if success and cookies:
                # 保存Cookie
                if self.save_cookies_to_file(cookies):
                    print("Cookie已保存成功！")
                    return True, cookies
                else:
                    print("Cookie保存失败！")
                    return False, cookies
            else:
                return False, None
                
        except Exception as e:
            print(f"登录过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False, None
        
        finally:
            # 关闭浏览器
            if self.driver:
                self.driver.quit()

    def login_with_phone(self, phone=None):
        """
        使用手机号自动登录（可选功能）
        
        Args:
            phone: 手机号码，如果为None则需要用户手动输入

        Returns:
            tuple: (是否成功, cookies字典)
        """
        try:
            self.init_driver(headless=False)
            self.driver.get(self.login_url)
            
            # 等待页面加载
            wait = WebDriverWait(self.driver, 10)
            
            # 找到手机号输入框
            try:
                phone_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='手机']"))
                )
                
                if not phone:
                    phone = input("请输入手机号: ")
                
                phone_input.send_keys(phone)
                
                # 找到获取验证码按钮
                code_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button:contains('获取验证码')"))
                )
                code_button.click()
                
                code = input("请输入验证码: ")
                
                # 找到验证码输入框
                code_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='验证码']"))
                )
                code_input.send_keys(code)
                
                # 找到登录按钮
                login_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button:contains('登录')"))
                )
                login_button.click()
                
                # 等待登录完成
                success, cookies = self.wait_for_login(timeout=60)
                
                if success:
                    self.save_cookies_to_file(cookies)
                
                return success, cookies
                
            except Exception as e:
                print(f"自动登录失败: {e}")
                return False, None
                
        finally:
            if self.driver:
                self.driver.quit()


def login_with_selenium(headless=False):
    """
    使用Selenium登录的便捷函数

    Args:
        headless: 是否使用无头模式

    Returns:
        bool: 是否登录成功
    """
    selenium_login = SeleniumLogin()
    success, cookies = selenium_login.login_with_selenium(headless=headless)
    return success


def login_with_phone(phone=None):
    """
    使用手机号登录的便捷函数

    Args:
        phone: 手机号码

    Returns:
        bool: 是否登录成功
    """
    selenium_login = SeleniumLogin()
    success, cookies = selenium_login.login_with_phone(phone=phone)
    return success


if __name__ == "__main__":
    print("=" * 60)
    print("番茄小说Selenium自动登录")
    print("=" * 60)
    
    print("\n请选择登录方式:")
    print("1. 浏览器手动登录（推荐）")
    print("2. 手机号自动登录")
    
    choice = input("\n请输入选择 (1/2): ").strip()
    
    if choice == "1":
        print("\n正在启动浏览器...")
        success = login_with_selenium(headless=False)
        
        if success:
            print("\n✓ 登录成功！Cookie已保存。")
        else:
            print("\n✗ 登录失败！")
    
    elif choice == "2":
        phone = input("\n请输入手机号: ").strip()
        print("\n正在启动浏览器...")
        success = login_with_phone(phone=phone)
        
        if success:
            print("\n✓ 登录成功！Cookie已保存。")
        else:
            print("\n✗ 登录失败！")
    
    else:
        print("\n无效的选择！")
    
    input("\n按回车键退出...")