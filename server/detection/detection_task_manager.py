#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测任务管理器
负责管理检测任务的完整工作流程：视频捕获 + 检测 + 结果回调
"""

import os
import sys
import threading
import time
import logging
from typing import Dict, Callable, Optional, Any
import traceback

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from server.video.video_capture_factory import VideoCaptureFactory
from server.detection.detection import LiquidDetectionEngine
from server.network.config_manager import ConfigManager

class DetectionTaskManager:
    """检测任务管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        
        # 任务状态管理
        self.tasks: Dict[str, Dict] = {}  # channel_id -> task_info
        self.detection_engines: Dict[str, LiquidDetectionEngine] = {}
        self.video_captures: Dict[str, Any] = {}
        
        # 线程管理
        self.detection_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
    def create_task(self, channel_id: str, config: dict, result_callback: Callable) -> bool:
        """创建检测任务"""
        try:
            if channel_id in self.tasks:
                self.logger.warning(f"任务 {channel_id} 已存在")
                return False
                
            # 保存任务信息
            self.tasks[channel_id] = {
                'config': config,
                'result_callback': result_callback,
                'status': 'created',
                'created_time': time.time()
            }
            
            self.logger.info(f"创建检测任务: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建任务失败 {channel_id}: {e}")
            return False
    
    def load_model(self, channel_id: str, model_path: str, device: str = 'cuda') -> bool:
        """加载检测模型"""
        try:
            if channel_id not in self.tasks:
                self.logger.error(f"任务不存在: {channel_id}")
                return False
                
            # 创建检测引擎
            detection_engine = LiquidDetectionEngine(device=device)
            
            # 加载模型
            if not detection_engine.load_model(model_path):
                self.logger.error(f"模型加载失败: {model_path}")
                return False
                
            self.detection_engines[channel_id] = detection_engine
            self.tasks[channel_id]['model_path'] = model_path
            self.tasks[channel_id]['device'] = device
            
            self.logger.info(f"模型加载成功 {channel_id}: {model_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"加载模型失败 {channel_id}: {e}")
            return False
    
    def configure_detection(self, channel_id: str, detection_config: dict) -> bool:
        """配置检测参数"""
        try:
            if channel_id not in self.detection_engines:
                self.logger.error(f"检测引擎不存在: {channel_id}")
                return False
                
            detection_engine = self.detection_engines[channel_id]
            
            # 配置检测参数
            boxes = detection_config.get('boxes', [])
            fixed_bottoms = detection_config.get('fixed_bottoms', [])
            fixed_tops = detection_config.get('fixed_tops', [])
            actual_heights = detection_config.get('actual_heights', [])
            
            detection_engine.configure(
                boxes=boxes,
                fixed_bottoms=fixed_bottoms,
                fixed_tops=fixed_tops,
                actual_heights=actual_heights
            )
            
            self.tasks[channel_id]['detection_config'] = detection_config
            self.logger.info(f"检测配置成功: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置检测失败 {channel_id}: {e}")
            return False

    def configure_annotation(self, channel_id: str, annotation_config: dict) -> bool:
        """
        配置ROI标注信息

        Args:
            channel_id: 通道ID
            annotation_config: 标注配置（从annotation_result.yaml加载）

        Returns:
            bool: 配置是否成功
        """
        try:
            if channel_id not in self.detection_engines:
                self.logger.error(f"检测引擎不存在: {channel_id}")
                return False

            detection_engine = self.detection_engines[channel_id]

            # 提取标注配置
            boxes = annotation_config.get('boxes', [])
            fixed_bottoms = annotation_config.get('fixed_bottoms', [])
            fixed_tops = annotation_config.get('fixed_tops', [])
            areas = annotation_config.get('areas', {})

            # 从areas中提取actual_heights
            actual_heights = []
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                area_info = areas.get(area_key, {})
                height_str = area_info.get('height', '20mm')
                # 提取数字部分
                height_value = float(height_str.replace('mm', '').strip())
                actual_heights.append(height_value)

            # 配置检测引擎
            detection_engine.configure(
                boxes=boxes,
                fixed_bottoms=fixed_bottoms,
                fixed_tops=fixed_tops,
                actual_heights=actual_heights
            )

            # 保存配置到任务
            self.tasks[channel_id]['annotation_config'] = annotation_config
            self.logger.info(f"[{channel_id}] ROI标注配置成功")
            return True

        except Exception as e:
            self.logger.error(f"配置ROI标注失败 {channel_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def start_task(self, channel_id: str, frame_id: int = None) -> bool:
        """启动检测任务

        Args:
            channel_id: 通道ID
            frame_id: 起始帧ID（可选，None表示从头开始）

        Returns:
            bool: 启动是否成功
        """
        try:
            if channel_id not in self.tasks:
                self.logger.error(f"任务不存在: {channel_id}")
                return False

            if channel_id in self.detection_threads and self.detection_threads[channel_id].is_alive():
                self.logger.warning(f"任务已在运行: {channel_id}")
                return False

            # 获取任务配置
            task_config = self.tasks[channel_id]['config']
            rtsp_url = task_config.get('rtsp_url')
            file_path = task_config.get('file_path')

            # 确定视频源（优先使用rtsp_url，其次使用file_path）
            video_source = rtsp_url if rtsp_url else file_path

            if not video_source:
                self.logger.error(f"视频源未配置: {channel_id}")
                return False

            # 如果模型未加载，尝试加载默认模型
            if channel_id not in self.detection_engines:
                default_config = self.config_manager.get_default_config()
                model_key = f"{channel_id}_model_path"
                model_path = default_config.get(model_key)

                if model_path:
                    if not self.load_model(channel_id, model_path, device='cpu'):
                        self.logger.error(f"默认模型加载失败: {channel_id}")
                        return False
                else:
                    self.logger.error(f"未找到默认模型配置: {model_key}")
                    return False

            # 创建视频捕获
            factory = VideoCaptureFactory()
            video_capture = factory.create_capture(video_source, channel_id)
            if not video_capture:
                self.logger.error(f"视频捕获创建失败: {channel_id}")
                return False

            # 如果指定了frame_id，定位到指定帧
            if frame_id is not None:
                from server.detection.frame_id_identify import get_frame_id_identifier
                identifier = get_frame_id_identifier()

                # 检测视频源类型
                video_source_type = identifier.detect_video_source_type(video_capture)
                self.logger.info(f"检测到视频源类型: {video_source_type} - 通道: {channel_id}")

                # 验证帧ID是否有效
                if not identifier.validate_frame_id(video_capture, frame_id, video_source_type):
                    self.logger.error(f"无效的帧ID: {frame_id} (类型: {video_source_type}) - 通道: {channel_id}")
                    if hasattr(video_capture, 'release'):
                        video_capture.release()
                    return False

                # 定位到指定帧
                seek_success = identifier.seek_to_frame(video_capture, frame_id, video_source_type)
                if not seek_success:
                    self.logger.error(f"定位到帧 {frame_id} 失败 (类型: {video_source_type}) - 通道: {channel_id}")
                    if hasattr(video_capture, 'release'):
                        video_capture.release()
                    return False

                if video_source_type == 'local_video':
                    self.logger.info(f"成功定位到帧序号 {frame_id} - 通道: {channel_id}")
                else:
                    self.logger.info(f"成功定位到SCR时间戳 {frame_id} - 通道: {channel_id}")

            self.video_captures[channel_id] = video_capture
            
            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[channel_id] = stop_event
            
            # 创建检测线程
            detection_thread = threading.Thread(
                target=self._detection_worker,
                args=(channel_id, stop_event),
                name=f"detection_{channel_id}"
            )
            
            self.detection_threads[channel_id] = detection_thread
            self.tasks[channel_id]['status'] = 'running'
            self.tasks[channel_id]['start_time'] = time.time()
            
            # 启动线程
            detection_thread.start()
            
            self.logger.info(f"检测任务启动成功: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动任务失败 {channel_id}: {e}")
            return False
    
    def stop_task(self, channel_id: str) -> bool:
        """停止检测任务"""
        try:
            if channel_id not in self.tasks:
                self.logger.error(f"任务不存在: {channel_id}")
                return False
                
            # 设置停止事件
            if channel_id in self.stop_events:
                self.stop_events[channel_id].set()
                
            # 等待线程结束
            if channel_id in self.detection_threads:
                thread = self.detection_threads[channel_id]
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    
            # 清理资源
            self._cleanup_task_resources(channel_id)
            
            self.tasks[channel_id]['status'] = 'stopped'
            self.tasks[channel_id]['stop_time'] = time.time()
            
            self.logger.info(f"检测任务停止成功: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"停止任务失败 {channel_id}: {e}")
            return False
    
    def _detection_worker(self, channel_id: str, stop_event: threading.Event):
        """检测工作线程"""
        try:
            self.logger.info(f"[{channel_id}] 检测线程启动")

            video_capture = self.video_captures.get(channel_id)
            detection_engine = self.detection_engines.get(channel_id)
            result_callback = self.tasks[channel_id]['result_callback']

            if not video_capture or not detection_engine:
                self.logger.error(f"[{channel_id}] 检测资源不完整")
                return

            # 从配置文件读取FPS限制
            fps_limit = self.config_manager.system_config.get('detection', {}).get('fps', 10)
            frame_interval = 1.0 / fps_limit if fps_limit > 0 else 0.1  # 默认10FPS

            frame_count = 0
            last_fps_time = time.time()
            fps_counter = 0

            # 检测视频源类型，决定帧ID分配策略
            # 支持多种视频捕获器类型
            is_local_video = False
            if hasattr(video_capture, 'is_video_file') and video_capture.is_video_file:
                # HKcapture类
                is_local_video = True
            elif hasattr(video_capture, '_is_local_file') and video_capture._is_local_file:
                # OpenCVCaptureWrapper类
                is_local_video = True

            if is_local_video:
                self.logger.info(f"[{channel_id}] 检测到本地视频文件，使用帧序号作为帧ID")
            else:
                self.logger.info(f"[{channel_id}] 检测到RTSP流，帧ID功能暂未实现")

            while not stop_event.is_set():
                try:
                    # 获取视频帧
                    ret, frame = video_capture.read()

                    if not ret or frame is None:
                        time.sleep(0.01)  # 没有新帧，短暂等待
                        continue

                    # 帧ID分配策略
                    if is_local_video:
                        # 本地视频：使用帧序号作为帧ID
                        frame_id = frame_count
                    else:
                        # RTSP流：使用NVR时间戳作为帧ID（后续实现）
                        frame_id = None

                    # 执行检测（传入帧ID）
                    detection_result = detection_engine.detect(
                        frame,
                        channel_id=channel_id,
                        frame_id=frame_id
                    )

                    # 无论检测是否成功，都调用回调函数
                    if detection_result:
                        # 添加帧ID到检测结果
                        if frame_id is not None:
                            detection_result['frame_id'] = frame_id

                        # 日志：检查帧ID
                        if frame_count % 30 == 0:  # 每30帧记录一次
                            self.logger.info(f"[{channel_id}] 帧{frame_count} - frame_id: {detection_result.get('frame_id')}")

                        # 调用回调函数（无论成功或失败）
                        result_callback(channel_id, detection_result)

                    frame_count += 1
                    fps_counter += 1

                    # 计算FPS（仅统计，不输出日志）
                    current_time = time.time()
                    if current_time - last_fps_time >= 1.0:
                        fps = fps_counter / (current_time - last_fps_time)
                        fps_counter = 0
                        last_fps_time = current_time

                    # 控制帧率（从配置文件读取）
                    time.sleep(frame_interval)

                except Exception as e:
                    self.logger.error(f"[{channel_id}] 检测循环异常: {e}")
                    self.logger.error(traceback.format_exc())
                    time.sleep(0.1)

        except Exception as e:
            self.logger.error(f"[{channel_id}] 检测线程异常: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"[{channel_id}] 检测线程结束")
    
    def _cleanup_task_resources(self, channel_id: str):
        """清理任务资源"""
        try:
            # 清理视频捕获
            if channel_id in self.video_captures:
                video_capture = self.video_captures[channel_id]
                if hasattr(video_capture, 'release'):
                    video_capture.release()
                del self.video_captures[channel_id]

            # 注意：不清理detection_engine，因为模型加载耗时，保留以便下次使用
            # 只在任务完全删除时才清理detection_engine

            # 清理线程相关
            if channel_id in self.detection_threads:
                del self.detection_threads[channel_id]

            if channel_id in self.stop_events:
                del self.stop_events[channel_id]

        except Exception as e:
            self.logger.error(f"清理资源失败 {channel_id}: {e}")
    
    def get_task_status(self, channel_id: str) -> dict:
        """获取任务状态"""
        if channel_id not in self.tasks:
            return {'error': '任务不存在'}
            
        task_info = self.tasks[channel_id].copy()
        
        # 添加运行时状态
        if channel_id in self.detection_threads:
            thread = self.detection_threads[channel_id]
            task_info['thread_alive'] = thread.is_alive()
        else:
            task_info['thread_alive'] = False
            
        return task_info
    
    def get_all_tasks_status(self) -> dict:
        """获取所有任务状态"""
        status = {}
        for channel_id in self.tasks:
            status[channel_id] = self.get_task_status(channel_id)
        return status
    
    def cleanup_all(self):
        """清理所有任务"""
        try:
            # 停止所有任务
            for channel_id in list(self.tasks.keys()):
                self.stop_task(channel_id)
                
            # 清理任务记录
            self.tasks.clear()
            
            self.logger.info("所有检测任务已清理")
            
        except Exception as e:
            self.logger.error(f"清理所有任务失败: {e}")