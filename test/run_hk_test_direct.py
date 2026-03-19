#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接在服务器上运行海康SDK测试
"""

import subprocess

def run_direct_hk_test():
    """直接在服务器上运行海康SDK测试"""
    print("=== 直接在服务器上运行海康SDK测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 直接在SSH中运行测试命令
    test_commands = '''
cd /home/lqj/liquid
source ~/anaconda3/bin/activate liquid
export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH

python3 -c "
import os
import sys
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 海康SDK测试 ===')

try:
    from HKcapture import HKcapture
    print('✓ HKcapture导入成功')
    
    # 创建捕获器实例
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    capture = HKcapture(
        source=rtsp_url,
        username='admin',
        password='cei345678',
        debug=True
    )
    print('✓ HKcapture实例创建成功')
    
    # 尝试打开连接
    print('尝试打开连接...')
    if capture.open():
        print('✓ 连接打开成功')
        
        # 尝试启动捕获
        print('尝试启动捕获...')
        if capture.start_capture():
            print('✓ 捕获启动成功')
            
            # 启用YUV队列
            capture.enable_yuv_queue(enabled=True)
            print('✓ YUV队列已启用')
            
            import time
            time.sleep(2)  # 等待数据流稳定
            
            # 尝试获取一帧数据
            print('尝试获取帧数据...')
            yuv_data = capture.get_yuv_data(timeout=5.0)
            if yuv_data:
                print(f'✓ 成功获取YUV数据: {yuv_data[\"width\"]}x{yuv_data[\"height\"]}')
            else:
                print('✗ 未获取到YUV数据')
            
            # 测试read方法
            print('测试read方法...')
            frame = capture.read()
            if frame is not None:
                print(f'✓ read方法成功: {frame.shape}')
            else:
                print('✗ read方法返回None')
            
            # 清理资源
            capture.stop_capture()
            capture.release()
            print('✓ 资源已清理')
            
        else:
            print('✗ 捕获启动失败')
            capture.release()
    else:
        print('✗ 连接打开失败')
        
except Exception as e:
    print(f'✗ 测试异常: {e}')
    import traceback
    traceback.print_exc()
"
'''
    
    ssh_cmd = f'ssh {username}@{server_ip} "{test_commands}"'
    
    try:
        print("执行海康SDK测试...")
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=120, encoding='utf-8', errors='ignore')
        
        print(f"返回码: {result.returncode}")
        if result.stdout:
            print("测试输出:")
            print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        print("测试执行超时")
    except Exception as e:
        print(f"测试执行异常: {e}")

def main():
    """主函数"""
    print("开始直接运行海康SDK测试")
    run_direct_hk_test()

if __name__ == "__main__":
    main()