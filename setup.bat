@echo off
echo ========================================
echo    LFBot Virtual Environment Setup
echo ========================================
echo.

REM Check if Python is installed
echo [1/5] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
python -c "import sys; print('Python version: ' + sys.version.split()[0])" 2>&1

REM Check if Python version is sufficient
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python version too low, need Python 3.8 or higher.
    python --version
    pause
    exit /b 1
)

REM Check if already in virtual environment
echo.
echo [2/5] Checking current environment...
python -c "import sys; print('Current environment: ' + ('Virtual' if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 'System'))" 2>&1

REM Create virtual environment
echo.
echo [3/5] Creating virtual environment...
if exist "venv\" (
    echo WARNING: Virtual environment already exists, recreating...
    rmdir /s /q venv 2>nul
)

python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    echo Please ensure you have sufficient permissions, or manually run: python -m venv venv
    pause
    exit /b 1
)
echo Virtual environment created successfully.

REM Activate virtual environment and install dependencies
echo.
echo [4/5] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    echo Please manually run: venv\Scripts\activate
    pause
    exit /b 1
)

echo Virtual environment activated.
echo Installing dependencies...

REM Upgrade pip
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
set PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple
echo Using PyPI mirror: %PYPI_MIRROR%
pip install -r requirements.txt -i %PYPI_MIRROR% --timeout 120 --retries 3
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    echo Please check requirements.txt file or network connection.
    pause
    exit /b 1
)

REM Check key dependencies
echo.
echo [5/5] Verifying installation...
python -c "import fastapi, uvicorn, pydantic, aiohttp, loguru; print('Core dependencies: FastAPI, Uvicorn, Pydantic, aiohttp, loguru')" 2>&1
python -c "try: import openai; print('OpenAI compatible library'); except: print('OpenAI library not installed (optional)')" 2>&1

echo.
echo ========================================
echo    Virtual Environment Setup Complete!
echo ========================================
echo.
echo Usage Instructions:
echo.
echo 1. Activate virtual environment:
echo    venv\Scripts\activate
echo.
echo 2. Run project:
echo    python run.py
echo.
echo 3. Start frontend (new terminal):
echo    cd frontend
echo    npm run dev
echo.
echo 4. Access application:
echo    - Frontend: http://localhost:3000
echo    - Backend: http://localhost:8003
echo    - API docs: http://localhost:8003/docs
echo.
echo 5. Exit virtual environment:
echo    deactivate
echo.
echo Notes:
echo - You need to activate the virtual environment every time you open a new terminal
echo - You can use the run.py script, it will check the virtual environment status
echo - To reinstall dependencies: pip install -r requirements.txt
echo.

REM Ask if user wants to run the project immediately
echo.
set /p run_now="Run project now? (y/N): "
if /i "%run_now%"=="y" (
    echo.
    echo Starting LFBot...
    python run.py
) else (
    echo.
    echo Please manually run: python run.py
)

pause
