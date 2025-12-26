#!/bin/bash

echo "=========================================="
echo "     综述生成系统启动脚本"
echo "=========================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖是否已安装
if ! pip show flask &> /dev/null; then
    echo "[信息] 安装依赖包..."
    pip install -r requirements.txt
fi

# 检查Ollama服务
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "[警告] Ollama服务未运行，请先启动Ollama"
    echo "[提示] 在另一个终端运行: ollama serve"
    echo ""
fi

echo "[信息] 启动Web服务..."
echo "[信息] 访问地址: http://127.0.0.1:5000"
echo "[信息] 按 Ctrl+C 停止服务"
echo "=========================================="
python app.py