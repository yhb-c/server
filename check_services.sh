#!/bin/bash
echo 检查服务状态...
API_PID=
if [ ! -z   ]; then
    echo API服务正在运行，PID: 
else
    echo API服务未运行
fi
INFERENCE_PID=
if [ ! -z  ]; then
    echo 推理服务正在运行，PID: 
else
    echo 推理服务未运行
fi
echo 端口监听状态:
netstat -tlnp | grep -E ':(8084|8085)' || echo 未发现服务端口监听
