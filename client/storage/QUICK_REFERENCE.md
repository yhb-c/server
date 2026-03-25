# 检测结果处理 - 快速参考

## ✅ 功能已实现

客户端接收到检测结果后会自动执行：

### 1️⃣ UI绘制
- 在视频画面上显示液位线（红色）
- 显示实际高度数值（毫米）
- 实时更新

### 2️⃣ CSV存储
- 自动保存到 `D:\system_client_sever\client\result`
- 文件格式：`{channel_id}_{timestamp}.csv`
- 包含时间戳、液位高度、统计数据

## 🚀 快速开始

```python
from client.network.command_manager import NetworkCommandManager

# 创建命令管理器（CSV存储自动启用）
command_manager = NetworkCommandManager('ws://192.168.0.121:8085')

# 连接信号
command_manager.detectionResultReceived.connect(on_detection_result)
command_manager.liquidHeightReceived.connect(on_liquid_height)

# 启动连接
command_manager.start_connection()

# 订阅通道
command_manager.send_subscribe_command('channel1')

# 启动检测
command_manager.send_detection_command('channel1', 'start_detection')

# 检测结果会自动：
# 1. 在UI上绘制液位线
# 2. 保存到CSV文件
```

## 📊 CSV文件格式

**简洁格式：时间戳 + 液位高度**

```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
1773897360.823456,121.3
1773897360.823456,136.1
1773897360.823456,99.2
```

**说明**:
- 每个液位高度值占一行
- 同一时间戳的多个值表示多个检测区域
- 时间戳为Unix时间戳（浮点数）
- 液位高度单位为毫米，保留2位小数

## 🔧 常用操作

### 自定义保存路径
```python
command_manager = NetworkCommandManager(
    server_url='ws://192.168.0.121:8085',
    csv_save_dir=r'E:\my_data'
)
```

### 禁用CSV存储
```python
command_manager = NetworkCommandManager(
    server_url='ws://192.168.0.121:8085',
    enable_csv_storage=False
)
```

### 获取CSV文件路径
```python
csv_path = command_manager.get_csv_filepath('channel1')
print(f"CSV文件: {csv_path}")
```

### 关闭CSV文件
```python
command_manager.close_csv_files()
```

## 🧪 测试

```bash
# 测试CSV存储功能
python test/test_csv_storage.py
```

## 📚 详细文档

- [CSV格式说明](./CSV_FORMAT.md)
- [CSV存储使用指南](./CSV_STORAGE_GUIDE.md)
- [检测结果处理流程](../test/CLIENT_DETECTION_RESULT_FLOW.md)
- [快速总结](../test/SUMMARY.md)

## 💡 关键点

1. **自动保存** - 无需额外代码，接收到结果自动保存
2. **双重输出** - UI显示 + CSV存储同时进行
3. **多通道支持** - 每个通道独立的CSV文件
4. **实时写入** - 每收到一个结果立即写入CSV
5. **数据完整** - 包含时间戳、高度、统计信息

## 🎯 总结

```
检测结果接收
    ↓
NetworkCommandManager
    ├─→ UI绘制（液位线）
    └─→ CSV存储（数据文件）
```

一切都是自动的！
