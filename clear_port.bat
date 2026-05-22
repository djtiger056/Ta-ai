@echo off
chcp 65001 >nul
echo ========================================
echo     LFBot 端口清理和启动工具
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  建议以管理员身份运行此脚本
    echo.
)

echo [1/3] 检查8003端口占用情况...
netstat -ano | findstr :8003

echo.
echo [2/3] 清理占用的进程...

REM 查找并停止占用8003端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8003 ^| findstr LISTENING') do (
    echo    停止进程 PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo [3/3] 等待端口释放...
timeout /t 3 /nobreak >nul

REM 最终检查
echo.
echo 清理后的端口状态:
netstat -ano | findstr :8003

echo.
echo ========================================
echo ✅ 端口清理完成！
echo.
echo 现在可以运行以下命令启动后端:
echo    python run.py
echo.
echo 或者运行启动脚本:
echo    oncestart.bat  ^(中文版^)
echo    start.bat      ^(英文版^)
echo ========================================
echo.
pause
