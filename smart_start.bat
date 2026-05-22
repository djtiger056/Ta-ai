@echo off
chcp 65001 >nul
title LFBot 后端启动
cd /d "%~dp0"

echo ========================================
echo     LFBot 后端启动（仅后端）
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo [!] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

echo [1/3] 激活虚拟环境...
call venv\Scripts\activate.bat
echo      OK

echo [2/3] 清理端口...
netstat -ano 2>nul | findstr ":8003.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8003.*LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo      已清理端口 8003
) else (
    echo      OK - 端口可用
)

echo [3/3] 启动后端...
echo.

python run.py

echo.
echo ========================================
echo LFBot 已停止运行
echo ========================================
pause
