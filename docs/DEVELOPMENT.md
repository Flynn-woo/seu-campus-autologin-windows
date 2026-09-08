# 开发与发布

## 本地开发

需要 Windows 10/11、Python 3.10–3.12 和 Microsoft Edge：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --cov=seu_autologin --cov-report=term-missing
```

程序调用系统 Edge，不需要运行 `playwright install`。

Windows 安装脚本使用 UTF-8 BOM 和 CRLF，CMD 使用 UTF-8 无 BOM 和 CRLF，以兼容系统自带 Windows PowerShell 5.1。

安装逻辑回归验证（使用真实 CIM 触发器构造、模拟任务注册，临时快捷方式写入测试目录）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_autostart.ps1
pwsh -NoProfile -File tests\test_autostart.ps1
```

## 构建

```powershell
powershell -NoProfile -File .\scripts\build.ps1 -PythonExe .\.venv\Scripts\python.exe
```

构建结果位于 `release`，采用 PyInstaller `onedir`，并生成 ZIP 和 SHA256。

`packaging/windows.spec` 在同一目录生成交互式和无窗口入口，共享依赖。任务计划使用 `SEUCampusAutoLoginOSSBackground.exe`，不依赖额外安装 Python、VBS 或用户的源代码目录。重新构建会保留历史版本 ZIP。
