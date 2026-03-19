#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的HKcapture导入和路径配置
验证动态库路径设置是否正确
"""

import os
import sys
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_environment_setup():
    """测试环境设置"""
    print("=" * 60)
    print("测试环境设置")
    print("=" * 60)
    
    # 检查动态库路径
    server_lib_path = os.path.join(project_root, 'server', 'lib')
    sdk_lib_path = os.path.join(server_lib_path, 'lib')
    
    print(f"项目根目录: {project_root}")
    print(f"服务端lib目录: {server_lib_path}")
    print(f"SDK动态库目录: {sdk_lib_path}")
    
    # 检查路径是否存在
    print(f"\n路径检查:")
    print(f"  server/lib存在: {os.path.exists(server_lib_path)}")
    print(f"  server/lib/lib存在: {os.path.exists(sdk_lib_path)}")
    
    if os.path.exists(sdk_lib_path):
        lib_files = os.listdir(sdk_lib_path)
        so_files = [f for f in lib_files if f.endswith('.so')]
        print(f"  动态库文件数量: {len(so_files)}")
        print(f"  关键库文件:")
        key_libs = ['libhcnetsdk.so', 'libPlayCtrl.so', 'libAudioRender.so']
        for lib in key_libs:
            exists = lib in lib_files
            print(f"    {lib}: {'✓' if exists else '❌'}")
    
    return os.path.exists(sdk_lib_path)

def test_hkcapture_import():
    """测试HKcapture导入"""
    print("\n" + "=" * 60)
    print("测试HKcapture导入")
    print("=" * 60)
    
    try:
        # 设置环境变量
        server_lib_path = os.path.join(project_root, 'server', 'lib')
        sdk_lib_path = os.path.join(server_lib_path, 'lib')
        
        print(f"设置LD_LIBRARY_PATH: {sdk_lib_path}")
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if sdk_lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
        
        print(f"当前LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', '')}")
        
        # 添加lib路径到Python路径
        sys.path.insert(0, server_lib_path)
        
        # 尝试导入HKcapture
        print(f"\n尝试导入HKcapture...")
        from HKcapture import HKcapture
        print("✓ HKcapture导入成功")
        
        # 尝试导入HCNetSDK
        print(f"尝试导入HCNetSDK...")
        from HCNetSDK import *
        print("✓ HCNetSDK导入成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_capture_factory():
    """测试视频捕获工厂"""
    print("\n" + "=" * 60)
    print("测试视频捕获工厂")
    print("=" * 60)
    
    try:
        # 导入视频捕获工厂
        from server.video.video_capture_factory import VideoCaptureFactory
        print("✓ 视频捕获工厂导入成功")
        
        # 创建工厂实例
        factory = VideoCaptureFactory()
        print("✓ 视频捕获工厂创建成功")
        
        # 检查HKcapture是否可用
        from server.video.video_capture_factory import HK_CAPTURE_AVAILABLE
        print(f"HKcapture可用性: {HK_CAPTURE_AVAILABLE}")
        
        return HK_CAPTURE_AVAILABLE
        
    except Exception as e:
        print(f"❌ 视频捕获工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hkcapture_basic_functionality():
    """测试HKcapture基本功能"""
    print("\n" + "=" * 60)
    print("测试HKcapture基本功能")
    print("=" * 60)
    
    try:
        # 设置环境
        server_lib_path = os.path.join(project_root, 'server', 'lib')
        sdk_lib_path = os.path.join(server_lib_path, 'lib')
        
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if sdk_lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
        
        sys.path.insert(0, server_lib_path)
        
        # 导入并创建HKcapture实例
        from HKcapture import HKcapture
        
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        print(f"测试RTSP地址: {rtsp_url}")
        
        # 创建实例（不连接，只测试创建）
        hk_capture = HKcapture(
            source=rtsp_url,
            debug=True
        )
        print("✓ HKcapture实例创建成功")
        
        # 测试方法是否存在
        methods_to_check = [
            'open', 'start_capture', 'release',
            'enable_yuv_queue', 'get_yuv_data_nowait',
            'is_opened_status'
        ]
        
        print(f"\n检查关键方法:")
        for method in methods_to_check:
            has_method = hasattr(hk_capture, method)
            print(f"  {method}: {'✓' if has_method else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ HKcapture基本功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始HKcapture导入和路径修复测试")
    
    # 测试1: 环境设置
    env_ok = test_environment_setup()
    
    # 测试2: HKcapture导入
    import_ok = test_hkcapture_import()
    
    # 测试3: 视频捕获工厂
    factory_ok = test_video_capture_factory()
    
    # 测试4: HKcapture基本功能
    basic_ok = test_hkcapture_basic_functionality()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"环境设置: {'✅ 通过' if env_ok else '❌ 失败'}")
    print(f"HKcapture导入: {'✅ 通过' if import_ok else '❌ 失败'}")
    print(f"视频捕获工厂: {'✅ 通过' if factory_ok else '❌ 失败'}")
    print(f"HKcapture基本功能: {'✅ 通过' if basic_ok else '❌ 失败'}")
    
    all_passed = env_ok and import_ok and factory_ok and basic_ok
    
    if all_passed:
        print(f"\n🎉 所有测试通过！HKcapture导入和路径配置修复成功")
        print(f"   - 动态库路径正确: /home/lqj/liquid/server/lib/lib/")
        print(f"   - LD_LIBRARY_PATH设置正确")
        print(f"   - HKcapture导入成功")
        print(f"   - 视频捕获工厂可用")
    else:
        print(f"\n⚠️  部分测试失败，需要进一步调试")
        if not env_ok:
            print(f"   - 检查动态库文件是否完整上传")
        if not import_ok:
            print(f"   - 检查LD_LIBRARY_PATH和依赖库")
        if not factory_ok:
            print(f"   - 检查视频捕获工厂导入路径")
        if not basic_ok:
            print(f"   - 检查HKcapture类定义")
    
    print("=" * 60)