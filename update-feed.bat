@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  Roma Daily - updating feed
echo ========================================
echo.
".venv\Scripts\python.exe" pipeline.py --fresh --skip-fixtures
if errorlevel 1 goto failed
echo.
".venv\Scripts\python.exe" -c "import json; d=json.load(open('data/articles.json', encoding='utf-8')); print('Generated at (UTC):', d.get('generated_at'))"
echo.
echo Update complete.
echo Now run start-site.bat, then press Ctrl+F5 in the browser.
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Update failed. Check the message above.
echo.
pause
exit /b 1
