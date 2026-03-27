#!/bin/bash
# 液位检测系统服务启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "液位检测系统 - 服务启动脚本"
echo "======================================"

# 激活conda环境
echo -e "\n${YELLOW}[1/4]${NC} 激活conda环境..."
source ~/anaconda3/bin/activate liquid
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} conda环境激活成功"
else
    echo -e "${RED}✗${NC} conda环境激活失败"
    exit 1
fi

# 检查并启动Go API服务
echo -e "\n${YELLOW}[2/4]${NC} 检查Go API服务..."
if pgrep -f "liquid-api" > /dev/null; then
    echo -e "${GREEN}✓${NC} Go API服务已在运行"
else
    echo -e "${YELLOW}→${NC} 启动Go API服务..."
    cd /home/lqj/liquid/api

    # 检查可执行文件是否存在
    if [ ! -f "./liquid-api" ]; then
        echo -e "${YELLOW}→${NC} 编译Go API服务..."
        go build -o liquid-api main.go
        if [ $? -ne 0 ]; then
            echo -e "${RED}✗${NC} Go API服务编译失败"
            exit 1
        fi
    fi

    nohup ./liquid-api > api.log 2>&1 &
    sleep 2

    if pgrep -f "liquid-api" > /dev/null; then
        echo -e "${GREEN}✓${NC} Go API服务启动成功 (端口8084)"
    else
        echo -e "${RED}✗${NC} Go API服务启动失败"
        exit 1
    fi
fi

# 检查并启动Python推理服务
echo -e "\n${YELLOW}[3/4]${NC} 检查Python推理服务..."
if pgrep -f "start_websocket_server" > /dev/null; then
    echo -e "${GREEN}✓${NC} Python推理服务已在运行"
else
    echo -e "${YELLOW}→${NC} 启动Python推理服务..."
    cd /home/lqj/liquid/server

    # 设置海康SDK库路径
    export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH

    nohup python websocket/start_websocket_server.py > inference.log 2>&1 &
    sleep 2

    if pgrep -f "start_websocket_server" > /dev/null; then
        echo -e "${GREEN}✓${NC} Python推理服务启动成功 (端口8085)"
    else
        echo -e "${RED}✗${NC} Python推理服务启动失败"
        exit 1
    fi
fi

# 验证服务状态
echo -e "\n${YELLOW}[4/4]${NC} 验证服务状态..."
echo ""
echo "服务状态:"
echo "----------------------------------------"

# 检查Go API服务
if pgrep -f "liquid-api" > /dev/null; then
    API_PID=$(pgrep -f "liquid-api" | head -1)
    echo -e "Go API服务:      ${GREEN}运行中${NC} (PID: $API_PID, 端口: 8084)"
else
    echo -e "Go API服务:      ${RED}未运行${NC}"
fi

# 检查Python推理服务
if pgrep -f "start_websocket_server" > /dev/null; then
    INFERENCE_PID=$(pgrep -f "start_websocket_server" | head -1)
    echo -e "Python推理服务:  ${GREEN}运行中${NC} (PID: $INFERENCE_PID, 端口: 8085)"
else
    echo -e "Python推理服务:  ${RED}未运行${NC}"
fi

echo "----------------------------------------"
echo -e "\n${GREEN}所有服务启动完成！${NC}"
echo ""
echo "API服务地址: http://192.168.0.121:8084"
echo "推理服务地址: ws://192.168.0.121:8085"
echo ""
