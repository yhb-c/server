#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只上传关键的.so文件和HKcapture.py
"""

import os
import subprocess
import time

def upload_essential_files():
    """上传必要的文件"""
    print("=== 上传必要的文件到服务端 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 要上传的文件列表
    files_to_upload = [
        # Python文件
        ("server/lib/HKcapture.py", "/home/lqj/liquid/server/lib/HKcapture.py"),
        ("server/lib/HCNetSDK.py", "/home/lqj/liquid/server/lib/HCNetSDK.py"),
        ("server/lib/PlayCtrl.py", "/home/lqj/liquid/server/lib/PlayCtrl.py"),
        
        # 关键的.so文件
        ("server/lib/lib/libhcnetsdk.so", "/home/lqj/liquid/server/lib/lib/libhcnetsdk.so"),
        ("server/lib/lib/libHCCore.so", "/home/lqj/liquid/server/lib/lib/libHCCore.so"),
        ("server/lib/lib/libPlayCtrl.so", "/home/lqj/liquid/server/lib/lib/libPlayCtrl.so"),
    ]
    
    success_count = 0
    total_count = len(files_to_upload)
    
    for local_file, remote_file in files_to_upload:
        if os.path.exists(local_file):
            print(f"上传: {local_file} -> {remote_file}")
            
            # 创建远程目录
            remote_dir = os.path.dirname(remote_file)
            ssh_cmd = f'ssh {username}@{server_ip} "mkdir -p {remote_dir}"'
            
            try:
                subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=15)
            except:
                pass
            
            # 上传文件
            scp_cmd = f'scp "{local_file}" {username}@{server_ip}:"{remote_file}"'
            
            try:
                result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print(f"  ✓ 上传成功")
                    success_count += 1
                else:
                    print(f"  ✗ 上传失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"  ✗ 上传超时")
            except Exception as e:
                print(f"  ✗ 上传异常: {e}")
        else:
            print(f"  ✗ 文件不存在: {local_file}")
    
    print(f"\n上传完成: {success_count}/{total_count}")
    return success_count > 0

def test_hikvision_after_upload():
    """上传后测试海康SDK"""
    print("\n=== 上传后测试海康SDK ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 创建简单的测试脚本
    test_script = '''#!/usr/bin/env python3
import os
import sys

# 设置环境
lib_path = "/home/lqj/liquid/server/lib/lib"
os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"
sys.path.insert(0, "/home/lqj/liquid/server/lib")

print("=== 检查文件 ===")
files_to_check = [
    "/home/lqj/liquid/server/lib/HKcapture.py",
    "/home/lqj/liquid/server/lib/lib/libhcnetsdk.so",
    "/home/lqj/liquid/server/lib/lib/libHCCore.so",
    "/home/lqj/liquid/server/lib/lib/libPlayCtrl.so"
]

for file_path in files_to_check:
    if os.path.exists(file_path):
        print(f"✓ {file_path}")
    else:
        print(f"✗ {file_path}")

print("\\n=== 测试导入 ===")
try:
    from HKcapture import HKcapture
    print("✓ HKcapture导入成功")
    
    # 创建实例测试
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    capture = HKcapture(source=rtsp_url, debug=True)
    print("✓ HKcapture实例创建成功")
    
except Exception as e:
    print(f"✗ HKcapture导入失败: {e}")
    import traceback
    traceback.print_exc()
'''
    
    # 保存并上传测试脚本
    local_test_script = "test/simple_hk_test.py"
    with open(local_test_script, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    remote_test_script = "/home/lqj/liquid/simple_hk_test.py"
    scp_cmd = f'scp "{local_test_script}" {username}@{server_ip}:"{remote_test_script}"'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("测试脚本上传成功")
            
            # 执行测试
            ssh_cmd = f'ssh {username}@{server_ip} "cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && python simple_hk_test.py"'
            
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='ignore')
            
            print("测试结果:")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"错误: {result.stderr}")
                
        else:
            print(f"测试脚本上传失败: {result.stderr}")
            
    except Exception as e:
        print(f"测试异常: {e}")

def main():
    """主函数"""
    print("开始上传必要的海康SDK文件")
    
    try:
        # 1. 上传必要文件
        if upload_essential_files():
            # 2. 测试上传结果
            test_hikvision_after_upload()
        else:
            print("文件上传失败")
            
    except Exception as e:
        print(f"上传过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()