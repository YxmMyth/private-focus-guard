@echo off
chcp 65001 >nul 2>&1
cd /d %~dp0
echo ====================================
echo FocusGuard
echo ====================================
echo.
python ui/main_window.py
echo.
echo ====================================
echo Application closed
echo ====================================
pause
