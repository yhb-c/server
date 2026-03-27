#!/bin/bash

# 服务端数据库初始化脚本
# 在服务器上执行此脚本来创建数据库表和初始化数据

echo "开始初始化数据库..."

# 数据库连接信息（请根据实际情况修改）
DB_USER="root"
DB_PASS=""  # 请填写实际密码
DB_NAME="liquid_db"

# 检查MySQL是否运行
if ! systemctl is-active --quiet mysql; then
    echo "MySQL服务未运行，正在启动..."
    sudo systemctl start mysql
fi

# 执行建表脚本
echo "执行建表脚本..."
mysql -u $DB_USER -p$DB_PASS < /home/lqj/liquid/server/database/schema.sql

if [ $? -eq 0 ]; then
    echo "建表脚本执行成功"
else
    echo "建表脚本执行失败"
    exit 1
fi

# 执行初始化数据脚本
echo "执行初始化数据脚本..."
mysql -u $DB_USER -p$DB_PASS < /home/lqj/liquid/server/database/init_users.sql

if [ $? -eq 0 ]; then
    echo "初始化数据脚本执行成功"
else
    echo "初始化数据脚本执行失败"
    exit 1
fi

# 验证表是否创建成功
echo "验证数据库表..."
mysql -u $DB_USER -p$DB_PASS -e "USE $DB_NAME; SHOW TABLES;"

echo "数据库初始化完成！"
