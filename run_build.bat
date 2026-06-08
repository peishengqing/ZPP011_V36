@echo off
echo 开始打包...
cd /d "E:\zpp011_dev\模块化脚本"
python -u build_pyside6.py > build_output.txt 2>&1
echo 打包完成，退出代码: %ERRORLEVEL%
pause
