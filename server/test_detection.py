#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
液位检测功能测试脚本
测试从RTSP流捕获帧，使用模型推理ROI区域得到液位高度数据
"""

import sys
import os
import time
import yaml
import cv2

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
sys.path.insert(0, os.path.dirname(__file__))

from lib.HKcapture import HKcapture
from detection.detection import LiquidDetectionEngine


def load_annotation_config(channel_id='channel1'):
    """加载ROI标注配置"""
    config_path = 'database/config/annotation_result.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if channel_id not in config:
        raise ValueError(f"通道 {channel_id} 不存在于配置文件中")

    return config[channel_id]


def test_detection():
    """测试液位检测功能"""

    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    channel_id = 'channel1'

    print(f"开始测试液位检测功能")
    print(f"RTSP地址: {rtsp_url}")
    print(f"通道ID: {channel_id}")
    print("-" * 60)

    # 加载ROI配置
    print("\n加载ROI标注配置...")
    annotation_config = load_annotation_config(channel_id)
    print(f"  标注区域数量: {annotation_config['annotation_count']}")
    print(f"  ROI boxes: {annotation_config['boxes']}")
    print(f"  固定顶部: {annotation_config['fixed_tops']}")
    print(f"  固定底部: {annotation_config['fixed_bottoms']}")

    # 创建RTSP捕获对象
    print("\n初始化RTSP捕获...")
    cap = HKcapture(
        source=rtsp_url,
        fps=25,
        debug=False,
        decode_device='cpu'
    )

    if not cap.open():
        print("❌ RTSP连接失败")
        return False

    if not cap.start_capture():
        print("❌ 启动捕获失败")
        cap.release()
        return False

    print("✓ RTSP捕获已启动")

    # 初始化液位检测器
    print("\n初始化液位检测器...")
    detector = LiquidDetectionEngine(
        model_path='database/model/detection_model/bestmodel/tensor.pt',
        device='cuda',
        batch_size=1
    )
    print("✓ 检测器初始化完成")

    # 等待第一帧
    print("\n等待视频帧...")
    for i in range(30):
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✓ 获取到第一帧: {frame.shape}")
            break
        time.sleep(0.1)
    else:
        print("❌ 无法获取视频帧")
        cap.stop_capture()
        cap.release()
        return False

    # 测试液位检测
    print("\n开始液位检测测试...")
    print("-" * 60)

    detection_count = 0
    success_count = 0

    try:
        for i in range(10):  # 测试10帧
            ret, frame = cap.read()

            if ret and frame is not None:
                detection_count += 1

                # 执行液位检测
                result = detector.detect(
                    frame_or_roi_frames=frame,
                    annotation_config=annotation_config,
                    channel_id=channel_id
                )

                if result and result.get('success'):
                    success_count += 1

                    # 显示检测结果
                    if detection_count <= 3:
                        print(f"\n帧 #{detection_count} 检测结果:")
                        liquid_positions = result.get('liquid_line_positions', {})
                        for area_key, level_data in liquid_positions.items():
                            print(f"  {area_key}:")
                            print(f"    液位高度: {level_data} mm")
                    elif detection_count % 5 == 0:
                        print(f"已检测 {detection_count} 帧...")
                else:
                    if detection_count <= 3:
                        print(f"⚠ 帧 #{detection_count} 检测失败")

            time.sleep(0.2)  # 约5fps检测

    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n❌ 检测过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止捕获
        print("\n正在停止捕获...")
        cap.stop_capture()
        cap.release()

    # 统计结果
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"  检测帧数: {detection_count}")
    print(f"  成功检测: {success_count}")
    print(f"  成功率: {success_count/detection_count*100:.1f}%" if detection_count > 0 else "  成功率: 0%")
    print("=" * 60)

    return success_count > 0


if __name__ == "__main__":
    success = test_detection()

    if success:
        print("\n✓ 液位检测功能测试成功")
        sys.exit(0)
    else:
        print("\n❌ 液位检测功能测试失败")
        sys.exit(1)
