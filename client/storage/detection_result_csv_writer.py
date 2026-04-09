# -*- coding: utf-8 -*-
"""
客户端检测结果CSV存储模块
保存接收到的检测结果到CSV文件
"""

import os
import csv
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DetectionResultCSVWriter:
    """检测结果CSV写入器 - 客户端版本（带缓存机制）"""

    def __init__(self, save_dir: str = None, main_window=None, flush_interval: float = 10.0, max_cache_size: int = 20 * 1024 * 1024):
        """
        初始化CSV写入器

        Args:
            save_dir: 保存目录路径（可选，默认使用项目根目录下的database/mission_result）
            main_window: 主窗口实例，用于获取通道任务信息
            flush_interval: 刷新间隔（秒），默认10秒
            max_cache_size: 最大缓存大小（字节），默认20MB
        """
        if save_dir is None:
            # 使用项目根目录下的database/mission_result
            try:
                from database.config import get_project_root
                import os
                project_root = get_project_root()
                save_dir = os.path.join(project_root, 'database', 'mission_result')
            except Exception as e:
                # print(f"[CSVWriter] 获取项目根目录失败: {e}")
                save_dir = r"D:\system_client_sever\client\database\mission_result"

        self.base_save_dir = Path(save_dir)
        self.main_window = main_window
        self.csv_files = {}  # {channel_id: (file_handle, csv_writer)}
        self.csv_filepaths = {}  # {channel_id: filepath}

        # 缓存配置
        self.flush_interval = flush_interval
        self.max_cache_size = max_cache_size
        self.cache_buffers = {}  # {channel_id: [row1, row2, ...]}
        self.cache_sizes = {}  # {channel_id: size_in_bytes}
        self.last_flush_times = {}  # {channel_id: timestamp}
        self.locks = {}  # {channel_id: threading.Lock()}

        # 确保基础目录存在
        self.base_save_dir.mkdir(parents=True, exist_ok=True)

        # print(f"[CSVWriter] 初始化完成，基础保存目录: {self.base_save_dir}")

    def _get_or_create_writer(self, channel_id: str):
        """
        获取或创建指定通道的CSV写入器

        Args:
            channel_id: 通道ID

        Returns:
            tuple: (file_handle, csv_writer)
        """
        if channel_id not in self.csv_files:
            # 获取通道的任务文件夹名称
            task_folder_name = self._get_channel_task_folder(channel_id)

            # 确定保存目录
            if task_folder_name and task_folder_name != "未分配任务":
                # 保存到任务文件夹
                save_dir = self.base_save_dir / task_folder_name
            else:
                # 保存到基础目录
                save_dir = self.base_save_dir

            # 确保目录存在
            save_dir.mkdir(parents=True, exist_ok=True)

            # 创建新的CSV文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'{channel_id}_{timestamp}.csv'
            csv_filepath = save_dir / csv_filename

            # 打开文件
            file_handle = open(csv_filepath, 'w', newline='', encoding='utf-8-sig')
            csv_writer = csv.writer(file_handle)

            # 写入表头 - 简化格式：时间戳 + 液位高度
            headers = ['时间戳', '液位高度(mm)']
            csv_writer.writerow(headers)
            file_handle.flush()

            # 保存到字典
            self.csv_files[channel_id] = (file_handle, csv_writer)
            self.csv_filepaths[channel_id] = csv_filepath

            # 初始化该通道的缓存
            self.cache_buffers[channel_id] = []
            self.cache_sizes[channel_id] = 0
            self.last_flush_times[channel_id] = time.time()
            self.locks[channel_id] = threading.Lock()

            # print(f"[CSVWriter] 创建CSV文件: {csv_filepath}")

        return self.csv_files[channel_id]

    def _get_channel_task_folder(self, channel_id: str) -> str:
        """
        获取通道当前的任务文件夹名称

        Args:
            channel_id: 通道ID（如 'channel1'）

        Returns:
            str: 任务文件夹名称，如果没有任务返回None
        """
        try:
            if not self.main_window:
                return None

            # 从通道任务标签获取任务名称
            channel_num = int(channel_id.replace('channel', ''))
            mission_var_name = f'channel{channel_num}mission'

            if hasattr(self.main_window, mission_var_name):
                mission_label = getattr(self.main_window, mission_var_name)
                task_folder_name = mission_label.text()

                if task_folder_name and task_folder_name != "未分配任务":
                    return task_folder_name

            return None

        except Exception as e:
            # print(f"[CSVWriter] 获取通道任务失败 ({channel_id}): {e}")
            return None

    def write_detection_result(self, channel_id: str, heights: List[float], timestamp: Optional[float] = None):
        """
        写入检测结果到缓存（简化版本 - 时间戳和液位高度）

        Args:
            channel_id: 通道ID
            heights: 液位高度列表 [h1, h2, h3, ...]
            timestamp: 时间戳（可选，默认使用当前时间）
        """
        try:
            # 获取写入器
            file_handle, csv_writer = self._get_or_create_writer(channel_id)

            # 使用提供的时间戳或当前时间
            ts = timestamp if timestamp else time.time()

            # 获取该通道的锁
            lock = self.locks.get(channel_id)
            if not lock:
                return

            with lock:
                # 写入每个液位高度到缓存（每个高度一行）
                for i, height in enumerate(heights):
                    if height is not None and height > 0:
                        row = [
                            ts,  # 时间戳
                            round(height, 2)  # 液位高度
                        ]

                        # 添加到缓存
                        self.cache_buffers[channel_id].append(row)

                        # 估算单行数据大小
                        row_size = sys.getsizeof(str(ts)) + sys.getsizeof(str(row[1])) + 2
                        self.cache_sizes[channel_id] += row_size

                # 检查是否需要刷新
                current_time = time.time()
                time_elapsed = current_time - self.last_flush_times[channel_id]

                # 条件1：缓存大小达到20MB
                # 条件2：距离上次刷新超过10秒
                if self.cache_sizes[channel_id] >= self.max_cache_size or time_elapsed >= self.flush_interval:
                    self._flush_cache(channel_id)

        except Exception as e:
            pass
            import traceback

    def write_full_detection_result(self, data: Dict):
        """
        写入完整的检测结果数据

        Args:
            data: 完整的检测结果字典
                {
                    'type': 'detection_result',
                    'channel_id': 'channel1',
                    'timestamp': 1773893554.5098188,
                    'heights': [120.5, 135.2, 98.7],
                    'data': {...}  # 可选的额外数据
                }
        """
        try:
            channel_id = data.get('channel_id', 'unknown')
            heights = data.get('heights', [])
            timestamp = data.get('timestamp')

            # 如果有heights数据，写入CSV
            if heights:
                self.write_detection_result(channel_id, heights, timestamp)

        except Exception as e:
            pass

    def _flush_cache(self, channel_id: str):
        """
        刷新指定通道的缓存到磁盘
        注意：此方法必须在lock保护下调用

        Args:
            channel_id: 通道ID
        """
        if channel_id not in self.cache_buffers or not self.cache_buffers[channel_id]:
            return

        try:
            file_handle, csv_writer = self.csv_files[channel_id]

            # 批量写入所有缓存数据
            csv_writer.writerows(self.cache_buffers[channel_id])
            file_handle.flush()

            # 清空缓存
            cache_count = len(self.cache_buffers[channel_id])
            cache_size_mb = self.cache_sizes[channel_id] / (1024 * 1024)
            self.cache_buffers[channel_id].clear()
            self.cache_sizes[channel_id] = 0
            self.last_flush_times[channel_id] = time.time()

            # print(f"[CSVWriter] [{channel_id}] 刷新缓存: {cache_count}条数据, {cache_size_mb:.2f}MB")

        except Exception as e:
            pass

    def force_flush(self, channel_id: str):
        """
        强制刷新指定通道的缓存（用于停止检测或程序退出时）

        Args:
            channel_id: 通道ID
        """
        if channel_id in self.locks:
            with self.locks[channel_id]:
                self._flush_cache(channel_id)

    def force_flush_all(self):
        """强制刷新所有通道的缓存"""
        for channel_id in list(self.cache_buffers.keys()):
            self.force_flush(channel_id)

    def close_channel(self, channel_id: str):
        """
        关闭指定通道的CSV文件

        Args:
            channel_id: 通道ID
        """
        # 先强制刷新缓存
        if channel_id in self.cache_buffers and self.cache_buffers[channel_id]:
            self.force_flush(channel_id)

        if channel_id in self.csv_files:
            file_handle, _ = self.csv_files[channel_id]
            file_handle.close()
            del self.csv_files[channel_id]

            # 清理缓存相关数据
            if channel_id in self.cache_buffers:
                del self.cache_buffers[channel_id]
            if channel_id in self.cache_sizes:
                del self.cache_sizes[channel_id]
            if channel_id in self.last_flush_times:
                del self.last_flush_times[channel_id]
            if channel_id in self.locks:
                del self.locks[channel_id]

            filepath = self.csv_filepaths.get(channel_id)
            # print(f"[CSVWriter] 关闭CSV文件: {filepath}")

    def close_all(self):
        """关闭所有CSV文件"""
        # 先强制刷新所有缓存
        self.force_flush_all()

        for channel_id in list(self.csv_files.keys()):
            self.close_channel(channel_id)

        # print(f"[CSVWriter] 所有CSV文件已关闭")

    def get_filepath(self, channel_id: str) -> Optional[Path]:
        """
        获取指定通道的CSV文件路径

        Args:
            channel_id: 通道ID

        Returns:
            Path: CSV文件路径，如果不存在返回None
        """
        return self.csv_filepaths.get(channel_id)

    def __del__(self):
        """析构函数 - 确保文件被关闭"""
        self.close_all()


# 使用示例
if __name__ == "__main__":
    # 创建CSV写入器
    csv_writer = DetectionResultCSVWriter()

    # 模拟写入检测结果
    test_data = {
        'channel_id': 'channel1',
        'heights': [120.5, 135.2, 98.7, 110.3, 125.8],
        'timestamp': time.time()
    }

    # 写入数据
    csv_writer.write_full_detection_result(test_data)

    # 或者直接写入高度数据
    csv_writer.write_detection_result('channel2', [100.0, 105.5, 110.2])

    # print(f"\nCSV files created:")
    for channel_id, filepath in csv_writer.csv_filepaths.items():
        # print(f"  {channel_id}: {filepath}")

        # 显示文件内容
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    pass

    # 关闭所有文件
    csv_writer.close_all()
