#!/bin/bash
# 部署脚本 - 将API服务和推理服务部署到远程服务器192.168.0.121

SERVER_IP="192.168.0.121"
SERVER_USER="lqj"
SERVER_PATH="/home/lqj/liquid"

echo "开始部署到远程服务器 $SERVER_IP..."

# 1. 创建部署目录
echo "1. 创建远程目录结构..."
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/api"
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/server"

# 2. 上传API服务文件
echo "2. 上传API服务文件..."
scp -r ../api/* $SERVER_USER@$SERVER_IP:$SERVER_PATH/api/

# 3. 上传推理服务文件
echo "3. 上传推理服务文件..."
scp -r ../server/* $SERVER_USER@$SERVER_IP:$SERVER_PATH/server/

# 4. 上传SDK库文件
echo "4. 上传SDK库文件..."
scp -r ../sdk $SERVER_USER@$SERVER_IP:$SERVER_PATH/

# 5. 在远程服务器上构建API服务
echo "5. 在远程服务器上构建API服务..."
ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH/api && go mod tidy && go build -o liquid-api main.go"

# 6. 设置执行权限
echo "6. 设置执行权限..."
ssh $SERVER_USER@$SERVER_IP "chmod +x $SERVER_PATH/api/liquid-api"

# 7. 创建启动脚本
echo "7. 创建远程启动脚本..."
ssh $SERVER_USER@$SERVER_IP "cat > $SERVER_PATH/start_services.sh << 'EOF'
#!/bin/bash
# 启动液位检测系统服务

cd /home/lqj/liquid

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
conda activate liquid
nohup python main.py > ../logs/inference.log 2>&1 &
INFERENCE_PID=\$!
echo \"推理服务已启动，PID: \$INFERENCE_PID\"

echo \"所有服务已启动\"
echo \"API服务: http://192.168.0.121:8084\"
echo \"推理服务: ws://192.168.0.121:8085\"
EOF"

# 8. 设置启动脚本权限
ssh $SERVER_USER@$SERVER_IP "chmod +x $SERVER_PATH/start_services.sh"

# 9. 创建日志目录
ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH/logs"

echo "部署完成！"
echo "要启动服务，请在远程服务器上运行："
echo "ssh $SERVER_USER@$SERVER_IP"
echo "cd $SERVER_PATH"
echo "./start_services.sh"