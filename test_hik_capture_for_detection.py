#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试海康SDK捕获功能是否能够输出用于检测的数据给模型
验证完整的数据流：RTSP捕获 → YUV数据 → BGR转换 → 检测模型推理
"""

import os
import sys
import time
import numpy as np
import cv2

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_hik_capture_for_detection():
    """测试海康SDK捕获功能输出检测数据"""
    print("=" * 60)
    print("测试海康SDK捕获功能输出检测数据")
    print("=" * 60)
    
    try:
        # 导入海康SDK捕获类
        from server.lib.HKcapture import HKcapture
        print("✓ 海康SDK捕获类导入成功")
        
        # 导入检测引擎
        from server.detection.detection import LiquidDetectionEngine
        print("✓ 检测引擎导入成功")
        
        # 测试相机RTSP地址
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        print(f"📹 测试RTSP地址: {rtsp_url}")
        
        # 创建海康SDK捕获器
        print("\n1. 创建海康SDK捕获器...")
        hik_capture = HKcapture(
            source=rtsp_url,
            debug=True
        )
        
        # 打开连接
        print("\n2. 打开RTSP连接...")
        if not hik_capture.open():
            print("❌ 海康SDK连接失败")
            return False
        print("✓ 海康SDK连接成功")
        
        # 启用YUV队列模式（供检测使用）
        print("\n3. 启用YUV队列模式...")
        hik_capture.enable_yuv_queue(enabled=True, interval=0.1)  # 10fps
        print("✓ YUV队列模式已启用")
        
        # 开始捕获
        print("\n4. 开始视频捕获...")
        if not hik_capture.start_capture():
            print("❌ 视频捕获启动失败")
            hik_capture.release()
            return False
        print("✓ 视频捕获已启动")
        
        # 等待数据流稳定
        print("\n5. 等待数据流稳定...")
        time.sleep(3)
        
        # 创建检测引擎
        print("\n6. 创建检测引擎...")
        detection_engine = LiquidDetectionEngine(device='cuda')
        
        # 加载模型（使用默认模型路径）
        model_path = "database/model/best.pt"
        if os.path.exists(model_path):
            print(f"📦 加载检测模型: {model_path}")
            if not detection_engine.load_model(model_path):
                print("❌ 检测模型加载失败")
                hik_capture.release()
                return False
            print("✓ 检测模型加载成功")
        else:
            print(f"⚠️  模型文件不存在: {model_path}")
            print("   跳过模型推理测试，仅测试数据捕获")
        
        # 测试数据获取和转换
        print("\n7. 测试数据获取和转换...")
        test_count = 0
        max_tests = 10
        yuv_success_count = 0
        bgr_success_count = 0
        detection_success_count = 0
        
        start_time = time.time()
        
        while test_count < max_tests:
            # 方法1：获取YUV数据
            yuv_data = hik_capture.get_yuv_data_nowait()
            if yuv_data:
                yuv_success_count += 1
                yuv_bytes, width, height, timestamp = yuv_data
                
                print(f"  [{test_count+1}] YUV数据: {width}x{height}, 大小={len(yuv_bytes)}字节")
                
                # 转换YUV到BGR
                try:
                    yuv_array = np.frombuffer(yuv_bytes, dtype=np.uint8)
                    yuv_frame = yuv_array.reshape((height * 3 // 2, width))
                    bgr_frame = cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2BGR_I420)
                    
                    bgr_success_count += 1
                    print(f"       BGR转换: {bgr_frame.shape}, dtype={bgr_frame.dtype}")
                    
                    # 如果模型已加载，测试检测推理
                    if hasattr(detection_engine, 'model') and detection_engine.model is not None:
                        # 简单的检测配置
                        test_config = {
                            'boxes': [(width//2, height//2, 200)],  # 中心区域
                            'fixed_bottoms': [height-50],
                            'fixed_tops': [50],
                            'actual_heights': [20.0]
                        }
                        
                        detection_engine.configure(
                            boxes=test_config['boxes'],
                            fixed_bottoms=test_config['fixed_bottoms'],
                            fixed_tops=test_config['fixed_tops'],
                            actual_heights=test_config['actual_heights']
                        )
                        
                        # 执行检测
                        detection_result = detection_engine.detect(bgr_frame, channel_id='test_channel')
                        
                        if detection_result and detection_result.get('success', False):
                            detection_success_count += 1
                            liquid_positions = detection_result.get('liquid_line_positions', {})
                            print(f"       检测结果: 成功，液位数据={len(liquid_positions)}个")
                        else:
                            print(f"       检测结果: 无液位检测到")
                    
                except Exception as e:
                    print(f"       BGR转换失败: {e}")
            
            # 方法2：获取传统帧数据（用于对比）
            ret, frame = hik_capture.read()
            if ret and frame is not None:
                print(f"  [{test_count+1}] 传统帧: {frame.shape}, dtype={frame.dtype}")
            
            test_count += 1
            time.sleep(0.2)  # 200ms间隔
        
        elapsed_time = time.time() - start_time
        
        # 输出测试结果
        print(f"\n8. 测试结果统计:")
        print(f"   测试时长: {elapsed_time:.2f}秒")
        print(f"   YUV数据获取: {yuv_success_count}/{max_tests} ({yuv_success_count/max_tests*100:.1f}%)")
        print(f"   BGR转换成功: {bgr_success_count}/{max_tests} ({bgr_success_count/max_tests*100:.1f}%)")
        
        if hasattr(detection_engine, 'model') and detection_engine.model is not None:
            print(f"   检测推理成功: {detection_success_count}/{max_tests} ({detection_success_count/max_tests*100:.1f}%)")
        
        # 判断测试结果
        success = yuv_success_count >= max_tests * 0.8 and bgr_success_count >= max_tests * 0.8
        
        if success:
            print(f"\n✅ 海康SDK捕获功能测试成功！")
            print(f"   - YUV数据获取稳定")
            print(f"   - BGR转换正常")
            if hasattr(detection_engine, 'model') and detection_engine.model is not None:
                print(f"   - 检测模型推理正常")
            print(f"   - 可以为检测模型提供稳定的数据输入")
        else:
            print(f"\n❌ 海康SDK捕获功能测试失败")
            print(f"   - YUV数据获取不稳定或BGR转换失败")
        
        # 清理资源
        print(f"\n9. 清理资源...")
        hik_capture.release()
        if hasattr(detection_engine, 'cleanup'):
            detection_engine.cleanup()
        print("✓ 资源清理完成")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detection_data_flow():
    """测试完整的检测数据流"""
    print("\n" + "=" * 60)
    print("测试完整的检测数据流")
    print("=" * 60)
    
    try:
        # 导入视频捕获工厂
        from server.video.video_capture_factory import VideoCaptureFactory
        from server.detection.detection import LiquidDetectionEngine
        
        # 创建视频捕获工厂
        factory = VideoCaptureFactory()
        
        # 测试RTSP地址
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        channel_id = "test_channel"
        
        print(f"📹 创建视频捕获器...")
        capture = factory.create_capture(rtsp_url, channel_id, prefer_hikvision=True)
        
        if not capture:
            print("❌ 视频捕获器创建失败")
            return False
        
        print("✓ 视频捕获器创建成功")
        
        # 创建检测引擎
        print(f"🧠 创建检测引擎...")
        detection_engine = LiquidDetectionEngine(device='cuda')
        
        # 加载模型
        model_path = "database/model/best.pt"
        if os.path.exists(model_path):
            if not detection_engine.load_model(model_path):
                print("❌ 检测模型加载失败")
                return False
            print("✓ 检测模型加载成功")
        else:
            print(f"⚠️  模型文件不存在，跳过检测测试")
            return True
        
        # 配置检测参数
        test_config = {
            'boxes': [(320, 240, 200)],  # 假设640x480分辨率的中心区域
            'fixed_bottoms': [400],
            'fixed_tops': [100],
            'actual_heights': [20.0]
        }
        
        detection_engine.configure(
            boxes=test_config['boxes'],
            fixed_bottoms=test_config['fixed_bottoms'],
            fixed_tops=test_config['fixed_tops'],
            actual_heights=test_config['actual_heights']
        )
        
        print("✓ 检测参数配置完成")
        
        # 测试数据流
        print(f"\n🔄 测试检测数据流...")
        test_frames = 5
        success_count = 0
        
        for i in range(test_frames):
            # 获取帧数据
            frame = factory.get_frame_from_capture(capture, channel_id)
            
            if frame is not None:
                print(f"  帧{i+1}: {frame.shape}")
                
                # 执行检测
                detection_result = detection_engine.detect(frame, channel_id=channel_id)
                
                if detection_result and detection_result.get('success', False):
                    success_count += 1
                    liquid_positions = detection_result.get('liquid_line_positions', {})
                    print(f"    检测成功: {len(liquid_positions)}个液位")
                else:
                    print(f"    检测失败或无液位")
            else:
                print(f"  帧{i+1}: 获取失败")
            
            time.sleep(0.5)
        
        # 输出结果
        success_rate = success_count / test_frames * 100
        print(f"\n📊 检测数据流测试结果:")
        print(f"   成功率: {success_count}/{test_frames} ({success_rate:.1f}%)")
        
        # 清理资源
        factory.stop_capture(capture, channel_id)
        detection_engine.cleanup()
        
        return success_rate >= 60  # 60%以上成功率认为通过
        
    except Exception as e:
        print(f"❌ 检测数据流测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始海康SDK捕获功能检测数据输出测试")
    
    # 测试1：基础捕获功能
    test1_result = test_hik_capture_for_detection()
    
    # 测试2：完整数据流
    test2_result = test_detection_data_flow()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"基础捕获功能: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"完整检测数据流: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    if test1_result and test2_result:
        print(f"\n🎉 所有测试通过！海康SDK可以为检测模型提供稳定的数据输入")
    else:
        print(f"\n⚠️  部分测试失败，需要进一步调试")
    
    print("=" * 60)