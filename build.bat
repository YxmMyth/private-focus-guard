@echo off
echo ====================================
echo FocusGuard v3.0 - Production Build
echo ====================================
echo.

REM 设置变量
set ENTRY_POINT=focusguard\main.py
set OUTPUT_DIR=build
set DIST_DIR=dist

REM 清理旧的构建
echo [1/6] Cleaning old builds...
if exist %OUTPUT_DIR% rmdir /s /q %OUTPUT_DIR%
if exist %DIST_DIR% rmdir /s /q %DIST_DIR%
if exist bundled_config.env del /q bundled_config.env
echo Done.
echo.

REM 复制配置文件为bundled_config.env
echo [2/6] Preparing bundled configuration...
copy /y "focusguard\.env" "bundled_config.env"
echo Done.
echo.

REM 构建
echo [3/6] Building with Nuitka...
python -m nuitka ^
  --standalone ^
  --onefile ^
  --enable-plugin=pyqt6 ^
  --windows-disable-console ^
  --output-dir=%OUTPUT_DIR% ^
  --output=FocusGuard.exe ^
  --include-data-files=bundled_config.env=bundled_config.env ^
  --include-package=services ^
  --include-package=monitors ^
  --include-package=storage ^
  --include-package=ui ^
  --include-package=pyautogui ^
  --include-package=pymsgbox ^
  --include-package=pyscreeze ^
  --include-package=pygetwindow ^
  --include-package=pyrect ^
  --include-package=pyperclip ^
  --include-package=pytweening ^
  --follow-imports ^
  --prefer-source-code ^
  --assume-yes-for-downloads ^
  %ENTRY_POINT%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [4/6] Copying bundled config to dist...
if not exist %DIST_DIR% mkdir %DIST_DIR%
copy /y "bundled_config.env" "%DIST_DIR%\"

echo.
echo [5/6] Creating distribution...
copy /y "%OUTPUT_DIR%\FocusGuard.dist\FocusGuard.exe" "%DIST_DIR%\"

echo.
echo [6/6] Creating README...
(
echo FocusGuard v3.0 - Production Build
echo.
echo 使用说明：
echo 1. 双击 FocusGuard.exe 启动程序
echo 2. 点击"开始监控"按钮开始监控
echo 3. 点击"设置"按钮可自定义参数
echo 4. 配置文件保存在 %%USERPROFILE%%\.focusguard\
echo.
echo 注意事项：
echo - 首次运行会自动创建配置目录和数据库
echo - 内置混元API密钥，无需手动配置
echo - 监控运行时最小化到系统托盘
echo.
echo 技术支持：https://github.com/your-repo
) > "%DIST_DIR%\README.txt"

echo.
echo ====================================
echo Build completed successfully!
echo.
echo Output: %DIST_DIR%\FocusGuard.exe
echo.
echo File size:
dir "%DIST_DIR%\FocusGuard.exe" | find "FocusGuard.exe"
echo.
pause
