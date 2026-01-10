@echo off
title FocusGuard - 实时监控
color 0A

echo.
echo ============================================================
echo         FocusGuard - 实时窗口监控
echo ============================================================
echo.
echo 监控已启动！每3秒检查一次窗口切换
echo.
echo 现在你可以:
echo   1. 打开不同的应用程序
echo   2. 切换浏览器标签页
echo   3. 查看下方实时显示的窗口信息
echo.
echo 按 Ctrl+C 停止监控
echo.
echo ============================================================
echo.

cd python
python quick_test.py

pause
