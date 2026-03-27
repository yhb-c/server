#!/bin/bash
# 重启WebSocket服务器脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "重启WebSocket服务器"
echo "======================================"

# 1. 停止现有服务
echo -e "\n${YELLOW}[1/3]${NC} 停止现有WebSocket服务..."
if pgrep -f "start_websocket_server" > /dev/null; then
    pkill -f "start_websocket_server"
    sleep 2
    
    if pgrep -f "start_websocket_server" > /dev/null; then
        echo -e "${RED}✗${NC} 服务停止失败，强制终止..."
        pkill -9 -f "start_websocket_server"
        sleep 1
    fi
    echo -e "${GREEN}✓${NC} 服务已停止"
else
    echo -e "${YELLOW}→${NC} 服务未运行"
fi

# 2. 激活conda环境
echo -e "\n${YELLOW}[2/3]${NC} 激活conda环境..."
source ~/anaconda3/bin/activate liquid
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} conda环境激活成功"
else
    echo -e "${RED}✗${NC} conda环境激活失败"
    exit 1
fi

# 3. 启动服务
echo -e "\n${YELLOW}[3/3]${NC} 启动WebSocket服务..."
cd /home/lqj/liquid/server

# 设置海康SDK库路径
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH

nohup python websocket/start_websocket_server.py > inference.log 2>&1 &
sleep 3

if pgrep -f "start_websocket_server" > /dev/null; then
    WS_PID=$(pgrep -f "start_websocket_server" | head -1)
    echo -e "${GREEN}✓${NC} WebSocket服务启动成功 (PID: $WS_PID, 端口: 8085)"
else
    echo -e "${RED}✗${NC} WebSocket服务启动失败"
    echo -e "\n查看日志:"
    tail -20 /home/lqj/liquid/server/inference.log
    exit 1
fi

echo -e "\n${GREEN}重启完成！${NC}"
echo "服务地址: ws://192.168.0.121:8085"
echo ""
