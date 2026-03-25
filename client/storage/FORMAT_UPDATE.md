# CSV数据格式更新完成

## ✅ 已更新为简洁格式

CSV文件格式已更新为：**时间戳 + 液位高度**

### 新格式

```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
```

### 特点

1. **简洁** - 只有2列：时间戳和液位高度
2. **灵活** - 每个液位高度值占一行，支持任意数量的检测区域
3. **易处理** - 标准CSV格式，易于分析

## 📝 示例

假设检测结果包含3个区域的液位高度：`[120.5, 135.2, 98.7]`

CSV文件内容：
```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
```

下一次检测：`[121.3, 136.1, 99.2]`

追加到CSV：
```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
1773897360.823456,121.3
1773897360.823456,136.1
1773897360.823456,99.2
```

## 🚀 使用方法

无需修改代码，格式已自动更新：

```python
from client.network.command_manager import NetworkCommandManager

# 创建命令管理器（CSV存储自动启用）
command_manager = NetworkCommandManager('ws://192.168.0.121:8085')

# 正常使用
command_manager.start_connection()
command_manager.send_subscribe_command('channel1')
command_manager.send_detection_command('channel1', 'start_detection')

# 检测结果会自动保存为新格式的CSV
```

## 📊 数据分析

### 使用Python读取

```python
import pandas as pd

# 读取CSV
df = pd.read_csv(r'D:\system_client_sever\client\result\channel1_20260319_131559.csv')

# 按时间戳分组，计算每次检测的平均高度
avg_by_time = df.groupby('时间戳')['液位高度(mm)'].mean()
print(avg_by_time)

# 统计每个时间点的检测区域数
count_by_time = df.groupby('时间戳')['液位高度(mm)'].count()
print(count_by_time)
```

### 使用Excel

直接用Excel打开CSV文件，可以：
- 筛选特定时间戳的数据
- 使用数据透视表分析
- 绘制图表

## 📁 文件位置

- **保存路径**: `D:\system_client_sever\client\result`
- **文件命名**: `{channel_id}_{timestamp}.csv`
- **示例**: `channel1_20260319_131559.csv`

## 📚 相关文档

- [CSV格式详细说明](./CSV_FORMAT.md)
- [快速参考](./QUICK_REFERENCE.md)
- [使用指南](./CSV_STORAGE_GUIDE.md)

## 🎯 总结

CSV格式已更新为最简洁的"时间戳,液位高度"格式，满足你的需求！

每次接收到检测结果，会自动：
1. ✅ 在UI上绘制液位线
2. ✅ 保存到CSV文件（新格式）

一切都是自动的，无需修改代码！
