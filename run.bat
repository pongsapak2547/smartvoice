@echo off
setlocal
title SmartVoice Launcher
cd /d "%~dp0"

echo.
echo ========================================
echo   SmartVoice - one-click launcher
echo ========================================
echo.

set "PY_CMD="
set "PY311_INSTALLER_VERSION=3.11.9"
set "PY311_INSTALLER_URL=https://www.python.org/ftp/python/%PY311_INSTALLER_VERSION%/python-%PY311_INSTALLER_VERSION%-amd64.exe"
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 --version >nul 2>nul && set "PY_CMD=py -3.12"
    if not defined PY_CMD py -3.11 --version >nul 2>nul && set "PY_CMD=py -3.11"
    if not defined PY_CMD py -3.10 --version >nul 2>nul && set "PY_CMD=py -3.10"
)

if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PY_CMD if exist "%ProgramFiles%\Python311\python.exe" set PY_CMD="%ProgramFiles%\Python311\python.exe"
if not defined PY_CMD if exist "%ProgramFiles%\Python310\python.exe" set PY_CMD="%ProgramFiles%\Python310\python.exe"

set "PATH_PY_VERSION="
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%A in ('call python -c "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))"' ) do set "PATH_PY_VERSION=%%A"
        if "%PATH_PY_VERSION%"=="3.10" set "PY_CMD=python"
        if "%PATH_PY_VERSION%"=="3.11" set "PY_CMD=python"
        if "%PATH_PY_VERSION%"=="3.12" set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo Python 3.10, 3.11 or 3.12 was not found.
    echo SmartVoice can install Python 3.11 for this Windows user.
    echo.
    choice /c YN /m "Install Python 3.11 now"
    if errorlevel 2 (
        echo.
        echo Install Python 3.11 from https://www.python.org/downloads/ and run this launcher again.
        pause
        exit /b 1
    ) else (
        echo.
        echo Downloading and installing Python 3.11...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$installer = Join-Path $env:TEMP 'python-%PY311_INSTALLER_VERSION%-amd64.exe'; Invoke-WebRequest -Uri '%PY311_INSTALLER_URL%' -OutFile $installer; Start-Process -FilePath $installer -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0' -Wait"
        if errorlevel 1 goto error
        where py >nul 2>nul
        if not errorlevel 1 py -3.11 --version >nul 2>nul && set "PY_CMD=py -3.11"
        if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        if not defined PY_CMD (
            echo Python 3.11 installation finished, but the launcher could not find it yet.
            echo Restart this launcher and try again.
            pause
            exit /b 1
        )
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto error
)

set "VENV_PY=.venv\Scripts\python.exe"

if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    ) else (
        echo .env.example was not found. Continuing with built-in defaults.
    )
)

echo Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto error

echo Installing SmartVoice dependencies. This can take a while on first run...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto error

echo Installing SmartVoice package...
"%VENV_PY%" -m pip install -e . --no-deps
if errorlevel 1 goto error

for /f "delims=" %%A in ('call "%VENV_PY%" -c "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))"' ) do set "PY_VERSION=%%A"
echo.
echo Opening SmartVoice at http://localhost:8501
echo Keep this window open while using the app.
echo.
start "" "http://localhost:8501"
"%VENV_PY%" -m streamlit run Home.py --server.port 8501 --server.headless true
goto end

:error
echo.
echo SmartVoice could not start. Check the error above.
echo If this is the first run, confirm internet access is available and retry any installer prompts.
pause
exit /b 1

:end
pause
