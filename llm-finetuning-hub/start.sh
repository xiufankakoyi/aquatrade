#!/bin/bash

echo "========================================"
echo "LLM Fine-tuning Hub 启动脚本"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 Node.js，请先安装 Node.js"
    exit 1
fi

echo "[1/4] 检查 Python 依赖..."
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || echo "[警告] 部分依赖安装失败，继续运行..."

echo "[2/4] 检查 Node.js 依赖..."
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
else
    echo "前端依赖已存在"
fi

echo "[3/4] 启动后端 API 服务器..."
python api_server.py &
API_PID=$!
sleep 3

echo "[4/4] 启动前端开发服务器..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "✓ 所有服务已启动："
echo "  - 后端 API: http://localhost:5001"
echo "  - 前端应用: http://localhost:3000"
echo "========================================"
echo ""
echo "提示: 按 Ctrl+C 停止所有服务"
echo ""

# 等待用户中断
trap "kill $API_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

