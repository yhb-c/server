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
import cv2
from typing import Dict, Callable, Optional, Any
import traceback

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from server.video.video_capture_factory import VideoCaptureFactory
from server.detection.detection import LiquidDetectionEngine
from server.network.config_manager import ConfigManager


def calculate_start_frame_id(client_frame_id, frame_id_type='pts'):
    """
    计算检测起始帧ID

    从客户端接收的帧ID基础上加1980ms，作为检测起始帧ID

    Args:
        client_frame_id: 客户端传入的帧ID
        frame_id_type: 帧ID类型，'pts'或'scr'

    Returns:
        int: 检测起始帧ID（client_frame_id + 1980）
    """
    if client_frame_id is None:
        return None

    # 无论是PTS还是SCR，都加1980ms
    start_frame_id = client_frame_id + 1980

    print(f"[calculate_start_frame_id] 客户端帧ID: {client_frame_id}, 类型: {frame_id_type}, 检测起始帧ID: {start_frame_id}")

    return start_frame_id


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
            import traceback
            self.logger.error(f"[调试] 异常堆栈:\n{traceback.format_exc()}")
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
            self.logger.info(f"[调试] start_task被调用 - channel_id: {channel_id}, frame_id: {frame_id}, 类型: {type(frame_id)}")

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

            # 如果指定了frame_id，记录起始帧ID（在检测循环中跳过之前的帧）
            if frame_id is not None:
                self.tasks[channel_id]['start_frame_id'] = frame_id
                self.logger.info(f"[调试] 设置起始帧ID到tasks字典: {frame_id} - 通道: {channel_id}")
            else:
                self.logger.info(f"[调试] frame_id为None，不设置起始帧ID - 通道: {channel_id}")

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

            # 获取视频FPS（用于计算跳帧）
            video_fps = 30  # 默认30fps
            if hasattr(video_capture, 'cv_capture'):
                video_fps = video_capture.cv_capture.get(cv2.CAP_PROP_FPS)
            elif hasattr(video_capture, 'cap'):
                video_fps = video_capture.cap.get(cv2.CAP_PROP_FPS)

            # 计算跳帧间隔（每隔几帧检测一次）
            if video_fps > 0 and fps_limit > 0:
                frame_skip = int(video_fps / fps_limit)  # 30fps / 10fps = 3，每3帧检测1帧
            else:
                frame_skip = 1  # 不跳帧

            self.logger.info(f"[{channel_id}] 视频FPS: {video_fps}, 检测FPS: {fps_limit}, 跳帧间隔: {frame_skip}")

            # 获取客户端传入的帧ID，计算检测起始帧ID
            client_frame_id = self.tasks[channel_id].get('start_frame_id', None)
            start_frame_id = calculate_start_frame_id(client_frame_id, frame_id_type='pts')
            frame_started = (start_frame_id is None)  # 如果没有设置起始帧ID，直接开始检测

            if start_frame_id is not None:
                self.logger.info(f"[{channel_id}] 客户端帧ID: {client_frame_id}, 检测将从帧ID {start_frame_id} 开始")
            else:
                self.logger.info(f"[{channel_id}] 检测从头开始（未设置起始帧ID）")

            # 导入frame_id_manager
            from server.detection.frame_id_manager import get_local_video_frame_id

            # 判断是否为本地视频
            is_video_file = hasattr(video_capture, 'is_video_file') and video_capture.is_video_file

            processed_count = 0  # 已处理帧数（用于日志统计）
            read_count = 0  # 已读取帧数（用于跳帧计算）
            skipped_frame_count = 0
            last_fps_time = time.time()
            fps_counter = 0

            while not stop_event.is_set():
                try:
                    # 获取视频帧
                    ret, frame = video_capture.read()

                    if not ret or frame is None:
                        time.sleep(0.01)  # 没有新帧，短暂等待
                        continue

                    read_count += 1

                    # 跳帧逻辑：每frame_skip帧检测一次
                    if read_count % frame_skip != 0:
                        continue  # 跳过此帧，不进行检测

                    # 获取当前帧ID
                    if is_video_file:
                        # 本地视频：使用PTS时间戳
                        current_frame_id = get_local_video_frame_id(video_capture)
                    else:
                        # RTSP流：暂不支持帧ID
                        current_frame_id = None

                    processed_count += 1

                    # 如果设置了起始帧ID，检查是否到达起始帧
                    if not frame_started and current_frame_id is not None:
                        if current_frame_id >= start_frame_id:
                            frame_started = True
                            self.logger.info(f"[{channel_id}] 到达起始帧ID: {current_frame_id} (>= {start_frame_id})，开始检测")
                            self.logger.info(f"[{channel_id}] 已跳过 {skipped_frame_count} 帧")
                        else:
                            # 跳过此帧，继续读取下一帧
                            skipped_frame_count += 1
                            continue

                    # 如果还没到达起始帧，跳过检测
                    if not frame_started:
                        skipped_frame_count += 1
                        continue

                    # 执行检测（传入当前帧ID）
                    detection_result = detection_engine.detect(
                        frame,
                        channel_id=channel_id,
                        frame_id=current_frame_id
                    )

                    # 无论检测是否成功，都调用回调函数
                    if detection_result:
                        # 调用回调函数（无论成功或失败）
                        result_callback(channel_id, detection_result)

                    fps_counter += 1

                    # 计算FPS（仅统计，不输出日志）
                    current_time = time.time()
                    if current_time - last_fps_time >= 1.0:
                        fps = fps_counter / (current_time - last_fps_time)
                        fps_counter = 0
                        last_fps_time = current_time


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