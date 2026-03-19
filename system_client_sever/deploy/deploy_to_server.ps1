# PowerShell部署脚本 - 将API服务和推理服务部署到远程服务器192.168.0.121

$SERVER_IP = "192.168.0.121"
$SERVER_USER = "lqj"
$SERVER_PATH = "/home/lqj/liquid"

Write-Host "开始部署到远程服务器 $SERVER_IP..." -ForegroundColor Green

# 1. 上传文件到远程服务器
Write-Host "1. 上传API服务文件..." -ForegroundColor Yellow
scp -r ..\api\* ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/api/

Write-Host "2. 上传推理服务文件..." -ForegroundColor Yellow  
scp -r ..\server\* ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/server/

Write-Host "3. 上传SDK库文件..." -ForegroundColor Yellow
scp -r ..\sdk ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

# 2. 在远程服务器上构建
Write-Host "4. 在远程服务器上构建..." -ForegroundColor Yellow
ssh ${SERVER_USER}@${SERVER_IP} "cd $SERVER_PATH; mkdir -p logs"
ssh ${SERVER_USER}@${SERVER_IP} "cd $SERVER_PATH/api; go mod tidy; go build -o liquid-api main.go; chmod +x liquid-api"

# 3. 创建启动脚本
Write-Host "5. 创建启动脚本..." -ForegroundColor Yellow
$startScript = "#!/bin/bash`ncd /home/lqj/liquid`nexport LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:`$LD_LIBRARY_PATH`necho 启动API服务...`ncd api`nnohup ./liquid-api > ../logs/api.log 2>&1 &`necho API服务已启动`ncd ../server`necho 启动推理服务...`nconda activate liquid`nnohup python main.py > ../logs/inference.log 2>&1 &`necho 推理服务已启动`necho 所有服务已启动"

echo $startScript | ssh ${SERVER_USER}@${SERVER_IP} "cat > $SERVER_PATH/start_services.sh"
ssh ${SERVER_USER}@${SERVER_IP} "chmod +x $SERVER_PATH/start_services.sh"

Write-Host "部署完成!" -ForegroundColor Green
Write-Host "要启动服务请运行:" -ForegroundColor Cyan
Write-Host "ssh $SERVER_USER@$SERVER_IP" -ForegroundColor White
Write-Host "cd $SERVER_PATH" -ForegroundColor White  
Write-Host "./start_services.sh" -ForegroundColor White