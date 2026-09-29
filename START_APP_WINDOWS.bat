@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo  Starting AI Calling Agent
echo ================================================

if not exist backend\.env (
  echo [ERROR] backend\.env missing. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
if not exist backend\venv\Scripts\python.exe (
  echo [ERROR] Backend venv missing. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
if not exist frontend\node_modules (
  echo [ERROR] Frontend dependencies missing. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)

where docker >nul 2>nul
if %errorlevel%==0 docker compose up -d postgres >nul 2>nul

start "AI Calling Agent - FastAPI" cmd /k "cd /d ""%~dp0backend"" && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
start "AI Calling Agent - Next.js" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo Backend:  http://localhost:8000/docs
echo AI test:  http://localhost:8000/api/ai/test
echo Frontend: http://localhost:3000
echo.
echo Wait until both terminal windows say they are ready, then open the Frontend URL.
pause
