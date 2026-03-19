#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket数据推送功能简化测试
直接测试detection_service推送液位数据到客户端
"""

import asyncio
import json
import logging
import time
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))


class MockWebSocketServer:
    """模拟WebSocket服务器"""

    def __init__(self):
        self.messages = []

    async def broadcast_to_channel(self, channel_id, data):
        """模拟推送数据"""
        self.messages.append({
            'channel_id': channel_id,
            'data': data,
            'timestamp': time.time()
        })
        print(f"[推送] {data.get('type')}: {channel_id}")


async def test_detection_service_push():
    """测试detection_service的推送功能"""

    print("=" * 60)
    print("WebSocket数据推送功能测试")
    print("=" * 60)

    # 导入detection_service（避免循环导入）
    sys.path.insert(0, os.path.dirname(__file__))

    # 手动导入避免循环依赖
    from lib.HKcapture import HKcapture
    from detection.detection import LiquidDetectionEngine
    import yaml

    # 创建模拟WebSocket服务器
    mock_ws_server = MockWebSocketServer()

    # 模拟detection_service的核心功能
    print("\n1. 初始化检测组件...")

    # 加载ROI配置
    with open('database/config/annotation_result.yaml', 'r', encoding='utf-8') as f:
        annotation_config = yaml.safe_load(f)['channel1']
    print(f"✓ ROI配置加载完成")

    # 初始化RTSP捕获
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    cap = HKcapture(source=rtsp_url, fps=25, debug=False)

    if not cap.open() or not cap.start_capture():
        print("❌ RTSP捕获启动失败")
        return False
    print(f"✓ RTSP捕获已启动")

    # 等待第一帧
    for _ in range(30):
        ret, frame = cap.read()
        if ret and frame is not None:
            break
        await asyncio.sleep(0.1)
    else:
        print("❌ 无法获取视频帧")
        cap.stop_capture()
        cap.release()
        return False
    print(f"✓ 获取到视频帧")

    # 初始化检测引擎
    detector = LiquidDetectionEngine(device='cpu', batch_size=1)
    if not detector.load_model('database/model/detection_model/bestmodel/tensor.pt'):
        print("❌ 模型加载失败")
        cap.stop_capture()
        cap.release()
        return False
    print(f"✓ 检测引擎初始化完成")

    # 模拟检测循环并推送数据
    print("\n2. 开始检测并推送数据...")
    print("-" * 60)

    channel_id = 'channel1'
    detection_count = 0

    try:
        for i in range(10):  # 测试10帧
            ret, frame = cap.read()

            if ret and frame is not None:
                # 执行检测
                result = detector.detect(
                    frame_or_roi_frames=frame,
                    annotation_config=annotation_config,
                    channel_id=channel_id
                )

                if result and result.get('success'):
                    detection_count += 1

                    # 构建推送数据（模拟detection_service._on_detection_result）
                    push_data = {
                        'type': 'detection_result',
                        'channel_id': channel_id,
                        'timestamp': time.time(),
                        'data': result
                    }

                    # 推送到WebSocket（模拟）
                    await mock_ws_server.broadcast_to_channel(channel_id, push_data)

                    # 显示推送的数据
                    if detection_count <= 3:
                        liquid_pos = result.get('liquid_line_positions', {})
                        print(f"  帧 #{detection_count}: 液位数据 = {liquid_pos}")

            await asyncio.sleep(0.2)

    except Exception as e:
        print(f"❌ 检测异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.stop_capture()
        cap.release()

    # 统计结果
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"  检测帧数: {detection_count}")
    print(f"  推送消息数: {len(mock_ws_server.messages)}")

    if mock_ws_server.messages:
        print(f"\n推送消息示例:")
        sample = mock_ws_server.messages[0]
        print(f"  通道: {sample['channel_id']}")
        print(f"  类型: {sample['data']['type']}")
        print(f"  时间戳: {sample['timestamp']}")
        result_data = sample['data']['data']
        print(f"  液位数据: {result_data.get('liquid_line_positions', {})}")
        print(f"  成功标志: {result_data.get('success')}")

    print("=" * 60)

    return len(mock_ws_server.messages) > 0


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("❌ 需要安装pyyaml: pip install pyyaml")
        sys.exit(1)

    # 运行测试
    success = asyncio.run(test_detection_service_push())

    if success:
        print("\n✓ WebSocket推送功能测试成功")
        sys.exit(0)
    else:
        print("\n❌ WebSocket推送功能测试失败")
        sys.exit(1)
