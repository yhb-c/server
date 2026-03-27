# 检测结果CSV存储模块

## 功能说明

本模块负责将服务器推送的液位检测结果保存到CSV文件中。

## 核心文件

- `detection_result_csv_writer.py`: CSV写入器实现

## 功能特性

### 1. 多通道并发写入
- 支持16个通道同时写入CSV文件
- 每个通道独立管理自己的CSV文件
- 线程安全的文件写入操作

### 2. 智能路径管理
- 根据通道分配的任务自动保存到对应任务文件夹
- 未分配任务的通道保存到基础目录
- 动态获取项目根目录，避免硬编码路径

### 3. 文件命名规则
- 格式: `{channel_id}_{timestamp}.csv`
- 示例: `channel1_20260327_143025.csv`
- 每次启动检测时创建新文件

### 4. CSV格式
```csv
时间戳,液位高度(mm)
1711519825.123,120.50
1711519825.456,135.20
1711519825.789,98.70
```

## 使用方式

### 初始化
```python
from client.storage.detection_result_csv_writer import DetectionResultCSVWriter

# 创建CSV写入器
csv_writer = DetectionResultCSVWriter(
    save_dir='/path/to/save',  # 可选，默认使用项目根目录
    main_window=main_window     # 主窗口实例，用于获取通道任务信息
)
```

### 写入检测结果
```python
# 方式1: 直接写入液位高度列表
csv_writer.write_detection_result(
    channel_id='channel1',
    heights=[120.5, 135.2, 98.7],
    timestamp=1711519825.123  # 可选
)

# 方式2: 写入完整的检测结果数据
csv_writer.write_full_detection_result({
    'type': 'detection_result',
    'channel_id': 'channel1',
    'timestamp': 1711519825.123,
    'heights': [120.5, 135.2, 98.7]
})
```

### 关闭文件
```python
# 关闭指定通道的CSV文件
csv_writer.close_channel('channel1')

# 关闭所有CSV文件
csv_writer.close_all()
```

## 集成到系统

### SystemWindow集成
在 `client/widgets/system_window.py` 中：

1. 初始化CSV写入器
```python
def _initCSVWriter(self):
    self.csv_writer = DetectionResultCSVWriter(main_window=self)
```

2. 接收检测结果时自动保存
```python
def _onDetectionResult(self, data):
    if self.csv_writer:
        channel_id = data.get('channel_id')
        heights = data.get('heights', [])
        timestamp = data.get('timestamp')
        self.csv_writer.write_detection_result(channel_id, heights, timestamp)
```

3. 窗口关闭时清理
```python
def closeEvent(self, event):
    if self.csv_writer:
        self.csv_writer.close_all()
```

## 数据流程

```
服务器 (16通道检测)
    |
    | WebSocket推送
    v
NetworkCommandManager
    |
    | detectionResultReceived信号
    v
SystemWindow._onDetectionResult()
    |
    | 调用csv_writer.write_detection_result()
    v
DetectionResultCSVWriter
    |
    | 1. 获取通道任务信息
    | 2. 确定保存路径
    | 3. 创建/打开CSV文件
    | 4. 写入液位数据
    v
CSV文件 (任务文件夹/channel_id_timestamp.csv)
```

## 目录结构

```
database/
└── mission_result/
    ├── 任务1_测试任务/
    │   ├── channel1_20260327_143025.csv
    │   ├── channel2_20260327_143025.csv
    │   └── ...
    ├── 任务2_生产任务/
    │   ├── channel3_20260327_150000.csv
    │   └── ...
    └── channel16_20260327_143025.csv  (未分配任务的通道)
```

## 注意事项

1. 文件自动刷新：每次写入后立即调用 `flush()` 确保数据写入磁盘
2. 异常处理：所有写入操作都有异常捕获，不会影响主程序运行
3. 资源清理：程序退出时自动关闭所有打开的CSV文件
4. 编码格式：使用 `utf-8-sig` 编码，确保Excel正确显示中文
