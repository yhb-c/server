#!/bin/bash
# 启动增强液位检测WebSocket服务器脚本
# 在服务器192.168.0.121上运行

echo "=========================================="
echo "启动增强液位检测WebSocket服务器"
echo "=========================================="

# 检查当前目录
if [ ! -f "start_websocket_server.py" ]; then
    echo "错误: 请在server目录下运行此脚本"
    exit 1
fi

# 激活conda环境
echo "激活conda环境: liquid"
source ~/anaconda3/bin/activate liquid

# 检查Python环境
echo "检查Python环境..."
python --version
which python

# 设置环境变量
export PYTHONPATH="/home/lqj/liquid/server:$PYTHONPATH"
export LD_LIBRARY_PATH="/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH"

echo "环境变量设置完成:"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  LD_LIBRARY_PATH: $LD_LIBRARY_PATH"

# 检查必要的文件
echo "检查必要文件..."
if [ ! -f "websocket/enhanced_ws_server.py" ]; then
    echo "错误: 找不到enhanced_ws_server.py"
    exit 1
fi

if [ ! -f "websocket/detection_service.py" ]; then
    echo "错误: 找不到detection_service.py"
    exit 1
fi

if [ ! -f "detection/detection.py" ]; then
    echo "错误: 找不到detection.py"
    exit 1
fi

# 创建日志目录
mkdir -p logs

echo "启动增强WebSocket服务器..."
echo "监听地址: 0.0.0.0:8085"
echo "客户端连接地址: ws://192.168.0.121:8085"
echo "按 Ctrl+C 停止服务器"
echo "=========================================="

# 启动服务器
python start_websocket_server.py 2>&1 | tee logs/websocket_server.log