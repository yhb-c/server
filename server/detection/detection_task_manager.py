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
from server.websocket.config_manager import ConfigManager

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
    
    def start_task(self, channel_id: str) -> bool:
        """启动检测任务"""
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
            
            if not rtsp_url:
                self.logger.error(f"RTSP地址未配置: {channel_id}")
                return False
                
            # 创建视频捕获
            video_capture = VideoCaptureFactory.create_capture(rtsp_url)
            if not video_capture:
                self.logger.error(f"视频捕获创建失败: {channel_id}")
                return False
                
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
            self.logger.info(f"检测线程启动: {channel_id}")
            
            video_capture = self.video_captures.get(channel_id)
            detection_engine = self.detection_engines.get(channel_id)
            result_callback = self.tasks[channel_id]['result_callback']
            
            if not video_capture or not detection_engine:
                self.logger.error(f"检测资源不完整: {channel_id}")
                return
                
            frame_count = 0
            last_fps_time = time.time()
            fps_counter = 0
            
            while not stop_event.is_set():
                try:
                    # 获取视频帧
                    frame = video_capture.read()
                    if frame is None:
                        self.logger.warning(f"获取视频帧失败: {channel_id}")
                        time.sleep(0.1)
                        continue
                        
                    # 执行检测
                    detection_result = detection_engine.detect(frame, channel_id=channel_id)
                    
                    if detection_result:
                        # 构建结果数据
                        result_data = {
                            'channel_id': channel_id,
                            'frame_count': frame_count,
                            'timestamp': time.time(),
                            'detection_result': detection_result
                        }
                        
                        # 回调结果
                        result_callback(channel_id, result_data)
                        
                    frame_count += 1
                    fps_counter += 1
                    
                    # 计算FPS
                    current_time = time.time()
                    if current_time - last_fps_time >= 1.0:
                        fps = fps_counter / (current_time - last_fps_time)
                        self.logger.debug(f"检测FPS {channel_id}: {fps:.2f}")
                        fps_counter = 0
                        last_fps_time = current_time
                        
                    # 控制帧率
                    time.sleep(0.033)  # 约30FPS
                    
                except Exception as e:
                    self.logger.error(f"检测循环异常 {channel_id}: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            self.logger.error(f"检测线程异常 {channel_id}: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"检测线程结束: {channel_id}")
    
    def _cleanup_task_resources(self, channel_id: str):
        """清理任务资源"""
        try:
            # 清理视频捕获
            if channel_id in self.video_captures:
                video_capture = self.video_captures[channel_id]
                if hasattr(video_capture, 'release'):
                    video_capture.release()
                del self.video_captures[channel_id]
                
            # 清理检测引擎
            if channel_id in self.detection_engines:
                detection_engine = self.detection_engines[channel_id]
                if hasattr(detection_engine, 'cleanup'):
                    detection_engine.cleanup()
                del self.detection_engines[channel_id]
                
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