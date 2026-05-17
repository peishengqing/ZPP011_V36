@echo off
chcp 936 >nul
title ZPP011 一键打包工具
echo ========================================
echo   ZPP011 偏差分析器 - 一键打包
echo ========================================
echo.

cd /d "%~dp0"

echo 正在清理旧构建文件...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo 正在执行打包脚本...
py build_exe.py

echo.
echo ========================================
echo 打包完成！请查看 dist 目录下的 exe 文件。
echo ========================================
pause