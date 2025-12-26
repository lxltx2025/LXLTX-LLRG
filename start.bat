@echo off
chcp 65001 >nul
echo ==========================================
echo     综述生成系统启动脚本
echo ==========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [信息] 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖是否已安装
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 安装依赖包...
    pip install -r requirements.txt
)

REM 检查Ollama服务
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] Ollama服务未运行，请先启动Ollama
    echo [提示] 在另一个终端运行: ollama serve
    echo.
)

echo [信息] 启动Web服务...
echo [信息] 访问地址: http://127.0.0.1:5000
echo [信息] 按 Ctrl+C 停止服务
echo ==========================================
python app.py

pause