#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速修复并启动WebSocket服务器
只上传修复的文件并重启服务器
"""

import paramiko
import time
import sys

def quick_fix_and_start():
    """快速修复并启动"""
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
        ssh.exec_command("pkill -f websocket")
        time.sleep(2)
        
        # 上传修复的enhanced_ws_server.py
        print("\n上传修复的文件...")
        sftp = ssh.open_sftp()
        
        local_file = "server/websocket/enhanced_ws_server.py"
        remote_file = f"{server_path}/websocket/enhanced_ws_server.py"
        sftp.put(local_file, remote_file)
        print(f"✓ 上传完成: {local_file}")
        
        sftp.close()
        
        # 启动WebSocket服务器
        print("\n启动WebSocket服务器...")
        
        # 设置海康SDK环境变量
        sdk_lib_path = f"{server_path}/lib/lib"
        
        command = f"""
        cd {server_path}/websocket && 
        source ~/anaconda3/bin/activate liquid && 
        export LD_LIBRARY_PATH={sdk_lib_path}:$LD_LIBRARY_PATH && 
        nohup python start_websocket_server.py > ../logs/websocket_server.log 2>&1 &
        """
        
        stdin, stdout, stderr = ssh.exec_command(command)
        time.sleep(8)
        
        # 检查服务器是否启动成功
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        
        if output.strip():
            print("✓ WebSocket服务器启动成功")
            print(f"服务器地址: ws://192.168.0.121:8085")
            
            # 查看服务器日志
            print("\n服务器启动日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -15 {server_path}/logs/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return True
        else:
            print("✗ WebSocket服务器启动失败")
            
            # 查看错误日志
            print("\n错误日志:")
            stdin, stdout, stderr = ssh.exec_command(f"tail -30 {server_path}/logs/websocket_server.log")
            log_output = stdout.read().decode('utf-8')
            if log_output:
                print(log_output)
            
            return False
        
    except Exception as e:
        print(f"✗ 操作失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("快速修复并启动WebSocket服务器...")
    
    success = quick_fix_and_start()
    
    if success:
        print("\n✓ WebSocket服务器启动成功")
        print("现在可以运行测试脚本验证连接")
    else:
        print("\n✗ WebSocket服务器启动失败")
        sys.exit(1)

if __name__ == "__main__":
    main()