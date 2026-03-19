# -*- coding: utf-8 -*-

"""
全局存储线程（单例模式）

职责：
1. 从所有通道的存储数据队列读取液位数据
2. 按通道ID区分，保存为CSV曲线文件
3. 使用内存缓冲机制，达到一定数据量后批量写入磁盘

架构特点：
- 全局单例：所有通道共用一个存储线程
- 内存缓冲：数据先存入内存，达到阈值后批量写入
- 按通道区分：使用 channel_id 区分不同通道的数据
"""

import os
import time
import queue
import threading
import yaml
import csv
from datetime import datetime
from typing import Dict, Optional, Any


class StorageThread:
    """全局存储线程类（单例模式）
    
    内存缓冲机制：
    - 数据先存入内存缓冲区
    - 达到 BUFFER_SIZE 条数据时批量写入磁盘
    - 每隔 FLUSH_INTERVAL 秒定期将缓冲区数据写入磁盘（防止数据丢失）
    - 线程停止或程序退出时将剩余数据写入磁盘
    """
    
    # ==================== 配置 ====================
    BUFFER_SIZE = 100000  # 每个ROI的内存缓冲区大小（条数）
    FLUSH_INTERVAL = 1200  # 定期刷新间隔（秒），20分钟，即使缓冲区未满也会写入磁盘
    
    # ==================== 全局单例状态 ====================
    _instance = None
    _lock = threading.Lock()
    _running = False
    _thread: Optional[threading.Thread] = None
    
    # 注册的通道 {channel_id: context}
    _registered_channels: Dict[str, Any] = {}
    
    # 内存缓冲区 {channel_id: {area_idx: [(time, value), ...]}}
    _memory_buffers: Dict[str, Dict[int, list]] = {}
    
    # CSV文件路径映射 {channel_id: {area_idx: filepath}}
    _csv_filepaths: Dict[str, Dict[int, str]] = {}
    
    # 区域名称映射 {channel_id: {area_idx: area_name}}
    _area_names: Dict[str, Dict[int, str]] = {}
    
    # 主窗口引用
    _main_window = None
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @classmethod
    def is_running(cls) -> bool:
        """检查全局存储线程是否正在运行"""
        return cls._running
    
    @classmethod
    def set_main_window(cls, main_window):
        """设置主窗口引用"""
        cls._main_window = main_window
    
    @classmethod
    def register_channel(cls, channel_id: str, context):
        """注册通道到全局存储线程
        
        Args:
            channel_id: 通道ID
            context: ChannelThreadContext 实例
        """
        with cls._lock:
            cls._registered_channels[channel_id] = context
            
            # 初始化该通道的缓冲区和路径
            cls._init_channel_storage(channel_id)
            


    
    @classmethod
    def unregister_channel(cls, channel_id: str):
        """从全局存储线程注销通道
        
        Args:
            channel_id: 通道ID
        """
        with cls._lock:
            # 先将该通道的缓冲区数据写入磁盘
            flushed_count = 0
            if channel_id in cls._memory_buffers:
                flushed_count = sum(len(buf) for buf in cls._memory_buffers[channel_id].values())
                cls._flush_channel_buffers(channel_id)
                del cls._memory_buffers[channel_id]
            
            if channel_id in cls._csv_filepaths:
                del cls._csv_filepaths[channel_id]
            
            if channel_id in cls._area_names:
                del cls._area_names[channel_id]
            
            if channel_id in cls._registered_channels:
                del cls._registered_channels[channel_id]
            


    
    @classmethod
    def start(cls) -> bool:
        """启动全局存储线程"""
        with cls._lock:
            if cls._running:
                return True
            
            cls._running = True
            cls._thread = threading.Thread(
                target=cls._run_loop,
                name="GlobalStorageThread",
                daemon=True
            )
            cls._thread.start()
            
            return True
    
    @classmethod
    def stop(cls):
        """停止全局存储线程"""
        # 计算总缓冲数据量
        total_buffered = sum(
            sum(len(buf) for buf in channel_buffers.values())
            for channel_buffers in cls._memory_buffers.values()
        )
        
        with cls._lock:
            if not cls._running:
                return
            
            cls._running = False
        
        # 等待线程结束
        if cls._thread and cls._thread.is_alive():
            cls._thread.join(timeout=2.0)
        
        # 将所有缓冲区数据写入磁盘
        cls.flush_all_on_exit()
        


    
    @classmethod
    def _init_channel_storage(cls, channel_id: str):
        """初始化通道的存储配置
        
        Args:
            channel_id: 通道ID
        """
        # 获取存储路径
        save_path = cls._get_channel_mission_path(channel_id)
        if not save_path:
            return
        
        # 创建存储目录
        os.makedirs(save_path, exist_ok=True)
        
        # 获取区域名称
        area_names = cls._get_area_names(channel_id)
        cls._area_names[channel_id] = area_names
        
        # 初始化缓冲区和文件路径
        cls._memory_buffers[channel_id] = {}
        cls._csv_filepaths[channel_id] = {}
        
        for area_idx, area_name in area_names.items():
            csv_filename = f"{area_name}.csv"
            csv_filepath = os.path.join(save_path, csv_filename)
            cls._csv_filepaths[channel_id][area_idx] = csv_filepath
            cls._memory_buffers[channel_id][area_idx] = []
    
    @classmethod
    def _run_loop(cls):
        """全局存储线程主循环"""
        last_log_time = time.time()
        last_flush_time = time.time()  # 上次定期刷新时间
        data_count = 0
        
        while cls._running:
            try:
                # 遍历所有注册的通道
                channels_snapshot = dict(cls._registered_channels)
                
                for channel_id, context in channels_snapshot.items():
                    # 检查通道是否有存储数据队列
                    if not hasattr(context, 'storage_data'):
                        continue
                    
                    # 从队列读取数据（非阻塞）
                    try:
                        detection_result = context.storage_data.get_nowait()
                        
                        if detection_result and 'liquid_line_positions' in detection_result:
                            liquid_positions = detection_result['liquid_line_positions']
                            current_time = datetime.now().strftime("%Y-%m-%d-%H:%M:%S.%f")[:-3]
                            

                            
                            # 确保该通道已初始化
                            if channel_id not in cls._memory_buffers:
                                cls._init_channel_storage(channel_id)
                            
                            # 为每个ROI写入数据到内存缓冲区
                            for area_idx, position_data in liquid_positions.items():
                                if channel_id in cls._memory_buffers and area_idx in cls._memory_buffers[channel_id]:
                                    height_mm = position_data.get('height_mm', 0.0)
                                    height_decimal = round(height_mm, 1)
                                    
                                    # 写入内存缓冲区
                                    cls._memory_buffers[channel_id][area_idx].append((current_time, height_decimal))
                                    data_count += 1
                                    
                                    current_buffer_size = len(cls._memory_buffers[channel_id][area_idx])
                                    
                                    # 检查是否达到缓冲区大小
                                    if current_buffer_size >= cls.BUFFER_SIZE:
                                        cls._flush_buffer_to_disk(
                                            cls._csv_filepaths[channel_id][area_idx],
                                            cls._memory_buffers[channel_id][area_idx]
                                        )
                                        cls._memory_buffers[channel_id][area_idx] = []
                    
                    except queue.Empty:
                        pass
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                
                # 每5秒打印一次统计
                if time.time() - last_log_time > 5.0:
                    total_buffered = sum(
                        sum(len(buf) for buf in channel_buffers.values())
                        for channel_buffers in cls._memory_buffers.values()
                    )
                    # print(f"📝 [全局存储线程] 已处理 {data_count} 条，缓冲区: {total_buffered} 条")
                    last_log_time = time.time()
                
                # 定期刷新：每隔 FLUSH_INTERVAL 秒将所有缓冲区数据写入磁盘
                if time.time() - last_flush_time >= cls.FLUSH_INTERVAL:
                    cls._periodic_flush_all_buffers()
                    last_flush_time = time.time()
                
                # 短暂休眠，避免CPU空转
                time.sleep(0.01)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
    
    @classmethod
    def _flush_buffer_to_disk(cls, filepath: str, buffer: list):
        """将缓冲区数据批量写入磁盘
        
        Args:
            filepath: CSV文件路径
            buffer: 数据列表 [(time, value), ...]
        """
        if not buffer:
            return
        
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                for time_str, value in buffer:
                    f.write(f"{time_str} {value:.1f}\n")
        except Exception as e:
            pass
    
    @classmethod
    def _periodic_flush_all_buffers(cls):
        """定期刷新：将所有通道的缓冲区数据写入磁盘
        
        用于防止缓冲区长时间未满导致数据丢失
        """
        total_flushed = 0
        
        with cls._lock:
            for channel_id, channel_buffers in cls._memory_buffers.items():
                csv_filepaths = cls._csv_filepaths.get(channel_id, {})
                for area_idx, buffer in list(channel_buffers.items()):
                    if buffer and area_idx in csv_filepaths:
                        cls._flush_buffer_to_disk(csv_filepaths[area_idx], buffer)
                        total_flushed += len(buffer)
                        # 清空已写入的缓冲区
                        cls._memory_buffers[channel_id][area_idx] = []
        
        pass
    
    @classmethod
    def _flush_channel_buffers(cls, channel_id: str):
        """将指定通道的所有缓冲区数据写入磁盘
        
        Args:
            channel_id: 通道ID
        """
        if channel_id not in cls._memory_buffers:
            return
        
        total_flushed = 0
        for area_idx, buffer in cls._memory_buffers[channel_id].items():
            if buffer and channel_id in cls._csv_filepaths and area_idx in cls._csv_filepaths[channel_id]:
                cls._flush_buffer_to_disk(cls._csv_filepaths[channel_id][area_idx], buffer)
                total_flushed += len(buffer)
        

    
    @classmethod
    def flush_all_on_exit(cls):
        """程序退出时写入所有通道的剩余数据"""
        total_flushed = 0
        
        for channel_id, channel_buffers in cls._memory_buffers.items():
            csv_filepaths = cls._csv_filepaths.get(channel_id, {})
            for area_idx, buffer in channel_buffers.items():
                if buffer and area_idx in csv_filepaths:
                    cls._flush_buffer_to_disk(csv_filepaths[area_idx], buffer)
                    total_flushed += len(buffer)
        
        # 清空缓冲区
        cls._memory_buffers.clear()
        cls._csv_filepaths.clear()
        cls._area_names.clear()
    
    # ==================== 辅助方法 ====================
    
    @staticmethod
    def _get_project_root():
        """获取项目根目录"""
        import sys
        
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        else:
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
            return project_root
    
    @classmethod
    def _get_channel_mission_path(cls, channel_id: str) -> Optional[str]:
        """从通道的 channelmission 标签获取任务路径"""
        if not cls._main_window:
            return None
        
        try:
            channel_num = int(channel_id.replace('channel', ''))
            mission_var_name = f'channel{channel_num}mission'
            
            if hasattr(cls._main_window, mission_var_name):
                mission_label = getattr(cls._main_window, mission_var_name)
                task_folder_name = mission_label.text()
                
                if not task_folder_name or task_folder_name.strip() == "" or task_folder_name == "未分配任务":
                    return None
                
                project_root = cls._get_project_root()
                mission_path = os.path.join(project_root, 'database', 'mission_result', task_folder_name.strip())
                return mission_path
            
            return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    @classmethod
    def _get_area_names(cls, channel_id: str) -> Dict[int, str]:
        """获取区域名称列表"""
        area_names = {}
        
        try:
            project_root = cls._get_project_root()
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if os.path.exists(annotation_file):
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    annotation_data = yaml.safe_load(f)
                
                if annotation_data and channel_id in annotation_data:
                    areas_config = annotation_data[channel_id].get('areas', {})
                    
                    for area_key, area_info in areas_config.items():
                        area_idx = int(area_key.split('_')[1]) - 1
                        area_name = area_info.get('name', '')
                        if area_name:
                            area_names[area_idx] = area_name
        except Exception as e:
            pass
        
        return area_names
    
    # ==================== 兼容旧接口 ====================
    
    @staticmethod
    def run(context, frame_rate: float, main_window=None):
        """兼容旧接口：启动存储（实际注册到全局线程）
        
        Args:
            context: ChannelThreadContext 实例
            frame_rate: 存储帧率（已废弃，全局线程不使用）
            main_window: 主窗口实例
        """
        channel_id = context.channel_id
        
        # 设置主窗口
        if main_window:
            StorageThread.set_main_window(main_window)
        
        # 注册通道
        StorageThread.register_channel(channel_id, context)
        
        # 启动全局存储线程（如果尚未启动）
        if not StorageThread.is_running():
            StorageThread.start()
        
        # 等待直到 storage_flag 变为 False
        while context.storage_flag:
            time.sleep(0.1)
        
        # 注销通道
        StorageThread.unregister_channel(channel_id)
