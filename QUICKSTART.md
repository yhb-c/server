# 快速参考

## 文件位置（已修正）

### 配置文件
- **主配置**: `/home/lqj/liquid/server/database/config/database.yaml`
- **任务配置**: `/home/lqj/liquid/server/database/config/mission/`
- **其他配置**: `/home/lqj/liquid/server/database/config/`

### 代码文件
- **数据库操作**: `/home/lqj/liquid/server/database/db.go`
- **数据迁移**: `/home/lqj/liquid/server/database/migrate.go`
- **配置加载**: `/home/lqj/liquid/server/database/config.go`
- **API 服务**: `/home/lqj/liquid/server/api_server.go`
- **数据库表结构**: `/home/lqj/liquid/server/database/schema.sql`

### 数据文件
- **CSV 结果**: `/home/lqj/liquid/server/database/mission_result/`

## 快速启动

### 1. 一键安装（推荐）
```bash
cd /home/lqj/liquid
./setup.sh
```

### 2. 测试配置
```bash
./test_config.sh
```

### 3. 手动步骤

#### 创建数据库
```bash
mysql -u root -p < server/database/schema.sql
```

#### 修改配置
```bash
vim server/database/config/database.yaml
# 修改 username 和 password
```

#### 执行迁移
```bash
cd server/database
go run migrate.go
```

#### 启动服务
```bash
cd /home/lqj/liquid/server
go run api_server.go
```

## 常用命令

### 查看数据库
```bash
mysql -u root -p liquid_db
```

```sql
-- 查看所有表
SHOW TABLES;

-- 查看任务
SELECT * FROM missions;

-- 查看任务结果统计
SELECT
    channel_name,
    region_name,
    COUNT(*) as count,
    AVG(value) as avg_value
FROM mission_results
GROUP BY channel_name, region_name;
```

### API 测试
```bash
# 获取任务列表
curl http://localhost:8080/api/missions

# 获取特定任务
curl http://localhost:8080/api/missions/1

# 获取任务结果
curl "http://localhost:8080/api/missions/1/results?channel=通道1"
```

## 配置说明

### database.yaml 结构
```yaml
database:          # 数据库连接配置
  host: localhost
  port: 3306
  username: root
  password: your_password
  database: liquid_db

server:            # API 服务器配置
  host: 0.0.0.0
  port: 8080
  mode: release    # debug/release/test

migration:         # 数据迁移路径配置
  mission_yaml_dir: /path/to/mission
  csv_result_dir: /path/to/results
  config_dir: /path/to/config
```

## 故障排查

### 配置文件找不到
```bash
# 检查配置文件是否存在
ls -la /home/lqj/liquid/server/database/config/database.yaml

# 如果不存在，从模板创建
cp server/database/config/database.yaml.example server/database/config/database.yaml
```

### 数据库连接失败
```bash
# 测试 MySQL 连接
mysql -h localhost -u root -p

# 检查 MySQL 服务状态
sudo systemctl status mysql

# 启动 MySQL
sudo systemctl start mysql
```

### 迁移失败
```bash
# 检查数据文件是否存在
ls -la /home/lqj/liquid/server/database/config/mission/
ls -la /home/lqj/liquid/server/database/mission_result/

# 查看详细错误日志
cd /home/lqj/liquid/server/database
go run migrate.go 2>&1 | tee migrate.log
```

## 目录结构对比

### ❌ 错误的位置（已删除）
```
/home/lqj/liquid/server/config/  # 这个目录不应该存在
```

### ✅ 正确的位置
```
/home/lqj/liquid/server/database/config/  # 实际使用的配置目录
├── database.yaml                         # 数据库配置
├── mission/                              # 任务 YAML 文件
│   └── 1_1.yaml
├── annotation_result.yaml
├── channel_config.yaml
├── default_config.yaml
└── ...
```
