#!/usr/bin/env python3
"""
简化的液位检测测试 - 直接测试模型推理
省略WebSocket、任务管理等复杂配置
"""

import sys
import os
import cv2
import numpy as np

# 添加项目路径
sys.path.insert(0, '/home/lqj/liquid/server')

from detection.detection import LiquidDetectionEngine

def test_detection_simple():
    """简化的检测测试"""

    print("=" * 60)
    print("简化液位检测测试")
    print("=" * 60)

    # 1. 创建检测引擎
    print("\n[1/4] 创建检测引擎...")
    engine = LiquidDetectionEngine(device='cpu')
    print("✓ 检测引擎创建成功")

    # 2. 加载模型
    print("\n[2/4] 加载YOLO模型...")
    model_path = "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt"
    if engine.load_model(model_path):
        print(f"✓ 模型加载成功: {model_path}")
    else:
        print(f"✗ 模型加载失败")
        return False

    # 3. 配置ROI (从annotation_result.yaml读取channel1的配置)
    print("\n[3/4] 配置ROI...")
    boxes = [[936, 532, 192]]  # channel1的ROI配置
    fixed_bottoms = [568]
    fixed_tops = [470]
    actual_heights = [20]  # 20mm

    engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)
    print(f"✓ ROI配置成功: {len(boxes)} 个ROI")

    # 4. 使用RTSP流进行检测
    print("\n[4/4] 连接RTSP流并检测...")
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"

    # 使用HKcapture打开RTSP流
    sys.path.insert(0, '/home/lqj/liquid/server/lib')
    from HKcapture import HKcapture

    cap = HKcapture(source=rtsp_url, debug=False)

    if not cap.open():
        print("✗ RTSP流连接失败")
        return False

    print(f"✓ RTSP流连接成功")

    if not cap.start_capture():
        print("✗ 捕获启动失败")
        cap.release()
        return False

    print("✓ 捕获启动成功")

    # 启用YUV队列
    cap.enable_yuv_queue(enabled=True, interval=0.1)

    print("\n开始检测 (10帧)...")
    print("-" * 60)

    frame_count = 0
    max_frames = 10

    import time
    while frame_count < max_frames:
        # 获取YUV数据
        yuv_data = cap.get_yuv_data_nowait()

        if yuv_data:
            yuv_bytes, width, height, timestamp = yuv_data

            # 转换YUV到BGR
            yuv_array = np.frombuffer(yuv_bytes, dtype=np.uint8)
            yuv_image = yuv_array.reshape((height * 3 // 2, width))
            frame = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)

            # 执行检测
            results = engine.detect(frame)

            frame_count += 1
            print(f"\n帧 #{frame_count}:")

            if results and len(results) > 0:
                for idx, result in enumerate(results):
                    if isinstance(result, dict):
                        height_mm = result.get('height', 0)
                        pixel_y = result.get('pixel_y', 0)
                        is_full = result.get('is_full', False)
                        print(f"  ROI {idx}: 液位={height_mm}mm, 像素Y={pixel_y}, 满液={'是' if is_full else '否'}")
                    else:
                        print(f"  ROI {idx}: {result}")
            else:
                print(f"  未检测到液位")

        time.sleep(0.1)

    print("\n" + "-" * 60)
    print(f"✓ 检测完成，共处理 {frame_count} 帧")

    # 清理
    cap.release()

    print("\n" + "=" * 60)
    print("✓ 简化液位检测测试成功")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_detection_simple()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
