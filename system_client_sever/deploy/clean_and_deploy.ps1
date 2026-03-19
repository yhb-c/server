# PowerShell脚本 - 清空服务器项目路径并重新部署API和推理服务

$SERVER_IP = "192.168.0.121"
$SERVER_USER = "lqj"
$SERVER_PATH = "/home/lqj/liquid"

Write-Host "开始清空并重新部署到远程服务器 $SERVER_IP..." -ForegroundColor Green

# 1. 停止现有服务
Write-Host "1. 停止现有服务..." -ForegroundColor Yellow
ssh ${SERVER_USER}@${SERVER_IP} "pkill -f 'liquid-api' || true"
ssh ${SERVER_USER}@${SERVER_IP} "pkill -f 'python.*8085' || true"
Start-Sleep -Seconds 3

# 2. 清空项目目录
Write-Host "2. 清空服务器项目目录..." -ForegroundColor Yellow
ssh ${SERVER_USER}@${SERVER_IP} "rm -rf $SERVER_PATH/*"
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p $SERVER_PATH"

# 3. 创建必要的目录结构
Write-Host "3. 创建目录结构..." -ForegroundColor Yellow
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p $SERVER_PATH/api"
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p $SERVER_PATH/server"
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p $SERVER_PATH/logs"

# 4. 上传API服务文件
Write-Host "4. 上传API服务文件..." -ForegroundColor Yellow
scp -r ..\api\* ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/api/

# 5. 上传推理服务文件
Write-Host "5. 上传推理服务文件..." -ForegroundColor Yellow
scp -r ..\server\* ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/server/

# 6. 在远程服务器上构建API服务
Write-Host "6. 构建API服务..." -ForegroundColor Yellow
ssh ${SERVER_USER}@${SERVER_IP} "cd $SERVER_PATH/api; source /home/lqj/anaconda3/bin/activate liquid; go mod tidy; go build -o liquid-api main.go; chmod +x liquid-api"

# 7. 创建启动脚本
Write-Host "7. 创建启动脚本..." -ForegroundColor Yellow
$startScript = @'
#!/bin/bash
# 启动液位检测系统服务

cd /home/lqj/liquid

# 激活conda环境
source /home/lqj/anaconda3/bin/activate liquid

# 设置环境变量
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH

# 启动API服务
echo "启动API服务..."
cd api
nohup ./liquid-api > ../logs/api.log 2>&1 &
API_PID=$!
echo "API服务已启动，PID: $API_PID"

# 启动推理服务
echo "启动推理服务..."
cd ../server
nohup python main.py > ../logs/inference.log 2>&1 &
INFERENCE_PID=$!
echo "推理服务已启动，PID: $INFERENCE_PID"

echo "所有服务已启动"
echo "API服务: http://192.168.0.121:8084"
echo "推理服务: ws://192.168.0.121:8085"
'@

echo $startScript | ssh ${SERVER_USER}@${SERVER_IP} "cat > $SERVER_PATH/start_services.sh"
ssh ${SERVER_USER}@${SERVER_IP} "chmod +x $SERVER_PATH/start_services.sh"

# 8. 创建停止脚本
Write-Host "8. 创建停止脚本..." -ForegroundColor Yellow
$stopScript = @'
#!/bin/bash
# 停止液位检测系统服务

echo "停止API服务..."
pkill -f 'liquid-api' && echo "API服务已停止" || echo "API服务未运行"

echo "停止推理服务..."
pkill -f 'python.*8085' && echo "推理服务已停止" || echo "推理服务未运行"

echo "所有服务已停止"
'@

echo $stopScript | ssh ${SERVER_USER}@${SERVER_IP} "cat > $SERVER_PATH/stop_services.sh"
ssh ${SERVER_USER}@${SERVER_IP} "chmod +x $SERVER_PATH/stop_services.sh"

# 9. 创建服务状态检查脚本
Write-Host "9. 创建状态检查脚本..." -ForegroundColor Yellow
$checkScript = @'
#!/bin/bash
# 检查液位检测系统服务状态

echo "检查服务状态..."

API_PID=$(pgrep -f 'liquid-api')
if [ ! -z "$API_PID" ]; then
    echo "API服务正在运行，PID: $API_PID"
else
    echo "API服务未运行"
fi

INFERENCE_PID=$(pgrep -f 'python.*8085')
if [ ! -z "$INFERENCE_PID" ]; then
    echo "推理服务正在运行，PID: $INFERENCE_PID"
else
    echo "推理服务未运行"
fi

echo "端口监听状态:"
netstat -tlnp | grep -E ':(8084|8085)' || echo "未发现服务端口监听"
'@

echo $checkScript | ssh ${SERVER_USER}@${SERVER_IP} "cat > $SERVER_PATH/check_services.sh"
ssh ${SERVER_USER}@${SERVER_IP} "chmod +x $SERVER_PATH/check_services.sh"

Write-Host "部署完成!" -ForegroundColor Green
Write-Host "服务器项目路径已清空并重新部署" -ForegroundColor Cyan
Write-Host ""
Write-Host "可用命令:" -ForegroundColor Cyan
Write-Host "启动服务: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${SERVER_PATH} && ./start_services.sh'" -ForegroundColor White
Write-Host "停止服务: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${SERVER_PATH} && ./stop_services.sh'" -ForegroundColor White
Write-Host "检查状态: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${SERVER_PATH} && ./check_services.sh'" -ForegroundColor White