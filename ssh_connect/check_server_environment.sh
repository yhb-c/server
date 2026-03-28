#!/bin/bash
# 服务器环境检测脚本

echo "检测服务器环境..."
echo "检测时间: $(date)"
echo "=" * 60

# 1. 系统信息
echo "1. 系统信息"
echo "-" * 40
echo "操作系统: $(lsb_release -d | cut -f2)"
echo "内核版本: $(uname -r)"
echo "架构: $(uname -m)"
echo "主机名: $(hostname)"
echo "IP地址: $(hostname -I | awk '{print $1}')"
echo

# 2. 服务状态检查
echo "2. 服务状态检查"
echo "-" * 40

# MySQL服务
if systemctl is-active --quiet mysql; then
    echo "✓ MySQL服务: 运行中"
    mysql_port=$(netstat -tlnp 2>/dev/null | grep :3306 | wc -l)
    if [ $mysql_port -gt 0 ]; then
        echo "✓ MySQL端口3306: 开放"
    else
        echo "✗ MySQL端口3306: 未开放"
    fi
else
    echo "✗ MySQL服务: 未运行"
fi

# Go API服务
api_process=$(ps aux | grep liquid-api | grep -v grep | wc -l)
if [ $api_process -gt 0 ]; then
    echo "✓ Go API服务: 运行中"
    api_port=$(netstat -tlnp 2>/dev/null | grep :8084 | wc -l)
    if [ $api_port -gt 0 ]; then
        echo "✓ Go API端口8084: 开放"
    else
        echo "✗ Go API端口8084: 未开放"
    fi
else
    echo "✗ Go API服务: 未运行"
fi

# Python推理服务
inference_process=$(ps aux | grep "python.*inference" | grep -v grep | wc -l)
if [ $inference_process -gt 0 ]; then
    echo "✓ Python推理服务: 运行中"
    inference_port=$(netstat -tlnp 2>/dev/null | grep :8085 | wc -l)
    if [ $inference_port -gt 0 ]; then
        echo "✓ 推理服务端口8085: 开放"
    else
        echo "✗ 推理服务端口8085: 未开放"
    fi
else
    echo "✗ Python推理服务: 未运行"
fi

echo

# 3. 环境检查
echo "3. 环境检查"
echo "-" * 40

# Conda环境
if command -v conda &> /dev/null; then
    echo "✓ Conda: 已安装"
    if conda info --envs | grep -q liquid; then
        echo "✓ liquid环境: 存在"
    else
        echo "✗ liquid环境: 不存在"
    fi
else
    echo "✗ Conda: 未安装"
fi

# Go环境
if command -v go &> /dev/null; then
    echo "✓ Go: 已安装 ($(go version | awk '{print $3}'))"
else
    echo "✗ Go: 未安装"
fi

# Python环境
if command -v python &> /dev/null; then
    echo "✓ Python: 已安装 ($(python --version 2>&1))"
else
    echo "✗ Python: 未安装"
fi

echo

# 4. 文件检查
echo "4. 关键文件检查"
echo "-" * 40

files=(
    "/home/lqj/liquid/server/network/api/liquid-api"
    "/home/lqj/liquid/start_inference_server.py"
    "/home/lqj/liquid/database/schema.sql"
    "/home/lqj/liquid/database/seed.sql"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file: 存在"
    else
        echo "✗ $file: 不存在"
    fi
done

echo

# 5. 网络连接测试
echo "5. 网络连接测试"
echo "-" * 40

# 测试端口连接
ports=(3306 8084 8085)
for port in "${ports[@]}"; do
    if nc -z localhost $port 2>/dev/null; then
        echo "✓ 端口$port: 可连接"
    else
        echo "✗ 端口$port: 不可连接"
    fi
done

echo
echo "=" * 60
echo "环境检测完成"