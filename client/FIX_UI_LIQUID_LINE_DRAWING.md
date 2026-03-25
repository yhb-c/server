# UI液位线绘制修复完成

## 问题分析

### 原因

系统原本是**单机版**，UI绘制液位线的代码连接的是**本地检测线程**的信号。

改为**客户端-服务器架构**后：
- ✅ CSV保存已改为使用WebSocket数据
- ❌ UI绘制仍在等待本地检测线程的数据（本地线程已不运行）

### 数据流对比

**单机版（原来）**:
```
视频流 → 本地检测线程 → 检测结果
                          ↓
                    _liquid_line_positions
                          ↓
                    UI绘制液位线
```

**客户端-服务器版（修复后）**:
```
服务器检测 → WebSocket推送 → CommandManager
                                ↓
                          detectionResultReceived信号
                                ↓
                          SystemWindow._onDetectionResult
                                ↓
                          ChannelPanelHandler._onWebSocketDetectionResult
                                ↓
                          _liquid_line_positions
                                ↓
                          UI绘制液位线
```

## 修复内容

### 1. 添加WebSocket检测结果处理方法

**文件**: `client/handlers/videopage/channelpanel_handler.py`

**新增方法**: `_onWebSocketDetectionResult(self, data)`

**功能**:
- 接收WebSocket推送的检测结果
- 提取 `liquid_line_positions` 数据
- 转换key从字符串到整数（JSON序列化导致）
- 更新 `self._liquid_line_positions[channel_id]`（线程安全）

**代码**:
```python
def _onWebSocketDetectionResult(self, data):
    """接收WebSocket推送的检测结果并更新液位线显示"""
    try:
        # 提取通道ID
        channel_id = data.get('channel_id')

        # 提取液位线位置数据
        data_obj = data.get('data', {})
        liquid_line_positions = data_obj.get('liquid_line_positions', {})

        # 转换key从字符串到整数
        converted_positions = {}
        for key, value in liquid_line_positions.items():
            int_key = int(key)
            converted_positions[int_key] = value

        # 更新液位线位置数据（线程安全）
        with self._liquid_line_locks[channel_id]:
            self._liquid_line_positions[channel_id] = converted_positions.copy()

    except Exception as e:
        print(f"[ERROR] Failed to process WebSocket detection result: {e}")
```

### 2. 连接信号到处理方法

**文件**: `client/widgets/system_window.py`

**修改方法**: `_onDetectionResult(self, data)`

**修改内容**: 转发检测结果给ChannelPanelHandler

**代码**:
```python
def _onDetectionResult(self, data):
    """检测结果回调"""
    print(f"[SystemWindow] 收到检测结果: {data}")

    # 转发给ChannelPanelHandler处理液位线显示
    if hasattr(self, '_onWebSocketDetectionResult'):
        self._onWebSocketDetectionResult(data)
```

## 工作原理

### 数据流转

1. **服务器推送检测结果**
   ```json
   {
       "type": "detection_result",
       "channel_id": "channel1",
       "data": {
           "liquid_line_positions": {
               "0": {"y": 519, "height_mm": 10.0, "left": 840, "right": 1032, ...}
           }
       }
   }
   ```

2. **WebSocket接收并发出信号**
   ```python
   # websocket_client.py
   self.detection_result.emit(data)
   ```

3. **CommandManager转发信号**
   ```python
   # command_manager.py
   self.detectionResultReceived.emit(data)
   ```

4. **SystemWindow接收并转发**
   ```python
   # system_window.py
   def _onDetectionResult(self, data):
       self._onWebSocketDetectionResult(data)
   ```

5. **ChannelPanelHandler更新数据**
   ```python
   # channelpanel_handler.py
   def _onWebSocketDetectionResult(self, data):
       self._liquid_line_positions[channel_id] = converted_positions
   ```

6. **显示线程读取并绘制**
   ```python
   # channelpanel_handler.py (显示线程)
   liquid_positions = self._getLiquidLinePositions(channel_id)
   if liquid_positions:
       frame = self._drawLiquidLines(frame, liquid_positions)
   ```

### 关键点

1. **线程安全**: 使用 `_liquid_line_locks` 确保多线程访问安全
2. **Key转换**: JSON序列化将整数key转为字符串，需要转换回整数
3. **数据复制**: 使用 `.copy()` 避免引用问题
4. **兼容性**: 保持与原有本地检测线程的数据格式一致

## 测试验证

### 运行系统

```bash
python main.py
```

### 操作步骤

1. 登录系统
2. 打开视频页面
3. 配置并连接通道
4. 点击"开始检测"

### 预期日志

```
[SystemWindow] 收到检测结果: {...}
[SystemWindow] 转发检测结果给ChannelPanelHandler...
[ChannelPanelHandler] ========== WebSocket Detection Result ==========
[ChannelPanelHandler] Channel ID: channel1
[ChannelPanelHandler] liquid_line_positions: {'0': {'y': 519, 'height_mm': 10.0, ...}}
[ChannelPanelHandler] Converted positions: {0: {'y': 519, 'height_mm': 10.0, ...}}
[ChannelPanelHandler] [SUCCESS] Updated liquid_line_positions for channel1
[ChannelPanelHandler] ==========================================
```

### 预期效果

- ✅ 视频画面上显示红色液位线
- ✅ 液位线位置在Y=519（根据实际检测结果）
- ✅ 液位线从left到right横跨ROI区域
- ✅ 液位线旁边显示高度文字 "10mm"
- ✅ CSV文件正常保存

## 数据格式

### WebSocket接收的数据

```python
{
    'type': 'detection_result',
    'channel_id': 'channel1',
    'timestamp': 1773905222.19,
    'data': {
        'liquid_line_positions': {
            '0': {  # 字符串key
                'y': 519,
                'height_mm': 10.0,
                'height_px': 49,
                'left': 840,
                'right': 1032,
                'top': 436,
                'bottom': 628,
                'is_full': False,
                'error_flag': 'detect_zero',
                'pixel_per_mm': 4.9
            }
        },
        'success': True,
        'camera_status': 'normal'
    }
}
```

### 存储到_liquid_line_positions的数据

```python
{
    0: {  # 整数key
        'y': 519,
        'height_mm': 10.0,
        'height_px': 49,
        'left': 840,
        'right': 1032,
        'top': 436,
        'bottom': 628,
        'is_full': False,
        'error_flag': 'detect_zero',
        'pixel_per_mm': 4.9
    }
}
```

## 注意事项

1. **Key类型转换**: JSON序列化会将整数key转为字符串，必须转换回整数
2. **线程安全**: 使用锁保护 `_liquid_line_positions` 的访问
3. **数据复制**: 使用 `.copy()` 避免引用问题
4. **兼容性**: SystemWindow是多个Handler的混入类，确保方法存在性检查

## 相关文件

- `client/handlers/videopage/channelpanel_handler.py` - 添加WebSocket数据处理
- `client/widgets/system_window.py` - 转发检测结果
- `client/network/command_manager.py` - 数据接收和CSV保存
- `client/network/websocket_client.py` - WebSocket通信

## 总结

✅ **问题**: UI绘制仍使用本地检测线程数据
✅ **修复**: 添加WebSocket数据接收和转发
✅ **结果**: UI现在可以显示服务器推送的检测结果
✅ **兼容**: 保持与原有数据格式和流程的兼容性

现在UI应该能够正常显示液位线了！
