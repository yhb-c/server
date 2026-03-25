# MySQL 数据库迁移方案

将 YAML 和 CSV 文件数据迁移到 MySQL 数据库的完整解决方案。

## 目录结构

```
server/
├── database/
│   ├── schema.sql          # 数据库表结构
│   ├── migrate.go          # 数据迁移工具
│   ├── db.go              # 数据库操作封装
│   ├── config.go          # 配置加载器
│   └── config/
│       ├── database.yaml  # 数据库配置文件
│       ├── mission/       # 任务 YAML 文件
│       └── ...           # 其他配置文件
└── api_server.go          # HTTP API 服务
```

## 1. 安装 MySQL

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

### 配置 MySQL
```bash
sudo mysql_secure_installation
```

## 2. 创建数据库

```bash
# 登录 MySQL
mysql -u root -p

# 执行建表脚本
source /home/lqj/liquid/server/database/schema.sql
```

或者直接执行：
```bash
mysql -u root -p < /home/lqj/liquid/server/database/schema.sql
```

## 3. 安装 Go 依赖

```bash
cd /home/lqj/liquid/server
go get github.com/go-sql-driver/mysql
go get github.com/gin-gonic/gin
go get gopkg.in/yaml.v2
```

## 4. 配置数据库连接

编辑配置文件：
```bash
vim /home/lqj/liquid/server/database/config/database.yaml
```

修改数据库连接信息：
```yaml
database:
  host: localhost
  port: 3306
  username: root        # 修改为你的用户名
  password: your_password  # 修改为你的密码
  database: liquid_db
  charset: utf8mb4
  parseTime: true
```

## 5. 执行数据迁移

```bash
cd /home/lqj/liquid/server/database
go run migrate.go
```

迁移工具会自动：
- 迁移任务 YAML 文件到 `missions` 表
- 迁移 CSV 结果数据到 `mission_results` 表
- 迁移配置 YAML 文件到 `configs` 表

## 6. 启动 API 服务

```bash
cd /home/lqj/liquid/server
go run api_server.go
```

服务将在 `http://localhost:8080` 启动。

## API 接口文档

### 任务管理

#### 创建任务
```bash
POST /api/missions
Content-Type: application/json

{
  "task_id": "1",
  "task_name": "测试任务",
  "status": "未启动",
  "selected_channels": ["通道1", "通道2"],
  "created_time": "2026-03-25T10:00:00Z",
  "mission_result_folder_path": "/path/to/results"
}
```

#### 获取任务列表
```bash
GET /api/missions?limit=10&offset=0
```

#### 获取单个任务
```bash
GET /api/missions/1
```

#### 更新任务状态
```bash
PUT /api/missions/1/status
Content-Type: application/json

{
  "status": "进行中"
}
```

#### 删除任务
```bash
DELETE /api/missions/1
```

#### 获取任务结果
```bash
GET /api/missions/1/results?channel=通道1&region=区域1&start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z
```

#### 创建任务结果
```bash
POST /api/missions/1/results
Content-Type: application/json

{
  "channel_name": "通道1",
  "region_name": "区域1",
  "timestamp": "2026-03-25T10:00:00Z",
  "value": 1.5
}
```

### 配置管理

#### 保存配置
```bash
POST /api/configs
Content-Type: application/json

{
  "config_type": "system",
  "config_name": "main",
  "config_data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

#### 获取配置列表
```bash
GET /api/configs?type=system
```

#### 获取单个配置
```bash
GET /api/configs/system/main
```

#### 删除配置
```bash
DELETE /api/configs/system/main
```

## 数据库表结构

### missions 表
存储任务信息：
- `id`: 主键
- `task_id`: 任务 ID（唯一）
- `task_name`: 任务名称
- `status`: 任务状态
- `created_time`: 创建时间
- `mission_result_folder_path`: 结果文件夹路径

### mission_channels 表
存储任务与通道的关联关系：
- `id`: 主键
- `mission_id`: 任务 ID（外键）
- `channel_name`: 通道名称

### mission_results 表
存储任务结果数据（CSV 数据）：
- `id`: 主键
- `mission_id`: 任务 ID（外键）
- `channel_name`: 通道名称
- `region_name`: 区域名称
- `timestamp`: 时间戳
- `value`: 数值

### configs 表
存储配置数据（YAML 配置）：
- `id`: 主键
- `config_type`: 配置类型
- `config_name`: 配置名称
- `config_data`: 配置数据（JSON 格式）

## 使用示例

### 使用 curl 测试 API

```bash
# 获取任务列表
curl http://localhost:8080/api/missions

