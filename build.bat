@echo off
chcp 65001 >nul

:: ---------- 1. 读取配置 ----------
for /f "tokens=2 delims=:" %%a in ('python -c "import json; cfg=json.load(open('config/version.json','r',encoding='utf-8')); print(cfg.get('app_name','智能助手'))"') do set APP_NAME=%%a
for /f "tokens=2 delims=:" %%a in ('python -c "import json; cfg=json.load(open('config/version.json','r',encoding='utf-8')); print(cfg.get('version','v1.0'))"') do set APP_VER=%%a

:: 去除首尾空格
set APP_NAME=%APP_NAME: =%
set APP_VER=%APP_VER: =%

:: ---------- 2. 显示标题 ----------
echo ================================================
echo %APP_NAME% %APP_VER% - 一键打包
echo ================================================
echo.

:: ---------- 3. 执行打包 ----------
python build.py

echo.
echo ================================================
echo 打包完成！请查看 dist 文件夹
echo ================================================
pause
