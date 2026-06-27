@echo off
setlocal

cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ================================================
echo  Standardizing Vietnamese Addresses
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found.
        echo Please install Python 3.11+ from https://www.python.org/downloads/
        echo Make sure "Add python.exe to PATH" is checked during install.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Creating .env from .env.example...
    copy ".env.example" ".env" >nul
)

if not exist ".streamlit" (
    mkdir ".streamlit"
)

if not exist ".streamlit\config.toml" (
    echo Creating Streamlit config...
    > ".streamlit\config.toml" echo [browser]
    >> ".streamlit\config.toml" echo gatherUsageStats = false
    >> ".streamlit\config.toml" echo.
    >> ".streamlit\config.toml" echo [server]
    >> ".streamlit\config.toml" echo headless = true
)

echo.
echo Starting app at http://127.0.0.1:8501
echo Keep this window open while using the app.
echo.

start "" "http://127.0.0.1:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false --server.headless true

pause
