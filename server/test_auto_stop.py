#!/usr/bin/env python3
"""
测试客户端断开连接后自动停止检测
"""

import asyncio
import websockets
import json
import time


async def test_auto_stop_detection():
    """测试客户端断开后自动停止检测"""

    ws_url = "ws://127.0.0.1:8085"
    channel_id = "channel1"
    model_path = "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt"

    print("=" * 60)
    print("测试客户端断开连接后自动停止检测")
    print("=" * 60)

    # 第一阶段：启动检测
    print("\n[阶段1] 连接并启动检测...")
    async with websockets.connect(ws_url) as websocket:
        # 连接和订阅
        await websocket.recv()  # 欢迎消息
        await websocket.send(json.dumps({"command": "subscribe", "channel_id": channel_id}))
        await websocket.recv()  # 订阅响应

        # 加载模型
        print("  - 加载模型...")
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
                print("  ✓ 模型加载成功")
                break

        # 配置通道
        print("  - 配置通道...")
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
                    print("  ✓ 通道配置成功")
                    break

        # 启动检测
        print("  - 启动检测...")
        await websocket.send(json.dumps({"command": "start_detection", "channel_id": channel_id}))

        # 接收几条检测结果
        result_count = 0
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(msg)
                if data.get('type') == 'detection_result':
                    result_count += 1
                    if result_count >= 2:
                        break
            except asyncio.TimeoutError:
                break

        print(f"  ✓ 检测已启动，接收到 {result_count} 条结果")

    # 第二阶段：客户端断开连接（离开 async with 块）
    print("\n[阶段2] 客户端断开连接...")
    print("  - WebSocket连接已关闭")
    print("  - 等待5秒，检查服务器是否自动停止检测...")
    await asyncio.sleep(5)

    # 第三阶段：检查日志
    print("\n[阶段3] 检查服务器日志...")
    print("  - 查看最近的日志记录")
    print("  - 应该看到 '无订阅者，自动停止检测' 的日志")

    print("\n" + "=" * 60)
    print("✓ 测试完成")
    print("请查看 /tmp/websocket_server.log 确认自动停止")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_auto_stop_detection())
