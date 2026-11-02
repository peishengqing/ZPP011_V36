chcp 65001 >nul
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================
echo    正在上传 ZPP011 V36
echo ==============================

git add .
git commit -m "auto update"
git push

echo.
echo 上传完成！
pause