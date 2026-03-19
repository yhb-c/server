#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket数据推送功能测试
测试detection_service.py推送液位高度数据到客户端
"""

import sys
import os
import asyncio
import json
import logging
import time

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from websocket.ws_server import WebSocketServer
from websocket.detection_service import DetectionService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MockWebSocketClient:
    """模拟WebSocket客户端"""

    def __init__(self, uri='ws://localhost:8085'):
        self.uri = uri
        self.received_messages = []
        self.websocket = None

    async def connect_and_subscribe(self, channel_id='channel1'):
        """连接并订阅通道"""
        try:
            import websockets

            print(f"\n连接到WebSocket服务器: {self.uri}")
            self.websocket = await websockets.connect(self.uri)
            print("✓ 连接成功")

            # 订阅通道
            subscribe_msg = {
                'command': 'subscribe',
                'channel_id': channel_id
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            print(f"✓ 已订阅通道: {channel_id}")

            # 接收订阅响应
            response = await self.websocket.recv()
            print(f"订阅响应: {response}")

            return True

        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    async def receive_messages(self, duration=5):
        """接收消息"""
        print(f"\n开始接收消息 (持续{duration}秒)...")
        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=1.0
                    )

                    data = json.loads(message)
                    self.received_messages.append(data)

                    # 显示接收到的消息
                    msg_type = data.get('type', 'unknown')
                    if msg_type == 'detection_result':
                        channel_id = data.get('channel_id')
                        result = data.get('data', {})
                        liquid_pos = result.get('liquid_line_positions', {})
                        print(f"  [检测结果] {channel_id}: {liquid_pos}")
                    elif msg_type == 'status_update':
                        status_type = data.get('status_type')
                        print(f"  [状态更新] {status_type}")
                    else:
                        print(f"  [消息] {msg_type}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"接收消息错误: {e}")
                    break

        except Exception as e:
            print(f"接收循环异常: {e}")

        print(f"\n接收完成，共收到 {len(self.received_messages)} 条消息")
        return self.received_messages

    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            print("✓ 连接已关闭")


async def test_websocket_push():
    """测试WebSocket推送功能"""

    print("=" * 60)
    print("WebSocket数据推送功能测试")
    print("=" * 60)

    # 创建WebSocket服务器
    print("\n1. 启动WebSocket服务器...")
    ws_server = WebSocketServer(host='0.0.0.0', port=8085)

    # 创建检测服务
    detection_service = DetectionService(websocket_server=ws_server)

    # 启动服务器
    server_task = asyncio.create_task(ws_server.start())
    await asyncio.sleep(1)  # 等待服务器启动
    print("✓ WebSocket服务器已启动")

    # 创建模拟客户端
    print("\n2. 创建模拟客户端...")
    client = MockWebSocketClient('ws://localhost:8085')

    # 连接并订阅
    if not await client.connect_and_subscribe('channel1'):
        print("❌ 客户端连接失败")
        return False

    # 配置检测服务
    print("\n3. 配置检测服务...")
    channel_id = 'channel1'

    # 加载模型
    model_path = 'database/model/detection_model/bestmodel/tensor.pt'
    if detection_service.load_model(channel_id, model_path, device='cpu'):
        print(f"✓ 模型加载成功")
    else:
        print(f"❌ 模型加载失败")
        await client.close()
        return False

    # 配置通道
    config = {
        'rtsp_url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
        'detection_config': {
            'boxes': [[936, 532, 192]],
            'fixed_bottoms': [568],
            'fixed_tops': [470],
            'actual_heights': [20.0]
        }
    }

    if detection_service.configure_channel(channel_id, config):
        print(f"✓ 通道配置成功")
    else:
        print(f"❌ 通道配置失败")
        await client.close()
        return False

    # 启动检测
    print("\n4. 启动检测...")
    if detection_service.start_detection(channel_id):
        print(f"✓ 检测已启动")
    else:
        print(f"❌ 检测启动失败")
        await client.close()
        return False

    # 接收推送的数据
    print("\n5. 接收推送数据...")
    messages = await client.receive_messages(duration=5)

    # 停止检测
    print("\n6. 停止检测...")
    detection_service.stop_detection(channel_id)
    print("✓ 检测已停止")

    # 关闭客户端
    await client.close()

    # 分析结果
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"  接收消息总数: {len(messages)}")

    detection_results = [m for m in messages if m.get('type') == 'detection_result']
    status_updates = [m for m in messages if m.get('type') == 'status_update']

    print(f"  检测结果消息: {len(detection_results)}")
    print(f"  状态更新消息: {len(status_updates)}")

    if detection_results:
        print(f"\n示例检测结果:")
        sample = detection_results[0]
        print(f"  通道: {sample.get('channel_id')}")
        print(f"  时间戳: {sample.get('timestamp')}")
        result_data = sample.get('data', {})
        print(f"  液位数据: {result_data.get('liquid_line_positions', {})}")

    print("=" * 60)

    # 清理
    detection_service.cleanup()

    return len(messages) > 0


if __name__ == "__main__":
    try:
        # 检查websockets库
        import websockets
    except ImportError:
        print("❌ 需要安装websockets: pip install websockets")
        sys.exit(1)

    # 运行测试
    success = asyncio.run(test_websocket_push())

    if success:
        print("\n✓ WebSocket推送功能测试成功")
        sys.exit(0)
    else:
        print("\n❌ WebSocket推送功能测试失败")
        sys.exit(1)
