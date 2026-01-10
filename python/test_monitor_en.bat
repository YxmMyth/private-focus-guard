@echo off
chcp 65001 >nul 2>&1
cd /d %~dp0
echo ========================================
echo Monitoring Test
echo ========================================
echo.
echo This test will:
echo 1. Detect current window 5 times
echo 2. Wait 3 seconds between each detection
echo 3. Save to database automatically
echo.
echo Please switch windows during the test!
echo ========================================
echo.
python test_monitoring.py
echo.
echo ========================================
echo Test completed!
echo ========================================
pause
