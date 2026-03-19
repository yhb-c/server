# -*- coding: utf-8 -*-
"""
CSV数据写入模块 - 保存检测结果到CSV文件
"""

import os
import csv
import time
from datetime import datetime
from pathlib import Path


class CSVWriter:
    """CSV数据写入器"""
    
    def __init__(self, save_path: str, channel_id: str):
        """
        初始化CSV写入器
        
        Args:
            save_path: 保存路径
            channel_id: 通道ID
        """
        self.save_path = save_path
        self.channel_id = channel_id
        self.csv_file = None
        self.csv_writer = None
        
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
            '通道ID',
            '液位高度(mm)',
            '液位百分比(%)',
            '置信度',
            '状态',
            '备注'
        ]
        self.csv_writer.writerow(headers)
        self.csv_file.flush()
    
    def write(self, detection_result: dict):
        """
        写入检测结果
        
        Args:
            detection_result: 检测结果字典
                {
                    'height_mm': float,
                    'liquid_level': float,
                    'confidence': float,
                    'timestamp': float,
                    'status': str,
                    'note': str
                }
        """
        if not self.csv_writer:
            return
        
        try:
            # 格式化时间戳
            timestamp = detection_result.get('timestamp', time.time())
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # 写入数据行
            row = [
                time_str,
                self.channel_id,
                round(detection_result.get('height_mm', 0), 2),
                round(detection_result.get('liquid_level', 0), 2),
                round(detection_result.get('confidence', 0), 3),
                detection_result.get('status', 'normal'),
                detection_result.get('note', '')
            ]
            
            self.csv_writer.writerow(row)
            self.csv_file.flush()
            
        except Exception as e:
            print(f"[CSVWriter] 写入失败: {e}")
    
    def close(self):
        """关闭CSV文件"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
    
    def __del__(self):
        """析构函数"""
        self.close()
