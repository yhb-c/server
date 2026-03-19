#!/usr/bin/env python3
"""
测试检测结果输出格式
"""

import asyncio
import websockets
import json


async def test_detection_output():
    """测试检测结果输出"""

    ws_url = "ws://127.0.0.1:8085"
    channel_id = "channel1"
    model_path = "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt"

    print("=" * 60)
    print("测试检测结果输出格式")
    print("=" * 60)

    async with websockets.connect(ws_url) as websocket:
        # 连接和订阅
        await websocket.recv()  # 欢迎消息
        await websocket.send(json.dumps({"command": "subscribe", "channel_id": channel_id}))
        await websocket.recv()  # 订阅响应

        # 加载模型
        print("\n[1] 加载模型...")
        await websocket.send(json.dumps({
            "command": "load_model",
            "channel_id": channel_id,
            "model_path": model_path,
            "device": "cpu"
        }))
        for _ in range(3):
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get('type') == 'command_response' and data.get('command') == 'load_model':
                print(f"✓ 模型加载成功")
                break

        # 配置通道
        print("\n[2] 配置通道...")
        await websocket.send(json.dumps({
            "command": "configure_channel",
            "channel_id": channel_id,
            "config": {
                "rtsp_url": "rtsp://admin:cei345678@192.168.0.27:8000/stream1",
                "detection_config": {
                    "boxes": [[936, 532, 192]],
                    "fixed_bottoms": [568],
                    "fixed_tops": [470],
                    "actual_heights": [20]
                }
            }
        }))
        for _ in range(3):
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get('type') in ['command_response', 'status_update']:
                if 'configured' in str(data):
                    print(f"✓ 通道配置成功")
                    break

        # 启动检测
        print("\n[3] 启动检测...")
        await websocket.send(json.dumps({"command": "start_detection", "channel_id": channel_id}))

        # 接收并打印完整的检测结果
        print("\n[4] 接收检测结果（完整JSON）...")
        print("-" * 60)

        result_count = 0
        for _ in range(20):
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(msg)

                if data.get('type') == 'detection_result':
                    result_count += 1
                    print(f"\n检测结果 #{result_count}:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))

                    if result_count >= 3:
                        break
            except asyncio.TimeoutError:
                break

        print("-" * 60)
        print(f"\n✓ 共接收 {result_count} 条检测结果")

        # 停止检测
        await websocket.send(json.dumps({"command": "stop_detection", "channel_id": channel_id}))
        await websocket.recv()

    print("\n" + "=" * 60)
    print("✓ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_detection_output())
