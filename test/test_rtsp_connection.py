#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RTSP连接测试脚本
测试服务器是否能连接到RTSP相机
"""

import paramiko
import sys

def test_rtsp_connection():
    """测试RTSP连接"""
    server_ip = '192.168.0.121'
    username = 'lqj'
    password = 'admin'
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    
    try:
        print(f"连接服务器 {server_ip}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=server_ip, username=username, password=password, timeout=10)
        print("✓ 服务器连接成功")
        
        # 测试网络连通性
        print(f"\n=== 测试网络连通性 ===")
        camera_ip = '192.168.0.27'
        stdin, stdout, stderr = ssh.exec_command(f"ping -c 3 {camera_ip}")
        ping_output = stdout.read().decode('utf-8')
        print(f"Ping {camera_ip}:")
        print(ping_output)
        
        # 测试端口连通性
        print(f"\n=== 测试端口连通性 ===")
        stdin, stdout, stderr = ssh.exec_command(f"telnet {camera_ip} 8000 < /dev/null")
        telnet_output = stdout.read().decode('utf-8')
        telnet_error = stderr.read().decode('utf-8')
        print(f"Telnet {camera_ip}:8000:")
        if telnet_output:
            print(telnet_output)
        if telnet_error:
            print(f"错误: {telnet_error}")
        
        # 使用ffprobe测试RTSP流
        print(f"\n=== 测试RTSP流 ===")
        print(f"RTSP地址: {rtsp_url}")
        
        # 激活conda环境并测试RTSP
        command = f"""
        source ~/anaconda3/bin/activate liquid && 
        python -c "
import cv2
import sys
print('测试RTSP连接...')
cap = cv2.VideoCapture('{rtsp_url}')
if cap.isOpened():
    ret, frame = cap.read()
    if ret and frame is not None:
        print('✓ RTSP连接成功')
        print(f'视频分辨率: {{frame.shape[1]}}x{{frame.shape[0]}}')
    else:
        print('✗ RTSP连接失败: 无法读取视频帧')
    cap.release()
else:
    print('✗ RTSP连接失败: 无法打开视频流')
"
        """
        
        stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
        rtsp_output = stdout.read().decode('utf-8')
        rtsp_error = stderr.read().decode('utf-8')
        
        print("RTSP测试结果:")
        if rtsp_output:
            print(rtsp_output)
        if rtsp_error:
            print(f"错误: {rtsp_error}")
        
        # 检查OpenCV版本和依赖
        print(f"\n=== 检查OpenCV环境 ===")
        opencv_command = f"""
        source ~/anaconda3/bin/activate liquid && 
        python -c "
import cv2
print(f'OpenCV版本: {{cv2.__version__}}')
print(f'支持的后端: {{cv2.getBuildInformation()}}' if hasattr(cv2, 'getBuildInformation') else '无法获取构建信息')
"
        """
        
        stdin, stdout, stderr = ssh.exec_command(opencv_command)
        opencv_output = stdout.read().decode('utf-8')
        opencv_error = stderr.read().decode('utf-8')
        
        if opencv_output:
            print(opencv_output)
        if opencv_error:
            print(f"OpenCV错误: {opencv_error}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    finally:
        ssh.close()

def main():
    """主函数"""
    print("测试RTSP相机连接...")
    print("目标相机: rtsp://admin:cei345678@192.168.0.27:8000/stream1")
    
    success = test_rtsp_connection()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()