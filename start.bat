@echo off
chcp 65001 >nul
title LFBot Launcher
cd /d "%~dp0"
set "PROJECT_DIR=%cd%"
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
set "BACKEND_PORT=8003"
set "FRONTEND_PORT=3000"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

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

REM ===== Check backend dependencies =====
"%VENV_PYTHON%" -c "import pip, fastapi, uvicorn, click" >nul 2>&1
if errorlevel 1 (
    echo [!] venv exists but dependencies are incomplete, repairing...
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

REM ===== Check ports =====
echo [2/4] Checking ports...
echo       Backend port %BACKEND_PORT%...
netstat -ano 2>nul | findstr ":%BACKEND_PORT%.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       Port %BACKEND_PORT% in use, cleaning...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%.*LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo       Cleaned
) else (
    echo       OK - port available
)

echo       Frontend port %FRONTEND_PORT%...
netstat -ano 2>nul | findstr ":%FRONTEND_PORT%.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       Port %FRONTEND_PORT% in use, cleaning...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT%.*LISTENING"') do (
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
"%VENV_PYTHON%" -c "import urllib.request; urllib.request.urlopen('http://localhost:%BACKEND_PORT%/api/health')" >nul 2>&1
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
echo   Backend:  http://localhost:%BACKEND_PORT%
echo   Frontend: http://localhost:%FRONTEND_PORT%
echo   API Docs: http://localhost:%BACKEND_PORT%/docs
echo.
echo   Close backend/frontend windows to stop
echo ========================================
echo.

set /p open_browser="Open browser? (Y/n): "
if /i not "%open_browser%"=="n" (
    start "" http://localhost:%FRONTEND_PORT%
)

echo.
echo Press any key to close this window...
pause >nul
