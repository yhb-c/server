#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整服务端文件夹上传脚本
上传整个server文件夹到服务器，解决所有依赖问题
"""

import paramiko
import os
import time
import sys
from pathlib import Path

def upload_directory(sftp, local_path, remote_path):
    """递归上传目录"""
    try:
        # 创建远程目录
        try:
            sftp.mkdir(remote_path)
        except:
            pass  # 目录可能已存在
        
        for item in os.listdir(local_path):
            local_item = os.path.join(local_path, item)
            remote_item = remote_path + '/' + item
            
            if os.path.isfile(local_item):
                print(f"上传文件: {local_item} -> {remote_item}")
                sftp.put(local_item, remote_item)
            elif os.path.isdir(local_item):
                # 跳过不需要的目录
                if item in ['__pycache__', '.git', '.vscode', 'logs']:
                    continue
                print(f"创建目录: {remote_item}")
                upload_directory(sftp, local_item, remote_item)
                
    except Exception as e:
        print(f"上传目录 {local_path} 失败: {e}")

def upload_complete_server():
    """上传完整服务端文件夹"""
    server_ip = '192.168.0.121'
    username = 'lqj'
    password = 'admin'
    
    local_server_path = "server"
    remote_base_path = "/home/lqj/liquid"
    remote_server_path = f"{remote_base_path}/server"
    
    try:
        print(f"连接服务器 {server_ip}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=server_ip, username=username, password=password, timeout=10)
        print("✓ 服务器连接成功")
        
        # 停止现有WebSocket服务器
        print("\n停止现有WebSocket服务器...")
        ssh.exec_command("pkill -f websocket")
        ssh.exec_command("pkill -f start_websocket")
        time.sleep(2)
        
        # 强制停止占用端口8085的进程
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
        
        # 备份现有server目录
        print("\n备份现有server目录...")
        backup_path = f"{remote_base_path}/server_backup_{int(time.time())}"
        ssh.exec_command(f"mv {remote_server_path} {backup_path}")
        print(f"✓ 备份完成: {backup_path}")
        
        # 创建SFTP连接
        print("\n开始上传完整server文件夹...")
        sftp = ssh.open_sftp()
        
        # 上传整个server目录
        upload_directory(sftp, local_server_path, remote_server_path)
        
        # 创建logs目录
        try:
            sftp.mkdir(f"{remote_server_path}/logs")
        except:
            pass
        
        sftp.close()
        print("✓ 完整server文件夹上传完成")
        
        # 设置执行权限
        print("\n设置执行权限...")
        ssh.exec_command(f"chmod +x {remote_server_path}/websocket/*.py")
        ssh.exec_command(f"chmod +x {remote_server_path}/*.py")
        
        # 启动WebSocket服务器
        print("\n启动WebSocket服务器...")
        command = f"""
        cd {remote_server_path}/websocket && 
        source ~/anaconda3/bin/activate liquid && 
        nohup python start_websocket_server.py > ../logs/websocket_server.log 2>&1 &
        """
        
        stdin, stdout, stderr = ssh.exec_command(command)
        time.sleep(8)  # 等待更长时间让服务器完全启动
        
        # 检查服务器是否启动成功
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        
        if output.strip():
            print("✓ WebSocket服务器启动成功")
            print(f"服务器地址: ws://192.168.0.121:8085")
            
            # 查看服务器日志
            print("\n服务器启动日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -15 {remote_server_path}/logs/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return True
        else:
            print("✗ WebSocket服务器启动失败")
            
            # 查看错误日志
            print("\n错误日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -30 {remote_server_path}/logs/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return False
        
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("开始上传完整服务端文件夹...")
    print("这将替换服务器上的整个server目录")
    
    # 检查本地server目录是否存在
    if not os.path.exists("server"):
        print("✗ 本地server目录不存在")
        sys.exit(1)
    
    success = upload_complete_server()
    
    if success:
        print("\n✓ 完整服务端上传和启动成功")
        print("现在可以运行测试脚本验证WebSocket连接")
    else:
        print("\n✗ 服务端上传或启动失败")
        sys.exit(1)

if __name__ == "__main__":
    main()