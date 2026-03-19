#!/bin/bash
# 启动重构后的检测系统

# 设置环境变量
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH

# 激活conda环境
source ~/anaconda3/bin/activate liquid

# 进入项目目录
cd /home/lqj/liquid/server

# 启动WebSocket服务器
echo "启动重构后的检测系统..."
python -m websocket.enhanced_ws_server

echo "检测系统启动完成"
