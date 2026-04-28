# Liquid Detection System - systemd服务配置

## 安装步骤

### 1. 复制服务文件到systemd目录
```bash
sudo cp /home/lqj/liquid/server/systemd/liquid-api.service /etc/systemd/system/
sudo cp /home/lqj/liquid/server/systemd/liquid-websocket.service /etc/systemd/system/
```

### 2. 重新加载systemd配置
```bash
sudo systemctl daemon-reload
```

### 3. 启用服务（开机自动启动）
```bash
sudo systemctl enable liquid-api
sudo systemctl enable liquid-websocket
```

### 4. 启动服务
```bash
sudo systemctl start liquid-api
sudo systemctl start liquid-websocket
```

## 常用命令

### 启动服务
```bash
sudo systemctl start liquid-api
sudo systemctl start liquid-websocket
```

### 停止服务
```bash
sudo systemctl stop liquid-api
sudo systemctl stop liquid-websocket
```

### 重启服务
```bash
sudo systemctl restart liquid-api
sudo systemctl restart liquid-websocket
```

### 查看服务状态
```bash
sudo systemctl status liquid-api
sudo systemctl status liquid-websocket
```

### 查看服务日志
```bash
sudo journalctl -u liquid-api -f
sudo journalctl -u liquid-websocket -f
```

### 禁用开机自动启动
```bash
sudo systemctl disable liquid-api
sudo systemctl disable liquid-websocket
```

## 卸载服务

### 1. 停止并禁用服务
```bash
sudo systemctl stop liquid-api liquid-websocket
sudo systemctl disable liquid-api liquid-websocket
```

### 2. 删除服务文件
```bash
sudo rm /etc/systemd/system/liquid-api.service
sudo rm /etc/systemd/system/liquid-websocket.service
```

### 3. 重新加载systemd配置
```bash
sudo systemctl daemon-reload
```

## 服务配置说明

### liquid-api.service
- 工作目录: /home/lqj/liquid/server/network/api
- 执行文件: liquid-api
- 日志文件: /home/lqj/liquid/logs/api.log
- 自动重启: 失败后5秒重启

### liquid-websocket.service
- 工作目录: /home/lqj/liquid/server/network
- 执行文件: Python脚本 start_websocket_server.py
- 日志文件: /home/lqj/liquid/logs/websocket.log
- 自动重启: 失败后5秒重启

## 注意事项

1. 服务以用户lqj身份运行
2. LD_LIBRARY_PATH环境变量已在服务配置中设置
3. 服务失败会自动重启，最多重启间隔5秒
4. 日志输出到项目logs目录，同时也可通过journalctl查看
