#!/bin/bash
# 清空服务器项目路径并重新部署API和推理服务

SERVER_IP="192.168.0.121"
SERVER_USER="lqj"
SERVER_PATH="/home/lqj/liquid"

echo "开始清空并重新部署到远程服务器 $SERVER_IP..."

# 1. 停止现有服务
echo "1. 停止现有服务..."
ssh $SERVER_USER@$SERVER_IP "pkill -f 'liquid-api' || true"
ssh $SERVER_USER@$SERVER_IP "pkill -f 'python.*8085' || true"
sleep 3

# 2. 清空项目目录
echo "2. 清空服务器项目目录..."
ssh $SERVER_USER@$SERVER_IP "rm -rf $SERVER_PATH/*"
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH"

# 3. 创建必要的目录结构
echo "3. 创建目录结构..."
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/api"
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/server"
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/logs"

# 4. 上传API服务文件
echo "4. 上传API服务文件..."
scp -r ../api/* $SERVER_USER@$SERVER_IP:$SERVER_PATH/api/

# 5. 上传推理服务文件
echo "5. 上传推理服务文件..."
scp -r ../server/* $SERVER_USER@$SERVER_IP:$SERVER_PATH/server/

# 6. 在远程服务器上构建API服务
echo "6. 构建API服务..."
ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH/api && source /home/lqj/anaconda3/bin/activate liquid && go mod tidy && go build -o liquid-api main.go && chmod +x liquid-api"

echo "部署完成!"
# 7. 创建启动脚本
echo "7. 创建启动脚本..."
ssh $SERVER_USER@$SERVER_IP "cat > $SERVER_PATH/start_services.sh << 'EOF'
#!/bin/bash
# 启动液位检测系统服务

cd /home/lqj/liquid

# 激活conda环境
source /home/lqj/anaconda3/bin/activate liquid

# 设置环境变量
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:\$LD_LIBRARY_PATH

# 启动API服务
echo \"启动API服务...\"
cd api
nohup ./liquid-api > ../logs/api.log 2>&1 &
API_PID=\$!
echo \"API服务已启动，PID: \$API_PID\"

# 启动推理服务
echo \"启动推理服务...\"
cd ../server
nohup python main.py > ../logs/inference.log 2>&1 &
INFERENCE_PID=\$!
echo \"推理服务已启动，PID: \$INFERENCE_PID\"

echo \"所有服务已启动\"
echo \"API服务: http://192.168.0.121:8084\"
echo \"推理服务: ws://192.168.0.121:8085\"
EOF"

# 8. 设置启动脚本权限
ssh $SERVER_USER@$SERVER_IP "chmod +x $SERVER_PATH/start_services.sh"

echo "服务器项目路径已清空并重新部署"
echo "要启动服务，请运行："
echo "ssh $SERVER_USER@$SERVER_IP 'cd $SERVER_PATH && ./start_services.sh'"