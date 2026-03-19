#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket服务器修复部署脚本
修复导入路径问题并重启增强WebSocket服务器
"""

import paramiko
import time
import sys
from pathlib import Path

def deploy_websocket_fix():
    """部署WebSocket修复"""
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
        
        # 停止现有WebSocket服务器
        print("\n停止现有WebSocket服务器...")
        stdin, stdout, stderr = ssh.exec_command("pkill -f websocket")
        time.sleep(2)
        
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        if output.strip():
            pids = output.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"强制停止进程 PID: {pid}")
                    ssh.exec_command(f"kill -9 {pid}")
        
        time.sleep(3)
        print("✓ 旧服务器已停止")
        
        # 上传修复的启动脚本
        print("\n上传修复的启动脚本...")
        sftp = ssh.open_sftp()
        
        local_file = "server/websocket/start_websocket_server.py"
        remote_file = f"{server_path}/websocket/start_websocket_server.py"
        sftp.put(local_file, remote_file)
        print(f"✓ 上传完成: {local_file}")
        
        # 上传修复的detection_service.py
        local_file = "server/websocket/detection_service.py"
        remote_file = f"{server_path}/websocket/detection_service.py"
        sftp.put(local_file, remote_file)
        print(f"✓ 上传完成: {local_file}")
        
        sftp.close()
        
        # 启动增强WebSocket服务器
        print("\n启动增强WebSocket服务器...")
        command = f"""
        cd {server_path}/websocket && 
        source ~/anaconda3/bin/activate liquid && 
        nohup python start_websocket_server.py > ../websocket_server.log 2>&1 &
        """
        
        stdin, stdout, stderr = ssh.exec_command(command)
        time.sleep(5)
        
        # 检查服务器是否启动成功
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        
        if output.strip():
            print("✓ 增强WebSocket服务器启动成功")
            
            # 查看服务器日志
            print("\n服务器启动日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -10 {server_path}/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return True
        else:
            print("✗ WebSocket服务器启动失败")
            
            # 查看错误日志
            print("\n错误日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -20 {server_path}/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return False
        
    except Exception as e:
        print(f"✗ 部署失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("开始WebSocket服务器修复部署...")
    
    success = deploy_websocket_fix()
    
    if success:
        print("\n✓ WebSocket服务器修复部署成功")
        print("现在可以运行测试脚本验证连接")
    else:
        print("\n✗ WebSocket服务器修复部署失败")
        sys.exit(1)

if __name__ == "__main__":
    main()