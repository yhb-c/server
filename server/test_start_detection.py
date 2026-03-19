#!/usr/bin/env python3
"""
最简化的WebSocket start_detection测试
直接测试服务器响应，省略所有不必要的配置
"""

import asyncio
import websockets
import json
import sys


async def test_start_detection():
    """测试start_detection指令"""

    ws_url = "ws://127.0.0.1:8085"
    channel_id = "channel1"

    print("=" * 60)
    print("WebSocket start_detection测试")
    print("=" * 60)

    try:
        # 连接WebSocket
        print(f"\n[1/3] 连接WebSocket服务器...")
        async with websockets.connect(ws_url) as websocket:
            print(f"✓ 连接成功")

            # 接收欢迎消息
            welcome_msg = await websocket.recv()
            print(f"✓ 收到欢迎消息")

            # 订阅通道
            print(f"\n[2/3] 订阅通道...")
            await websocket.send(json.dumps({
                "command": "subscribe",
                "channel_id": channel_id
            }))
            response = await websocket.recv()
            print(f"✓ 订阅成功")

            # 发送start_detection
            print(f"\n[3/3] 发送start_detection指令...")
            await websocket.send(json.dumps({
                "command": "start_detection",
                "channel_id": channel_id
            }))
            print(f"✓ start_detection指令已发送")

            # 接收响应
            print(f"\n接收服务器响应...")
            print("-" * 60)

            for i in range(5):  # 接收5条消息
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)

                    msg_type = data.get('type')
                    print(f"\n消息 #{i+1}:")
                    print(f"  类型: {msg_type}")

                    if msg_type == 'detection_result':
                        print(f"  通道: {data.get('channel_id')}")
                        print(f"  结果: {data.get('results')}")
                    elif msg_type == 'command_response':
                        print(f"  成功: {data.get('success')}")
                        print(f"  消息: {data.get('message')}")
                    elif msg_type == 'status_update':
                        print(f"  状态: {data.get('status_type')}")
                        print(f"  数据: {data.get('data')}")
                    else:
                        print(f"  完整数据: {data}")

                except asyncio.TimeoutError:
                    print(f"\n等待超时")
                    break

            print("\n" + "-" * 60)

    except ConnectionRefusedError:
        print(f"✗ 连接被拒绝，请确保WebSocket服务正在运行")
        return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("✓ 测试完成")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_start_detection())
    sys.exit(0 if success else 1)
