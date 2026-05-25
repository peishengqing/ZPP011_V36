@echo off
echo =============================================
echo ZPP011 开发环境一键配置脚本
echo =============================================

echo [INFO] 正在创建虚拟环境...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] 创建虚拟环境失败，请检查Python安装
    pause
    exit /b 1
)

echo [INFO] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [INFO] 安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [ERROR] 安装依赖失败，请检查网络
    pause
    exit /b 1
)

echo [INFO] 配置Git提交模板...
git config --local commit.template .gitmessage.txt

echo =============================================
echo [OK] 开发环境配置完成！
echo [INFO] 运行命令：venv\Scripts\activate && python main.py
echo =============================================
pause
