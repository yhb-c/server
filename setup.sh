#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Liquid 数据库迁移和服务启动脚本 ===${NC}\n"

# 检查 MySQL 是否安装
if ! command -v mysql &> /dev/null; then
    echo -e "${RED}错误: MySQL 未安装${NC}"
    echo "请先安装 MySQL: sudo apt install mysql-server"
    exit 1
fi

# 检查 Go 是否安装
if ! command -v go &> /dev/null; then
    echo -e "${RED}错误: Go 未安装${NC}"
    echo "请先安装 Go: https://golang.org/doc/install"
    exit 1
fi

# 提示用户输入数据库信息
echo -e "${YELLOW}请输入 MySQL 配置信息:${NC}"
read -p "MySQL 主机 [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "MySQL 端口 [3306]: " DB_PORT
DB_PORT=${DB_PORT:-3306}

read -p "MySQL 用户名 [root]: " DB_USER
DB_USER=${DB_USER:-root}

read -sp "MySQL 密码: " DB_PASSWORD
echo

read -p "数据库名称 [liquid_db]: " DB_NAME
DB_NAME=${DB_NAME:-liquid_db}

# 测试数据库连接
echo -e "\n${YELLOW}测试数据库连接...${NC}"
if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1;" &> /dev/null; then
    echo -e "${GREEN}✓ 数据库连接成功${NC}"
else
    echo -e "${RED}✗ 数据库连接失败，请检查配置${NC}"
    exit 1
fi

# 创建数据库
echo -e "\n${YELLOW}创建数据库...${NC}"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
echo -e "${GREEN}✓ 数据库创建成功${NC}"

# 执行建表脚本
echo -e "\n${YELLOW}创建数据表...${NC}"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < server/database/schema.sql
echo -e "${GREEN}✓ 数据表创建成功${NC}"

# 更新配置文件
echo -e "\n${YELLOW}更新配置文件...${NC}"
cat > server/config/database.yaml <<EOF
database:
  host: $DB_HOST
  port: $DB_PORT
  username: $DB_USER
  password: $DB_PASSWORD
  database: $DB_NAME
  charset: utf8mb4
  parseTime: true
  maxOpenConns: 100
  maxIdleConns: 10
  connMaxLifetime: 3600

server:
  host: 0.0.0.0
  port: 8080
  mode: release

migration:
  mission_yaml_dir: /home/lqj/liquid/server/database/config/mission
  csv_result_dir: /home/lqj/liquid/server/database/mission_result
  config_dir: /home/lqj/liquid/server/database/config
  batch_size: 1000

logging:
  level: info
  file: /var/log/liquid/server.log
  max_size: 100
  max_backups: 10
  max_age: 30
EOF
echo -e "${GREEN}✓ 配置文件更新成功${NC}"

# 安装 Go 依赖
echo -e "\n${YELLOW}安装 Go 依赖...${NC}"
cd server
go get github.com/go-sql-driver/mysql
go get github.com/gin-gonic/gin
go get gopkg.in/yaml.v2
echo -e "${GREEN}✓ 依赖安装成功${NC}"

# 询问是否执行数据迁移
echo -e "\n${YELLOW}是否执行数据迁移？(y/n)${NC}"
read -p "> " DO_MIGRATE

if [ "$DO_MIGRATE" = "y" ] || [ "$DO_MIGRATE" = "Y" ]; then
    echo -e "\n${YELLOW}执行数据迁移...${NC}"
    cd database
    go run migrate.go
    echo -e "${GREEN}✓ 数据迁移完成${NC}"
    cd ..
fi

# 询问是否启动 API 服务
echo -e "\n${YELLOW}是否启动 API 服务？(y/n)${NC}"
read -p "> " START_SERVER

if [ "$START_SERVER" = "y" ] || [ "$START_SERVER" = "Y" ]; then
    echo -e "\n${GREEN}启动 API 服务...${NC}"
    echo -e "${YELLOW}服务将在 http://localhost:8080 启动${NC}"
    echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}\n"
    go run api_server.go
fi

echo -e "\n${GREEN}=== 完成 ===${NC}"
