#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终的海康SDK测试
"""

import subprocess

def run_final_hk_test():
    """运行最终的海康SDK测试"""
    print("=== 运行最终的海康SDK测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 直接运行测试命令
    test_cmd = f'''ssh {username}@{server_ip} "
cd /home/lqj/liquid
source ~/anaconda3/bin/activate liquid
export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH

python3 -c '
import os
import sys
import time

sys.path.insert(0, \"/home/lqj/liquid/server/lib\")

print(\"=== 海康SDK RTSP测试 ===\")

try:
    from HKcapture import HKcapture
    print(\"✓ HKcapture导入成功\")
    
    rtsp_url = \"rtsp://admin:cei345678@192.168.0.27:8000/stream1\"
    print(f\"RTSP地址: {rtsp_url}\")
    
    capture = HKcapture(
        source=rtsp_url,
        username=\"admin\",
        password=\"cei345678\",
        debug=True
    )
    print(\"✓ HKcapture实例创建成功\")
    
    print(\"尝试打开连接...\")
    if capture.open():
        print(\"✓ 连接打开成功\")
        
        print(\"尝试启动捕获...\")
        if capture.start_capture():
            print(\"✓ 捕获启动成功\")
            
            capture.enable_yuv_queue(enabled=True)
            print(\"✓ YUV队列已启用\")
            
            print(\"等待数据流稳定...\")
            time.sleep(3)
            
            print(\"尝试获取YUV数据...\")
            yuv_data = capture.get_yuv_data(timeout=5.0)
            if yuv_data:
                width = yuv_data.get(\"width\", 0)
                height = yuv_data.get(\"height\", 0)
                print(f\"✓ 成功获取YUV数据: {width}x{height}\")
            else:
                print(\"✗ 未获取到YUV数据\")
            
            print(\"尝试read方法...\")
            frame = capture.read()
            if frame is not None:
                print(f\"✓ read方法成功: {frame.shape}\")
            else:
                print(\"✗ read方法返回None\")
            
            capture.stop_capture()
            capture.release()
            print(\"✓ 资源已清理\")
            
        else:
            print(\"✗ 捕获启动失败\")
            capture.release()
    else:
        print(\"✗ 连接打开失败\")
        
except Exception as e:
    print(f\"✗ 测试异常: {e}\")
    import traceback
    traceback.print_exc()

print(\"测试完成\")
'
"'''
    
    try:
        print("执行海康SDK RTSP测试...")
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=150, encoding='utf-8', errors='ignore')
        
        print(f"返回码: {result.returncode}")
        
        if result.stdout:
            print("测试输出:")
            print("=" * 60)
            print(result.stdout)
            print("=" * 60)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
            
        return result.returncode == 0
            
    except subprocess.TimeoutExpired:
        print("测试执行超时")
        return False
    except Exception as e:
        print(f"测试异常: {e}")
        return False

def main():
    """主函数"""
    print("开始最终海康SDK测试")
    
    success = run_final_hk_test()
    
    if success:
        print("\n海康SDK RTSP捕获测试成功完成")
    else:
        print("\n海康SDK RTSP捕获测试失败")

if __name__ == "__main__":
    main()