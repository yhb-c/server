# MySQL 数据库迁移方案

将 YAML 和 CSV 文件数据迁移到 MySQL 数据库的完整解决方案。

## 目录结构

```
server/
├── database/
│   ├── schema.sql          # 数据库表结构
│   ├── migrate.go          # 数据迁移工具
│   └── db.go              # 数据库操作封装
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

修改以下文件中的数据库连接字符串（DSN）：

### migrate.go
```go
dsn := "username:password@tcp(localhost:3306)/liquid_db?parseTime=true&charset=utf8mb4"
```

### api_server.go
```go
dsn := "username:password@tcp(localhost:3306)/liquid_db?parseTime=true&charset=utf8mb4"
```

将 `username` 和 `password` 替换为你的 MySQL 用户名和密码。

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
