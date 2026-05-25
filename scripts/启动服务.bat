@echo off
chcp 65001 >nul
echo ============================================================
echo 图书推荐系统 - 启动脚本
echo ============================================================
echo.
echo 数据库: douban_books @ 10.67.53.94
echo.

cd /d "%~dp0..\backend"

echo 正在启动服务...
echo 服务将在 http://localhost:5000 运行
echo 按 Ctrl+C 停止服务
echo.
python app.py

pause
