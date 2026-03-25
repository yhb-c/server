#!/bin/bash

# 测试配置文件是否正确

echo "=== 测试配置文件 ==="

CONFIG_FILE="/home/lqj/liquid/server/database/config/database.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

echo "✓ 配置文件存在"

# 检查必要的目录
MISSION_DIR="/home/lqj/liquid/server/database/config/mission"
CSV_DIR="/home/lqj/liquid/server/database/mission_result"

if [ -d "$MISSION_DIR" ]; then
    echo "✓ 任务配置目录存在: $MISSION_DIR"
    echo "  文件数量: $(ls -1 $MISSION_DIR/*.yaml 2>/dev/null | wc -l)"
else
    echo "❌ 任务配置目录不存在: $MISSION_DIR"
fi

if [ -d "$CSV_DIR" ]; then
    echo "✓ CSV 结果目录存在: $CSV_DIR"
    echo "  子目录数量: $(ls -1d $CSV_DIR/*/ 2>/dev/null | wc -l)"
else
    echo "❌ CSV 结果目录不存在: $CSV_DIR"
fi

echo ""
echo "=== 配置文件内容预览 ==="
head -20 "$CONFIG_FILE"

echo ""
echo "=== 测试完成 ==="
