# 配置文件说明

## 配置文件结构

```
config/
├── main.yaml           # 推理服务主配置（服务器、模型、日志等）
└── channels.yaml       # 通道配置（16个通道的RTSP地址、ROI等）
```

## 配置文件说明

### main.yaml - 推理服务主配置

此文件包含推理服务的全局配置：
- 服务器配置（WebSocket地址、端口）
- 模型配置（模型路径、设备）
- 日志配置（日志级别、路径）
- 性能配置（队列大小、帧跳过）

**注意：** 此配置文件独立于Go API服务器的配置。

### channels.yaml - 通道配置

此文件包含所有通道的配置：
- 通道启用状态
- RTSP流地址
- 检测间隔
- ROI区域坐标
- 容器参数（高度、顶部、底部坐标）

每个通道可以独立配置，互不影响。

## 与其他配置的关系

### server/database/config/default_config.yaml
- 用途：Go API服务器的默认配置
- 范围：系统级配置、存储配置
- 不影响推理服务

### server/api/config.yaml
- 用途：Go API服务器的运行配置
- 范围：API端口、数据库连接
- 不影响推理服务

## 配置优先级

推理服务只读取 `inference/config/` 目录下的配置文件，不依赖其他配置。

## 修改配置

1. 修改 `main.yaml` 后需要重启推理服务
2. 修改 `channels.yaml` 后需要重启推理服务
3. 可以通过WebSocket命令动态启动/停止通道检测，无需重启服务

## 配置示例

### 启用多个通道

编辑 `channels.yaml`，将需要的通道设置为 `enabled: true`：

```yaml
channels:
  channel1:
    enabled: true
    rtsp_url: rtsp://admin:password@192.168.0.27:8000/stream1
    ...
  
  channel2:
    enabled: true
    rtsp_url: rtsp://admin:password@192.168.0.28:8000/stream1
    ...
```

### 修改模型路径

编辑 `main.yaml`：

```yaml
model:
  type: yolov11
  path: /path/to/your/model.pt
  device: cuda  # 或 cpu
```

### 修改WebSocket端口

编辑 `main.yaml`：

```yaml
server:
  ws_host: 0.0.0.0
  ws_port: 8085  # 修改为其他端口
```
