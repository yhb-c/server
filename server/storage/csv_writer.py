# -*- coding: utf-8 -*-
"""
CSV数据写入模块 - 保存检测结果到CSV文件
"""

import os
import csv
import time
import sys
import threading
from datetime import datetime
from pathlib import Path


class CSVWriter:
    """CSV数据写入器（带缓存机制）"""

    def __init__(self, save_path: str, channel_id: str, flush_interval: float = 10.0, max_cache_size: int = 20 * 1024 * 1024):
        """
        初始化CSV写入器

        Args:
            save_path: 保存路径
            channel_id: 通道ID
            flush_interval: 刷新间隔（秒），默认10秒
            max_cache_size: 最大缓存大小（字节），默认20MB
        """
        self.save_path = save_path
        self.channel_id = channel_id
        self.csv_file = None
        self.csv_writer = None

        # 缓存配置
        self.flush_interval = flush_interval
        self.max_cache_size = max_cache_size
        self.cache_buffer = []  # 缓存数据列表
        self.cache_size = 0  # 当前缓存大小（字节）
        self.last_flush_time = time.time()  # 上次刷新时间
        self.lock = threading.Lock()  # 线程锁

        # 确保目录存在
        os.makedirs(save_path, exist_ok=True)

        # 创建CSV文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'{channel_id}_{timestamp}.csv'
        self.csv_filepath = os.path.join(save_path, csv_filename)

        # 打开CSV文件并写入表头
        self._open_csv()
    
    def _open_csv(self):
        """打开CSV文件并写入表头"""
        self.csv_file = open(self.csv_filepath, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)

        # 写入表头
        headers = [
            '时间戳',
            '帧ID',
            '液位高度(mm)'
        ]
        self.csv_writer.writerow(headers)
        self.csv_file.flush()

    def write(self, detection_result: dict):
        """
        写入检测结果到缓存

        Args:
            detection_result: 检测结果字典
                {
                    'height_mm': float,
                    'frame_id': int (帧ID，本地视频为帧序号，RTSP流为NVR时间戳)
                }
        """
        if not self.csv_writer:
            return

        try:
            with self.lock:
                # 获取当前时间戳
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 获取帧ID（本地视频为序列号，RTSP流为NVR时间戳）
                frame_id = detection_result.get('frame_id', '')

                # 调试日志：检测重复写入
                if self.cache_buffer and self.cache_buffer[-1][1] == frame_id:
                    print(f"[CSVWriter] 警告：检测到重复帧ID {frame_id}，通道：{self.channel_id}")

                # 构建数据行
                row = [
                    timestamp,
                    frame_id if frame_id is not None else '',
                    round(detection_result.get('height_mm', 0), 2)
                ]

                # 添加到缓存
                self.cache_buffer.append(row)

                # 估算单行数据大小
                row_size = sys.getsizeof(str(timestamp)) + sys.getsizeof(str(frame_id)) + sys.getsizeof(str(row[2])) + 3
                self.cache_size += row_size

                # 检查是否需要刷新
                current_time = time.time()
                time_elapsed = current_time - self.last_flush_time

                # 条件1：缓存大小达到20MB
                # 条件2：距离上次刷新超过10秒
                if self.cache_size >= self.max_cache_size or time_elapsed >= self.flush_interval:
                    self._flush_cache()

        except Exception as e:
            print(f"[CSVWriter] 写入缓存失败: {e}")

    def _flush_cache(self):
        """
        刷新缓存到磁盘
        注意：此方法必须在lock保护下调用
        """
        if not self.cache_buffer:
            return

        try:
            self.csv_writer.writerows(self.cache_buffer)
            self.csv_file.flush()

            self.cache_buffer.clear()
            self.cache_size = 0
            self.last_flush_time = time.time()

        except Exception as e:
            print(f"[CSVWriter] 刷新缓存失败: {e}")

    def force_flush(self):
        """
        强制刷新缓存（用于停止检测或程序退出时）
        """
        with self.lock:
            self._flush_cache()
    
    def close(self):
        """关闭CSV文件"""
        # 先强制刷新缓存
        if self.cache_buffer:
            self.force_flush()

        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
    
    def __del__(self):
        """析构函数"""
        self.close()
