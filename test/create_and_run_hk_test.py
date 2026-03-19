#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在服务器上创建并运行海康SDK测试
"""

import subprocess

def create_and_run_hk_test():
    """在服务器上创建并运行海康SDK测试"""
    print("=== 在服务器上创建并运行海康SDK测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 创建测试脚本内容
    test_script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康SDK RTSP捕获测试
"""

import os
import sys
import time

# 设置环境
lib_path = "/home/lqj/liquid/server/lib/lib"
os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"
sys.path.insert(0, "/home/lqj/liquid/server/lib")

print("=== 海康SDK RTSP捕获测试 ===")
print(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH')}")

try:
    # 导入HKcapture
    from HKcapture import HKcapture
    print("✓ HKcapture导入成功")
    
    # 相机参数
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    print(f"RTSP地址: {rtsp_url}")
    
    # 创建捕获器实例
    capture = HKcapture(
        source=rtsp_url,
        username="admin",
        password="cei345678",
        port=8000,
        channel=1,
        fps=25,
        debug=True
    )
    print("✓ HKcapture实例创建成功")
    
    # 打开连接
    print("尝试打开连接...")
    if capture.open():
        print("✓ 连接打开成功")
        
        # 启动捕获
        print("尝试启动捕获...")
        if capture.start_capture():
            print("✓ 捕获启动成功")
            
            # 启用YUV队列
            capture.enable_yuv_queue(enabled=True, interval=0.1)
            print("✓ YUV队列已启用")
            
            # 等待数据流稳定
            print("等待数据流稳定...")
            time.sleep(3)
            
            # 测试获取YUV数据
            print("测试获取YUV数据...")
            success_count = 0
            for i in range(5):
                try:
                    yuv_data = capture.get_yuv_data(timeout=2.0)
                    if yuv_data:
                        success_count += 1
                        print(f"  第{i+1}次: 成功获取YUV数据 {yuv_data['width']}x{yuv_data['height']}")
                    else:
                        print(f"  第{i+1}次: YUV数据为空")
                except Exception as e:
                    print(f"  第{i+1}次: 获取YUV数据异常 - {e}")
                
                time.sleep(0.5)
            
            print(f"YUV数据获取成功率: {success_count}/5")
            
            # 测试read方法
            print("\\n测试read方法...")
            read_success_count = 0
            for i in range(3):
                try:
                    frame = capture.read()
                    if frame is not None:
                        read_success_count += 1
                        print(f"  第{i+1}次: read成功 {frame.shape}")
                    else:
                        print(f"  第{i+1}次: read返回None")
                except Exception as e:
                    print(f"  第{i+1}次: read异常 - {e}")
                
                time.sleep(0.5)
            
            print(f"read方法成功率: {read_success_count}/3")
            
            # 停止捕获
            print("\\n停止捕获...")
            capture.stop_capture()
            print("✓ 捕获已停止")
            
            # 释放资源
            capture.release()
            print("✓ 资源已释放")
            
            # 输出测试结果
            print("\\n=== 测试结果 ===")
            if success_count > 0 or read_success_count > 0:
                print("✓ 海康SDK RTSP捕获测试成功")
            else:
                print("✗ 海康SDK RTSP捕获测试失败")
                
        else:
            print("✗ 捕获启动失败")
            capture.release()
    else:
        print("✗ 连接打开失败")
        
except Exception as e:
    print(f"✗ 测试异常: {e}")
    import traceback
    traceback.print_exc()

print("\\n测试完成")
'''
    
    # 步骤1: 在服务器上创建测试脚本
    print("步骤1: 在服务器上创建测试脚本")
    
    create_script_cmd = f'''ssh {username}@{server_ip} "cat > /home/lqj/liquid/hk_rtsp_test.py << 'EOF'
{test_script_content}
EOF"'''
    
    try:
        result = subprocess.run(create_script_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✓ 测试脚本创建成功")
        else:
            print(f"✗ 测试脚本创建失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 创建脚本异常: {e}")
        return False
    
    # 步骤2: 设置脚本权限
    print("步骤2: 设置脚本权限")
    chmod_cmd = f'ssh {username}@{server_ip} "chmod +x /home/lqj/liquid/hk_rtsp_test.py"'
    
    try:
        result = subprocess.run(chmod_cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print("✓ 脚本权限设置成功")
        else:
            print(f"✗ 脚本权限设置失败: {result.stderr}")
    except Exception as e:
        print(f"✗ 设置权限异常: {e}")
    
    # 步骤3: 运行测试脚本
    print("步骤3: 运行海康SDK测试")
    
    run_cmd = f'''ssh {username}@{server_ip} "cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH && python hk_rtsp_test.py"'''
    
    try:
        print("执行海康SDK RTSP捕获测试...")
        result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True, timeout=180, encoding='utf-8', errors='ignore')
        
        print(f"返回码: {result.returncode}")
        
        if result.stdout:
            print("测试输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("✗ 测试执行超时")
        return False
    except Exception as e:
        print(f"✗ 测试执行异常: {e}")
        return False

def main():
    """主函数"""
    print("开始在服务器上创建并运行海康SDK测试")
    
    try:
        success = create_and_run_hk_test()
        if success:
            print("\n海康SDK测试执行完成")
        else:
            print("\n海康SDK测试执行失败")
    except Exception as e:
        print(f"测试过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()