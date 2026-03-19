#!/usr/bin/env python3
"""
WebSocket客户端测试脚本
模拟客户端发送start_detection指令到服务器
"""

import asyncio
import websockets
import json
import sys


async def test_websocket_detection():
    """测试WebSocket检测功能"""

    # WebSocket服务器地址（本地）
    ws_url = "ws://127.0.0.1:8085"
    channel_id = "channel1"

    print("=" * 60)
    print("WebSocket客户端测试")
    print("=" * 60)
    print(f"服务器地址: {ws_url}")
    print(f"测试通道: {channel_id}")
    print()

    try:
        # 连接到WebSocket服务器
        print(f"[1/5] 正在连接到WebSocket服务器...")
        async with websockets.connect(ws_url) as websocket:
            print(f"✓ 连接成功")
            print()

            # 接收欢迎消息
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            print(f"[2/5] 收到欢迎消息:")
            print(f"  类型: {welcome_data.get('type')}")
            print(f"  消息: {welcome_data.get('message')}")
            print(f"  客户端ID: {welcome_data.get('client_id')}")
            print()

            # 发送订阅命令
            print(f"[3/7] 发送订阅命令...")
            subscribe_cmd = {
                "command": "subscribe",
                "channel_id": channel_id
            }
            await websocket.send(json.dumps(subscribe_cmd))
            print(f"✓ 订阅命令已发送: {subscribe_cmd}")

            # 接收订阅响应
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"  响应: {response_data}")
            print()

            # 发送load_model命令（必须先加载模型）
            print(f"[4/7] 发送load_model命令...")
            load_model_cmd = {
                "command": "load_model",
                "channel_id": channel_id,
                "model_path": "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt",
                "device": "cpu"
            }
            await websocket.send(json.dumps(load_model_cmd))
            print(f"✓ load_model命令已发送")

            # 接收模型加载响应
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"  响应: {response_data}")
            print()

            # 发送configure_channel命令
            print(f"[5/7] 发送configure_channel命令...")
            configure_cmd = {
                "command": "configure_channel",
                "channel_id": channel_id,
                "config": {
                    "rtsp_url": "rtsp://admin:cei345678@192.168.0.27:8000/stream1",
                    "model_path": "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt",
                    "device": "cpu"
                }
            }
            await websocket.send(json.dumps(configure_cmd))
            print(f"✓ configure_channel命令已发送")

            # 接收配置响应
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"  响应: {response_data}")
            print()

            # 发送start_detection命令
            print(f"[6/7] 发送start_detection命令...")
            start_detection_cmd = {
                "command": "start_detection",
                "channel_id": channel_id
            }
            await websocket.send(json.dumps(start_detection_cmd))
            print(f"✓ start_detection命令已发送: {start_detection_cmd}")
            print()

            # 接收检测启动响应和检测数据
            print(f"[7/7] 接收检测数据...")
            print("-" * 60)

            frame_count = 0
            max_frames = 10  # 接收10帧数据后停止

            while frame_count < max_frames:
                try:
                    # 设置超时时间
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)

                    msg_type = data.get('type')

                    if msg_type == 'detection_result':
                        frame_count += 1
                        channel = data.get('channel_id')
                        results = data.get('results', [])
                        timestamp = data.get('timestamp')

                        print(f"\n帧 #{frame_count} - 通道: {channel}")
                        print(f"  时间戳: {timestamp}")

                        if results:
                            for idx, result in enumerate(results):
                                roi_id = result.get('roi_id', idx)
                                height = result.get('height', 0)
                                pixel_y = result.get('pixel_y', 0)
                                is_full = result.get('is_full', False)

                                print(f"  ROI {roi_id}:")
                                print(f"    液位高度: {height} mm")
                                print(f"    像素位置: {pixel_y}")
                                print(f"    满液状态: {'是' if is_full else '否'}")
                        else:
                            print(f"  未检测到液位")

                    elif msg_type == 'response':
                        status = data.get('status')
                        message_text = data.get('message')
                        print(f"\n服务器响应: {status} - {message_text}")

                    elif msg_type == 'error':
                        error_msg = data.get('message')
                        print(f"\n错误: {error_msg}")
                        break

                except asyncio.TimeoutError:
                    print(f"\n等待数据超时 (5秒)")
                    break
                except Exception as e:
                    print(f"\n接收数据异常: {e}")
                    break

            print()
            print("-" * 60)
            print(f"✓ 测试完成，共接收 {frame_count} 帧检测数据")

            # 发送stop_detection命令
            print()
            print("发送stop_detection命令...")
            stop_detection_cmd = {
                "command": "stop_detection",
                "channel_id": channel_id
            }
            await websocket.send(json.dumps(stop_detection_cmd))
            print(f"✓ stop_detection命令已发送")

            # 接收停止响应
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"  响应: {response_data}")

    except ConnectionRefusedError:
        print(f"✗ 连接被拒绝")
        print(f"  请确保WebSocket服务器正在运行: {ws_url}")
        return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()
    print("=" * 60)
    print("✓ WebSocket检测功能测试成功")
    print("=" * 60)
    return True


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(test_websocket_detection())
    sys.exit(0 if success else 1)
