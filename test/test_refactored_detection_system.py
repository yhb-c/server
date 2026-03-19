#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的检测系统
部署并测试新的detection_service.py和detection_task_manager.py
"""

import os
import sys
import subprocess
import time
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def upload_refactored_files():
    """上传重构后的文件到服务器"""
    print("=== 上传重构后的文件到服务器 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    password = "admin"
    
    # 需要上传的文件列表
    files_to_upload = [
        ("server/websocket/detection_service.py", "/home/lqj/liquid/server/websocket/detection_service.py"),
        ("server/detection/detection_task_manager.py", "/home/lqj/liquid/server/detection/detection_task_manager.py"),
        ("server/video/video_capture_factory.py", "/home/lqj/liquid/server/video/video_capture_factory.py"),
        ("server/video/hik_capture.py", "/home/lqj/liquid/server/video/hik_capture.py"),
        ("server/video/rtsp_capture.py", "/home/lqj/liquid/server/video/rtsp_capture.py"),
        ("server/websocket/config_manager.py", "/home/lqj/liquid/server/websocket/config_manager.py"),
        ("server/websocket/enhanced_ws_server.py", "/home/lqj/liquid/server/websocket/enhanced_ws_server.py")
    ]
    
    for local_file, remote_file in files_to_upload:
        if os.path.exists(local_file):
            print(f"上传文件: {local_file} -> {remote_file}")
            
            # 使用scp上传文件
            scp_cmd = f'scp "{local_file}" {username}@{server_ip}:"{remote_file}"'
            
            try:
                result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"  ✓ 上传成功: {local_file}")
                else:
                    print(f"  ✗ 上传失败: {local_file}")
                    print(f"    错误: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"  ✗ 上传超时: {local_file}")
            except Exception as e:
                print(f"  ✗ 上传异常: {local_file}, 错误: {e}")
        else:
            print(f"  ✗ 文件不存在: {local_file}")

def create_startup_script():
    """创建启动脚本"""
    print("\n=== 创建启动脚本 ===")
    
    startup_script = '''#!/bin/bash
# 启动重构后的检测系统

# 设置环境变量
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH

# 激活conda环境
source ~/anaconda3/bin/activate liquid

# 进入项目目录
cd /home/lqj/liquid/server

# 启动WebSocket服务器
echo "启动重构后的检测系统..."
python -m websocket.enhanced_ws_server

echo "检测系统启动完成"
'''
    
    # 保存启动脚本
    script_path = "test/start_refactored_system.sh"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(startup_script)
    
    print(f"启动脚本已创建: {script_path}")
    
    return script_path

def deploy_and_start_system():
    """部署并启动系统"""
    print("\n=== 部署并启动重构后的系统 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    password = "admin"
    
    # 创建启动脚本
    script_path = create_startup_script()
    
    # 上传启动脚本
    remote_script = "/home/lqj/liquid/start_refactored_system.sh"
    scp_cmd = f'scp "{script_path}" {username}@{server_ip}:"{remote_script}"'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✓ 启动脚本上传成功")
        else:
            print(f"✗ 启动脚本上传失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 上传启动脚本异常: {e}")
        return False
    
    # 设置脚本权限并执行
    ssh_commands = [
        f"chmod +x {remote_script}",
        f"cd /home/lqj/liquid && nohup {remote_script} > refactored_system.log 2>&1 &"
    ]
    
    for cmd in ssh_commands:
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        print(f"执行命令: {cmd}")
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"  ✓ 命令执行成功")
                if result.stdout:
                    print(f"    输出: {result.stdout}")
            else:
                print(f"  ✗ 命令执行失败")
                print(f"    错误: {result.stderr}")
        except Exception as e:
            print(f"  ✗ 命令执行异常: {e}")
    
    return True

def check_system_status():
    """检查系统状态"""
    print("\n=== 检查系统状态 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 检查进程状态
    check_commands = [
        "ps aux | grep enhanced_ws_server | grep -v grep",
        "netstat -tlnp | grep :8085",
        "tail -20 /home/lqj/liquid/refactored_system.log"
    ]
    
    for cmd in check_commands:
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        print(f"\n执行检查: {cmd}")
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.stdout:
                print(f"输出:\n{result.stdout}")
            if result.stderr:
                print(f"错误:\n{result.stderr}")
        except Exception as e:
            print(f"检查异常: {e}")

def test_websocket_connection():
    """测试WebSocket连接"""
    print("\n=== 测试WebSocket连接 ===")
    
    import websocket
    import threading
    import json
    
    ws_url = "ws://192.168.0.121:8085"
    
    def on_message(ws, message):
        print(f"收到消息: {message}")
    
    def on_error(ws, error):
        print(f"WebSocket错误: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print("WebSocket连接关闭")
    
    def on_open(ws):
        print("WebSocket连接成功")
        
        # 发送测试消息
        test_message = {
            "type": "load_model",
            "channel_id": "test_channel",
            "model_path": "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt",
            "device": "cuda"
        }
        
        ws.send(json.dumps(test_message))
        print(f"发送测试消息: {test_message}")
    
    try:
        ws = websocket.WebSocketApp(ws_url,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        
        # 运行WebSocket客户端
        ws.run_forever()
        
    except Exception as e:
        print(f"WebSocket测试异常: {e}")

def main():
    """主函数"""
    print("开始测试重构后的检测系统")
    
    try:
        # 1. 上传重构后的文件
        upload_refactored_files()
        
        # 2. 部署并启动系统
        if deploy_and_start_system():
            print("\n系统部署成功，等待启动...")
            time.sleep(5)
            
            # 3. 检查系统状态
            check_system_status()
            
            # 4. 测试WebSocket连接
            print("\n准备测试WebSocket连接...")
            time.sleep(2)
            test_websocket_connection()
        else:
            print("系统部署失败")
            
    except Exception as e:
        print(f"测试过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()