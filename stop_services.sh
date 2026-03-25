#!/bin/bash
# 液位检测系统服务停止脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "液位检测系统 - 服务停止脚本"
echo "======================================"

# 停止Go API服务
echo -e "\n${YELLOW}[1/2]${NC} 停止Go API服务..."
if pgrep -f "liquid-api" > /dev/null; then
    pkill -f "liquid-api"
    sleep 1
    if pgrep -f "liquid-api" > /dev/null; then
        echo -e "${RED}✗${NC} Go API服务停止失败，尝试强制停止..."
        pkill -9 -f "liquid-api"
    fi
    echo -e "${GREEN}✓${NC} Go API服务已停止"
else
    echo -e "${YELLOW}→${NC} Go API服务未运行"
fi

# 停止Python推理服务
echo -e "\n${YELLOW}[2/2]${NC} 停止Python推理服务..."
if pgrep -f "websocket.ws_server" > /dev/null; then
    pkill -f "websocket.ws_server"
    sleep 1
    if pgrep -f "websocket.ws_server" > /dev/null; then
        echo -e "${RED}✗${NC} Python推理服务停止失败，尝试强制停止..."
        pkill -9 -f "websocket.ws_server"
    fi
    echo -e "${GREEN}✓${NC} Python推理服务已停止"
else
    echo -e "${YELLOW}→${NC} Python推理服务未运行"
fi

echo -e "\n${GREEN}所有服务已停止！${NC}"
