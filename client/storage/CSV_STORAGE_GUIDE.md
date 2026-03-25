# 检测结果CSV存储功能使用指南

## 功能概述

客户端接收到检测结果后，会自动执行两个操作：
1. **UI绘制** - 在视频画面上显示液位线
2. **CSV存储** - 将检测结果保存到CSV文件

## 📁 存储位置

默认保存路径：`D:\system_client_sever\client\result`

文件命名格式：`{channel_id}_{timestamp}.csv`
- 例如：`channel1_20260319_121530.csv`

## 📊 CSV文件格式

### 表头

| 列名 | 说明 | 示例 |
|------|------|------|
| 时间戳 | Unix时间戳 | 1773893554.5098 |
| 日期时间 | 可读的日期时间 | 2026-03-19 12:15:30.509 |
| 通道ID | 通道标识 | channel1 |
| 区域1高度(mm) | 第1个检测区域的液位高度 | 120.50 |
| 区域2高度(mm) | 第2个检测区域的液位高度 | 135.20 |
| 区域3高度(mm) | 第3个检测区域的液位高度 | 98.70 |
| 区域4高度(mm) | 第4个检测区域的液位高度 | 110.30 |
| 区域5高度(mm) | 第5个检测区域的液位高度 | 125.80 |
| 区域6高度(mm) | 第6个检测区域的液位高度 | - |
| 区域7高度(mm) | 第7个检测区域的液位高度 | - |
| 区域8高度(mm) | 第8个检测区域的液位高度 | - |
| 平均高度(mm) | 所有有效区域的平均高度 | 118.10 |
| 最大高度(mm) | 最大液位高度 | 135.20 |
| 最小高度(mm) | 最小液位高度 | 98.70 |
| 有效区域数 | 有效检测区域的数量 | 5 |
| 备注 | 额外备注信息 | - |

### 示例数据

```csv
时间戳,日期时间,通道ID,区域1高度(mm),区域2高度(mm),区域3高度(mm),区域4高度(mm),区域5高度(mm),区域6高度(mm),区域7高度(mm),区域8高度(mm),平均高度(mm),最大高度(mm),最小高度(mm),有效区域数,备注
1773893554.5098,2026-03-19 12:15:30.509,channel1,120.50,135.20,98.70,110.30,125.80,,,118.10,135.20,98.70,5,
1773893555.6234,2026-03-19 12:15:31.623,channel1,121.30,136.10,99.20,111.00,126.50,,,118.82,136.10,99.20,5,
1773893556.7456,2026-03-19 12:15:32.745,channel1,122.10,137.00,99.80,111.70,127.20,,,119.56,137.00,99.80,5,
```

## 🚀 使用方法

### 方法1: 自动启用（推荐）

创建 `NetworkCommandManager` 时，CSV存储功能默认启用：

```python
from client.network.command_manager import NetworkCommandManager

# 创建命令管理器（CSV存储自动启用）
command_manager = NetworkCommandManager('ws://192.168.0.121:8085')

# 连接信号
command_manager.detectionResultReceived.connect(on_detection_result)

# 启动连接
command_manager.start_connection()

# 订阅通道
command_manager.send_subscribe_command('channel1')

# 启动检测
command_manager.send_detection_command('channel1', 'start_detection')

# 检测结果会自动保存到CSV文件
```

### 方法2: 自定义保存路径

```python
# 指定自定义保存路径
command_manager = NetworkCommandManager(
    server_url='ws://192.168.0.121:8085',
    enable_csv_storage=True,
    csv_save_dir=r'E:\my_data\detection_results'
)
```

### 方法3: 禁用CSV存储

```python
# 禁用CSV存储
command_manager = NetworkCommandManager(
    server_url='ws://192.168.0.121:8085',
    enable_csv_storage=False
)
```

## 📝 完整示例

