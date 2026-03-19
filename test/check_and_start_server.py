#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查并启动WebSocket服务器脚本
使用现有的WebSocket服务器，不重新部署
"""

import paramiko
import time
import sys

def check_and_start_server():
    """检查并启动WebSocket服务器"""
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
        
        # 检查端口8085是否被占用
        print("\n检查WebSocket服务器状态...")
        stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
        output = stdout.read().decode('utf-8')
        
        if output.strip():
            print(f"✓ 端口8085已被占用，PID: {output.strip()}")
            
            # 检查进程详情
            stdin, stdout, stderr = ssh.exec_command("ps aux | grep 8085")
            process_info = stdout.read().decode('utf-8')
            print(f"进程信息:\n{process_info}")
            
            return True
        else:
            print("✗ 端口8085未被占用，需要启动WebSocket服务器")
            
            # 启动现有的WebSocket服务器
            print("\n启动WebSocket服务器...")
            
            # 使用原有的启动脚本
            command = f"""
            cd {server_path} && 
            source ~/anaconda3/bin/activate liquid && 
            nohup python -m websocket.start_websocket_server > websocket_server.log 2>&1 &
            """
            
            stdin, stdout, stderr = ssh.exec_command(command)
            time.sleep(5)
            
            # 再次检查端口
            stdin, stdout, stderr = ssh.exec_command("lsof -ti:8085")
            output = stdout.read().decode('utf-8')
            
            if output.strip():
                print("✓ WebSocket服务器启动成功")
                
                # 查看启动日志
                print("\n启动日志:")
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
        print(f"✗ 操作失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("检查并启动WebSocket服务器...")
    
    success = check_and_start_server()
    
    if success:
        print("\n✓ WebSocket服务器运行正常")
        print("现在可以运行测试脚本验证连接")
    else:
        print("\n✗ WebSocket服务器启动失败")
        sys.exit(1)

if __name__ == "__main__":
    main()