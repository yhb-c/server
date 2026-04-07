#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import websockets
import json
import time


async def test_connection():
    """测试WebSocket连接保持"""
    uri = "ws://192.168.0.121:8085"

    print("="*60)
    print("WebSocket连接保持测试")
    print("="*60)
    print(f"连接地址: {uri}")
    print("测试时长: 90秒")
    print("="*60)

    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{time.strftime('%H:%M:%S')}] 连接成功")

            # 订阅所有通道
            print(f"[{time.strftime('%H:%M:%S')}] 开始订阅通道...")
            for i in range(1, 17):
                channel_id = f'channel{i}'
                subscribe_msg = {
                    'command': 'subscribe',
                    'channel_id': channel_id,
                    'timestamp': time.time()
                }
                await websocket.send(json.dumps(subscribe_msg))

                # 接收响应
                response = await websocket.recv()
                print(f"[{time.strftime('%H:%M:%S')}] 订阅 {channel_id} 成功")

            print(f"[{time.strftime('%H:%M:%S')}] 所有通道订阅完成")
            print(f"[{time.strftime('%H:%M:%S')}] 保持连接90秒，接收消息...")

            # 保持连接90秒，接收消息
            start_time = time.time()
            message_count = 0

            while time.time() - start_time < 90:
                try:
                    # 设置超时为1秒
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_count += 1

                    # 解析消息
                    data = json.loads(message)
                    msg_type = data.get('type', 'unknown')

                    if msg_type == 'detection_result':
                        channel_id = data.get('channel_id', 'unknown')
                        if message_count % 100 == 0:  # 每100条消息打印一次
                            print(f"[{time.strftime('%H:%M:%S')}] 已接收 {message_count} 条消息 (最新: {channel_id})")

                except asyncio.TimeoutError:
                    # 超时，继续等待
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0:  # 每10秒打印一次
                        print(f"[{time.strftime('%H:%M:%S')}] 连接保持中... ({elapsed}秒)")
                    continue

            print("\n" + "="*60)
            print("[测试结果]")
            print("="*60)
            print(f"✓ 测试通过: 连接保持90秒")
            print(f"✓ 接收消息数: {message_count}")
            print(f"✓ 连接状态: 正常")
            print("="*60)

    except websockets.exceptions.ConnectionClosed as e:
        print(f"\n✗ 连接断开: {e}")
        print(f"✗ 断开时间: {time.strftime('%H:%M:%S')}")
        print(f"✗ 关闭代码: {e.code}")
        print(f"✗ 关闭原因: {e.reason}")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_connection())
