# WebSocket服务端架构说明

## 文件职责划分

### 1. enhanced_ws_server.py - WebSocket通信层（唯一推送出口）
**职责：**
- 管理WebSocket客户端连接和断开
- 接收并处理客户端命令（订阅、加载模型、配置通道、启动/停止检测等）
- 管理通道订阅关系（哪些客户端订阅了哪些通道）
- **推送检测结果和状态更新到订阅的客户端（唯一的推送出口）**
- 集成DetectionService处理检测业务逻辑

**核心方法：**
- `broadcast_to_channel(channel_id, data)` - 推送数据到订阅该通道的所有客户端

### 2. detection_service.py - 检测业务逻辑层
**职责：**
- 管理检测任务的生命周期（加载模型、配置通道、启动/停止检测）
- 管理通道状态信息
- 接收检测结果回调
- 将检测结果转发给WebSocket服务器进行推送（不直接推送）

**核心方法：**
- `load_model()` - 加载检测模型
- `configure_channel()` - 配置检测通道
- `start_detection()` / `stop_detection()` - 启动/停止检测
- `_on_detection_result()` - 接收检测结果回调
- `_send_detection_result()` - 将检测结果转发给WebSocket服务器

### 3. start_websocket_server.py - 启动脚本
**职责：**
- 服务器启动入口
- 初始化配置管理器
- 创建并启动EnhancedWebSocketServer实例
- 处理信号和优雅关闭

## 数据流向

```
检测引擎
  ↓ (检测结果回调)
DetectionService._on_detection_result()
  ↓ (构建推送数据)
DetectionService._send_detection_result()
  ↓ (通过asyncio.run_coroutine_threadsafe转发)
EnhancedWebSocketServer.broadcast_to_channel()
  ↓ (推送到订阅的客户端)
客户端WebSocket连接
```

## 为什么只有一个推送出口？

1. **职责单一**：WebSocket通信层专注于网络通信，检测业务层专注于检测逻辑
2. **易于维护**：所有推送逻辑集中在一个地方，便于调试和修改
3. **订阅管理**：只有WebSocket服务器知道哪些客户端订阅了哪些通道
4. **线程安全**：通过asyncio.run_coroutine_threadsafe确保从同步线程安全地调用异步方法

## 修改历史

- 2026-03-28: 明确职责划分，确保enhanced_ws_server.py是唯一的推送出口
