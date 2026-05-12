@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================
echo    正在同步 GitHub 仓库
echo ==============================

git pull

if errorlevel 1 (
    echo.
    echo ❌ 同步失败，请检查是否有冲突
    pause
    exit /b
)

echo.
echo ✅ 同步完成！本地已更新为最新代码
pause