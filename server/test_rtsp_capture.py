#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RTSP流捕获和YUV解码测试脚本
测试从RTSP相机捕获视频流并解码为YUV数据
"""

import sys
import os
import time
import numpy as np

# 添加lib路径
lib_path = os.path.join(os.path.dirname(__file__), 'lib', 'lib')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

# 设置LD_LIBRARY_PATH环境变量，让系统能找到海康SDK依赖库
if 'LD_LIBRARY_PATH' in os.environ:
    os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{os.environ['LD_LIBRARY_PATH']}"
else:
    os.environ['LD_LIBRARY_PATH'] = lib_path

print(f"SDK库路径: {lib_path}")

from lib.HKcapture import HKcapture


def test_rtsp_capture():
    """测试RTSP流捕获和YUV解码"""

    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"

    print(f"开始测试RTSP流捕获")
    print(f"RTSP地址: {rtsp_url}")
    print("-" * 60)

    # 创建捕获对象
    cap = HKcapture(
        source=rtsp_url,
        fps=25,
        debug=True,
        decode_device='cpu'
    )

    print(f"捕获对象类型: {'海康威视SDK' if cap.is_hikvision else 'OpenCV RTSP'}")
    print(f"视频文件: {cap.is_video_file}")

    # 打开连接
    print("\n正在连接RTSP流...")
    if not cap.open():
        print("❌ 连接失败")
        return False

    print("✓ 连接成功")

    # 开始捕获
    print("\n正在启动视频捕获...")
    if not cap.start_capture():
        print("❌ 启动捕获失败")
        cap.release()
        return False

    print("✓ 捕获已启动")

    # 测试读取帧并转换为YUV
    print("\n开始测试帧捕获和YUV解码...")
    print("-" * 60)

    frame_count = 0
    success_count = 0
    start_time = time.time()

    try:
        for i in range(50):  # 测试50帧
            ret, frame = cap.read()

            if ret and frame is not None:
                frame_count += 1

                # 转换BGR到YUV
                yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)

                # 分离YUV通道
                y_channel, u_channel, v_channel = cv2.split(yuv_frame)

                success_count += 1

                # 前3帧显示详细信息
                if frame_count <= 3:
                    print(f"\n帧 #{frame_count}:")
                    print(f"  BGR shape: {frame.shape}")
                    print(f"  YUV shape: {yuv_frame.shape}")
                    print(f"  Y channel: {y_channel.shape}, 范围: [{y_channel.min()}, {y_channel.max()}]")
                    print(f"  U channel: {u_channel.shape}, 范围: [{u_channel.min()}, {u_channel.max()}]")
                    print(f"  V channel: {v_channel.shape}, 范围: [{v_channel.min()}, {v_channel.max()}]")
                elif frame_count % 10 == 0:
                    print(f"已处理 {frame_count} 帧...")
            else:
                if i < 5:
                    print(f"⚠ 第 {i+1} 次读取失败")

            time.sleep(0.04)  # 约25fps

    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止捕获
        print("\n正在停止捕获...")
        cap.stop_capture()

        # 释放资源
        print("正在释放资源...")
        cap.release()

    # 统计结果
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"  总耗时: {elapsed_time:.2f}秒")
    print(f"  成功捕获: {success_count} 帧")
    print(f"  实际帧率: {success_count/elapsed_time:.2f} fps")
    print(f"  成功率: {success_count/50*100:.1f}%")
    print("=" * 60)

    return success_count > 0


if __name__ == "__main__":
    # 需要导入cv2用于YUV转换
    try:
        import cv2
    except ImportError:
        print("❌ 需要安装opencv-python: pip install opencv-python")
        sys.exit(1)

    success = test_rtsp_capture()

    if success:
        print("\n✓ RTSP捕获和YUV解码测试成功")
        sys.exit(0)
    else:
        print("\n❌ RTSP捕获和YUV解码测试失败")
        sys.exit(1)
