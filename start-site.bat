@echo off
chcp 65001 >nul
cd /d "%~dp0"
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo Server is already running. Opening a fresh page...
  start "" "http://localhost:8000/?v=%RANDOM%%RANDOM%"
  exit /b 0
)
echo Starting local preview at http://localhost:8000
echo Close this window or press Ctrl+C to stop the server.
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000/?v=%RANDOM%%RANDOM%"
".venv\Scripts\python.exe" -m http.server 8000 --directory site
pause
