@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo  AI Calling Agent - First-time Setup
echo ================================================

where py >nul 2>nul || (echo [ERROR] Python launcher ^(py^) not found.& exit /b 1)
where node >nul 2>nul || (echo [ERROR] Node.js not found.& exit /b 1)
where npm >nul 2>nul || (echo [ERROR] npm not found.& exit /b 1)

if not exist backend\.env copy backend\.env.example backend\.env >nul
if not exist frontend\.env.local copy frontend\.env.local.example frontend\.env.local >nul

if not exist backend\venv (
  echo [1/4] Creating Python virtual environment...
  py -3.12 -m venv backend\venv 2>nul || py -m venv backend\venv
)

echo [2/4] Installing backend dependencies...
call backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt || exit /b 1

echo [3/4] Installing frontend dependencies...
pushd frontend
call npm install || (popd & exit /b 1)
popd

echo [4/4] Preparing PostgreSQL...
where docker >nul 2>nul
if %errorlevel%==0 (
  docker compose up -d postgres
) else (
  echo Docker not found. Use local PostgreSQL and create database ai_calling_agent.
)

echo.
echo Setup complete.
echo NEXT: run CONFIGURE_OPENROUTER_WINDOWS.ps1 once, then START_APP_WINDOWS.bat
echo.
pause
