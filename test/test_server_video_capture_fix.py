#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的服务端视频捕获功能
验证使用lib/HKcapture.py的视频捕获工厂
"""

import os
import sys
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_server_video_capture():
    """测试服务端视频捕获功能"""
    print("=" * 60)
    print("测试修改后的服务端视频捕获功能")
    print("=" * 60)
    
    try:
        # 导入视频捕获工厂
        from server.video.video_capture_factory import VideoCaptureFactory
        print("✓ 视频捕获工厂导入成功")
        
        # 创建工厂实例
        factory = VideoCaptureFactory()
        print("✓ 视频捕获工厂创建成功")
        
        # 测试RTSP地址
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        channel_id = "test_channel"
        
        print(f"\n📹 测试RTSP地址: {rtsp_url}")
        
        # 创建视频捕获器
        print("\n1. 创建视频捕获器...")
        capture = factory.create_capture(rtsp_url, channel_id, prefer_hikvision=True)
        
        if not capture:
            print("❌ 视频捕获器创建失败")
            return False
        
        print("✓ 视频捕获器创建成功")
        print(f"   捕获器类型: {type(capture).__name__}")
        
        # 检查捕获器是否存活
        print("\n2. 检查捕获器状态...")
        is_alive = factory.is_capture_alive(capture)
        print(f"   捕获器存活状态: {is_alive}")
        
        # 测试获取帧数据
        print("\n3. 测试帧数据获取...")
        frame_count = 0
        max_frames = 5
        
        for i in range(max_frames):
            frame = factory.get_frame_from_capture(capture, channel_id)
            
            if frame is not None:
                frame_count += 1
                print(f"   帧{i+1}: {frame.shape}, dtype={frame.dtype}")
            else:
                print(f"   帧{i+1}: 获取失败")
            
            time.sleep(0.5)  # 等待500ms
        
        # 输出测试结果
        print(f"\n4. 测试结果统计:")
        print(f"   成功获取帧数: {frame_count}/{max_frames}")
        success_rate = frame_count / max_frames * 100
        print(f"   成功率: {success_rate:.1f}%")
        
        # 停止捕获器
        print(f"\n5. 停止捕获器...")
        factory.stop_capture(capture, channel_id)
        print("✓ 捕获器已停止")
        
        # 判断测试结果
        if success_rate >= 60:  # 60%以上成功率认为通过
            print(f"\n✅ 服务端视频捕获测试成功！")
            print(f"   - 使用lib/HKcapture.py成功")
            print(f"   - 帧数据获取正常")
            return True
        else:
            print(f"\n❌ 服务端视频捕获测试失败")
            print(f"   - 帧数据获取成功率过低: {success_rate:.1f}%")
            return False
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hkcapture_direct():
    """直接测试lib/HKcapture.py"""
    print("\n" + "=" * 60)
    print("直接测试lib/HKcapture.py")
    print("=" * 60)
    
    try:
        # 添加lib路径
        lib_dir = os.path.join(project_root, 'server', 'lib')
        sys.path.insert(0, lib_dir)
        
        # 导入HKcapture
        from HKcapture import HKcapture
        print("✓ HKcapture导入成功")
        
        # 测试RTSP地址
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        
        print(f"📹 测试RTSP地址: {rtsp_url}")
        
        # 创建HKcapture实例
        print("\n1. 创建HKcapture实例...")
        hk_capture = HKcapture(
            source=rtsp_url,
            debug=True
        )
        print("✓ HKcapture实例创建成功")
        
        # 启用YUV队列
        print("\n2. 启用YUV队列...")
        hk_capture.enable_yuv_queue(enabled=True, interval=0.1)
        print("✓ YUV队列已启用")
        
        # 打开连接
        print("\n3. 打开RTSP连接...")
        if not hk_capture.open():
            print("❌ RTSP连接失败")
            return False
        print("✓ RTSP连接成功")
        
        # 开始捕获
        print("\n4. 开始视频捕获...")
        if not hk_capture.start_capture():
            print("❌ 视频捕获启动失败")
            hk_capture.release()
            return False
        print("✓ 视频捕获已启动")
        
        # 等待数据流稳定
        print("\n5. 等待数据流稳定...")
        time.sleep(3)
        
        # 测试YUV数据获取
        print("\n6. 测试YUV数据获取...")
        yuv_count = 0
        max_tests = 5
        
        for i in range(max_tests):
            yuv_data = hk_capture.get_yuv_data_nowait()
            if yuv_data:
                yuv_count += 1
                yuv_bytes, width, height, timestamp = yuv_data
                print(f"   YUV{i+1}: {width}x{height}, 大小={len(yuv_bytes)}字节")
            else:
                print(f"   YUV{i+1}: 获取失败")
            
            time.sleep(0.2)
        
        # 输出结果
        yuv_success_rate = yuv_count / max_tests * 100
        print(f"\n7. YUV数据获取结果:")
        print(f"   成功获取: {yuv_count}/{max_tests}")
        print(f"   成功率: {yuv_success_rate:.1f}%")
        
        # 清理资源
        print(f"\n8. 清理资源...")
        hk_capture.release()
        print("✓ 资源清理完成")
        
        return yuv_success_rate >= 60
        
    except Exception as e:
        print(f"❌ 直接测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始服务端视频捕获修复测试")
    
    # 测试1：视频捕获工厂
    test1_result = test_server_video_capture()
    
    # 测试2：直接测试HKcapture
    test2_result = test_hkcapture_direct()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"视频捕获工厂测试: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"HKcapture直接测试: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    if test1_result and test2_result:
        print(f"\n🎉 所有测试通过！服务端视频捕获修复成功")
        print(f"   - 成功使用lib/HKcapture.py")
        print(f"   - 视频捕获工厂正常工作")
        print(f"   - YUV数据获取稳定")
    else:
        print(f"\n⚠️  部分测试失败，需要进一步调试")
    
    print("=" * 60)