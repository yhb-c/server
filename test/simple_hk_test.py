#!/usr/bin/env python3
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

print("\n=== 测试导入 ===")
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
