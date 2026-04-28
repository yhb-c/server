#!/usr/bin/env python3
"""
模拟客户端发送通道五启动检测信号的调试脚本
完整流程：加载模型 -> 配置通道 -> 启动检测
"""

import asyncio
import websockets
import json
import os
import sys

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.insert(0, project_dir)


async def test_channel5_detection():
    """测试通道五完整检测流程"""

    uri = "ws://localhost:8085"
    channel_id = "5"

    print("=" * 60)
    print("通道五检测启动测试")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            print(f"\n已连接到服务器: {uri}")

            # 步骤1: 订阅通道五
            print(f"\n步骤1: 订阅通道 {channel_id}")
            subscribe_msg = {
                'command': 'subscribe',
                'channel_id': channel_id
            }
            await websocket.send(json.dumps(subscribe_msg))
            print(f"发送: {json.dumps(subscribe_msg, ensure_ascii=False)}")

            response = await websocket.recv()
            print(f"响应: {response}")
            await asyncio.sleep(1)

            # 步骤2: 加载模型
            print(f"\n步骤2: 加载模型")
            model_path = "/home/lqj/liquid/server/models/best.pt"
            load_model_msg = {
                'command': 'load_model',
                'channel_id': channel_id,
                'model_path': model_path,
                'device': 'cuda'
            }
            await websocket.send(json.dumps(load_model_msg))
            print(f"发送: {json.dumps(load_model_msg, ensure_ascii=False)}")

            response = await websocket.recv()
            print(f"响应: {response}")
            await asyncio.sleep(2)

            # 步骤3: 配置通道
            print(f"\n步骤3: 配置通道")

            # 读取ROI配置
            import yaml
            annotation_file = os.path.join(project_dir, 'server', 'database', 'config', 'annotation_result.yaml')
            annotation_config = {}

            if os.path.exists(annotation_file):
                try:
                    with open(annotation_file, 'r', encoding='utf-8') as f:
                        all_annotations = yaml.safe_load(f)
                        if channel_id in all_annotations:
                            annotation_config = all_annotations[channel_id]
                            print(f"已加载ROI配置，区域数: {annotation_config.get('annotation_count', 0)}")
                except Exception as e:
                    print(f"加载ROI配置失败: {e}")
            else:
                print(f"ROI配置文件不存在: {annotation_file}")

            config = {
                'detection_config': {
                    'confidence_threshold': 0.5,
                    'iou_threshold': 0.45
                },
                'annotation_config': annotation_config
            }

            configure_msg = {
                'command': 'configure_channel',
                'channel_id': channel_id,
                'config': config
            }
            await websocket.send(json.dumps(configure_msg))
            print(f"发送: configure_channel (配置已省略)")

            response = await websocket.recv()
            print(f"响应: {response}")
            await asyncio.sleep(1)

            # 步骤4: 启动检测
            print(f"\n步骤4: 启动检测")
            start_detection_msg = {
                'command': 'start_detection',
                'channel_id': channel_id
            }
            await websocket.send(json.dumps(start_detection_msg))
            print(f"发送: {json.dumps(start_detection_msg, ensure_ascii=False)}")

            response = await websocket.recv()
            print(f"响应: {response}")

            # 步骤5: 监听检测结果
            print(f"\n步骤5: 监听检测结果（30秒）...")
            start_time = asyncio.get_event_loop().time()
            message_count = 0

            while asyncio.get_event_loop().time() - start_time < 30:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    message_data = json.loads(message)
                    message_count += 1

                    msg_type = message_data.get('type', 'unknown')
                    if msg_type == 'detection_result':
                        print(f"[{message_count}] 检测结果 - 通道: {message_data.get('channel_id')}, "
                              f"帧ID: {message_data.get('frame_id')}, "
                              f"液位: {message_data.get('liquid_level', 'N/A')}")
                    else:
                        print(f"[{message_count}] {msg_type}: {json.dumps(message_data, ensure_ascii=False)}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"接收消息失败: {e}")
                    break

            print(f"\n监听结束，共收到 {message_count} 条消息")

            # 步骤6: 停止检测
            print(f"\n步骤6: 停止检测")
            stop_detection_msg = {
                'command': 'stop_detection',
                'channel_id': channel_id
            }
            await websocket.send(json.dumps(stop_detection_msg))
            print(f"发送: {json.dumps(stop_detection_msg, ensure_ascii=False)}")

            response = await websocket.recv()
            print(f"响应: {response}")

    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_channel5_detection())
