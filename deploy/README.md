# 液位检测系统远程服务器部署文档

本文档说明如何将液位检测系统部署到远程Linux服务器192.168.0.121上。

## 服务器环境配置

### 基本信息
- **服务器IP**: 192.168.0.121
- **用户**: lqj
- **项目路径**: /home/lqj/liquid
- **操作系统**: Linux

### Conda环境配置
- **Conda安装路径**: /home/lqj/anaconda3/
- **环境名称**: liquid
- **环境路径**: /home/lqj/anaconda3/envs/liquid/
- **激活命令**: `source ~/anaconda3/bin/activate liquid`

### 开发环境版本
- **Go版本**: go1.26.1 linux/amd64
- **Go路径**: /home/lqj/anaconda3/envs/liquid/bin/go
- **Python版本**: Python 3.11.14
- **Python路径**: /home/lqj/anaconda3/envs/liquid/bin/python

## 服务端口配置

- **Go API服务**: 端口8084 (http://192.168.0.121:8084)
- **Python推理服务**: 端口8085 (ws://192.168.0.121:8085)

## 部署脚本说明

### PowerShell部署脚本 (Windows)
```powershell
.\deploy_to_server.ps1
```
- 自动上传API服务、推理服务和SDK文件
- 在远程服务器上构建Go API服务
- 创建服务启动脚本

### Bash部署脚本 (Linux/Mac)
```bash
./deploy_to_server.sh
```
- 功能与PowerShell脚本相同
- 适用于Linux和Mac系统

## 服务管理

### 启动服务
```bash
ssh lqj@192.168.0.121
cd /home/lqj/liquid
./start_services.sh
```

### 检查服务状态
```bash
./check_services.sh
```

### 停止服务
```bash
./stop_services.sh
```

## 环境变量设置

服务启动时会自动设置以下环境变量：
```bash
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH
```

## 文件结构

```
/home/lqj/liquid/
├── api/                    # Go API服务
│   ├── liquid-api         # 编译后的可执行文件
│   ├── vendor/            # Go依赖包
│   └── ...
├── server/                # Python推理服务
│   ├── main.py           # 推理服务主程序
│   └── ...
├── sdk/                   # 海康威视SDK
│   └── hikvision/
│       └── lib/          # SDK库文件
├── logs/                  # 服务日志
│   ├── api.log           # API服务日志
│   └── inference.log     # 推理服务日志
└── start_services.sh      # 服务启动脚本
```

## 部署步骤

1. **准备本地环境**
   - 确保本地已安装Go和Python环境
   - 在api目录下运行 `go mod vendor` 生成vendor目录

2. **执行部署脚本**
   ```powershell
   cd deploy
   .\deploy_to_server.ps1
   ```

3. **启动服务**
   ```bash
   ssh lqj@192.168.0.121
   cd /home/lqj/liquid
   ./start_services.sh
   ```

4. **验证部署**
   - 检查API服务: `wget -qO- http://192.168.0.121:8084/health`
   - 检查端口状态: `netstat -tlnp | grep -E ':(8084|8085)'`

## 故障排除

### 常见问题

1. **Go依赖下载失败**
   - 使用vendor模式: `go build -mod=vendor`
   - 确保vendor目录已上传到服务器

2. **权限问题**
   - 确保liquid-api文件有执行权限: `chmod +x liquid-api`
   - 确保启动脚本有执行权限: `chmod +x start_services.sh`

3. **端口占用**
   - 检查端口状态: `netstat -tlnp | grep 8084`
   - 停止占用进程: `pkill -f liquid-api`

### 日志查看

- API服务日志: `tail -f /home/lqj/liquid/logs/api.log`
- 推理服务日志: `tail -f /home/lqj/liquid/logs/inference.log`

## 客户端配置

客户端配置文件 `client/config/client_config.yaml` 应指向远程服务器：

```yaml
server:
  api_url: "http://192.168.0.121:8084"
  websocket_url: "ws://192.168.0.121:8085"
```

## 测试相机配置

- **RTSP地址**: rtsp://admin:cei345678@192.168.0.27:8000/stream1
- **用途**: 系统功能测试和验证