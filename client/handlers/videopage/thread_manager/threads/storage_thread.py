# -*- coding: utf-8 -*-

"""
全局存储线程（客户端版本 - 接收服务器数据）

职责：
1. 从所有通道的存储数据队列读取液位数据
2. 保存为CSV文件
3. 按通道ID区分，保存到对应任务文件夹

架构特点：
- 全局单例：所有通道共用一个存储线程
- 简化存储：直接写入CSV文件
- 按通道区分：使用 channel_id 区分不同通道的数据
"""

import os
import csv
import time
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class DetectionResultCSVWriter:
    """检测结果CSV写入器 - 客户端版本"""

    def __init__(self, save_dir: str = None, main_window=None):
        """
        初始化CSV写入器

        Args:
            save_dir: 保存目录路径（可选，默认使用项目根目录下的database/mission_result）
            main_window: 主窗口实例，用于获取通道任务信息
        """
        if save_dir is None:
            # 使用项目根目录下的database/mission_result
            try:
                from database.config import get_project_root
                project_root = get_project_root()
                save_dir = os.path.join(project_root, 'database', 'mission_result')
            except Exception as e:
                save_dir = r"D:\system_client_sever\client\database\mission_result"

        self.base_save_dir = Path(save_dir)
        self.main_window = main_window
        self.csv_files = {}  # {channel_id: (file_handle, csv_writer)}
        self.csv_filepaths = {}  # {channel_id: filepath}

        # 确保基础目录存在
        self.base_save_dir.mkdir(parents=True, exist_ok=True)

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
            return None

    def write_detection_result(self, channel_id: str, heights: List[float], timestamp: Optional[float] = None):
        """
        写入检测结果（简化版本 - 时间戳和液位高度）

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

            # 写入每个液位高度（每个高度一行）
            for i, height in enumerate(heights):
                if height is not None and height > 0:
                    row = [
                        ts,  # 时间戳
                        round(height, 2)  # 液位高度
                    ]
                    csv_writer.writerow(row)

            # 立即刷新到磁盘
            file_handle.flush()

        except Exception as e:
            pass

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

    def close_all(self):
        """关闭所有CSV文件"""
        for channel_id in list(self.csv_files.keys()):
            self.close_channel(channel_id)

    def __del__(self):
        """析构函数 - 确保文件被关闭"""
        self.close_all()


class StorageThread:
    """全局存储线程类（单例模式 - 客户端版本）"""

    # ==================== 全局单例状态 ====================
    _instance = None
    _lock = threading.Lock()
    _running = False
    _thread: Optional[threading.Thread] = None

    # 注册的通道 {channel_id: context}
    _registered_channels: Dict[str, Any] = {}

    # CSV写入器
    _csv_writer: Optional[DetectionResultCSVWriter] = None

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
        # 初始化CSV写入器
        if cls._csv_writer is None:
            cls._csv_writer = DetectionResultCSVWriter(main_window=main_window)

    @classmethod
    def register_channel(cls, channel_id: str, context):
        """注册通道到全局存储线程

        Args:
            channel_id: 通道ID
            context: ChannelThreadContext 实例
        """
        with cls._lock:
            cls._registered_channels[channel_id] = context
            print(f"[存储线程] 注册通道: {channel_id}")

    @classmethod
    def unregister_channel(cls, channel_id: str):
        """从全局存储线程注销通道

        Args:
            channel_id: 通道ID
        """
        with cls._lock:
            if channel_id in cls._registered_channels:
                # 关闭该通道的CSV文件
                if cls._csv_writer:
                    cls._csv_writer.close_channel(channel_id)
                del cls._registered_channels[channel_id]
                print(f"[存储线程] 注销通道: {channel_id}")

    @classmethod
    def start(cls) -> bool:
        """启动全局存储线程"""
        with cls._lock:
            if cls._running:
                return True

            # 初始化CSV写入器
            if cls._csv_writer is None:
                cls._csv_writer = DetectionResultCSVWriter(main_window=cls._main_window)

            cls._running = True
            cls._thread = threading.Thread(
                target=cls._run_loop,
                name="GlobalStorageThread",
                daemon=True
            )
            cls._thread.start()
            print("[存储线程] 全局存储线程已启动")

            return True

    @classmethod
    def stop(cls):
        """停止全局存储线程"""
        with cls._lock:
            if not cls._running:
                return

            cls._running = False

        # 等待线程结束
        if cls._thread and cls._thread.is_alive():
            cls._thread.join(timeout=2.0)

        # 关闭所有CSV文件
        if cls._csv_writer:
            cls._csv_writer.close_all()

        print("[存储线程] 全局存储线程已停止")

    @classmethod
    def _run_loop(cls):
        """全局存储线程主循环"""
        last_log_time = time.time()
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
                            # 提取液位高度数据
                            liquid_positions = detection_result['liquid_line_positions']
                            heights = []

                            # 按area_idx顺序提取高度
                            for area_idx in sorted(liquid_positions.keys()):
                                position_data = liquid_positions[area_idx]
                                height_mm = position_data.get('height_mm', 0.0)
                                heights.append(height_mm)

                            # 获取时间戳
                            timestamp = detection_result.get('timestamp', time.time())

                            # 使用CSV写入器保存数据
                            if cls._csv_writer and heights:
                                cls._csv_writer.write_detection_result(
                                    channel_id=channel_id,
                                    heights=heights,
                                    timestamp=timestamp
                                )
                                data_count += 1

                    except queue.Empty:
                        pass
                    except Exception as e:
                        print(f"[存储线程] 处理数据异常: {e}")
                        import traceback
                        traceback.print_exc()

                # 每5秒打印一次统计
                if time.time() - last_log_time > 5.0:
                    if data_count > 0:
                        print(f"[存储线程] 已处理 {data_count} 条数据")
                    last_log_time = time.time()

                # 短暂休眠，避免CPU空转
                time.sleep(0.01)

            except Exception as e:
                print(f"[存储线程] 主循环异常: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

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
