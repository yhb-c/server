#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的HKcapture导入测试
"""

import os
import sys

def test_hkcapture_import():
    """测试HKcapture导入"""
    print("=" * 50)
    print("测试HKcapture导入")
    print("=" * 50)
    
    try:
        # 设置环境变量
        server_lib_path = '/home/lqj/liquid/server/lib'
        sdk_lib_path = '/home/lqj/liquid/server/lib/lib'
        
        print(f"设置LD_LIBRARY_PATH: {sdk_lib_path}")
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if sdk_lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
        
        print(f"当前LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', '')}")
        
        # 添加lib路径到Python路径
        sys.path.insert(0, server_lib_path)
        
        # 检查路径
        print(f"\n路径检查:")
        print(f"  server/lib存在: {os.path.exists(server_lib_path)}")
        print(f"  server/lib/lib存在: {os.path.exists(sdk_lib_path)}")
        
        if os.path.exists(sdk_lib_path):
            lib_files = os.listdir(sdk_lib_path)
            so_files = [f for f in lib_files if f.endswith('.so')]
            print(f"  动态库文件数量: {len(so_files)}")
        
        # 尝试导入HKcapture
        print(f"\n尝试导入HKcapture...")
        import HKcapture
        print("HKcapture导入成功")
        
        # 尝试导入HCNetSDK
        print(f"尝试导入HCNetSDK...")
        import HCNetSDK
        print("HCNetSDK导入成功")
        
        return True
        
    except ImportError as e:
        print(f"导入失败: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_capture_factory():
    """测试视频捕获工厂"""
    print("\n" + "=" * 50)
    print("测试视频捕获工厂")
    print("=" * 50)
    
    try:
        # 添加项目路径
        sys.path.insert(0, '/home/lqj/liquid')
        
        # 导入视频捕获工厂
        from server.video.video_capture_factory import VideoCaptureFactory
        print("视频捕获工厂导入成功")
        
        # 创建工厂实例
        factory = VideoCaptureFactory()
        print("视频捕获工厂创建成功")
        
        # 检查HKcapture是否可用
        from server.video.video_capture_factory import HK_CAPTURE_AVAILABLE
        print(f"HKcapture可用性: {HK_CAPTURE_AVAILABLE}")
        
        return HK_CAPTURE_AVAILABLE
        
    except Exception as e:
        print(f"视频捕获工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始HKcapture导入测试")
    
    # 测试1: HKcapture导入
    import_ok = test_hkcapture_import()
    
    # 测试2: 视频捕获工厂
    factory_ok = test_video_capture_factory()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"HKcapture导入: {'通过' if import_ok else '失败'}")
    print(f"视频捕获工厂: {'通过' if factory_ok else '失败'}")
    
    if import_ok and factory_ok:
        print("\n所有测试通过！HKcapture导入和路径配置修复成功")
    else:
        print("\n部分测试失败，需要进一步调试")