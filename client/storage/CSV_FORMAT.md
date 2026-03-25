# CSV数据格式说明

## 📊 CSV文件格式

### 表头
```csv
时间戳,液位高度(mm)
```

### 数据格式

每个液位高度值占一行：

```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
1773897360.823456,121.3
1773897360.823456,136.1
1773897360.823456,99.2
```

### 说明

- **时间戳**: Unix时间戳（浮点数），精确到微秒
- **液位高度**: 液位高度值，单位毫米，保留2位小数
- **多个区域**: 如果一次检测有多个区域的液位高度，每个高度占一行，使用相同的时间戳

## 📁 文件命名

格式：`{channel_id}_{timestamp}.csv`

示例：
- `channel1_20260319_131559.csv`
- `channel2_20260319_132030.csv`

## 💾 保存位置

默认保存路径：`D:\system_client_sever\client\result`

## 📝 示例数据

假设一次检测返回3个区域的液位高度 `[120.5, 135.2, 98.7]`，CSV文件内容为：

```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
```

下一次检测返回3个区域的液位高度 `[121.3, 136.1, 99.2]`，追加到CSV：

```csv
时间戳,液位高度(mm)
1773897359.709856,120.5
1773897359.709856,135.2
1773897359.709856,98.7
1773897360.823456,121.3
1773897360.823456,136.1
1773897360.823456,99.2
```

## 🔄 数据处理

### 使用Python读取

```python
import pandas as pd

# 读取CSV文件
df = pd.read_csv(r'D:\system_client_sever\client\result\channel1_20260319_131559.csv')

# 查看数据
print(df.head())

# 按时间戳分组（同一时间戳的多个高度值）
grouped = df.groupby('时间戳')

# 计算每个时间点的统计数据
stats = grouped['液位高度(mm)'].agg(['mean', 'max', 'min', 'count'])
print(stats)

# 绘制曲线（使用平均值）
import matplotlib.pyplot as plt
avg_heights = grouped['液位高度(mm)'].mean()
plt.plot(avg_heights.index, avg_heights.values)
plt.xlabel('时间戳')
plt.ylabel('平均液位高度 (mm)')
plt.title('液位高度变化曲线')
plt.show()
```

### 转换时间戳为可读格式

```python
from datetime import datetime

# 读取CSV
df = pd.read_csv(r'D:\system_client_sever\client\result\channel1_20260319_131559.csv')

# 转换时间戳为日期时间
df['日期时间'] = pd.to_datetime(df['时间戳'], unit='s')

# 保存为新的CSV
df.to_csv('channel1_with_datetime.csv', index=False, encoding='utf-8-sig')
```

## 📊 数据分析示例

### 计算每次检测的平均高度

```python
import pandas as pd

df = pd.read_csv(r'D:\system_client_sever\client\result\channel1_20260319_131559.csv')

# 按时间戳分组，计算平均值
avg_by_time = df.groupby('时间戳')['液位高度(mm)'].mean().reset_index()
avg_by_time.columns = ['时间戳', '平均液位高度(mm)']

print(avg_by_time)
```

### 统计每个时间点的区域数量

```python
# 统计每个时间戳有多少个液位高度值（即多少个检测区域）
count_by_time = df.groupby('时间戳')['液位高度(mm)'].count().reset_index()
count_by_time.columns = ['时间戳', '检测区域数']

print(count_by_time)
```

## 💡 优势

1. **简洁** - 只有两列，易于理解和处理
2. **灵活** - 支持任意数量的检测区域
3. **标准** - 标准CSV格式，兼容所有工具
4. **高效** - 文件大小小，读写速度快
5. **易分析** - 可以轻松使用pandas、Excel等工具分析

## 🔧 自定义

如果需要添加其他字段，可以修改 `detection_result_csv_writer.py` 中的表头和数据行。
