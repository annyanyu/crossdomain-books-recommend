@echo off
chcp 65001 >nul
echo ============================================================
echo Book Recommendation System - Starting...
echo ============================================================
echo.
echo Database: douban_books @ 10.67.53.94
echo.

cd /d "%~dp0..\backend"

echo Starting Flask server...
echo Server will run at http://localhost:5000
echo Press Ctrl+C to stop
echo.
python app.py

pause
