# CSV存储路径修改说明

## 修改内容

### 原路径
```
D:\system_client_sever\client\result
```

### 新路径
```
D:\system_client_sever\client\database\mission_result
```

## 修改文件

**文件**: `client/storage/detection_result_csv_writer.py`

**修改位置**: 第18行，`DetectionResultCSVWriter` 类的 `__init__` 方法

**修改前**:
```python
def __init__(self, save_dir: str = r"D:\system_client_sever\client\result"):
```

**修改后**:
```python
def __init__(self, save_dir: str = r"D:\system_client_sever\client\database\mission_result"):
```

## 影响范围

### 自动生效的场景

所有使用默认参数创建 `DetectionResultCSVWriter` 的地方都会自动使用新路径：

1. **NetworkCommandManager** (`client/network/command_manager.py`)
   ```python
   self.csv_writer = DetectionResultCSVWriter()  # 使用默认路径
   ```

2. **其他使用默认路径的代码**
   - 所有未指定 `save_dir` 参数的实例化

### 不受影响的场景

如果代码中显式指定了路径，则不受影响：
```python
csv_writer = DetectionResultCSVWriter(save_dir="自定义路径")  # 使用自定义路径
```

## CSV文件命名格式

文件名格式保持不变：
```
{channel_id}_{YYYYMMDD}_{HHMMSS}.csv
```

示例：
```
channel1_20260320_150637.csv
channel2_20260320_151234.csv
```

## 数据格式

CSV文件格式保持不变：
```csv
timestamp,area_0_height_mm,area_1_height_mm,area_2_height_mm
1773905222.19,120.5,135.2,98.7
1773905223.14,121.0,136.0,99.0
```

## 目录结构

```
D:\system_client_sever\client\
├── database\
│   └── mission_result\          ← 新的CSV存储目录
│       ├── channel1_20260320_150637.csv
│       ├── channel2_20260320_151234.csv
│       └── ...
└── result\                      ← 旧目录（可以删除或保留）
    └── (旧的CSV文件)
```

## 测试验证

### 步骤1: 启动系统
```bash
python main.py
```

### 步骤2: 启动检测
1. 登录系统
2. 配置并连接通道
3. 点击"开始检测"

### 步骤3: 验证CSV文件位置
检查文件是否保存到新路径：
```
D:\system_client_sever\client\database\mission_result\
```

### 预期结果
- ✅ CSV文件保存到新路径
- ✅ 文件名格式正确
- ✅ 数据格式正确

## 日志输出

启动检测后，应该看到：
```
[CSVWriter] 初始化完成，保存目录: D:\system_client_sever\client\database\mission_result
[CSVWriter] [SUCCESS] Wrote 1 records to CSV
[CSVWriter] File path: D:\system_client_sever\client\database\mission_result\channel1_20260320_150637.csv
```

## 注意事项

1. **目录权限**: 确保程序有权限在新目录创建文件
2. **磁盘空间**: 确保有足够的磁盘空间
3. **旧文件**: 旧路径的CSV文件不会自动迁移，需要手动处理
4. **备份**: 如果旧路径有重要数据，请先备份

## 迁移旧数据（可选）

如果需要迁移旧路径的CSV文件到新路径：

### Windows命令
```cmd
xcopy "D:\system_client_sever\client\result\*.csv" "D:\system_client_sever\client\database\mission_result\" /Y
```

### 或者手动复制
1. 打开 `D:\system_client_sever\client\result\`
2. 选择所有CSV文件
3. 复制到 `D:\system_client_sever\client\database\mission_result\`

## 总结

✅ **修改完成**: CSV存储路径已更新
✅ **自动生效**: 使用默认参数的代码自动使用新路径
✅ **向后兼容**: 可以通过参数指定自定义路径
✅ **目录已存在**: 新目录已创建，可以直接使用

现在重新运行系统，CSV文件将保存到新路径！
