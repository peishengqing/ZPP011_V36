@echo off
chcp 65001 >nul
title ZPP011 一键打包（含自动备份）
cd /d "%~dp0"
echo 启动打包脚本...
python "%~dp0build_with_backup.py"
pause
