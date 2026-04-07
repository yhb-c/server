#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket客户端测试 - 持续接收检测结果并保存CSV
"""

import asyncio
import websockets
import json
import time
import csv
import os
from pathlib import Path
from datetime import datetime


class DetectionCSVWriter:
    """检测结果CSV写入器"""

    def __init__(self, save_dir=None):
        """初始化CSV写入器

        Args:
            save_dir: 保存目录，默认为 test/results
        """
        if save_dir is None:
            save_dir = Path(__file__).parent / 'results'
        else:
            save_dir = Path(save_dir)

        save_dir.mkdir(parents=True, exist_ok=True)
        self.save_dir = save_dir
        self.csv_files = {}  # {channel_id: file_handle}
        self.csv_writers = {}  # {channel_id: csv.writer}

        print(f"[CSV] 保存目录: {self.save_dir}")

    def write_result(self, channel_id, heights, timestamp=None):
        """写入检测结果

        Args:
            channel_id: 通道ID
            heights: 液位高度列表
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = time.time()

        # 如果该通道还没有CSV文件，创建它
        if channel_id not in self.csv_files:
            self._create_csv_file(channel_id)

        # 写入数据
        writer = self.csv_writers[channel_id]
        row = [datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]
        row.extend(heights)
        writer.writerow(row)

        # 立即刷新到磁盘
        self.csv_files[channel_id].flush()

    def _create_csv_file(self, channel_id):
        """创建CSV文件"""
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{channel_id}_{timestamp_str}.csv"
        filepath = self.save_dir / filename

        # 打开文件
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)

        # 写入表头
        header = ['时间戳', '液位1(mm)', '液位2(mm)', '液位3(mm)', '液位4(mm)']
        writer.writerow(header)

        self.csv_files[channel_id] = file_handle
        self.csv_writers[channel_id] = writer

        print(f"[CSV] 创建文件: {filepath}")

    def close_all(self):
        """关闭所有CSV文件"""
        for channel_id, file_handle in self.csv_files.items():
            file_handle.close()
            print(f"[CSV] 关闭文件: {channel_id}")

        self.csv_files.clear()
        self.csv_writers.clear()


async def run_detection_client():
    """运行检测客户端 - 持续接收并保存数据"""
    uri = "ws://192.168.0.121:8085"
    csv_writer = DetectionCSVWriter()

    print("="*60)
    print("液位检测客户端 - CSV数据记录")
    print("="*60)
    print(f"服务器地址: {uri}")
    print(f"CSV保存目录: {csv_writer.save_dir}")
    print("按 Ctrl+C 停止")
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
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"[{time.strftime('%H:%M:%S')}] 订阅 {channel_id} 成功")
                except asyncio.TimeoutError:
                    print(f"[{time.strftime('%H:%M:%S')}] 订阅 {channel_id} 超时")

            print(f"[{time.strftime('%H:%M:%S')}] 所有通道订阅完成")
            print(f"[{time.strftime('%H:%M:%S')}] 开始接收检测结果...")

            # 持续接收消息
            message_count = 0
            start_time = time.time()

            while True:
                try:
                    message = await websocket.recv()
                    message_count += 1

                    # 解析消息
                    data = json.loads(message)
                    msg_type = data.get('type', 'unknown')

                    if msg_type == 'detection_result':
                        channel_id = data.get('channel_id', 'unknown')
                        timestamp = data.get('timestamp')
                        data_obj = data.get('data', {})
                        liquid_line_positions = data_obj.get('liquid_line_positions', {})

                        # 提取液位高度
                        heights = []
                        if isinstance(liquid_line_positions, dict):
                            for key in sorted(liquid_line_positions.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                                position_data = liquid_line_positions[key]
                                if isinstance(position_data, dict):
                                    height_mm = position_data.get('height_mm', 0)
                                    heights.append(height_mm)

                        # 保存到CSV
                        if heights:
                            csv_writer.write_result(channel_id, heights, timestamp)

                            # 每100条消息打印一次
                            if message_count % 100 == 0:
                                elapsed = int(time.time() - start_time)
                                print(f"[{time.strftime('%H:%M:%S')}] 已接收 {message_count} 条消息 | 运行时间: {elapsed}秒 | 最新: {channel_id}")

                except websockets.exceptions.ConnectionClosed as e:
                    print(f"\n[{time.strftime('%H:%M:%S')}] 连接断开: {e}")
                    break
                except Exception as e:
                    print(f"\n[{time.strftime('%H:%M:%S')}] 处理消息错误: {e}")
                    continue

    except KeyboardInterrupt:
        print(f"\n[{time.strftime('%H:%M:%S')}] 用户中断")
    except Exception as e:
        print(f"\n[{time.strftime('%H:%M:%S')}] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭所有CSV文件
        csv_writer.close_all()

        elapsed = int(time.time() - start_time)
        print("\n" + "="*60)
        print("[运行统计]")
        print("="*60)
        print(f"运行时间: {elapsed}秒")
        print(f"接收消息数: {message_count}")
        print(f"CSV文件数: {len(csv_writer.csv_files)}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(run_detection_client())
