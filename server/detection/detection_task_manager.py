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

            self.logger.info(f"[{channel_id}] 配置ROI: boxes={len(boxes)}, bottoms={len(fixed_bottoms)}, tops={len(fixed_tops)}, heights={actual_heights}")

            # 配置检测引擎
            detection_engine.configure(
                boxes=boxes,
                fixed_bottoms=fixed_bottoms,
                fixed_tops=fixed_tops,
                actual_heights=actual_heights
            )

            # 保存配置到任务
            self.tasks[channel_id]['annotation_config'] = annotation_config
            self.logger.info(f"ROI标注配置成功: {channel_id}")
            return True

        except Exception as e:
            self.logger.error(f"配置ROI标注失败 {channel_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def start_task(self, channel_id: str) -> bool:
        """启动检测任务"""
        try:
            self.logger.info(f"========== start_task被调用 ==========")
            self.logger.info(f"通道: {channel_id}")
            self.logger.info(f"现有任务列表: {list(self.tasks.keys())}")

            if channel_id not in self.tasks:
                self.logger.error(f"任务不存在: {channel_id}")
                return False

            self.logger.info(f"检查检测线程状态...")
            if channel_id in self.detection_threads and self.detection_threads[channel_id].is_alive():
                self.logger.warning(f"任务已在运行: {channel_id}")
                return False

            # 获取任务配置
            task_config = self.tasks[channel_id]['config']
            self.logger.info(f"任务配置: {task_config}")
            rtsp_url = task_config.get('rtsp_url')
            self.logger.info(f"RTSP地址: {rtsp_url}")

            if not rtsp_url:
                self.logger.error(f"RTSP地址未配置: {channel_id}")
                self.logger.error(f"完整任务配置: {self.tasks[channel_id]}")
                return False

            # 如果模型未加载，尝试加载默认模型
            self.logger.info(f"检查检测引擎: {channel_id in self.detection_engines}")
            if channel_id not in self.detection_engines:
                self.logger.warning(f"检测引擎不存在，尝试加载默认模型")
                default_config = self.config_manager.get_default_config()
                model_key = f"{channel_id}_model_path"
                model_path = default_config.get(model_key)
                self.logger.info(f"默认模型路径: {model_path}")

                if model_path:
                    self.logger.info(f"自动加载默认模型: {channel_id} -> {model_path}")
                    if not self.load_model(channel_id, model_path, device='cpu'):
                        self.logger.error(f"默认模型加载失败: {channel_id}")
                        return False
                else:
                    self.logger.error(f"未找到默认模型配置: {model_key}")
                    return False
            else:
                self.logger.info(f"检测引擎已存在: {channel_id}")

            # 创建视频捕获
            self.logger.info(f"开始创建视频捕获: {rtsp_url}")
            factory = VideoCaptureFactory()
            video_capture = factory.create_capture(rtsp_url, channel_id)
            self.logger.info(f"视频捕获创建结果: {video_capture is not None}")
            if not video_capture:
                self.logger.error(f"视频捕获创建失败: {channel_id}")
                return False

            self.video_captures[channel_id] = video_capture
            self.logger.info(f"视频捕获已保存到字典")
            
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
            self.logger.info(f"[{channel_id}] ========== 检测线程启动 ==========")

            video_capture = self.video_captures.get(channel_id)
            detection_engine = self.detection_engines.get(channel_id)
            result_callback = self.tasks[channel_id]['result_callback']

            self.logger.info(f"[{channel_id}] 检查资源: video_capture={video_capture is not None}, detection_engine={detection_engine is not None}, callback={result_callback is not None}")

            if not video_capture or not detection_engine:
                self.logger.error(f"[{channel_id}] 检测资源不完整: video_capture={video_capture}, detection_engine={detection_engine}")
                return

            # 从配置文件读取FPS限制
            fps_limit = self.config_manager.system_config.get('detection', {}).get('fps_limit', 25)
            frame_interval = 1.0 / fps_limit if fps_limit > 0 else 0.04  # 默认25FPS
            self.logger.info(f"[{channel_id}] FPS限制: {fps_limit}, 帧间隔: {frame_interval:.4f}秒")

            frame_count = 0
            last_fps_time = time.time()
            fps_counter = 0

            self.logger.info(f"[{channel_id}] 进入检测循环...")

            while not stop_event.is_set():
                try:
                    # 获取视频帧
                    ret, frame = video_capture.read()

                    if frame_count == 0:
                        self.logger.info(f"[{channel_id}] 第一帧读取: ret={ret}, frame={'None' if frame is None else f'{frame.shape}'}")

                    if not ret or frame is None:
                        if frame_count == 0:
                            self.logger.error(f"[{channel_id}] 无法读取第一帧，视频源可能有问题")
                        time.sleep(0.01)  # 没有新帧，短暂等待
                        continue

                    # 执行检测
                    if frame_count == 0:
                        self.logger.info(f"[{channel_id}] 开始执行第一帧检测...")

                    detection_result = detection_engine.detect(frame, channel_id=channel_id)

                    if frame_count == 0:
                        result_str = 'None' if detection_result is None else f'success={detection_result.get("success")}'
                        self.logger.info(f"[{channel_id}] 第一帧检测完成: result={result_str}")

                    # 无论检测是否成功，都调用回调函数
                    if detection_result:
                        # 添加时间戳到检测结果
                        detection_result['timestamp'] = time.time()

                        # 记录日志（仅在检测成功时）
                        if detection_result.get('success'):
                            liquid_positions = detection_result.get('liquid_line_positions', {})

                            if frame_count == 0:
                                self.logger.info(f"[{channel_id}] 第一帧检测成功: {len(liquid_positions)}个ROI")

                            for roi_id, position_data in liquid_positions.items():
                                height_mm = position_data.get('height_mm', 0)
                                is_full = position_data.get('is_full', False)
                                self.logger.info(f"[{channel_id}] ROI{roi_id} 检测结果: 高度={height_mm}mm, 满液={is_full}")
                        else:
                            if frame_count == 0:
                                self.logger.warning(f"[{channel_id}] 第一帧检测失败或无结果")

                        # 调用回调函数（无论成功或失败）
                        if frame_count == 0:
                            self.logger.info(f"[{channel_id}] 调用回调函数推送结果...")

                        result_callback(channel_id, detection_result)

                        if frame_count == 0:
                            self.logger.info(f"[{channel_id}] 回调函数调用完成")

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
            self.logger.info(f"[{channel_id}] ========== 检测线程结束 ==========")
    
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