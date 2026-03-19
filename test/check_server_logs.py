#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查服务器日志脚本
查看WebSocket服务器的详细日志信息
"""

import paramiko
import sys

def check_server_logs():
    """检查服务器日志"""
    server_ip = '192.168.0.121'
    username = 'lqj'
    password = 'admin'
    server_path = '/home/lqj/liquid/server'
    
    try:
        print(f"连接服务器 {server_ip}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=server_ip, username=username, password=password, timeout=10)
        print("✓ 服务器连接成功")
        
        # 检查服务器状态
        print("\n=== 服务器状态检查 ===")
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        if output.strip():
            print(f"✓ WebSocket服务器运行中，PID: {output.strip()}")
        else:
            print("✗ WebSocket服务器未运行")
            return False
        
        # 查看最新的服务器日志
        print("\n=== WebSocket服务器日志 ===")
        stdin, stdout, stderr = ssh.exec_command(f"tail -50 {server_path}/logs/websocket_server.log")
        log_output = stdout.read().decode('utf-8', errors='ignore')
        if log_output:
            print(log_output)
        else:
            print("无日志输出")
        
        # 检查进程详情
        print("\n=== 进程详情 ===")
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep websocket")
        process_info = stdout.read().decode('utf-8')
        print(process_info)
        
        # 检查网络连接
        print("\n=== 网络连接状态 ===")
        stdin, stdout, stderr = ssh.exec_command("netstat -tlnp | grep :8085")
        network_info = stdout.read().decode('utf-8')
        print(network_info)
        
        return True
        
    except Exception as e:
        print(f"✗ 检查失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("检查WebSocket服务器日志...")
    
    success = check_server_logs()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()