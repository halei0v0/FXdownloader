# FXdownloader

<img src="https://cdn.jsdelivr.net/gh/halei0v0/warehouse@imgmd//imgmd/20260714171411871.png" alt="1" style="zoom:10%;" />

多源小说下载工具，支持蚂蚁文学、顶点小说、笔下文学、铅笔小说、海棠文学、番茄小说六大源，多源自动搜索、分工加速下载、失败自动重试。

## 功能特点

- **多源聚合搜索** - 输入书名即可同时搜索六大源，无需手动切换，自动给出所有可用结果
- **多源分工下载** - 主源下载失败时自动切换其他源重试，按章节标题跨源匹配
- **自动补缺重试** - 检测缺失/失败章节并自动用其他源重新下载
- **章节去重排序** - 自动剔除章节列表开头倒序的"最新章节"，正确排序
- **现代化 WebUI** - 基于 pywebview + HTML/CSS/JS 的深色主题界面
- **字体解密** - 自动解密番茄小说的字体加密内容
- **批量下载** - 支持选择章节范围批量下载，并发加速
- **EXE 打包** - 支持 PyInstaller 一键打包为独立可执行文件

## 支持的小说源

| 源 | 域名 | 特点 |
|---|---|---|
| 蚂蚁文学 | mayiwsk.com | 无需登录，支持搜索 |
| 顶点小说 | 23wxx.net | 无需登录，og:meta 完整 |
| 笔下文学 | bxwxber.cc | 无需登录，GBK 编码 |
| 铅笔小说 | 23qb.net | 无需登录，支持搜索，章节列表在独立 catalog 页 |
| 海棠文学 | htwenxe.com | 杰奇 CMS，部分章节需登录 |
| 番茄小说 | fanqienovel.com | 需登录，支持字体解密 |

## 环境要求

- Python 3.8+
- Windows / Linux / macOS
- Edge 浏览器驱动（仅番茄官网登录需要）

## 安装步骤

1. 克隆项目：
```bash
git clone https://github.com/halei0v0/FXdownloader.git
cd FXdownloader
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 安装 Scrapling（可选，用于多源爬取，推荐 editable 安装）：
```bash
pip install -e Scrapling-main
```

## 使用方法

### WebUI 模式（推荐）

**Windows：** 双击 `启动WebUI.bat`

**命令行：**
```bash
python web_ui/app.py
```

打开后自动启动本地服务器并弹出窗口。界面操作：
1. 顶部选择源（搜索时会自动多源选取）
2. 输入书名或小说 URL，点击搜索
3. 搜索结果中每条标注来源源，点击选择
4. 获取章节列表后，勾选要下载的章节
5. 点击下载，等待完成

### GUI 模式（旧版 tkinter）

```bash
python gui.py
```

### 命令行模式

```bash
# 通过 URL 下载
python main.py download https://fanqienovel.com/page/711914860

# 通过小说 ID 下载
python main.py download 711914860

# 下载指定章节范围
python main.py download 711914860 --start 1 --end 50

# 搜索小说
python main.py search 诡秘之主

# 列出已下载的小说
python main.py list

# 导出已下载的小说
python main.py export 711914860
```

### 打包为 EXE

**Windows：** 双击 `打包.bat`

**命令行：**
```bash
pyinstaller FXdownloader.spec
```

打包后的可执行文件位于 `dist/FXdownloader.exe`。

## 项目结构

```
FXdownloader/
├── web_ui/
│   ├── app.py              # WebUI 后端（pywebview 桥接）
│   └── index.html          # WebUI 前端（HTML/CSS/JS）
├── sources/
│   ├── __init__.py         # 源注册表
│   ├── base.py             # 源抽象基类
│   ├── biquge_source.py    # 蚂蚁文学源
│   ├── generic_source.py   # 顶点/笔下/铅笔/海棠 可配置源
│   ├── fanqie_source.py    # 番茄小说源
│   ├── bing_search.py      # Bing 搜索（补充搜索方式）
│   └── multi_source.py     # 多源搜索 + 分工下载管理
├── config.py               # 配置管理
├── database.py             # SQLite 数据库操作
├── downloader.py           # 下载器核心
├── spider.py               # 番茄小说爬虫
├── font_decrypt.py         # 字体解密
├── selenium_login.py        # Selenium 自动登录
├── gui.py                  # 旧版 tkinter GUI
├── main.py                 # 命令行入口
├── FXdownloader.spec       # PyInstaller 打包配置
├── Scrapling-main/         # Scrapling 爬虫库源码
├── 启动WebUI.bat           # WebUI 启动脚本
├── 启动.bat                # 旧版 GUI 启动脚本
├── 启动命令行.bat          # 命令行启动脚本
├── 打包.bat                # 打包脚本
└── requirements.txt        # 依赖列表
```

## 依赖项

- **requests** - HTTP 请求库
- **beautifulsoup4** - HTML 解析
- **lxml** - XML/HTML 解析引擎
- **pywebview** - WebUI 窗口容器
- **scrapling** - 高级爬虫框架（多源爬取）
- **curl_cffi** - TLS 指纹模拟（scrapling 依赖）
- **selenium** - 浏览器自动化（番茄登录）
- **fonttools** - 字体处理
- **Pillow** - 图像处理
- **ddddocr** - 验证码识别
- **fake-useragent** - 随机 User-Agent

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 免责声明

本工具仅供个人学习和研究使用，请勿用于商业用途。使用本工具下载的内容版权归原作者所有，请在下载后 24 小时内删除。

## 注意事项

- 请遵守相关法律法规，尊重版权
- 请勿频繁请求，避免对服务器造成压力
- 番茄官网模式下载需要登录，请使用 Selenium 自动登录或手动添加 Cookie
- 番茄官网可能出现人机验证，触发后需等待几小时恢复
- 如需使用自动登录，请下载对应版本的 msedgedriver.exe
- 多源搜索依赖各源自身搜索接口，部分源搜索不可用时会影响结果数量

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

halei0v0

## 更新日志

### v2.0

- 新增 5 个小说源：蚂蚁文学、顶点小说、笔下文学、铅笔小说、海棠文学
- 多源聚合搜索：输入书名同时搜索所有源，无需切换模式
- 多源分工下载：主源失败自动切换其他源，按章节标题跨源匹配重试
- 章节列表去重排序：自动剔除开头倒序的"最新章节"
- 全新 WebUI：pywebview + HTML/CSS/JS 深色主题界面
- 修复打包问题：scrapling、browserforge、apify_fingerprint_datapoints 数据文件完整打包
- 修复 Bing 搜索：改用各源自身搜索为主，Bing 作为补充

### v1.0.6

- 大幅提高第三方下载模式的下载速度
- 10 章并发下载
- 优化官网模式下载时间预估

### v1.0.5

- 第三方下载模式已可用
- 自动选择 API
- 多 API 支持

### v1.0.4

- 修复登录问题，Cookie 验证从 5 个提高到 24 个
- 下载进度条和预估时间
- 设置界面改进，添加"恢复默认设置"按钮
- 下载速度调整（0.5x-2.0x）
- 界面尺寸增大
- 字体解码修复

### v1.0.3

- 动态章节下载速度以减少触发人机验证
- 断点续传功能

### v1.0.2

- 下载历史显示数据库中的小说信息
- 批量导出/下载功能
- 优化下载历史管理界面

### v1.0.1

- 增加账户登录功能
- 支持 SVIP 账号下载全本小说

### v1.0

- 初始版本发布
- 支持 GUI 和 CLI 两种模式
- 内置字体解密机制
