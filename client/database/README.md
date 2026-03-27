# 客户端配置管理模块

客户端配置同步管理模块，实现配置的本地缓存、服务器同步和离线支持。

## 功能特性

1. 配置本地缓存：配置数据缓存在本地JSON文件，支持离线使用
2. 服务器同步：配置修改实时同步到服务器MySQL数据库
3. 离线支持：离线期间的配置修改会在上线后批量同步
4. 配置导入导出：支持配置与YAML文件的相互转换
5. 配置类型管理：支持按类型（camera_config、model_config等）管理配置

## 目录结构

```
client/database/
├── __init__.py                  # 模块初始化
├── config_manager.py            # 配置管理器核心类
├── test_config_manager.py       # 测试脚本
└── README.md                    # 本文档
```

## 配置类型

- `camera_config`: 相机相关配置（RTSP地址、分辨率、帧率等）
- `model_config`: 模型相关配置（模型路径、置信度阈值等）
- `display_config`: 界面显示配置（FPS显示、液位线颜色等）
- `system_config`: 系统配置（服务器地址、端口等）

## 使用方法

### 1. 初始化配置管理器

```python
from database.config_manager import ConfigManager

# 初始化（使用默认公用账户"user"）
config_manager = ConfigManager(
    user_id="user",
    api_base_url="http://192.168.0.121:8084"
)
```

### 2. 从服务器拉取配置

```python
# 用户登录时拉取所有配置
success = config_manager.fetch_all_configs_from_server()
if success:
    print("配置拉取成功")
else:
    print("拉取失败，使用本地缓存")
```

### 3. 获取配置

```python
# 获取单个配置
camera_rtsp = config_manager.get_config('camera_rtsp')

# 获取指定类型的所有配置
camera_configs = config_manager.get_configs_by_type('camera_config')

# 获取所有配置
all_configs = config_manager.get_all_configs()
```

### 4. 更新配置

```python
# 更新单个配置（立即更新本地并同步到服务器）
config_value = {
    'url': 'rtsp://admin:password@192.168.0.27:8000/stream1',
    'width': 1920,
    'height': 1080,
    'fps': 25
}

success = config_manager.update_config(
    config_key='camera_rtsp',
    config_value=config_value,
    config_type='camera_config',
    description='相机RTSP流配置'
)
```

### 5. 批量更新配置

```python
configs = [
    {
        'config_key': 'camera_rtsp',
        'config_value': {...},
        'config_type': 'camera_config',
        'description': '相机配置'
    },
    {
        'config_key': 'display_ui',
        'config_value': {...},
        'config_type': 'display_config',
        'description': '显示配置'
    }
]

success = config_manager.batch_update_configs(configs)
```

### 6. 离线配置同步

```python
# 客户端重新连接服务器后，同步离线期间的配置修改
success = config_manager.sync_offline_changes()
```

### 7. 配置导入导出

```python
# 导出配置到YAML文件
config_manager.export_to_yaml(
    config_type='camera_config',
    output_path='./config/camera_config.yaml'
)

# 从YAML文件导入配置
config_manager.import_from_yaml(
    config_type='camera_config',
    yaml_path='./config/camera_config.yaml'
)
```

## 配置缓存

配置缓存文件存储在：`client/config/cache/user_{user_id}_config.json`

缓存文件格式：
```json
{
  "camera_rtsp": {
    "config_value": {
      "url": "rtsp://...",
      "width": 1920,
      "height": 1080,
      "fps": 25
    },
    "config_type": "camera_config",
    "description": "相机RTSP流配置",
    "updated_at": "2026-03-25T16:30:00"
  }
}
```

## 工作流程

### 用户登录流程
1. 客户端启动，初始化ConfigManager
2. 调用`fetch_all_configs_from_server()`从服务器拉取配置
3. 配置缓存到本地JSON文件
4. 应用程序使用缓存的配置

### 配置修改流程
1. 用户在界面修改配置
2. 调用`update_config()`更新配置
3. 立即更新本地缓存文件
4. 通过HTTP API同步到服务器
5. 服务器更新MySQL数据库

### 离线使用流程
1. 客户端离线时，配置修改只更新本地缓存
2. 服务器同步失败，但本地配置已更新
3. 客户端重新上线后，调用`sync_offline_changes()`
4. 批量同步离线期间的所有配置修改

## 测试

运行测试脚本：
```bash
cd /home/lqj/liquid/client/database
python test_config_manager.py
```

## 注意事项

1. 配置同步采用"最后写入优胜"策略，以最新时间戳为准
2. 配置值使用JSON格式存储，支持复杂数据结构
3. 本地缓存文件自动创建，无需手动管理
4. 服务器同步失败不影响本地配置使用
5. 当前使用公用账户"user"，所有客户端共享配置
