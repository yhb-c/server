# 网络通信模块

本模块负责客户端与服务端的所有网络通信功能，包括实时检测数据传输和配置管理。

## 模块结构

```
network/
├── websocket_client.py      # WebSocket客户端 - 实时通信
├── command_manager.py        # 命令管理器 - 封装WebSocket操作
├── api/                      # HTTP API客户端 - RESTful接口
│   ├── __init__.py
│   ├── api_manager.py        # API管理器
│   ├── base_api.py           # 基础API类
│   ├── auth_api.py           # 认证API
│   ├── channel_api.py        # 通道管理API
│   ├── mission_api.py        # 任务管理API
│   ├── config_api.py         # 配置管理API
│   ├── model_api.py          # 模型管理API
│   ├── video_api.py          # 视频管理API
│   └── dataset_api.py        # 数据集管理API
└── readme.md                 # 本文档

```

## 三大通信组件

### 1. WebSocket客户端 (websocket_client.py)

用于与Python推理服务（端口8085）进行实时双向通信。

功能：
- 发送检测命令（start_detection, stop_detection, start_all等）
- 接收实时检测结果
- 接收视频帧数据
- 自动重连机制

主要方法：
- `send_command(command, **kwargs)` - 发送命令到服务器
- `start()` - 启动WebSocket连接
- `stop()` - 停止WebSocket连接
- `force_reconnect()` - 强制重新连接

信号：
- `connection_status` - 连接状态变化
- `detection_result` - 检测结果接收
- `video_frame` - 视频帧数据接收

使用示例：
```python
from network.websocket_client import WebSocketClient

ws_client = WebSocketClient('ws://192.168.0.121:8085')
ws_client.connection_status.connect(on_connection_status)
ws_client.detection_result.connect(on_detection_result)
ws_client.start()

ws_client.send_command('start_detection', channel_id='channel_1')
```

### 2. 命令管理器 (command_manager.py)

封装WebSocket客户端，提供更高级的业务接口。

功能：
- 封装常用检测命令
- 管理连接状态
- 处理CSV数据存储
- 转发信号到UI层

主要方法：
- `send_detection_command(channel_id, action)` - 发送检测命令
- `send_model_load_command(channel_id, model_path, device)` - 发送模型加载命令
- `send_annotation_command(channel_id, frame_data, conf_threshold)` - 发送自动标注命令
- `send_configure_channel_command(channel_id, config)` - 发送配置通道命令
- `send_subscribe_command(channel_id)` - 发送订阅通道命令
- `enable_csv_storage_for_channel(channel_id)` - 启用CSV存储
- `close_csv_files()` - 关闭所有CSV文件

信号：
- `connectionStatusChanged` - 连接状态变化
- `detectionResultReceived` - 检测结果接收
- `commandResponseReceived` - 命令响应接收
- `liquidHeightReceived` - 液位高度数据接收

使用示例：
```python
from network.command_manager import NetworkCommandManager

cmd_manager = NetworkCommandManager('ws://192.168.0.121:8085')
cmd_manager.connectionStatusChanged.connect(on_connection_changed)
cmd_manager.detectionResultReceived.connect(on_detection_result)
cmd_manager.start_connection()

cmd_manager.send_detection_command('channel_1', 'start_detection')
```

### 3. HTTP API客户端 (api/)

用于与Go API服务（端口8084）进行RESTful通信，管理配置数据。

功能：
- 用户认证（登录/登出）
- 通道管理（CRUD操作）
- 任务管理（CRUD操作）
- 配置管理（读取/保存配置）
- 模型管理（查询模型信息）
- 视频管理
- 数据集管理

主要类：
- `APIManager` - API管理器，统一管理所有API客户端
- `AuthAPI` - 认证API
- `ChannelAPI` - 通道管理API
- `MissionAPI` - 任务管理API
- `ConfigAPI` - 配置管理API
- `ModelAPI` - 模型管理API
- `VideoAPI` - 视频管理API
- `DatasetAPI` - 数据集管理API

使用示例：
```python
from network.api.api_manager import APIManager

api_manager = APIManager('http://192.168.0.121:8084')

result = api_manager.login('admin', 'password')
if result['code'] == 0:
    token = result['data']['token']

    channels = api_manager.channel.get_all_channels()
    missions = api_manager.mission.get_all_missions()
```

## 通信架构

```
客户端 (Client)
    |
    +-- WebSocket (端口8085) --> Python推理服务
    |   |
    |   +-- 实时检测命令
    |   +-- 实时检测结果
    |   +-- 视频帧数据
    |
    +-- HTTP API (端口8084) --> Go API服务
        |
        +-- 用户认证
        +-- 通道/任务管理
        +-- 配置数据CRUD
        +-- 模型信息查询
```

## 使用场景

### 场景1：启动检测
1. 通过HTTP API获取通道配置
2. 通过WebSocket发送start_detection命令
3. 通过WebSocket接收实时检测结果

### 场景2：配置通道
1. 通过HTTP API获取通道列表
2. 通过WebSocket发送configure_channel命令
3. 通过HTTP API保存配置到数据库

### 场景3：模型管理
1. 通过HTTP API查询可用模型列表
2. 通过WebSocket发送load_model命令
3. 通过WebSocket发送检测命令使用新模型

## 注意事项

1. WebSocket连接需要先启动才能发送命令
2. HTTP API需要先登录获取token才能访问其他接口
3. 命令管理器会自动处理重连，但HTTP API需要手动处理token过期
4. CSV存储功能在命令管理器中可选启用
5. 所有网络操作都是异步的，通过信号机制通知结果

## 依赖关系

- `websocket_client.py` - 独立模块，无内部依赖
- `command_manager.py` - 依赖 `websocket_client.py`
- `api/` - 独立模块，无内部依赖（除了base_api.py）

## 服务器配置

- **Go API服务**: http://192.168.0.121:8084
- **Python推理服务**: ws://192.168.0.121:8085
- **数据库**: MySQL（通过Go API访问）
