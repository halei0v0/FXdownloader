# FXdownloader

一个简单易用的番茄小说平台小说下载工具，支持图形界面和命令行两种操作方式。

**注意！！**下载**全部章节**需要**番茄小说网站的SVIP账号**，否则只能下载官网可视部分！！

## 功能特点

- 🎨 **现代化GUI界面** - 美观的图形界面，操作简单直观
- 💻 **命令行支持** - 支持命令行操作，方便脚本集成
- 📥 **批量章节下载** - 支持下载指定章节范围的小说
- 📝 **导出TXT** - 支持将下载的小说导出为TXT格式
- 🔐 **字体解密** - 自动解密番茄小说的字体加密内容
- 💾 **本地数据库** - 使用SQLite数据库存储下载内容
- 📚 **下载历史管理** - 查看和管理所有已下载的小说记录
- 📦 **批量下载** - 支持批量导出多个小说到指定目录
- 🌐 **智能重试** - 内置请求重试机制，提高下载成功率

## 环境要求

- Python 3.8+
- Windows/Linux/macOS

## 安装步骤

1. 克隆或下载本项目到本地：
```bash
git clone https://github.com/halei0v0/FXdownloader.git
cd FXdownloader
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

### 图形界面模式

**Windows用户：**

- 双击运行 `启动.bat` 文件
- 下载[release版本](https://github.com/halei0v0/FXdownloader/releases)

**其他系统：**
```bash
python gui.py
```

### 命令行模式

**Windows用户：**
- 双击运行 `启动命令行.bat` 文件

**其他系统：**
```bash
python main.py [命令] [参数]
```

#### 可用命令

**下载小说**
```bash
# 通过URL下载
python main.py download https://fanqienovel.com/page/711914860

# 通过小说ID下载
python main.py download 711914860

# 下载指定章节范围
python main.py download 711914860 --start 1 --end 50

# 下载并自动导出
python main.py download 711914860 --export
```

**搜索小说**
```bash
python main.py search 诡秘之主
```

**列出已下载的小说**
```bash
python main.py list
```

**导出已下载的小说**
```bash
python main.py export 711914860
```

**删除小说**
```bash
python main.py delete 711914860
```

## 项目结构

```
FXdownloader/
├── config.py           # 配置文件
├── database.py         # 数据库操作模块
├── downloader.py       # 下载器核心模块
├── font_decrypt.py     # 字体解密模块
├── gui.py             # 图形界面模块
├── main.py            # 命令行入口
├── spider.py          # 爬虫模块
├── requirements.txt   # 依赖列表
├── 启动.bat           # Windows GUI启动脚本
├── 启动命令行.bat     # Windows CLI启动脚本
├── 更新依赖.bat       # Windows依赖更新脚本
├── downloads/         # 下载文件存储目录
├── database/          # 数据库文件目录
└── font_cache/        # 字体缓存目录
```

## 依赖项

- requests - HTTP请求库
- beautifulsoup4 - HTML解析
- lxml - XML/HTML解析引擎
- fake-useragent - 随机User-Agent
- fonttools - 字体处理
- Pillow - 图像处理
- ddddocr - 验证码识别
- parsel - 网页解析

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 免责声明

本工具仅供个人学习和研究使用，请勿用于商业用途。使用本工具下载的内容版权归原作者所有，请在下载后24小时内删除。

## 注意事项

- 请遵守相关法律法规，尊重版权
- 请勿频繁请求，避免对服务器造成压力
- 本工具不保证100%可用性，番茄小说可能会更新反爬机制
- 建议合理设置请求间隔，避免IP被封禁
- 如果要使用自动识别登录，一点更要下载对应版本的msedgedriver.exe

## 贡献

欢迎提交 Issue 和 Pull Request！【虽然作为新手的我并不会用 Pull Request(●ˇ∀ˇ●)】

## 作者

halei0v0

## 更新日志

### v1.0.6

1. 大幅提高第三方下载模式的下载速度

- ✅10章并发下载
- ✅优化官网模式下载时间预估

###  v1.0.5 

1. 第三方下载模式已可用

- ✅自动选择API

- ✅多API支持

下载需要耐心等待！

软件后台在进行API测试

### v1.0.4

1. 修复登录问题 (selenium_login.py)

- ✅将Cookie验证从5个提高到24个

- ✅登录成功时显示"已加载 24 个 Cookie"消息

- ✅只有在显示24个Cookie后才关闭网页

1. 下载进度条和预估时间 (gui.py)

- ✅在日志区域上方添加了进度条

- ✅显示下载进度百分比

- ✅实时计算并显示预估剩余时间

- ✅下载完成后进度条自动更新到100%

3. 设置界面改进 (gui.py)

- ✅添加了"恢复默认设置"按钮

- ✅可以一键恢复所有设置到默认值

4. 下载速度调整 (config.py + gui.py)

- ✅添加了下载速度配置功能（0.5x-2.0x）

- ✅提供了滑块控件调整速度

- ✅添加了详细的说明文字，包括人机验证警告

- ✅默认速度为1.0x，推荐设置为0.8x-1.2x

5. 界面尺寸增大 (gui.py)

- ✅主窗口：850x700 → 950x800

- ✅设置对话框：450x750 → 500x800

6. 字体解码修复 (font_decrypt.py)

- ✅修复了"火l"应为"火山"的解码错误

- ✅将58420码点的映射从'l'改为'山'

### v1.0.3

- ✅动态的章节下载速度以减少触发人机验证的可能【如果出现连续下载失败那就是触发了官网的人机验证，等待几个小时即可恢复】
- ✅断点续传功能

### v1.0.2

- ✅下载历史显示数据库中的小说信息
- ✅批量导出功能，批量下载功能，支持一次性导出多个小说
- ✅优化了下载历史管理界面

### v1.0.1
- ✅增加账户登录功能
- ✅支持SVIP账号下载全本小说

### v1.0

- ✅初始版本发布
- ✅支持GUI和CLI两种模式
- ✅内置字体解密机制