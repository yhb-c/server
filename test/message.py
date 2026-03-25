#!/usr/bin/env python3
"""
WebSocket消息推送测试
1. 测试单次消息最大容量
2. 测试多通道并发推送的FPS吞吐量
"""

import asyncio
import websockets
import json
import time
import sys
import logging
import os
from datetime import datetime
from typing import List, Dict
import statistics


class WebSocketMaxMessageTest:
    """WebSocket最大消息测试类"""

    def __init__(self, host='localhost', port=8085, log_dir='test/logs'):
        self.host = host
        self.port = port
        self.ws_url = f"ws://{host}:{port}"
        self.websocket = None
        self.test_results = []

        # 设置日志
        self.log_dir = log_dir
        self.setup_logging()

    def setup_logging(self):
        """设置日志系统"""
        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

        # 生成日志文件名（带时间戳）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'websocket_max_message_test_{timestamp}.log'
        self.log_file_path = os.path.join(self.log_dir, log_filename)

        # 配置日志格式
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'

        # 创建logger
        self.logger = logging.getLogger('WebSocketMaxMessageTest')
        self.logger.setLevel(logging.DEBUG)

        # 清除已有的handlers
        self.logger.handlers.clear()

        # 文件handler - 记录所有级别
        file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        self.logger.addHandler(file_handler)

        # 控制台handler - 只显示INFO及以上
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        self.logger.addHandler(console_handler)

        self.logger.info(f"日志文件: {self.log_file_path}")
        self.logger.info(f"测试目标: {self.ws_url}")

    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.logger.info(f"正在连接到 {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url)

            # 接收欢迎消息
            welcome_msg = await self.websocket.recv()
            self.logger.info(f"连接成功")
            self.logger.debug(f"欢迎消息: {welcome_msg}")
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.logger.info("已断开连接")

    def generate_detection_result(self, num_detections=1, roi_count=1, channel_id='test_channel', frame_id=0):
        """
        生成模拟检测结果

        Args:
            num_detections: 检测对象数量
            roi_count: ROI区域数量（最多32个）
            channel_id: 通道ID
            frame_id: 帧ID

        Returns:
            dict: 检测结果数据
        """
        # 限制ROI数量最多32个
        roi_count = min(roi_count, 32)

        result = {
            'type': 'detection_result',
            'channel_id': channel_id,
            'timestamp': datetime.now().isoformat(),
            'frame_id': frame_id,
            'detections': [],
            'roi_results': [],
            'statistics': {
                'total_detections': num_detections,
                'processing_time_ms': 25.5,
                'fps': 30.0
            }
        }

        # 生成检测对象
        for i in range(num_detections):
            detection = {
                'id': i,
                'class': 'liquid',
                'confidence': 0.95 + (i % 5) * 0.01,
                'bbox': [100 + i * 10, 200 + i * 10, 150 + i * 10, 250 + i * 10],
                'area': 2500,
                'center': [125 + i * 10, 225 + i * 10],
                'properties': {
                    'color': 'blue',
                    'texture': 'smooth',
                    'temperature': 25.5 + i * 0.1
                }
            }
            result['detections'].append(detection)

        # 生成ROI结果
        for i in range(roi_count):
            roi_result = {
                'roi_id': f'roi_{i}',
                'name': f'检测区域{i}',
                'coordinates': [[100 + i * 50, 100], [200 + i * 50, 100],
                               [200 + i * 50, 300], [100 + i * 50, 300]],
                'liquid_height': 150.5 + i * 10,
                'liquid_percentage': 75.5 + i * 2,
                'status': 'normal',
                'detections_in_roi': min(num_detections, 10 + i * 5)
            }
            result['roi_results'].append(roi_result)

        return result

    async def test_message_size(self, num_detections, roi_count):
        """
        测试特定大小的消息

        Args:
            num_detections: 检测对象数量
            roi_count: ROI区域数量

        Returns:
            dict: 测试结果
        """
        self.logger.debug(f"开始生成测试数据: 检测数={num_detections}, ROI数={roi_count}")
        result_data = self.generate_detection_result(num_detections, roi_count)
        message = json.dumps(result_data, ensure_ascii=False)
        message_size = len(message.encode('utf-8'))

        self.logger.info("="*60)
        self.logger.info(f"测试消息大小: {message_size:,} 字节 ({message_size/1024:.2f} KB)")
        self.logger.info(f"检测对象数: {num_detections}, ROI数: {roi_count}")

        test_result = {
            'num_detections': num_detections,
            'roi_count': roi_count,
            'message_size_bytes': message_size,
            'message_size_kb': message_size / 1024,
            'message_size_mb': message_size / (1024 * 1024),
            'success': False,
            'send_time_ms': 0,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            # 测试发送时间
            self.logger.debug("开始发送消息...")
            start_time = time.time()
            await self.websocket.send(message)
            send_time = (time.time() - start_time) * 1000

            test_result['success'] = True
            test_result['send_time_ms'] = send_time

            self.logger.info(f"✓ 发送成功")
            self.logger.info(f"  发送耗时: {send_time:.2f} ms")
            self.logger.debug(f"  传输速率: {message_size / 1024 / (send_time / 1000):.2f} KB/s")

        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"✗ 发送失败: {e}")
            self.logger.debug(f"错误详情", exc_info=True)

        return test_result

    async def run_progressive_test(self):
        """运行渐进式测试，逐步增加消息大小"""
        self.logger.info("="*60)
        self.logger.info("WebSocket最大消息推送测试 - 渐进式模式")
        self.logger.info("="*60)

        # 连接到服务器
        if not await self.connect():
            self.logger.error("无法连接到服务器，测试终止")
            return

        # 测试配置：逐步增加检测对象和ROI数量
        test_configs = [
            # (检测对象数, ROI数)
            (10, 5),       # 小消息
            (50, 10),      # 中等消息
            (100, 20),     # 较大消息
            (200, 30),     # 大消息
            (500, 50),     # 很大消息
            (1000, 100),   # 超大消息
            (2000, 200),   # 极大消息
            (5000, 500),   # 巨大消息
            (10000, 1000), # 超巨大消息
        ]

        self.logger.info(f"将测试 {len(test_configs)} 种不同大小的消息...")
        self.logger.debug(f"测试配置: {test_configs}")

        for idx, (num_detections, roi_count) in enumerate(test_configs, 1):
            self.logger.info(f"\n[测试 {idx}/{len(test_configs)}]")
            result = await self.test_message_size(num_detections, roi_count)
            self.test_results.append(result)

            # 如果发送失败，停止测试
            if not result['success']:
                self.logger.warning(f"达到最大消息限制！")
                break

            # 短暂延迟
            await asyncio.sleep(0.5)

        # 断开连接
        await self.disconnect()

        # 打印测试总结
        self.print_summary()
        self.save_results_to_json()

    async def run_custom_test(self, num_detections, roi_count):
        """
        运行自定义测试

        Args:
            num_detections: 检测对象数量
            roi_count: ROI区域数量
        """
        self.logger.info("="*60)
        self.logger.info("WebSocket自定义消息测试")
        self.logger.info("="*60)

        if not await self.connect():
            self.logger.error("无法连接到服务器，测试终止")
            return

        result = await self.test_message_size(num_detections, roi_count)
        self.test_results.append(result)

        await self.disconnect()
        self.print_summary()
        self.save_results_to_json()

    def print_summary(self):
        """打印测试总结"""
        self.logger.info("="*60)
        self.logger.info("测试总结")
        self.logger.info("="*60)

        if not self.test_results:
            self.logger.warning("没有测试结果")
            return

        # 统计成功和失败的测试
        successful_tests = [r for r in self.test_results if r['success']]
        failed_tests = [r for r in self.test_results if not r['success']]

        self.logger.info(f"总测试数: {len(self.test_results)}")
        self.logger.info(f"成功: {len(successful_tests)}")
        self.logger.info(f"失败: {len(failed_tests)}")

        if successful_tests:
            max_successful = max(successful_tests, key=lambda x: x['message_size_bytes'])
            avg_send_time = sum(r['send_time_ms'] for r in successful_tests) / len(successful_tests)
            total_data_sent = sum(r['message_size_bytes'] for r in successful_tests)

            self.logger.info(f"\n最大成功消息:")
            self.logger.info(f"  大小: {max_successful['message_size_bytes']:,} 字节 ({max_successful['message_size_kb']:.2f} KB / {max_successful['message_size_mb']:.2f} MB)")
            self.logger.info(f"  检测对象数: {max_successful['num_detections']}")
            self.logger.info(f"  ROI数: {max_successful['roi_count']}")
            self.logger.info(f"  发送耗时: {max_successful['send_time_ms']:.2f} ms")

            self.logger.info(f"\n统计信息:")
            self.logger.info(f"  平均发送耗时: {avg_send_time:.2f} ms")
            self.logger.info(f"  总发送数据量: {total_data_sent:,} 字节 ({total_data_sent/1024:.2f} KB)")

        if failed_tests:
            first_failed = failed_tests[0]
            self.logger.info(f"\n首次失败:")
            self.logger.info(f"  消息大小: {first_failed['message_size_bytes']:,} 字节 ({first_failed['message_size_kb']:.2f} KB)")
            self.logger.info(f"  检测对象数: {first_failed['num_detections']}")
            self.logger.info(f"  ROI数: {first_failed['roi_count']}")
            self.logger.info(f"  错误: {first_failed['error']}")

        # 详细结果表格
        self.logger.info(f"\n详细结果:")
        header = f"{'检测数':<10} {'ROI数':<10} {'大小(KB)':<15} {'状态':<10} {'耗时(ms)':<12}"
        self.logger.info(header)
        self.logger.info("-" * 60)
        for r in self.test_results:
            status = "✓ 成功" if r['success'] else "✗ 失败"
            send_time = f"{r['send_time_ms']:.2f}" if r['success'] else "N/A"
            row = f"{r['num_detections']:<10} {r['roi_count']:<10} {r['message_size_kb']:<15.2f} {status:<10} {send_time:<12}"
            self.logger.info(row)

    def save_results_to_json(self):
        """保存测试结果到JSON文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f'websocket_test_results_{timestamp}.json'
        json_file_path = os.path.join(self.log_dir, json_filename)

        results_data = {
            'test_info': {
                'host': self.host,
                'port': self.port,
                'ws_url': self.ws_url,
                'test_time': datetime.now().isoformat(),
                'log_file': self.log_file_path
            },
            'summary': {
                'total_tests': len(self.test_results),
                'successful_tests': len([r for r in self.test_results if r['success']]),
                'failed_tests': len([r for r in self.test_results if not r['success']])
            },
            'results': self.test_results
        }

        try:
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"\n测试结果已保存到: {json_file_path}")
        except Exception as e:
            self.logger.error(f"保存JSON结果失败: {e}")

    async def run_throughput_test(self, num_channels=16, target_fps=30, duration_seconds=10, roi_count=5, num_detections=10):
        """
        运行吞吐量测试 - 测试多通道并发推送的FPS性能

        Args:
            num_channels: 通道数量（模拟多个摄像头）
            target_fps: 目标FPS
            duration_seconds: 测试持续时间（秒）
            roi_count: 每个通道的ROI数量（最多32个）
            num_detections: 每帧检测对象数量
        """
        self.logger.info("="*60)
        self.logger.info("WebSocket吞吐量测试 - 多通道FPS测试")
        self.logger.info("="*60)
        self.logger.info(f"测试参数:")
        self.logger.info(f"  通道数: {num_channels}")
        self.logger.info(f"  目标FPS: {target_fps}")
        self.logger.info(f"  测试时长: {duration_seconds}秒")
        self.logger.info(f"  每通道ROI数: {min(roi_count, 32)}")
        self.logger.info(f"  每帧检测数: {num_detections}")

        # 连接到服务器
        if not await self.connect():
            self.logger.error("无法连接到服务器，测试终止")
            return

        # 计算每帧间隔时间
        frame_interval = 1.0 / target_fps

        # 统计数据
        channel_stats = {i: {'sent': 0, 'failed': 0, 'total_time': 0} for i in range(num_channels)}
        start_test_time = time.time()

        self.logger.info(f"\n开始发送数据...")

        try:
            frame_id = 0
            while time.time() - start_test_time < duration_seconds:
                frame_start = time.time()

                # 为每个通道发送一帧数据
                tasks = []
                for channel_idx in range(num_channels):
                    channel_id = f"channel_{channel_idx}"
                    task = self.send_channel_frame(
                        channel_id, frame_id, num_detections, roi_count, channel_stats[channel_idx]
                    )
                    tasks.append(task)

                # 并发发送所有通道的数据
                await asyncio.gather(*tasks, return_exceptions=True)

                frame_id += 1

                # 控制帧率
                elapsed = time.time() - frame_start
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)

        except KeyboardInterrupt:
            self.logger.warning("\n测试被用户中断")

        # 测试结束
        test_duration = time.time() - start_test_time
        await self.disconnect()

        # 打印吞吐量测试结果
        self.print_throughput_summary(channel_stats, test_duration, num_channels, target_fps)

    async def send_channel_frame(self, channel_id, frame_id, num_detections, roi_count, stats):
        """
        发送单个通道的一帧数据

        Args:
            channel_id: 通道ID
            frame_id: 帧ID
            num_detections: 检测对象数量
            roi_count: ROI数量
            stats: 统计字典
        """
        try:
            result_data = self.generate_detection_result(num_detections, roi_count, channel_id, frame_id)
            message = json.dumps(result_data, ensure_ascii=False)

            send_start = time.time()
            await self.websocket.send(message)
            send_time = time.time() - send_start

            stats['sent'] += 1
            stats['total_time'] += send_time

        except Exception as e:
            stats['failed'] += 1
            self.logger.debug(f"通道 {channel_id} 帧 {frame_id} 发送失败: {e}")

    def print_throughput_summary(self, channel_stats, test_duration, num_channels, target_fps):
        """打印吞吐量测试总结"""
        self.logger.info("\n" + "="*60)
        self.logger.info("吞吐量测试总结")
        self.logger.info("="*60)

        total_sent = sum(s['sent'] for s in channel_stats.values())
        total_failed = sum(s['failed'] for s in channel_stats.values())
        total_frames = total_sent + total_failed

        actual_fps = total_sent / test_duration if test_duration > 0 else 0
        actual_fps_per_channel = actual_fps / num_channels if num_channels > 0 else 0

        self.logger.info(f"\n整体统计:")
        self.logger.info(f"  测试时长: {test_duration:.2f} 秒")
        self.logger.info(f"  通道数: {num_channels}")
        self.logger.info(f"  目标FPS: {target_fps} (每通道)")
        self.logger.info(f"  总发送帧数: {total_sent}")
        self.logger.info(f"  总失败帧数: {total_failed}")
        self.logger.info(f"  成功率: {(total_sent/total_frames*100) if total_frames > 0 else 0:.2f}%")
        self.logger.info(f"  实际总FPS: {actual_fps:.2f} (所有通道)")
        self.logger.info(f"  实际每通道FPS: {actual_fps_per_channel:.2f}")

        # 每个通道的详细统计
        self.logger.info(f"\n每通道详细统计:")
        self.logger.info(f"{'通道':<15} {'成功':<10} {'失败':<10} {'FPS':<10} {'平均延迟(ms)':<15}")
        self.logger.info("-" * 60)

        for channel_idx in sorted(channel_stats.keys()):
            stats = channel_stats[channel_idx]
            channel_fps = stats['sent'] / test_duration if test_duration > 0 else 0
            avg_latency = (stats['total_time'] / stats['sent'] * 1000) if stats['sent'] > 0 else 0

            self.logger.info(
                f"channel_{channel_idx:<7} {stats['sent']:<10} {stats['failed']:<10} "
                f"{channel_fps:<10.2f} {avg_latency:<15.2f}"
            )

    async def run_max_roi_test(self, duration_seconds=30, target_fps=30, num_detections=10):
        """
        测试32个ROI同时发送的性能

        Args:
            duration_seconds: 测试持续时间（秒）
            target_fps: 目标FPS
            num_detections: 每帧检测对象数量
        """
        roi_count = 32  # 固定32个ROI

        self.logger.info("="*60)
        self.logger.info("WebSocket 32 ROI性能测试")
        self.logger.info("="*60)
        self.logger.info(f"测试参数:")
        self.logger.info(f"  ROI数量: {roi_count}")
        self.logger.info(f"  目标FPS: {target_fps}")
        self.logger.info(f"  测试时长: {duration_seconds}秒")
        self.logger.info(f"  每帧检测数: {num_detections}")

        # 连接到服务器
        if not await self.connect():
            self.logger.error("无法连接到服务器，测试终止")
            return

        # 生成一个测试消息，计算大小
        sample_data = self.generate_detection_result(num_detections, roi_count, 'test', 0)
        sample_message = json.dumps(sample_data, ensure_ascii=False)
        message_size = len(sample_message.encode('utf-8'))

        self.logger.info(f"  单帧消息大小: {message_size:,} 字节 ({message_size/1024:.2f} KB)")

        # 计算每帧间隔时间
        frame_interval = 1.0 / target_fps

        # 统计数据
        stats = {
            'sent': 0,
            'failed': 0,
            'total_send_time': 0,
            'send_times': [],
            'frame_intervals': []
        }

        start_test_time = time.time()
        last_frame_time = start_test_time

        self.logger.info(f"\n开始发送数据...")

        try:
            frame_id = 0
            while time.time() - start_test_time < duration_seconds:
                frame_start = time.time()

                # 生成并发送一帧数据（包含32个ROI）
                try:
                    result_data = self.generate_detection_result(
                        num_detections, roi_count, 'channel_0', frame_id
                    )
                    message = json.dumps(result_data, ensure_ascii=False)

                    send_start = time.time()
                    await self.websocket.send(message)
                    send_time = time.time() - send_start

                    stats['sent'] += 1
                    stats['total_send_time'] += send_time
                    stats['send_times'].append(send_time * 1000)  # 转换为ms

                    # 记录帧间隔
                    frame_interval_actual = frame_start - last_frame_time
                    stats['frame_intervals'].append(frame_interval_actual * 1000)
                    last_frame_time = frame_start

                except Exception as e:
                    stats['failed'] += 1
                    self.logger.debug(f"帧 {frame_id} 发送失败: {e}")

                frame_id += 1

                # 控制帧率
                elapsed = time.time() - frame_start
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)

        except KeyboardInterrupt:
            self.logger.warning("\n测试被用户中断")

        # 测试结束
        test_duration = time.time() - start_test_time
        await self.disconnect()

        # 打印32 ROI测试结果
        self.print_max_roi_summary(stats, test_duration, target_fps, message_size, roi_count)

    def print_max_roi_summary(self, stats, test_duration, target_fps, message_size, roi_count):
        """打印32 ROI测试总结"""
        self.logger.info("\n" + "="*60)
        self.logger.info("32 ROI性能测试总结")
        self.logger.info("="*60)

        total_frames = stats['sent'] + stats['failed']
        actual_fps = stats['sent'] / test_duration if test_duration > 0 else 0
        avg_send_time = (stats['total_send_time'] / stats['sent'] * 1000) if stats['sent'] > 0 else 0

        self.logger.info(f"\n基本统计:")
        self.logger.info(f"  测试时长: {test_duration:.2f} 秒")
        self.logger.info(f"  ROI数量: {roi_count}")
        self.logger.info(f"  目标FPS: {target_fps}")
        self.logger.info(f"  实际FPS: {actual_fps:.2f}")
        self.logger.info(f"  FPS达成率: {(actual_fps/target_fps*100) if target_fps > 0 else 0:.2f}%")
        self.logger.info(f"  总发送帧数: {stats['sent']}")
        self.logger.info(f"  总失败帧数: {stats['failed']}")
        self.logger.info(f"  成功率: {(stats['sent']/total_frames*100) if total_frames > 0 else 0:.2f}%")

        self.logger.info(f"\n消息统计:")
        self.logger.info(f"  单帧消息大小: {message_size:,} 字节 ({message_size/1024:.2f} KB)")
        self.logger.info(f"  总发送数据量: {message_size * stats['sent']:,} 字节 ({message_size * stats['sent']/1024/1024:.2f} MB)")
        self.logger.info(f"  平均吞吐量: {message_size * actual_fps / 1024:.2f} KB/s")

        if stats['send_times']:
            self.logger.info(f"\n发送延迟统计:")
            self.logger.info(f"  平均发送时间: {avg_send_time:.2f} ms")
            self.logger.info(f"  最小发送时间: {min(stats['send_times']):.2f} ms")
            self.logger.info(f"  最大发送时间: {max(stats['send_times']):.2f} ms")
            self.logger.info(f"  发送时间标准差: {statistics.stdev(stats['send_times']) if len(stats['send_times']) > 1 else 0:.2f} ms")

        if len(stats['frame_intervals']) > 1:
            # 跳过第一个间隔（不准确）
            intervals = stats['frame_intervals'][1:]
            self.logger.info(f"\n帧间隔统计:")
            self.logger.info(f"  平均帧间隔: {statistics.mean(intervals):.2f} ms")
            self.logger.info(f"  最小帧间隔: {min(intervals):.2f} ms")
            self.logger.info(f"  最大帧间隔: {max(intervals):.2f} ms")
            self.logger.info(f"  帧间隔标准差: {statistics.stdev(intervals):.2f} ms")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='WebSocket消息推送测试')
    parser.add_argument('--host', default='localhost', help='WebSocket服务器地址')
    parser.add_argument('--port', type=int, default=8085, help='WebSocket服务器端口')
    parser.add_argument('--mode', choices=['progressive', 'custom', 'throughput', 'max_roi'], default='progressive',
                       help='测试模式: progressive(渐进式容量测试) / custom(自定义容量测试) / throughput(吞吐量FPS测试) / max_roi(32 ROI性能测试)')
    parser.add_argument('--detections', type=int, default=100,
                       help='检测对象数量')
    parser.add_argument('--rois', type=int, default=20,
                       help='ROI数量（最多32个）')
    parser.add_argument('--log-dir', default='test/logs', help='日志文件保存目录')

    # 吞吐量测试参数
    parser.add_argument('--channels', type=int, default=16,
                       help='吞吐量测试: 通道数量（模拟多个摄像头）')
    parser.add_argument('--fps', type=int, default=30,
                       help='目标FPS')
    parser.add_argument('--duration', type=int, default=10,
                       help='测试持续时间（秒）')

    args = parser.parse_args()

    tester = WebSocketMaxMessageTest(host=args.host, port=args.port, log_dir=args.log_dir)

    try:
        if args.mode == 'progressive':
            await tester.run_progressive_test()
        elif args.mode == 'custom':
            await tester.run_custom_test(args.detections, args.rois)
        elif args.mode == 'throughput':
            await tester.run_throughput_test(
                num_channels=args.channels,
                target_fps=args.fps,
                duration_seconds=args.duration,
                roi_count=args.rois,
                num_detections=args.detections
            )
        elif args.mode == 'max_roi':
            await tester.run_max_roi_test(
                duration_seconds=args.duration,
                target_fps=args.fps,
                num_detections=args.detections
            )
    except KeyboardInterrupt:
        tester.logger.warning("\n测试被用户中断")
    except Exception as e:
        tester.logger.error(f"\n测试异常: {e}", exc_info=True)


if __name__ == '__main__':
    asyncio.run(main())
