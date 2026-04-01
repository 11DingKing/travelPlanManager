@echo off
chcp 65001 >nul
cd /d "%~dp0backend"

echo 启动旅行计划管理器...
python day.py

pause
