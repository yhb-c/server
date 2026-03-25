# 客户端检测结果处理流程修复方案

## 问题分析

### 当前问题

1. **服务器发送完整数据**：服务器已经发送了完整的 `liquid_line_positions` 数据
2. **客户端只提取heights**：`command_manager.py` 只提取了 `heights` 列表
3. **UI无法绘制**：`ChannelPanel` 需要完整的 `liquid_line_positions` 才能绘制液位线

### 数据流转

```
服务器 → WebSocket → CommandManager → ChannelPanel
         (完整数据)    (只提取heights)   (需要liquid_line_positions)
```

## 修复方案

### 方案1：修改CommandManager（推荐）

修改 `command_manager.py` 的 `_on_detection_result` 方法：

1. 提取完整的 `liquid_line_positions`
2. 发出新信号 `liquidLinePositionsReceived`
3. 保持 `liquidHeightReceived` 信号用于兼容性

#### 代码修改

```python
class NetworkCommandManager(QtCore.QObject):
    # 信号定义
    connectionStatusChanged = QtCore.Signal(bool, str)
    detectionResultReceived = QtCore.Signal(dict)
    commandResponseReceived = QtCore.Signal(str, dict)
    liquidHeightReceived = QtCore.Signal(str, list)  # 保留：用于CSV存储
    liquidLinePositionsReceived = QtCore.Signal(str, dict)  # 新增：用于UI绘制

    def _on_detection_result(self, data):
        """检测结果处理"""
        print(f"[CommandManager] ========== Detection Result Processing Start ==========")

        if data.get('type') != 'detection_result':
            print(f"[CommandManager] [WARN] Message type is not detection_result: {data.get('type')}")
            self.detectionResultReceived.emit(data)
            return

        channel_id = data.get('channel_id')
        data_obj = data.get('data', {})

        # 1. 提取完整的 liquid_line_positions（用于UI绘制）
        liquid_line_positions = data_obj.get('liquid_line_positions', {})
        print(f"[CommandManager] Extracted liquid_line_positions: {liquid_line_positions}")

        # 2. 从 liquid_line_positions 提取 heights（用于CSV存储）
        heights = []
        if isinstance(liquid_line_positions, dict):
            for key in sorted(liquid_line_positions.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                position_data = liquid_line_positions[key]
                if isinstance(position_data, dict):
                    height_mm = position_data.get('height_mm', 0)
                    heights.append(height_mm)

        print(f"[CommandManager] Extracted heights: {heights}")

        if not channel_id:
            print(f"[CommandManager] [WARN] channel_id is empty")
            return

        # 3. 发送 liquid_line_positions 信号（用于UI绘制）
        if liquid_line_positions:
            print(f"[CommandManager] Emitting liquidLinePositionsReceived signal...")
            self.liquidLinePositionsReceived.emit(channel_id, liquid_line_positions)
            print(f"[CommandManager] [OK] liquidLinePositionsReceived signal emitted")

        # 4. 发送 heights 信号（用于兼容性）
        if heights:
            print(f"[CommandManager] Emitting liquidHeightReceived signal...")
            self.liquidHeightReceived.emit(channel_id, heights)
            print(f"[CommandManager] [OK] liquidHeightReceived signal emitted")

        # 5. 保存到CSV文件
        if self.csv_writer and heights:
            print(f"[CommandManager] Saving to CSV...")
            try:
                timestamp = data.get('timestamp')
                self.csv_writer.write_detection_result(channel_id, heights, timestamp)
                print(f"[CommandManager] [SUCCESS] Detection result saved to CSV")
                csv_path = self.csv_writer.get_filepath(channel_id)
                if csv_path:
                    print(f"[CommandManager] CSV file path: {csv_path}")
            except Exception as e:
                print(f"[CommandManager] [FAIL] CSV save failed: {e}")
                import traceback
                print(f"[CommandManager] Exception traceback: {traceback.format_exc()}")

        # 6. 转发完整检测结果信号
        self.detectionResultReceived.emit(data)
        print(f"[CommandManager] ========== Detection Result Processing Complete ==========\n")
```

### 方案2：在ChannelPanel中连接信号

修改 `ChannelPanel` 或其父组件，连接 `liquidLinePositionsReceived` 信号：

```python
# 在VideoPage或MainWindow中
command_manager.liquidLinePositionsReceived.connect(self._on_liquid_line_positions)

def _on_liquid_line_positions(self, channel_id: str, liquid_line_positions: dict):
    """处理液位线位置数据"""
    print(f"[VideoPage] Received liquid line positions for {channel_id}")

    # 找到对应的ChannelPanel
    channel_panel = self.get_channel_panel(channel_id)
    if channel_panel:
        # 获取视频尺寸（从通道配置或视频流）
        video_width = 1920  # 从配置获取
        video_height = 1080  # 从配置获取

        # 更新液位线显示
        channel_panel.updateLiquidLines(
            liquid_line_positions,
            is_new_data=True,
            video_width=video_width,
            video_height=video_height
        )
```

## 实现步骤

### 步骤1：修改CommandManager

文件：`client/network/command_manager.py`

1. 添加新信号 `liquidLinePositionsReceived`
2. 修改 `_on_detection_result` 方法提取 `liquid_line_positions`
3. 发出新信号

### 步骤2：连接信号到UI

文件：需要找到创建 `NetworkCommandManager` 的地方

1. 连接 `liquidLinePositionsReceived` 信号
2. 在信号处理函数中调用 `ChannelPanel.updateLiquidLines()`

### 步骤3：测试验证

1. 运行服务器
2. 运行客户端
3. 启动检测
4. 观察：
   - 控制台日志显示 `liquid_line_positions` 被正确提取
   - UI上显示红色液位线
   - CSV文件正确保存高度数据

## 数据格式示例

### 服务器发送的数据

```json
{
    "type": "detection_result",
    "channel_id": "channel1",
    "timestamp": 1773893554.5098188,
    "data": {
        "liquid_line_positions": {
            "0": {
                "y": 450,
                "height_mm": 120.5,
                "height_px": 180,
                "left": 100,
                "right": 300,
                "top": 200,
                "bottom": 630,
                "is_full": false,
                "error_flag": null,
                "pixel_per_mm": 1.5,
                "valid": true
            }
        },
        "success": true
    }
}
```

### CommandManager提取的数据

```python
# 用于UI绘制
liquid_line_positions = {
    0: {
        'y': 450,
        'height_mm': 120.5,
        'left': 100,
        'right': 300,
        'top': 200,
        'bottom': 630,
        'valid': True,
        ...
    }
}

# 用于CSV存储
heights = [120.5, 135.2, 98.7]
```

### ChannelPanel接收的数据

```python
# updateLiquidLines() 方法接收
liquid_positions = {
    0: {
        'y': 450,
        'height_mm': 120.5,
        'left': 100,
        'right': 300,
        ...
    }
}
```

## 注意事项

1. **字典key类型**：服务器发送的key是字符串 `"0"`, `"1"`，需要转换为整数
2. **视频尺寸**：需要从通道配置或视频流获取原始视频尺寸
3. **坐标系统**：`liquid_line_positions` 中的坐标是原始视频坐标，UI绘制时需要缩放
4. **valid字段**：检查 `valid` 字段决定是否绘制该液位线
5. **CSV存储**：只需要 `height_mm` 字段，其他字段不保存

## 兼容性

- 保留 `liquidHeightReceived` 信号，确保现有代码不受影响
- 新增 `liquidLinePositionsReceived` 信号，用于UI绘制
- CSV存储继续使用 `heights` 列表
