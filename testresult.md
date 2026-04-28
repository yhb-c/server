YOLO11 官方通过 vid_stride 参数提供了开箱即用的原生固定间隔跳帧能力，无需用户自行实现帧计数逻辑。该参数属于 Ultralytics 框架的通用推理参数，# 1. 复制服务文件到systemd目录
sudo cp /home/lqj/liquid/server/systemd/liquid-api.service /etc/systemd/system/
sudo cp /home/lqj/liquid/server/systemd/liquid-websocket.service /etc/systemd/system/

# 2. 重新加载systemd配置
sudo systemctl daemon-reload

# 3. 停止当前手动运行的服务
sudo systemctl stop liquid-api liquid-websocket 2>/dev/null || true
kill $(ps aux | grep liquid-api | grep -v grep | awk '{print $2}') 2>/dev/null || true
kill $(ps aux | grep start_websocket_server.py | grep -v grep | awk '{print $2}') 2>/dev/null || true

# 4. 启用服务（开机自动启动）
sudo systemctl enable liquid-api
sudo systemctl enable liquid-websocket

# 5. 启动服务
sudo systemctl start liquid-api
sudo systemctl start liquid-websocket

# 6. 查看服务状态
sudo systemctl status liquid-api
sudo systemctl status liquid-websocket
