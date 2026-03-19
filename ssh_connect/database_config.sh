#!/bin/bash
# 数据库配置脚本 - 解决MySQL权限和Go API连接问题

echo "开始配置MySQL数据库..."

# 1. 停止MySQL服务重新配置
echo "1. 重新配置MySQL服务..."
sudo systemctl stop mysql

# 2. 启动MySQL安全模式
echo "2. 启动MySQL并重置root密码..."
sudo systemctl start mysql

# 3. 配置root用户权限
echo "3. 配置root用户权限..."
sudo mysql << 'EOF'
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';
FLUSH PRIVILEGES;
EOF

# 4. 创建液位检测数据库
echo "4. 创建液位检测数据库..."
mysql -u root -proot << 'EOF'
CREATE DATABASE IF NOT EXISTS liquid_detection CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SHOW DATABASES;
EOF

# 5. 导入数据库结构
echo "5. 导入数据库结构..."
if [ -f /home/lqj/liquid/database/schema.sql ]; then
    mysql -u root -proot liquid_detection < /home/lqj/liquid/database/schema.sql
    echo "数据库结构导入成功"
else
    echo "警告: schema.sql文件不存在，跳过结构导入"
fi

# 6. 导入初始数据
echo "6. 导入初始数据..."
if [ -f /home/lqj/liquid/database/seed.sql ]; then
    mysql -u root -proot liquid_detection < /home/lqj/liquid/database/seed.sql
    echo "初始数据导入成功"
else
    echo "警告: seed.sql文件不存在，跳过数据导入"
fi

# 7. 验证数据库配置
echo "7. 验证数据库配置..."
mysql -u root -proot liquid_detection -e "SHOW TABLES;" && echo "数据库配置验证成功" || echo "数据库配置验证失败"

# 8. 测试连接
echo "8. 测试数据库连接..."
mysql -u root -proot -e "SELECT 'MySQL连接成功' as status, NOW() as time;" && echo "数据库连接测试通过"

echo "MySQL数据库配置完成"
echo "数据库信息:"
echo "  主机: localhost"
echo "  端口: 3306"
echo "  用户: root"
echo "  密码: root"
echo "  数据库: liquid_detection"