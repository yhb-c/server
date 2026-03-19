#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上传修复的detection_service.py文件
"""

import paramiko
import sys

def upload_detection_service():
    """上传detection_service.py"""
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
        
        # 上传修复的detection_service.py
        print("\n上传修复的detection_service.py...")
        sftp = ssh.open_sftp()
        
        local_file = "server/websocket/detection_service.py"
        remote_file = f"{server_path}/websocket/detection_service.py"
        sftp.put(local_file, remote_file)
        print(f"✓ 上传完成: {local_file}")
        
        sftp.close()
        
        print("\n文件上传完成，服务器将自动重新加载模块")
        return True
        
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("上传修复的detection_service.py...")
    
    success = upload_detection_service()
    
    if success:
        print("\n✓ detection_service.py上传成功")
        print("现在可以测试RTSP连接功能")
    else:
        print("\n✗ 文件上传失败")
        sys.exit(1)

if __name__ == "__main__":
    main()