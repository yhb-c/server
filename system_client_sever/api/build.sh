#!/bin/bash
# Go API服务构建脚本

echo "开始构建Go API服务..."

# 检查Go环境
if ! command -v go &> /dev/null; then
    echo "错误: Go环境未安装"
    exit 1
fi

# 进入API目录
cd "$(dirname "$0")"

# 下载依赖
echo "下载Go模块依赖..."
go mod tidy

# 构建Linux版本
echo "构建Linux版本..."
GOOS=linux GOARCH=amd64 go build -o liquid-api main.go

# 构建Windows版本
echo "构建Windows版本..."
GOOS=windows GOARCH=amd64 go build -o liquid-api.exe main.go

echo "构建完成!"
echo "Linux版本: liquid-api"
echo "Windows版本: liquid-api.exe"