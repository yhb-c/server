# -*- coding: utf-8 -*-
"""
数据管理模块 - 管理检测数据的存储和查询
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class DataManager:
    """数据管理器"""
    
    def __init__(self, base_path: str):
        """
        初始化数据管理器
        
        Args:
            base_path: 数据存储基础路径
        """
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def save_detection_result(self, channel_id: str, result: dict):
        """
        保存检测结果
        
        Args:
            channel_id: 通道ID
            result: 检测结果
        """
        # 按日期组织目录
        date_str = datetime.now().strftime('%Y%m%d')
        date_dir = os.path.join(self.base_path, channel_id, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%H%M%S_%f')
        filename = f'result_{timestamp}.json'
        filepath = os.path.join(date_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def get_results_by_date(self, channel_id: str, date: str) -> List[dict]:
        """
        获取指定日期的检测结果
        
        Args:
            channel_id: 通道ID
            date: 日期字符串 (YYYYMMDD)
            
        Returns:
            检测结果列表
        """
        date_dir = os.path.join(self.base_path, channel_id, date)
        
        if not os.path.exists(date_dir):
            return []
        
        results = []
        for filename in sorted(os.listdir(date_dir)):
            if filename.endswith('.json'):
                filepath = os.path.join(date_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                        results.append(result)
                except:
                    continue
        
        return results
    
    def get_latest_result(self, channel_id: str) -> Optional[dict]:
        """
        获取最新的检测结果
        
        Args:
            channel_id: 通道ID
            
        Returns:
            最新的检测结果，如果没有则返回None
        """
        channel_dir = os.path.join(self.base_path, channel_id)
        
        if not os.path.exists(channel_dir):
            return None
        
        # 获取最新的日期目录
        date_dirs = sorted([d for d in os.listdir(channel_dir) 
                           if os.path.isdir(os.path.join(channel_dir, d))], 
                          reverse=True)
        
        if not date_dirs:
            return None
        
        # 获取最新日期目录中的最新文件
        latest_date_dir = os.path.join(channel_dir, date_dirs[0])
        result_files = sorted([f for f in os.listdir(latest_date_dir) 
                              if f.endswith('.json')], 
                             reverse=True)
        
        if not result_files:
            return None
        
        # 读取最新文件
        latest_file = os.path.join(latest_date_dir, result_files[0])
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def cleanup_old_data(self, channel_id: str, days: int = 30):
        """
        清理旧数据
        
        Args:
            channel_id: 通道ID
            days: 保留天数
        """
        channel_dir = os.path.join(self.base_path, channel_id)
        
        if not os.path.exists(channel_dir):
            return
        
        # 计算截止日期
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y%m%d')
        
        # 删除旧目录
        for date_dir in os.listdir(channel_dir):
            if date_dir < cutoff_str:
                dir_path = os.path.join(channel_dir, date_dir)
                if os.path.isdir(dir_path):
                    import shutil
                    shutil.rmtree(dir_path)
