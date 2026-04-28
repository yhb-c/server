#!/usr/bin/env python3
"""
模拟客户端发送通道五启动检测信号的调试脚本
用于测试WebSocket服务器的检测启动功能
"""

import asyncio
import websockets
import json
import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.insert(0, project_dir)


class TestClient:
    """测试客户端"""

    def __init__(self, server_url='ws://localhost:8085'):
        """
        初始化测试客户端

        Args:
            server_url: WebSocket服务器地址
        """
        self.server_url = server_url
        self.websocket = None

    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            print(f"已连接到服务器: {self.server_url}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    async def send_command(self, command_data):
        """
        发送命令到服务器

        Args:
            command_data: 命令数据字典
        """
        try:
            await self.websocket.send(json.dumps(command_data))
            print(f"已发送命令: {json.dumps(command_data, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"发送命令失败: {e}")

    async def receive_response(self, timeout=5):
        """
        接收服务器响应

        Args:
            timeout: 超时时间（秒）
        """
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            response_data = json.loads(response)
            print(f"收到响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
            return response_data
        except asyncio.TimeoutError:
            print(f"接收响应超时（{timeout}秒）")
            return None
        except Exception as e:
            print(f"接收响应失败: {e}")
            return None

    async def subscribe_channel(self, channel_id):
        """
        订阅通道

        Args:
            channel_id: 通道ID
        """
        command = {
            'command': 'subscribe',
            'channel_id': channel_id
        }
        await self.send_command(command)
        await self.receive_response()

    async def start_detection(self, channel_id, frame_id=None):
        """
        启动检测

        Args:
            channel_id: 通道ID
            frame_id: 起始帧ID（可选）
        """
        command = {
            'command': 'start_detection',
            'channel_id': channel_id
        }

        if frame_id is not None:
            command['frame_id'] = frame_id

        await self.send_command(command)
        await self.receive_response()

    async def stop_detection(self, channel_id):
        """
        停止检测

        Args:
            channel_id: 通道ID
        """
        command = {
            'command': 'stop_detection',
            'channel_id': channel_id
        }
        await self.send_command(command)
        await self.receive_response()

    async def listen_messages(self, duration=10):
        """
        监听服务器消息

        Args:
            duration: 监听时长（秒）
        """
        print(f"\n开始监听服务器消息（{duration}秒）...")
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < duration:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=1)
                message_data = json.loads(message)
                print(f"收到消息: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"接收消息失败: {e}")
                break

        print("监听结束")

    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            print("已断开连接")


async def test_channel5_detection():
    """测试通道五检测启动"""

    print("=" * 60)
    print("通道五检测启动测试")
    print("=" * 60)

    # 创建测试客户端
    client = TestClient()

    # 连接到服务器
    if not await client.connect():
        return

    try:
        # 1. 订阅通道五
        print("\n步骤1: 订阅通道五")
        await client.subscribe_channel('5')
        await asyncio.sleep(1)

        # 2. 启动通道五检测
        print("\n步骤2: 启动通道五检测")
        await client.start_detection('5')
        await asyncio.sleep(1)

        # 3. 监听检测结果
        print("\n步骤3: 监听检测结果")
        await client.listen_messages(duration=30)

        # 4. 停止检测
        print("\n步骤4: 停止通道五检测")
        await client.stop_detection('5')
        await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
    finally:
        # 关闭连接
        await client.close()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


async def test_channel5_with_frame_id():
    """测试通道五从指定帧ID开始检测"""

    print("=" * 60)
    print("通道五指定帧ID检测启动测试")
    print("=" * 60)

    # 创建测试客户端
    client = TestClient()

    # 连接到服务器
    if not await client.connect():
        return

    try:
        # 1. 订阅通道五
        print("\n步骤1: 订阅通道五")
        await client.subscribe_channel('5')
        await asyncio.sleep(1)

        # 2. 启动通道五检测（从帧ID 100开始）
        print("\n步骤2: 启动通道五检测（从帧ID 100开始）")
        await client.start_detection('5', frame_id=100)
        await asyncio.sleep(1)

        # 3. 监听检测结果
        print("\n步骤3: 监听检测结果")
        await client.listen_messages(duration=30)

        # 4. 停止检测
        print("\n步骤4: 停止通道五检测")
        await client.stop_detection('5')
        await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
    finally:
        # 关闭连接
        await client.close()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


def main():
    """主函数"""
    print("\n请选择测试模式:")
    print("1. 通道五检测启动测试（从头开始）")
    print("2. 通道五检测启动测试（从指定帧ID开始）")

    choice = input("\n请输入选项（1或2，默认1）: ").strip()

    if choice == '2':
        asyncio.run(test_channel5_with_frame_id())
    else:
        asyncio.run(test_channel5_detection())


if __name__ == '__main__':
    main()
