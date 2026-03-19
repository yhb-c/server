#!/bin/bash
# 停止远程服务器上的服务

SERVER_IP="192.168.0.121"
SERVER_USER="lqj"

echo "停止远程服务器上的服务..."

# 创建远程停止脚本
ssh $SERVER_USER@$SERVER_IP "cat > /home/lqj/liquid/stop_services.sh << 'EOF'
#!/bin/bash
echo \"停止液位检测系统服务...\"

# 停止API服务
API_PID=\$(ps aux | grep liquid-api | grep -v grep | awk '{print \$2}')
if [ ! -z \"\$API_PID\" ]; then
    kill \$API_PID
    echo \"API服务已停止 (PID: \$API_PID)\"
else
    echo \"API服务未运行\"
fi

# 停止推理服务
INFERENCE_PID=\$(ps aux | grep \"python.*main.py\" | grep -v grep | awk '{print \$2}')
if [ ! -z \"\$INFERENCE_PID\" ]; then
    kill \$INFERENCE_PID
    echo \"推理服务已停止 (PID: \$INFERENCE_PID)\"
else
    echo \"推理服务未运行\"
fi

echo \"所有服务已停止\"
EOF"

# 设置权限并执行
ssh $SERVER_USER@$SERVER_IP "chmod +x /home/lqj/liquid/stop_services.sh && /home/lqj/liquid/stop_services.sh"

echo "服务停止完成"