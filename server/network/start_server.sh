#!/bin/bash
# WebSocket服务器启动脚本 - 设置环境变量后启动

# 设置海康SDK库路径
SDK_LIB_PATH="/home/lqj/liquid/server/lib/lib"
SDK_COM_PATH="/home/lqj/liquid/server/lib/lib/HCNetSDKCom"

# 设置LD_LIBRARY_PATH环境变量
export LD_LIBRARY_PATH="${SDK_LIB_PATH}:${SDK_COM_PATH}:${LD_LIBRARY_PATH}"

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 使用liquid环境的Python启动服务器
/home/lqj/anaconda3/envs/liquid/bin/python start_websocket_server.py
