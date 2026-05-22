@echo off
echo 正在检查并清理8003端口占用...

REM 查找占用8003端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8003 ^| findstr LISTENING') do (
    echo 找到占用8003端口的进程 PID: %%a
    echo 正在停止进程...
    taskkill /PID %%a /F
)

echo 等待端口释放...
timeout /t 2 /nobreak >nul

REM 再次检查端口状态
netstat -ano | findstr :8003

echo 端口清理完成，现在可以启动后端服务了。
pause
