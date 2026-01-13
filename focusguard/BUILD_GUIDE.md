# FocusGuard v3.0 - Nuitka 打包指南

## 📦 打包前准备

### 1. 环境检查

```bash
# 检查 Python 版本（需要 3.10+）
python --version

# 检查依赖是否完整
pip list | grep -E "PyQt6|pywin32|psutil|pyautogui|aiohttp|tencentcloud"
```

### 2. 安装 Nuitka

```bash
pip install nuitka
```

### 3. 安装 C 编译器

**Windows**：
- 安装 Visual Studio Build Tools 或 Visual Studio Community
- 下载地址：https://visualstudio.microsoft.com/downloads/
- 选择 "Desktop development with C++" 工作负载

---

## 🔧 打包配置

### 1. 创建打包脚本

创建文件 `build.bat`：

```batch
@echo off
echo ====================================
echo FocusGuard v3.0 - Nuitka Build Script
echo ====================================
echo.

REM 设置变量
set ENTRY_POINT=focusguard\main.py
set OUTPUT_DIR=build
set DIST_DIR=dist

REM 清理旧的构建
echo [1/5] Cleaning old builds...
if exist %OUTPUT_DIR% rmdir /s /q %OUTPUT_DIR%
if exist %DIST_DIR% rmdir /s /q %DIST_DIR%
if exist *.spec del /q *.spec
echo Done.
echo.

REM 构建
echo [2/5] Building with Nuitka...
python -m nuitka ^
  --standalone ^
  --onefile ^
  --enable-plugin=pyqt6 ^
  --windows-disable-console ^
  --output-dir=%OUTPUT_DIR% ^
  --output=FocusGuard.exe ^
  --include-data-files=focusguard/config=focusguard/config ^
  --include-package=services ^
  --include-package=monitors ^
  --include-package=storage ^
  --include-package=ui ^
  --follow-imports ^
  --prefer-source-code ^
  %ENTRY_POINT%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [3/5] Copying additional files...
xcopy /e /i /y "focusguard\config" "%OUTPUT_DIR%\FocusGuard.dist\config\"
xcopy /e /i /y "focusguard\*.md" "%OUTPUT_DIR%\FocusGuard.dist\"

echo.
echo [4/5] Creating distribution...
if not exist %DIST_DIR% mkdir %DIST_DIR%
copy /y "%OUTPUT_DIR%\FocusGuard.dist\FocusGuard.exe" "%DIST_DIR%\"

echo.
echo [5/5] Build completed successfully!
echo.
echo Output: %DIST_DIR%\FocusGuard.exe
echo.
pause
```

### 2. 简化版打包命令（如果脚本失败）

直接在命令行运行：

```bash
python -m nuitka ^
  --standalone ^
  --onefile ^
  --enable-plugin=pyqt6 ^
  --windows-disable-console ^
  --output-dir=build ^
  --output=FocusGuard.exe ^
  --include-package=services ^
  --include-package=monitors ^
  --include-package=storage ^
  --include-package=ui ^
  focusguard/main.py
```

---

## ⚠️ 常见问题与解决方案

### 问题 1：ImportError: No module named 'xxx'

**原因**：Nuitka 没有包含某个依赖包

**解决方案**：
```bash
# 添加 --include-package 参数
python -m nuitka ^
  --include-package=missing_package ^
  --include-package=another_missing_package ^
  focusguard/main.py
```

### 问题 2：RecursionError: maximum recursion depth exceeded

**原因**：Nuitka 尝试递归分析所有导入

**解决方案**：
```bash
# 添加 --follow-imports 参数限制范围
python -m nuitka ^
  --follow-imports=standardlib ^
  --nofollow-import-to=tensorflow,torch ^
  focusguard/main.py
```

### 问题 3：Qt plugins not found

**原因**：PyQt6 插件路径不正确

**解决方案**：
```bash
# 添加 Qt 插件路径
python -m nuitka ^
  --enable-plugin=pyqt6 ^
  --include-data-files=PyQt6/Qt6/plugins/platforms/qwindows.dll=Qt6/plugins/platforms/ ^
  focusguard/main.py
```

### 问题 4：打包后文件体积过大（>200MB）

**原因**：Nuitka 默认包含所有依赖

