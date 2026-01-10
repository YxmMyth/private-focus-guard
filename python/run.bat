@echo off
chcp 65001 >nul 2>&1
cd /d %~dp0
echo ======================================
echo Starting FocusGuard...
echo ======================================
python ui/main_window.py
pause
