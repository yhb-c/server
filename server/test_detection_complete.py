#!/usr/bin/env python3
"""
完整的WebSocket start_detection测试
包括模型加载、通道配置，测试detection_result推送
"""

import asyncio
import websockets
import json
import sys


async def test_detection_complete():
    """完整测试检测流程"""

    ws_url = "ws://127.0.0.1:8085"
    channel_id = "channel1"
    model_path = "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt"

    print("=" * 60)
    print("完整WebSocket检测测试")
    print("=" * 60)

    try:
        async with websockets.connect(ws_url) as websocket:
            # 1. 连接
            print(f"\n[1/5] 连接WebSocket...")
            welcome_msg = await websocket.recv()
            print(f"✓ 连接成功")

            # 2. 订阅
            print(f"\n[2/5] 订阅通道...")
            await websocket.send(json.dumps({
                "command": "subscribe",
                "channel_id": channel_id
            }))
            await websocket.recv()
            print(f"✓ 订阅成功")

            # 3. 加载模型
            print(f"\n[3/5] 加载模型...")
            await websocket.send(json.dumps({
                "command": "load_model",
                "channel_id": channel_id,
                "model_path": model_path,
                "device": "cpu"
            }))

            # 等待模型加载响应
            for _ in range(3):
                msg = await websocket.recv()
                data = json.loads(msg)
                if data.get('type') == 'command_response' and data.get('command') == 'load_model':
                    if data.get('success'):
                        print(f"✓ 模型加载成功")
                    else:
                        print(f"✗ 模型加载失败: {data.get('message')}")
                        return False
                    break

            # 4. 配置通道
            print(f"\n[4/5] 配置通道...")
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

            # 等待配置响应
            for _ in range(3):
                msg = await websocket.recv()
                data = json.loads(msg)
                if data.get('type') == 'command_response' and data.get('command') == 'configure_channel':
                    if data.get('success'):
                        print(f"✓ 通道配置成功")
                    else:
                        print(f"✗ 通道配置失败: {data.get('message')}")
                        return False
                    break
                elif data.get('type') == 'status_update' and data.get('status_type') == 'channel_configured':
                    print(f"✓ 通道配置成功")
                    break

            # 5. 启动检测
            print(f"\n[5/5] 启动检测...")
            await websocket.send(json.dumps({
                "command": "start_detection",
                "channel_id": channel_id
            }))
            print(f"✓ start_detection指令已发送")

            # 接收检测结果
            print(f"\n接收detection_result...")
            print("-" * 60)

            result_count = 0
            max_results = 5

            for i in range(20):  # 最多接收20条消息
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message)

                    msg_type = data.get('type')

                    if msg_type == 'detection_result':
                        result_count += 1
                        print(f"\n检测结果 #{result_count}:")
                        print(f"  通道: {data.get('channel_id')}")
                        print(f"  时间戳: {data.get('timestamp')}")

                        results = data.get('results', [])
                        if results:
                            for idx, result in enumerate(results):
                                if isinstance(result, dict):
                                    height = result.get('height', 0)
                                    pixel_y = result.get('pixel_y', 0)
                                    is_full = result.get('is_full', False)
                                    print(f"  ROI {idx}: 液位={height}mm, 像素Y={pixel_y}, 满液={'是' if is_full else '否'}")
                        else:
                            print(f"  未检测到液位")

                        if result_count >= max_results:
                            break

                    elif msg_type == 'command_response':
                        success = data.get('success')
                        message_text = data.get('message')
                        print(f"\n命令响应: {success} - {message_text}")
                        if not success:
                            break

                    elif msg_type == 'status_update':
                        status_type = data.get('status_type')
                        print(f"\n状态更新: {status_type}")

                except asyncio.TimeoutError:
                    print(f"\n等待超时")
                    break

            print("\n" + "-" * 60)
            print(f"✓ 共接收 {result_count} 条检测结果")

            # 停止检测
            print(f"\n停止检测...")
            await websocket.send(json.dumps({
                "command": "stop_detection",
                "channel_id": channel_id
            }))
            await websocket.recv()
            print(f"✓ 检测已停止")

    except ConnectionRefusedError:
        print(f"✗ 连接被拒绝")
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
    success = asyncio.run(test_detection_complete())
    sys.exit(0 if success else 1)
