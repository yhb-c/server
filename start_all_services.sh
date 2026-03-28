#!/bin/bash
# 启动所有服务（API + WebSocket推理服务）

echo "=========================================="
echo "液位检测系统 - 启动所有服务"
echo "=========================================="

# 激活conda环境
echo "[1/4] 激活conda环境: liquid"
source ~/anaconda3/bin/activate liquid

# 检查环境
echo "[2/4] 检查环境..."
echo "  Python: $(python --version)"
echo "  Go: $(go version)"

# 设置环境变量
export PYTHONPATH="/home/lqj/liquid/server:$PYTHONPATH"
export LD_LIBRARY_PATH="/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH"

# 创建日志目录
mkdir -p /home/lqj/liquid/logs

# 启动API服务（后台运行）
echo "[3/4] 启动API服务 (端口8084)..."
cd /home/lqj/liquid/api
nohup ./liquid-api > /home/lqj/liquid/logs/api_service.log 2>&1 &
API_PID=$!
echo "  API服务已启动，PID: $API_PID"
echo "  日志文件: /home/lqj/liquid/logs/api_service.log"

# 等待API服务启动
sleep 2

# 启动WebSocket推理服务（后台运行）
echo "[4/4] 启动WebSocket推理服务 (端口8085)..."
cd /home/lqj/liquid/server
nohup python start_websocket_server.py > /home/lqj/liquid/logs/websocket_service.log 2>&1 &
WS_PID=$!
echo "  WebSocket服务已启动，PID: $WS_PID"
echo "  日志文件: /home/lqj/liquid/logs/websocket_service.log"

# 等待服务启动
sleep 3

# 检查服务状态
echo ""
echo "=========================================="
echo "服务状态检查"
echo "=========================================="

# 检查API服务
if ps -p $API_PID > /dev/null 2>&1; then
    echo "[OK] API服务运行中 (PID: $API_PID)"
    if netstat -tuln | grep -q ":8084 "; then
        echo "     端口8084已监听"
    else
        echo "     警告: 端口8084未监听"
    fi
else
    echo "[失败] API服务启动失败"
fi

# 检查WebSocket服务
if ps -p $WS_PID > /dev/null 2>&1; then
    echo "[OK] WebSocket服务运行中 (PID: $WS_PID)"
    if netstat -tuln | grep -q ":8085 "; then
        echo "     端口8085已监听"
    else
        echo "     警告: 端口8085未监听"
    fi
else
    echo "[失败] WebSocket服务启动失败"
fi

echo ""
echo "=========================================="
echo "服务访问地址"
echo "=========================================="
echo "API服务: http://192.168.0.121:8084"
echo "WebSocket服务: ws://192.168.0.121:8085"
echo ""
echo "查看日志:"
echo "  API日志: tail -f /home/lqj/liquid/logs/api_service.log"
echo "  WebSocket日志: tail -f /home/lqj/liquid/logs/websocket_service.log"
echo ""
echo "停止服务:"
echo "  bash /home/lqj/liquid/stop_all_services.sh"
echo "=========================================="