```python
import sys
from pathlib import Path
from qtpy import QtWidgets
from client.network.command_manager import NetworkCommandManager

class DetectionApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # 创建命令管理器（启用CSV存储）
        self.command_manager = NetworkCommandManager(
            server_url='ws://192.168.0.121:8085',
            enable_csv_storage=True
        )

        # 连接信号
        self.command_manager.connectionStatusChanged.connect(self.on_connection)
        self.command_manager.detectionResultReceived.connect(self.on_detection_result)
        self.command_manager.liquidHeightReceived.connect(self.on_liquid_height)

        # 启动连接
        self.command_manager.start_connection()

    def on_connection(self, is_connected, message):
        if is_connected:
            print("连接成功，开始订阅和检测")
            # 订阅通道
            self.command_manager.send_subscribe_command('channel1')
            # 启动检测
            self.command_manager.send_detection_command('channel1', 'start_detection')

    def on_detection_result(self, data):
        """检测结果会自动保存到CSV"""
        print(f"收到检测结果: {data}")
        # 数据已自动保存到CSV文件

    def on_liquid_height(self, channel_id, heights):
        """液位高度数据"""
        print(f"通道 {channel_id} 液位高度: {heights}")
        # 更新UI显示液位线
        self.update_liquid_display(channel_id, heights)

    def closeEvent(self, event):
        """关闭窗口时关闭CSV文件"""
        self.command_manager.close_csv_files()
        self.command_manager.stop_connection()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DetectionApp()
    window.show()
    sys.exit(app.exec_())
```

## 🔧 管理CSV文件

### 获取CSV文件路径

```python
# 获取指定通道的CSV文件路径
csv_filepath = command_manager.get_csv_filepath('channel1')
print(f"CSV文件: {csv_filepath}")
```

### 关闭CSV文件

```python
# 关闭所有CSV文件
command_manager.close_csv_files()
```

### 禁用CSV存储

```python
# 运行时禁用CSV存储
command_manager.disable_csv_storage()
```

## 🧪 测试CSV存储功能

运行测试脚本：

```bash
python test/test_csv_storage.py
```

测试脚本会：
1. 连接到服务器
2. 订阅通道
3. 启动检测
4. 接收检测结果并保存到CSV
5. 显示CSV文件路径和内容预览

## 📊 数据分析

### 使用Python读取CSV

```python
import pandas as pd

# 读取CSV文件
df = pd.read_csv(r'D:\system_client_sever\client\result\channel1_20260319_121530.csv')

# 查看数据
print(df.head())

# 统计分析
print(f"平均高度: {df['平均高度(mm)'].mean():.2f} mm")
print(f"最大高度: {df['最大高度(mm)'].max():.2f} mm")
print(f"最小高度: {df['最小高度(mm)'].min():.2f} mm")

# 绘制曲线
import matplotlib.pyplot as plt
plt.plot(df['日期时间'], df['平均高度(mm)'])
plt.xlabel('时间')
plt.ylabel('平均高度 (mm)')
plt.title('液位高度变化曲线')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### 使用Excel打开

直接用Excel打开CSV文件即可查看和分析数据。

## 🔍 故障排查

### 问题1: CSV文件未创建

**原因**: CSV写入器初始化失败
**解决**: 检查保存目录是否有写入权限

### 问题2: 数据未保存

**原因**: CSV存储被禁用
**解决**: 确保 `enable_csv_storage=True`

### 问题3: 文件路径错误

**原因**: 路径格式不正确
**解决**: 使用原始字符串 `r'D:\path\to\dir'`

## 📚 相关文件

- **CSV写入器**: `client/storage/detection_result_csv_writer.py`
- **命令管理器**: `client/network/command_manager.py`
- **测试脚本**: `test/test_csv_storage.py`

## 💡 最佳实践

1. **及时关闭文件** - 程序退出前调用 `close_csv_files()`
2. **定期备份** - 定期备份CSV文件到其他位置
3. **监控磁盘空间** - 长时间运行会产生大量数据
4. **数据清理** - 定期清理旧的CSV文件
5. **错误处理** - 捕获CSV写入异常，避免影响主程序

## 🎯 总结

客户端接收到检测结果后会自动：
1. ✅ 在UI上绘制液位线（实时显示）
2. ✅ 保存到CSV文件（持久化存储）
3. ✅ 发射信号供其他组件使用（扩展性）

整个过程是自动的，无需额外代码，只需创建 `NetworkCommandManager` 即可。
