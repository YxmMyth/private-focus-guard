@echo off
REM FocusGuard Python 安装脚本

echo ================================================
echo   FocusGuard Python - 依赖安装
echo ================================================
echo.

REM 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

echo [1/3] 检测到Python版本:
python --version
echo.

REM 升级pip
echo [2/3] 升级pip...
python -m pip install --upgrade pip
echo.

REM 安装依赖
echo [3/3] 安装项目依赖...
echo 这可能需要几分钟...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败！
    echo 可能的解决方案:
    echo 1. 检查网络连接
    echo 2. 使用国内镜像: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
    pause
    exit /b 1
)
echo.

echo ================================================
echo   ✅ 安装完成！
echo ================================================
echo.
echo 运行测试程序:
echo   python main.py
echo.
echo 或者运行测试:
echo   python monitors\windows_monitor.py
echo.
pause
