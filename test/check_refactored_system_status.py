#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查重构后系统的状态
"""

import subprocess
import time

def check_server_status():
    """检查服务器状态"""
    print("=== 检查服务器状态 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 检查命令列表
    commands = [
        ("检查Python进程", "ps aux | grep python"),
        ("检查端口8085", "netstat -tlnp | grep 8085 || echo '端口8085未监听'"),
        ("检查日志文件", "ls -la /home/lqj/liquid/*.log"),
        ("查看最新日志", "tail -30 /home/lqj/liquid/refactored_system.log 2>/dev/null || echo '日志文件不存在'"),
        ("检查conda环境", "source ~/anaconda3/bin/activate liquid && which python && python --version"),
        ("检查项目文件", "ls -la /home/lqj/liquid/server/websocket/"),
        ("手动测试导入", "cd /home/lqj/liquid/server && source ~/anaconda3/bin/activate liquid && python -c 'import websocket.enhanced_ws_server; print(\"导入成功\")'")
    ]
    
    for desc, cmd in commands:
        print(f"\n{desc}:")
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if result.stdout:
                print(f"输出: {result.stdout}")
            if result.stderr:
                print(f"错误: {result.stderr}")
            if result.returncode != 0:
                print(f"返回码: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            print("命令执行超时")
        except Exception as e:
            print(f"执行异常: {e}")

def try_manual_start():
    """尝试手动启动服务"""
    print("\n=== 尝试手动启动服务 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 手动启动命令
    start_cmd = """
cd /home/lqj/liquid/server && 
export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH && 
source ~/anaconda3/bin/activate liquid && 
nohup python -m websocket.enhanced_ws_server > ../manual_start.log 2>&1 &
"""
    
    ssh_cmd = f'ssh {username}@{server_ip} "{start_cmd}"'
    print(f"执行启动命令...")
    
    try:
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
        print(f"启动命令执行完成，返回码: {result.returncode}")
        if result.stdout:
            print(f"输出: {result.stdout}")
        if result.stderr:
            print(f"错误: {result.stderr}")
            
        # 等待一下再检查
        time.sleep(3)
        
        # 检查是否启动成功
        check_cmd = "ps aux | grep enhanced_ws_server | grep -v grep && netstat -tlnp | grep 8085"
        ssh_check = f'ssh {username}@{server_ip} "{check_cmd}"'
        
        result = subprocess.run(ssh_check, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        if result.stdout:
            print(f"启动检查结果: {result.stdout}")
        else:
            print("服务未成功启动")
            
    except Exception as e:
        print(f"手动启动异常: {e}")

def main():
    """主函数"""
    print("检查重构后系统状态")
    
    # 1. 检查服务器状态
    check_server_status()
    
    # 2. 尝试手动启动
    try_manual_start()
    
    # 3. 再次检查状态
    print("\n=== 再次检查状态 ===")
    time.sleep(2)
    check_server_status()

if __name__ == "__main__":
    main()