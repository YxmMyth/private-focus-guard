@echo off
REM FocusGuard Python - 快速测试脚本

echo ================================================
echo   FocusGuard - 运行监控测试
echo ================================================
echo.
echo 💡 提示:
echo    - 切换到不同的应用程序窗口
echo    - 观察控制台输出
echo    - 按 Ctrl+C 停止监控
echo.
echo ================================================
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [错误] 程序运行失败！
    echo.
    echo 可能的原因:
    echo 1. 依赖未安装 - 运行 setup.bat
    echo 2. Python版本过低 - 需要 Python 3.10+
    echo 3. 缺少系统依赖 - 需要安装 Visual C++ Build Tools
    echo.
    pause
)
