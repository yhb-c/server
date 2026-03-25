# -*- coding: utf-8 -*-
"""
客户端检测结果CSV存储模块
保存接收到的检测结果到CSV文件
"""

import os
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DetectionResultCSVWriter:
    """检测结果CSV写入器 - 客户端版本"""

    def __init__(self, save_dir: str = r"D:\system_client_sever\client\database\mission_result"):
        """
        初始化CSV写入器

        Args:
            save_dir: 保存目录路径
        """
        self.save_dir = Path(save_dir)
        self.csv_files = {}  # {channel_id: (file_handle, csv_writer)}
        self.csv_filepaths = {}  # {channel_id: filepath}

        # 确保目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)

        print(f"[CSVWriter] 初始化完成，保存目录: {self.save_dir}")

    def _get_or_create_writer(self, channel_id: str):
        """
        获取或创建指定通道的CSV写入器

        Args:
            channel_id: 通道ID

        Returns:
            tuple: (file_handle, csv_writer)
        """
        if channel_id not in self.csv_files:
            # 创建新的CSV文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'{channel_id}_{timestamp}.csv'
            csv_filepath = self.save_dir / csv_filename

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

            print(f"[CSVWriter] 创建CSV文件: {csv_filepath}")

        return self.csv_files[channel_id]

    def write_detection_result(self, channel_id: str, heights: List[float], timestamp: Optional[float] = None):
        """
        写入检测结果（简化版本 - 时间戳和液位高度）

        Args:
            channel_id: 通道ID
            heights: 液位高度列表 [h1, h2, h3, ...]
            timestamp: 时间戳（可选，默认使用当前时间）
        """
        try:
            print(f"[CSVWriter] ========== Start Writing CSV ==========")
            print(f"[CSVWriter] Channel ID: {channel_id}")
            print(f"[CSVWriter] Heights: {heights}")
            print(f"[CSVWriter] Timestamp: {timestamp}")

            # 获取写入器
            print(f"[CSVWriter] Getting or creating CSV writer...")
            file_handle, csv_writer = self._get_or_create_writer(channel_id)
            print(f"[CSVWriter] [OK] CSV writer ready")

            # 使用提供的时间戳或当前时间
            ts = timestamp if timestamp else time.time()
            print(f"[CSVWriter] Using timestamp: {ts}")

            # 写入每个液位高度（每个高度一行）
            write_count = 0
            for i, height in enumerate(heights):
                if height is not None and height > 0:
                    row = [
                        ts,  # 时间戳
                        round(height, 2)  # 液位高度
                    ]
                    csv_writer.writerow(row)
                    write_count += 1
                    print(f"[CSVWriter] Wrote height #{i+1}: {round(height, 2)} mm")
                else:
                    print(f"[CSVWriter] Skipped height #{i+1} (invalid value): {height}")

            # 立即刷新到磁盘
            file_handle.flush()
            print(f"[CSVWriter] [SUCCESS] Wrote {write_count} records to CSV")
            print(f"[CSVWriter] File path: {self.csv_filepaths.get(channel_id)}")
            print(f"[CSVWriter] ========== CSV Writing Complete ==========\n")

        except Exception as e:
            print(f"[CSVWriter] [FAIL] Write failed - Channel: {channel_id}, Error: {e}")
            import traceback
            print(f"[CSVWriter] Exception traceback: {traceback.format_exc()}")

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
            print(f"[CSVWriter] 写入完整结果失败: {e}")

    def close_channel(self, channel_id: str):
        """
        关闭指定通道的CSV文件

        Args:
            channel_id: 通道ID
        """
        if channel_id in self.csv_files:
            file_handle, _ = self.csv_files[channel_id]
            file_handle.close()
            del self.csv_files[channel_id]

            filepath = self.csv_filepaths.get(channel_id)
            print(f"[CSVWriter] 关闭CSV文件: {filepath}")

    def close_all(self):
        """关闭所有CSV文件"""
        for channel_id in list(self.csv_files.keys()):
            self.close_channel(channel_id)

        print(f"[CSVWriter] 所有CSV文件已关闭")

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

    print(f"\nCSV files created:")
    for channel_id, filepath in csv_writer.csv_filepaths.items():
        print(f"  {channel_id}: {filepath}")

        # 显示文件内容
        if filepath.exists():
            print(f"\n  Content of {filepath.name}:")
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    print(f"    {line.rstrip()}")

    # 关闭所有文件
    csv_writer.close_all()
