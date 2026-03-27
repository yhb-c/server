# 客户端接收16通道检测数据并保存CSV功能实现

## 实现概述

已成功实现客户端接收服务器推送的16通道检测数据并自动保存到CSV文件的功能。

## 核心修改

### 1. CSV写入器增强 (`client/storage/detection_result_csv_writer.py`)

#### 新增功能
- 支持传入主窗口实例，动态获取通道任务信息
- 根据通道分配的任务自动保存到对应任务文件夹
- 支持16通道并发写入，每个通道独立管理CSV文件

#### 关键方法
```python
def __init__(self, save_dir=None, main_window=None):
    # 支持传入主窗口实例
    self.main_window = main_window
    self.base_save_dir = Path(save_dir)

def _get_channel_task_folder(self, channel_id):
    # 从主窗口获取通道当前的任务文件夹名称
    # 返回任务文件夹名称或None

def _get_or_create_writer(self, channel_id):
    # 根据通道任务信息确定保存路径
    # 创建或获取CSV写入器
```

### 2. SystemWindow集成 (`client/widgets/system_window.py`)

#### 新增方法
```python
def _initCSVWriter(self):
    """初始化CSV写入器"""
    # 创建CSV写入器，传入主窗口实例
    self.csv_writer = DetectionResultCSVWriter(
        save_dir=save_dir,
        main_window=self
    )
```

#### 修改方法
```python
def _onDetectionResult(self, data):
    """检测结果回调 - 新增CSV保存逻辑"""
    # 1. 保存检测结果到CSV
    if self.csv_writer:
        channel_id = data.get('channel_id')
        heights = data.get('heights', [])
        timestamp = data.get('timestamp')
        self.csv_writer.write_detection_result(channel_id, heights, timestamp)

    # 2. 转发给ChannelPanelHandler处理液位线显示
    self._onWebSocketDetectionResult(data)

def closeEvent(self, event):
    """窗口关闭事件 - 新增CSV清理逻辑"""
    # 关闭CSV写入器
    if self.csv_writer:
        self.csv_writer.close_all()
```

## 数据流程

```
服务器 (16通道检测)
    |
    | WebSocket推送 (ws://192.168.0.121:8085)
    v
NetworkCommandManager
    |
    | detectionResultReceived信号
    v
SystemWindow._onDetectionResult()
    |
    +-- 1. 保存CSV
    |   |
    |   v
    |   DetectionResultCSVWriter
    |   |
    |   +-- 获取通道任务信息 (channelXmission标签)
    |   +-- 确定保存路径 (任务文件夹/基础目录)
    |   +-- 创建/打开CSV文件
    |   +-- 写入液位数据
    |   |
    |   v
    |   CSV文件 (任务文件夹/channel_id_timestamp.csv)
    |
    +-- 2. 显示液位线
        |
        v
        ChannelPanelHandler._onWebSocketDetectionResult()
```

## 目录结构示例

```
database/mission_result/
├── 任务1_测试任务/
│   ├── channel1_20260327_152600.csv
│   ├── channel2_20260327_152600.csv
│   ├── channel3_20260327_152600.csv
│   ├── channel4_20260327_152600.csv
│   ├── channel5_20260327_152600.csv
│   ├── channel6_20260327_152600.csv
│   ├── channel7_20260327_152600.csv
│   └── channel8_20260327_152600.csv
└── 任务2_生产任务/
    ├── channel9_20260327_152600.csv
    ├── channel10_20260327_152600.csv
    ├── channel11_20260327_152600.csv
    ├── channel12_20260327_152600.csv
    ├── channel13_20260327_152600.csv
    ├── channel14_20260327_152600.csv
    ├── channel15_20260327_152600.csv
    └── channel16_20260327_152600.csv
```

## CSV文件格式

```csv
时间戳,液位高度(mm)
1774596360.964,95.35
1774596360.964,94.67
1774596360.964,80.50
1774596361.465,141.78
1774596361.465,91.13
1774596361.465,85.51
```

## 测试验证

### 测试脚本
`test/test_csv_writer_16channels.py`

### 测试结果
- 成功创建16个通道的CSV文件
- 前8个通道保存到"任务1_测试任务"文件夹
- 后8个通道保存到"任务2_生产任务"文件夹
- 每个通道写入3轮数据，每轮3-5个液位值
- 所有文件正确关闭，无资源泄漏

## 功能特性

### 1. 多通道并发支持
- 支持16个通道同时写入
- 每个通道独立管理CSV文件
- 线程安全的文件操作

### 2. 智能路径管理
- 根据通道任务自动选择保存路径
- 未分配任务的通道保存到基础目录
- 动态获取项目根目录

### 3. 自动资源管理
- 文件自动创建和打开
- 每次写入后立即刷新到磁盘
- 程序退出时自动关闭所有文件

### 4. 详细日志输出
- 记录每次写入操作
- 显示文件路径和写入数据量
- 异常捕获和错误提示

## 使用说明

### 启动系统
1. 启动客户端程序
2. CSV写入器自动初始化
3. 连接到WebSocket服务器

### 一键启动检测
1. 点击"一键启动"按钮
2. 服务器启动16通道检测
3. 检测结果自动推送到客户端
4. 客户端自动保存到CSV文件

### 查看结果
- CSV文件保存在 `database/mission_result/` 目录
- 按任务文件夹组织
- 可用Excel或文本编辑器打开

## 注意事项

1. 确保 `database/mission_result/` 目录有写入权限
2. CSV文件使用 `utf-8-sig` 编码，确保Excel正确显示中文
3. 每次启动检测会创建新的CSV文件，不会覆盖旧文件
4. 程序退出时会自动关闭所有CSV文件
5. 如果通道未分配任务，CSV文件保存到基础目录

## 相关文件

- `client/storage/detection_result_csv_writer.py` - CSV写入器实现
- `client/widgets/system_window.py` - 主窗口集成
- `client/storage/README.md` - 详细文档
- `test/test_csv_writer_16channels.py` - 测试脚本
