#!/bin/bash
# 检查远程服务器上的服务状态

SERVER_IP="192.168.0.121"
SERVER_USER="lqj"

echo "检查远程服务器 $SERVER_IP 上的服务状态..."

ssh $SERVER_USER@$SERVER_IP "
echo '服务状态检查:'
echo '=================='

# 检查API服务
API_PID=\$(ps aux | grep liquid-api | grep -v grep | awk '{print \$2}')
if [ ! -z \"\$API_PID\" ]; then
    echo \"✓ API服务运行中 (PID: \$API_PID)\"
    if netstat -tlnp 2>/dev/null | grep -q :8084; then
        echo \"✓ API端口8084已开放\"
    else
        echo \"✗ API端口8084未开放\"
    fi
else
    echo \"✗ API服务未运行\"
fi

# 检查推理服务
INFERENCE_PID=\$(ps aux | grep 'python.*main.py' | grep -v grep | awk '{print \$2}')
if [ ! -z \"\$INFERENCE_PID\" ]; then
    echo \"✓ 推理服务运行中 (PID: \$INFERENCE_PID)\"
    if netstat -tlnp 2>/dev/null | grep -q :8085; then
        echo \"✓ 推理服务端口8085已开放\"
    else
        echo \"✗ 推理服务端口8085未开放\"
    fi
else
    echo \"✗ 推理服务未运行\"
fi

echo ''
echo '日志文件:'
echo '=================='
if [ -f /home/lqj/liquid/logs/api.log ]; then
    echo \"API服务日志 (最后10行):\"
    tail -10 /home/lqj/liquid/logs/api.log
else
    echo \"API服务日志文件不存在\"
fi

echo ''
if [ -f /home/lqj/liquid/logs/inference.log ]; then
    echo \"推理服务日志 (最后10行):\"
    tail -10 /home/lqj/liquid/logs/inference.log
else
    echo \"推理服务日志文件不存在\"
fi
"