# 获取特定任务
curl http://localhost:8080/api/missions/1

# 获取任务结果（带过滤条件）
curl "http://localhost:8080/api/missions/1/results?channel=通道1&region=区域1"

# 更新任务状态
curl -X PUT http://localhost:8080/api/missions/1/status \
  -H "Content-Type: application/json" \
  -d '{"status":"进行中"}'

# 获取配置
curl http://localhost:8080/api/configs/system/main
```

## 性能优化建议

1. **索引优化**：已在表结构中添加必要的索引
2. **连接池**：已配置数据库连接池（最大 100 个连接）
3. **批量插入**：迁移工具使用事务批量插入数据
4. **查询优化**：使用预编译语句防止 SQL 注入

## 备份与恢复

### 备份数据库
```bash
mysqldump -u root -p liquid_db > liquid_db_backup.sql
```

### 恢复数据库
```bash
mysql -u root -p liquid_db < liquid_db_backup.sql
```

## 故障排查

### 连接失败
- 检查 MySQL 服务是否运行：`sudo systemctl status mysql`
- 检查用户名和密码是否正确
- 检查数据库是否存在：`SHOW DATABASES;`

### 迁移失败
- 检查文件路径是否正确
- 检查文件格式是否符合预期
- 查看日志输出的错误信息

### API 错误
- 检查数据库连接是否正常
- 查看服务器日志
- 使用 Postman 或 curl 测试接口

## 下一步

1. 添加用户认证和授权
2. 实现数据分页和排序
3. 添加数据统计和分析接口
4. 实现实时数据推送（WebSocket）
5. 添加数据导出功能
1. 数据库设计
创建用户表(users)：存储用户基本信息(user_id, username, password等)
创建配置表(user_configs)：存储用户配置信息
user_id: 关联用户
config_key: 配置项名称
config_value: 配置项值(JSON格式存储复杂配置)
config_type: 配置类型(如camera_config, model_config, display_config等)
updated_at: 最后更新时间
2. 客户端实现流程
用户登录时从服务器拉取该用户的所有配置
本地缓存配置文件，用于离线使用
用户修改配置时：
立即更新本地配置文件
通过WebSocket或HTTP API发送配置更新请求到服务器
请求包含：user_id, config_key, config_value, config_type
3. 服务端实现流程
提供配置管理API接口：
GET /api/config/:user_id - 获取用户所有配置
POST /api/config - 创建/更新配置
DELETE /api/config/:user_id/:config_key - 删除配置
接收客户端配置更新请求后：
验证用户身份
更新MySQL数据库中对应用户的配置记录
如果配置涉及服务端文件(如模型配置)，同步更新服务端对应的配置文件
4. 配置同步策略
实时同步：客户端修改立即推送到服务器
冲突处理：采用"最后写入优胜"策略，以最新时间戳为准
离线支持：客户端离线时修改本地配置，上线后批量同步到服务器
5. 服务端文件管理
为每个用户创建独立的配置文件目录：/home/lqj/liquid/user_configs/{user_id}/
当数据库配置更新时，同步生成对应的配置文件
推理服务根据user_id加载对应用户的配置文件
6. 安全考虑
配置更新需要用户身份验证
敏感配置(如密码)需要加密存储
限制配置文件大小和更新频率，防止滥用
这个方案的核心是：数据库作为配置的唯一真实来源，客户端和服务端文件都是数据库的镜像。