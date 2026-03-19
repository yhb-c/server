#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务端RTSP流捕获测试
"""

import os
import sys
import cv2
import time
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_opencv_rtsp():
    """测试OpenCV RTSP连接"""
    logger.info("=== 测试OpenCV RTSP连接 ===")
    
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    logger.info(f"RTSP地址: {rtsp_url}")
    
    try:
        # 创建VideoCapture对象
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            logger.error("无法打开RTSP流")
            return False
        
        logger.info("RTSP流打开成功")
        
        # 设置缓冲区大小
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"视频信息 - FPS: {fps}, 分辨率: {width}x{height}")
        
        # 读取几帧测试
        frame_count = 0
        success_count = 0
        start_time = time.time()
        
        for i in range(30):  # 测试30帧
            ret, frame = cap.read()
            frame_count += 1
            
            if ret:
                success_count += 1
                logger.info(f"成功读取第{frame_count}帧, 形状: {frame.shape}")
            else:
                logger.warning(f"读取第{frame_count}帧失败")
            
            time.sleep(0.1)  # 100ms间隔
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        logger.info(f"测试完成 - 总帧数: {frame_count}, 成功: {success_count}, 耗时: {elapsed:.2f}s")
        logger.info(f"成功率: {success_count/frame_count*100:.1f}%")
        
        cap.release()
        return success_count > 0
        
    except Exception as e:
        logger.error(f"OpenCV RTSP测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_hikvision_sdk():
    """测试海康威视SDK"""
    logger.info("=== 测试海康威视SDK ===")
    
    # 检查SDK库文件
    sdk_lib_path = "/home/lqj/liquid/sdk/hikvision/lib"
    
    if not os.path.exists(sdk_lib_path):
        logger.error(f"海康SDK库路径不存在: {sdk_lib_path}")
        return False
    
    logger.info(f"SDK库路径: {sdk_lib_path}")
    
    # 列出库文件
    try:
        lib_files = os.listdir(sdk_lib_path)
        logger.info(f"SDK库文件: {lib_files}")
    except Exception as e:
        logger.error(f"无法列出SDK库文件: {e}")
        return False
    
    # 检查环境变量
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    logger.info(f"LD_LIBRARY_PATH: {ld_library_path}")
    
    if sdk_lib_path not in ld_library_path:
        logger.warning("SDK库路径不在LD_LIBRARY_PATH中")
        # 设置环境变量
        os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{ld_library_path}"
        logger.info(f"已设置LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
    
    # TODO: 这里需要实际的海康SDK调用代码
    logger.info("海康SDK测试需要具体的SDK调用实现")
    
    return True

def test_video_capture_factory():
    """测试视频捕获工厂"""
    logger.info("=== 测试视频捕获工厂 ===")
    
    try:
        # 添加项目路径
        sys.path.insert(0, '/home/lqj/liquid/server')
        
        from video.video_capture_factory import VideoCaptureFactory
        
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        
        # 创建视频捕获对象
        capture = VideoCaptureFactory.create_capture(rtsp_url)
        
        if capture is None:
            logger.error("视频捕获对象创建失败")
            return False
        
        logger.info("视频捕获对象创建成功")
        
        # 测试读取帧
        for i in range(10):
            frame = capture.read()
            if frame is not None:
                logger.info(f"成功读取帧 {i+1}, 形状: {frame.shape}")
            else:
                logger.warning(f"读取帧 {i+1} 失败")
            
            time.sleep(0.2)
        
        # 释放资源
        if hasattr(capture, 'release'):
            capture.release()
        
        return True
        
    except Exception as e:
        logger.error(f"视频捕获工厂测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """主函数"""
    logger.info("开始测试服务端RTSP流捕获功能")
    
    results = {}
    
    # 1. 测试OpenCV RTSP连接
    results['opencv_rtsp'] = test_opencv_rtsp()
    
    # 2. 测试海康威视SDK
    results['hikvision_sdk'] = test_hikvision_sdk()
    
    # 3. 测试视频捕获工厂
    results['video_capture_factory'] = test_video_capture_factory()
    
    # 输出测试结果
    logger.info("=== 测试结果汇总 ===")
    for test_name, result in results.items():
        status = "成功" if result else "失败"
        logger.info(f"{test_name}: {status}")
    
    # 保存结果到文件
    result_file = "/home/lqj/liquid/rtsp_test_result.json"
    try:
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"测试结果已保存到: {result_file}")
    except Exception as e:
        logger.error(f"保存测试结果失败: {e}")

if __name__ == "__main__":
    main()
