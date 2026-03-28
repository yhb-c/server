#!/bin/bash
# 重启WebSocket服务器脚本

echo "=========================================="
echo "重启WebSocket服务器"
echo "=========================================="

# 查找并停止现有进程
echo "查找现有进程..."
PID=$(ps aux | grep "python.*start_websocket_server.py" | grep -v grep | awk '{print $2}')

if [ -n "$PID" ]; then
    echo "找到进程 PID: $PID"
    echo "正在停止服务器..."
    kill $PID
    sleep 2
    
    # 检查是否还在运行
    if ps -p $PID > /dev/null 2>&1; then
        echo "进程未响应，强制停止..."
        kill -9 $PID
        sleep 1
    fi
    echo "服务器已停止"
else
    echo "未找到运行中的服务器进程"
fi

# 启动服务器
echo "启动服务器..."
cd /home/lqj/liquid/server
bash start_enhanced_detection_server.sh &

echo "服务器启动命令已执行"
echo "=========================================="
