@echo off
REM 启动增强液位检测WebSocket服务器脚本
REM 在服务器192.168.0.121上运行

echo ==========================================
echo 启动增强液位检测WebSocket服务器
echo ==========================================

REM 检查当前目录
if not exist "start_websocket_server.py" (
    echo 错误: 请在server目录下运行此脚本
    pause
    exit /b 1
)

echo 检查Python环境...
python --version
where python

REM 设置环境变量
set PYTHONPATH=/home/lqj/liquid/server;%PYTHONPATH%
set LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib;%LD_LIBRARY_PATH%

echo 环境变量设置完成:
echo   PYTHONPATH: %PYTHONPATH%
echo   LD_LIBRARY_PATH: %LD_LIBRARY_PATH%

REM 检查必要的文件
echo 检查必要文件...
if not exist "websocket\enhanced_ws_server.py" (
    echo 错误: 找不到enhanced_ws_server.py
    pause
    exit /b 1
)

if not exist "websocket\detection_service.py" (
    echo 错误: 找不到detection_service.py
    pause
    exit /b 1
)

if not exist "detection\detection.py" (
    echo 错误: 找不到detection.py
    pause
    exit /b 1
)

REM 创建日志目录
if not exist "logs" mkdir logs

echo 启动增强WebSocket服务器...
echo 监听地址: 0.0.0.0:8085
echo 客户端连接地址: ws://192.168.0.121:8085
echo 按 Ctrl+C 停止服务器
echo ==========================================

REM 启动服务器
python start_websocket_server.py