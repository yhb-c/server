# -*- coding: utf-8 -*-

"""
单个通道的线程上下文

包含该通道的所有线程、队列和控制标志
"""

import threading
import queue
from typing import Optional
from collections import deque


class ChannelThreadContext:
    """单个通道的线程上下文
    
    包含该通道的所有线程、队列和控制标志
    """
    
    def __init__(self, channel_id: str, max_buffer_size: int = 2):
        """
        Args:
            channel_id: 通道ID
            max_buffer_size: 帧缓存队列最大容量（默认2帧，避免积压）
        """
        self.channel_id = channel_id
        
        # ========== 数据队列 ==========
        # frame_buffer - 捕获线程写入，显示/检测线程读取
        self.frame_buffer = queue.Queue(maxsize=max_buffer_size)
        
        #  显示结果队列 - 检测线程写入，显示线程读取（高频更新，小缓冲）
        # 容量计算：detection_frame_rate=5fps，10个数据 = 2秒缓冲
        self.detection_mission_results = queue.Queue(maxsize=10)
        
        #  存储数据队列 - 检测线程写入，存储线程读取（大缓冲，应对I/O延迟）
        # 容量计算：detection_frame_rate=5fps，50个数据 = 10秒缓冲（存储线程全速消费）
        self.storage_data = queue.Queue(maxsize=50)
        
        # 显示帧队列 - 显示线程写入，存储线程读取
        self.display_frames = queue.Queue(maxsize=10)
        
        # ========== 线程对象 ==========
        self.capture_thread: Optional[threading.Thread] = None
        self.display_thread: Optional[threading.Thread] = None
        self.detection_thread: Optional[threading.Thread] = None
        # 注意：curve_thread已改为全局单例，不再存储在context中
        self.storage_thread: Optional[threading.Thread] = None
        
        # ========== 控制标志 ==========
        self.capture_flag = False     # 捕获线程运行标志
        self.display_flag = False     # 显示线程运行标志
        self.channel_detect_status = False   # 检测线程运行标志
        # 注意：curve_flag已改为全局单例管理，不再存储在context中
        self.storage_flag = False     # 存储线程运行标志
        
        # ========== 状态数据 ==========
        self.capture_count = 0        # 捕获帧计数
        self.display_count = 0        # 显示帧计数
        self.detection_count = 0      # 检测帧计数
        self.storage_count = 0        # 存储帧计数
        
        # 检测是否启动（影响显示线程的行为）
        self.detection_enabled = False
        
        # 存储路径配置
        self.storage_path = None
        
        # 最新检测结果（用于显示线程叠加信息）
        self.latest_detection = None
        self.detection_lock = threading.Lock()
        
        #  最新帧（用于非消费性读取）
        # 捕获线程写入，显示线程/其他组件可以读取副本而不消费队列
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # 曲线数据缓存（用于实时绘制）
        self.curve_data = deque(maxlen=1000)  # 保留最近1000个数据点
        
        # 曲线区域索引映射（保留用于向后兼容，虽然现在由全局曲线线程管理）
        self.curve_area_index_map = {}  # {csv_filepath: area_idx}
        self.curve_next_area_idx = 0
        
        #  每个通道独立的回调函数
        self.on_frame_displayed = None
        self.on_detection_mission_result = None
        
        #  每个通道独立的检测模型
        self.detection_model = None
        
        # 相机姿态异常标志（True时暂停向检测线程输入帧）
        self.camera_position_paused = False
        
    def clear_queues(self):
        """清空所有队列"""
        queues = [
            self.frame_buffer,
            self.detection_mission_results,
            self.storage_data,  #  添加存储数据队列
            self.display_frames
        ]
        
        for q in queues:
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

