#!/bin/bash

# 设置海康SDK库路径
export LD_LIBRARY_PATH="/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH"

echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo ""

# 运行测试
cd /home/lqj/liquid/server
python3 test_rtsp_capture.py
