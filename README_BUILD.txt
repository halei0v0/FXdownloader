打包为 Windows 可执行文件（EXE）说明

先决条件：
- 在 Windows 上已安装 Python 3.8+ 并加入 PATH
- 推荐使用虚拟环境

快速步骤（在 cmd.exe 中运行）：

1) 进入项目目录：

cd /d "f:\Github项目\FXdownloader"

2) 运行打包脚本（默认无控制台窗口）：

build_exe.bat

如果希望打包时保留控制台窗口（便于调试），请传参：

build_exe.bat console

脚本行为说明：
- 脚本会创建/复用 `.venv` 虚拟环境，安装 `requirements.txt` 中的依赖，然后安装 `pyinstaller`。
- 使用 PyInstaller 将 `main.py` 打包为单文件可执行（默认 `--onefile`，无控制台窗口）。
- 脚本会自动将 `templates/`、`static/`、`locales.py`、`config.py` 包含进可执行体；如果存在 `WebView2` 文件夹也会一并包含。
- 脚本包含一组常见 `--hidden-import`（如 `webview`, `aiohttp`, `ebooklib` 等）。如果打包报缺少模块的错误，请根据提示在脚本中添加对应的 `--hidden-import`。

常见问题与排查：
- 打包失败并提示某模块找不到：将模块名添加到 `HIDDEN_IMPORTS`（脚本顶部）或在运行 pyinstaller 时追加 `--hidden-import=包名`。
- 运行 exe 时缺少资源（模板/静态文件）：确认 `--add-data` 指定的路径是否正确。Windows 下使用分号分隔 `源;目标`（脚本中已配置）。
- WebView 无法启动：请在目标机器安装 WebView2 运行时，或将 WebView2 runtime 文件夹放到项目根并重试（脚本会把该文件夹包含到 exe）。

进阶：
- 如果单文件模式产生问题，可改为目录模式（去掉 `--onefile`），方便排查：编辑 `build_exe.bat` 中 `set PYI_OPTS`，删除 `--onefile`。
- 若需要自定义图标：在 pyinstaller 命令中加入 `--icon=youricon.ico`。

如果你希望我在当前环境尝试执行构建并把完整输出贴上来，请回复 “现在构建”，我将尝试运行并收集 stdout/stderr（注意：远端运行受限于执行环境）。
