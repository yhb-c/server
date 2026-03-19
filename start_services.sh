#!/bin/bash
cd /home/lqj/liquid
source /home/lqj/anaconda3/bin/activate liquid
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:
echo 启动API服务...
cd api
nohup ./liquid-api > ../logs/api.log 2>&1 &
API_PID=$!
echo API服务已启动，PID: 
cd ../server
echo 启动推理服务...
nohup python main.py > ../logs/inference.log 2>&1 &
INFERENCE_PID=$!
echo 推理服务已启动，PID: 
echo 所有服务已启动
echo API服务: http://192.168.0.121:8084
echo 推理服务: ws://192.168.0.121:8085
