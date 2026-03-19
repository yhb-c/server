#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查海康SDK测试结果
"""

import subprocess

def check_hk_test_result():
    """检查海康SDK测试结果"""
    print("=== 检查海康SDK测试结果 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 重新运行测试并保存结果到文件
    run_test_cmd = f'''ssh {username}@{server_ip} "cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH && python hk_rtsp_test.py > hk_test_result.log 2>&1"'''
    
    try:
        print("重新运行海康SDK测试...")
        result = subprocess.run(run_test_cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✓ 测试执行完成")
        else:
            print(f"✗ 测试执行失败，返回码: {result.returncode}")
        
        # 读取测试结果
        read_result_cmd = f'ssh {username}@{server_ip} "cat /home/lqj/liquid/hk_test_result.log"'
        
        result = subprocess.run(read_result_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        if result.stdout:
            print("\n海康SDK测试结果:")
            print("=" * 50)
            print(result.stdout)
            print("=" * 50)
        else:
            print("无法获取测试结果")
            
    except subprocess.TimeoutExpired:
        print("测试执行超时")
    except Exception as e:
        print(f"检查测试结果异常: {e}")

def run_simple_hk_test():
    """运行简化的海康SDK测试"""
    print("\n=== 运行简化的海康SDK测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 简化的测试命令
    simple_test_cmd = f'''ssh {username}@{server_ip} "cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH && python -c \\"
import sys
sys.path.insert(0, '/home/lqj/liquid/server/lib')
print('开始简化海康SDK测试')
try:
    from HKcapture import HKcapture
    print('✓ HKcapture导入成功')
    
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    capture = HKcapture(source=rtsp_url, username='admin', password='cei345678', debug=True)
    print('✓ HKcapture实例创建成功')
    
    if capture.open():
        print('✓ 连接打开成功')
        if capture.start_capture():
            print('✓ 捕获启动成功')
            capture.enable_yuv_queue(enabled=True)
            print('✓ YUV队列已启用')
            
            import time
            time.sleep(2)
            
            yuv_data = capture.get_yuv_data(timeout=3.0)
            if yuv_data:
                print(f'✓ 成功获取YUV数据: {yuv_data[\\\\\\\"width\\\\\\\"]}x{yuv_data[\\\\\\\"height\\\\\\\"]}')
            else:
                print('✗ 未获取到YUV数据')
            
            capture.stop_capture()
            capture.release()
            print('✓ 资源已清理')
        else:
            print('✗ 捕获启动失败')
    else:
        print('✗ 连接打开失败')
        
except Exception as e:
    print(f'✗ 测试异常: {e}')
    import traceback
    traceback.print_exc()
print('简化测试完成')
\\""'''
    
    try:
        print("执行简化海康SDK测试...")
        result = subprocess.run(simple_test_cmd, shell=True, capture_output=True, text=True, timeout=90, encoding='utf-8', errors='ignore')
        
        print(f"返回码: {result.returncode}")
        
        if result.stdout:
            print("测试输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        print("简化测试执行超时")
    except Exception as e:
        print(f"简化测试异常: {e}")

def main():
    """主函数"""
    print("开始检查海康SDK测试结果")
    
    try:
        # 1. 检查之前的测试结果
        check_hk_test_result()
        
        # 2. 运行简化测试
        run_simple_hk_test()
        
    except Exception as e:
        print(f"检查过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()