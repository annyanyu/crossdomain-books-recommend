@echo off
chcp 65001 >nul
echo ============================================================
echo 图书推荐系统 - 启动脚本
echo ============================================================
echo.

cd /d "%~dp0..\backend"

echo 步骤1: 初始化数据库...
python init_database.py
if %errorlevel% neq 0 (
    echo 数据库初始化失败！
    pause
    exit /b 1
)

echo.
echo 步骤2: 启动服务...
echo 服务将在 http://localhost:5000 运行
echo 按 Ctrl+C 停止服务
echo.
python app.py

pause