**解决方案**：
```bash
# 排除不需要的包
python -m nuitka ^
  --nofollow-import-to=tkinter,matplotlib,numpy,pandas ^
  --include-package=PyQt6 ^
  --include-package=win32gui ^
  --include-package=psutil ^
  --include-package=pyautogui ^
  focusguard/main.py
```

---

## 🎯 优化建议

### 1. 减小文件体积

**使用 UPX 压缩**：

```bash
# 下载 UPX：https://upx.github.io/
upx --best --lzma build/FocusGuard.dist/FocusGuard.exe
```

**预期效果**：压缩 50-70%

### 2. 加快启动速度

```bash
# 使用 --lto=no（禁用链接时优化）
python -m nuitka ^
  --lto=no ^
  focusguard/main.py
```

### 3. 减少内存占用

```bash
# 限制内存使用
python -m nuitka ^
  --memory=2048 ^
  focusguard/main.py
```

---

## 📋 打包后验证清单

- [ ] 双击 FocusGuard.exe 能正常启动
- [ ] 主窗口显示正常
- [ ] 点击"开始监控"按钮无错误
- [ ] 窗口监控正常工作
- [ ] Chrome 历史读取正常
- [ ] LLM API 调用成功
- [ ] 干预对话框弹出正常
- [ ] CLOSE_WINDOW 功能正常
- [ ] MINIMIZE_WINDOW 功能正常
- [ ] CLOSE_TAB 功能正常
- [ ] 日志输出正常

---

## 🔐 发布准备

### 1. 创建安装程序（可选）

使用 Inno Setup 创建安装向导：

```iss
; FocusGuard.iss
[Setup]
AppName=FocusGuard
AppVersion=3.0
DefaultDirName={pf}\FocusGuard
DefaultGroupName=FocusGuard
OutputBaseFilename=FocusGuard-Setup-3.0
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\FocusGuard.exe"; DestDir: "{app}"
Source: "focusguard\config\*"; DestDir: "{app}\config"

[Icons]
Name: "{group}\FocusGuard"; Filename: "{app}\FocusGuard.exe"
Name: "{commondesktop}\FocusGuard"; Filename: "{app}\FocusGuard.exe"

[Run]
Filename: "{app}\FocusGuard.exe"; Description: "Launch FocusGuard"; Flags: nowait postinstall skipifsilent
```

### 2. 测试安装程序

```bash
# 编译安装脚本
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FocusGuard.iss
```

### 3. 创建发布包

```
release/
├── FocusGuard-Setup-3.0.exe
├── FocusGuard.exe (standalone)
├── README.txt
└── CHANGELOG.txt
```

---

## 📝 版本信息

**当前版本**：v3.0
**构建日期**：2026-01-13
**Python 版本**：3.10+
**目标平台**：Windows 10/11

---

## 🐛 已知打包问题

### 1. pyautogui 依赖

**问题**：pyautogui 依赖多个子模块（pymsgbox, pyscreeze, pygetwindow 等）

**解决方案**：
```bash
# 确保所有依赖都包含
pip install pyautogui[all]
python -m nuitka ^
  --include-package=pyautogui ^
  --include-package=pymsgbox ^
  --include-package=pyscreeze ^
  --include-package=pygetwindow ^
  --include-package=pyrect ^
  focusguard/main.py
```

### 2. 配置文件缺失

**问题**：打包后找不到 config 目录

**解决方案**：
```bash
# 使用 --include-data-files
python -m nuitka ^
  --include-data-files=focusguard/config=focusguard/config ^
  focusguard/main.py
```

### 3. 数据库路径问题

**问题**：打包后 `~/.focusguard` 路径可能不正确

**解决方案**：已在代码中处理
```python
import os
HOME = os.path.expanduser("~")
DB_DIR = os.path.join(HOME, ".focusguard")
os.makedirs(DB_DIR, exist_ok=True)
```

---

## 🚀 快速开始

### 最简单的打包命令（推荐）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 打包
python build.bat

# 3. 测试
dist\FocusGuard.exe
```

---

## 📞 技术支持

如果遇到问题：

1. 检查 Nuitka 版本：`python -m nuitka --version`
2. 查看完整日志：`python -m nuitka --verbose ...`
3. 参考官方文档：https://nuitka.net/doc/user-manual.html

---

**最后更新**：2026-01-13
