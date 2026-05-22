@echo off
chcp 936 >nul
title LFBot Launcher
cd /d "%~dp0"
set "PROJECT_DIR=%cd%"
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"

echo ========================================
echo       LFBot AI - One Click Start
echo ========================================
echo.

REM ===== Check venv =====
if not exist "%VENV_PYTHON%" (
    echo [!] venv not found, running setup...
    echo.
    call setup.bat
    if errorlevel 1 (
        echo [X] Setup failed
        pause
        exit /b 1
    )
)

REM ===== Activate venv =====
echo [1/4] Activating venv...
call "%PROJECT_DIR%\venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [X] Failed to activate venv
    pause
    exit /b 1
)
echo       OK

REM ===== Check port =====
echo [2/4] Checking port 8003...
netstat -ano 2>nul | findstr ":8003.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       Port 8003 in use, cleaning...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8003.*LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo       Cleaned
) else (
    echo       OK - port available
)

REM ===== Start backend =====
echo [3/4] Starting backend...
start "LFBot-Backend" /D "%PROJECT_DIR%" "%VENV_PYTHON%" run.py

echo       Waiting for backend...
set /a retries=0
:wait_backend
timeout /t 2 /nobreak >nul
set /a retries+=1
"%VENV_PYTHON%" -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/api/health')" >nul 2>&1
if not errorlevel 1 (
    echo       OK - backend ready
    goto backend_ok
)
if %retries% lss 15 goto wait_backend
echo       [!] Backend start timeout - check backend window
:backend_ok

REM ===== Start frontend =====
echo [4/4] Starting frontend...
if not exist "%PROJECT_DIR%\frontend\node_modules\" (
    echo       First run - installing frontend deps...
    pushd "%PROJECT_DIR%\frontend"
    call npm install
    popd
)
start "LFBot-Frontend" /D "%PROJECT_DIR%\frontend" cmd /k npm run dev

echo.
echo ========================================
echo           All services started!
echo ========================================
echo.
echo   Backend:  http://localhost:8003
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8003/docs
echo.
echo   Close backend/frontend windows to stop
echo ========================================
echo.

set /p open_browser="Open browser? (Y/n): "
if /i not "%open_browser%"=="n" (
    start "" http://localhost:3000
)

echo.
echo Press any key to close this window...
pause >nul
