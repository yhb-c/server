# 液位检测服务模块
# 负责从RTSP流获取视频帧，进行液位检测，并通过WebSocket推送检测结果

import asyncio
import cv2
import json
import time
import threading
import logging
from datetime import datetime
from typing import Dict, Optional, Any
import numpy as np
import os
import sys
from pathlib import Path

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from detection.detection import LiquidDetectionEngine


class DetectionService:
    """
    液位检测服务
    
    职责：
    - 管理RTSP视频流连接
    - 执行液位检测
    - 推送检测结果到WebSocket客户端
    - 管理检测状态和配置
    """
    
    def __init__(self, websocket_server=None):
        """
        初始化检测服务
        
        Args:
            websocket_server: WebSocket服务器实例
        """
        self.logger = logging.getLogger(__name__)
        self.websocket_server = websocket_server
        
        # 检测引擎字典 {channel_id: LiquidDetectionEngine}
        self.detection_engines: Dict[str, LiquidDetectionEngine] = {}
        
        # 视频捕获字典 {channel_id: cv2.VideoCapture}
        self.video_captures: Dict[str, cv2.VideoCapture] = {}
        
        # 检测线程字典 {channel_id: threading.Thread}
        self.detection_threads: Dict[str, threading.Thread] = {}
        
        # 检测状态字典 {channel_id: bool}
        self.detection_status: Dict[str, bool] = {}
        
        # 通道配置字典 {channel_id: dict}
        self.channel_configs: Dict[str, dict] = {}
        
        # 停止事件字典 {channel_id: threading.Event}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # 统计信息
        self.detection_stats: Dict[str, dict] = {}
    
    def load_model(self, channel_id: str, model_path: str, device: str = 'cuda') -> bool:
        """
        为指定通道加载检测模型
        
        Args:
            channel_id: 通道ID
            model_path: 模型文件路径（支持相对路径和绝对路径）
            device: 设备类型 ('cuda' 或 'cpu')
            
        Returns:
            bool: 加载是否成功
        """
        try:
            self.logger.info(f"[{channel_id}] === 开始加载检测模型 ===")
            self.logger.info(f"[{channel_id}] 原始模型路径: {model_path}")
            self.logger.info(f"[{channel_id}] 设备类型: {device}")
            
            # 处理相对路径，转换为绝对路径
            if not os.path.isabs(model_path):
                # 相对于服务器项目根目录
                server_root = Path(__file__).parent.parent
                absolute_model_path = str(server_root / model_path)
                self.logger.info(f"[{channel_id}] 转换为绝对路径: {absolute_model_path}")
            else:
                absolute_model_path = model_path
            
            # 检查模型文件是否存在
            if not os.path.exists(absolute_model_path):
                self.logger.error(f"[{channel_id}] 模型文件不存在: {absolute_model_path}")
                # 尝试查找可能的模型文件
                model_dir = os.path.dirname(absolute_model_path)
                if os.path.exists(model_dir):
                    files = os.listdir(model_dir)
                    self.logger.info(f"[{channel_id}] 目录 {model_dir} 中的文件: {files}")
                return False
            else:
                file_size = os.path.getsize(absolute_model_path)
                self.logger.info(f"[{channel_id}] 模型文件存在 ✓ (大小: {file_size} 字节)")
            
            # 创建检测引擎
            self.logger.info(f"[{channel_id}] 创建液位检测引擎...")
            engine = LiquidDetectionEngine(
                model_path=absolute_model_path,
                device=device,
                batch_size=1
            )
            
            self.logger.info(f"[{channel_id}] 检测引擎创建成功 ✓")
            
            # 加载模型
            self.logger.info(f"[{channel_id}] 加载YOLO模型...")
            model_loaded = engine.load_model(absolute_model_path)
            
            if not model_loaded:
                self.logger.error(f"[{channel_id}] YOLO模型加载失败")
                return False
            else:
                self.logger.info(f"[{channel_id}] YOLO模型加载成功 ✓")
            
            self.detection_engines[channel_id] = engine
            
            # 初始化统计信息
            self.detection_stats[channel_id] = {
                'total_frames': 0,
                'detection_count': 0,
                'last_detection_time': None,
                'fps': 0.0,
                'model_path': absolute_model_path,
                'device': device
            }
            
            self.logger.info(f"[{channel_id}] === 检测模型加载完成 ===")
            return True
            
        except Exception as e:
            self.logger.error(f"[{channel_id}] 检测模型加载异常: {e}")
            import traceback
            self.logger.error(f"[{channel_id}] 异常详情:\n{traceback.format_exc()}")
            return False
    
    def configure_channel(self, channel_id: str, config: dict) -> bool:
        """
        配置通道检测参数
        
        Args:
            channel_id: 通道ID
            config: 配置参数
                - rtsp_url: RTSP流地址（可选，如果未提供则从配置文件读取）
                - boxes: 检测区域框 [(cx, cy, size), ...]
                - fixed_bottoms: 底部线条 [y1, y2, ...]
                - fixed_tops: 顶部线条 [y1, y2, ...]
                - actual_heights: 实际高度 [h1, h2, ...] (毫米)
                - annotation_initstatus: 初始状态 [0, 1, 2, ...]
                
        Returns:
            bool: 配置是否成功
        """
        try:
            self.logger.info(f"[{channel_id}] === 开始配置通道参数 ===")
            self.logger.info(f"[{channel_id}] 配置内容: {config}")
            
            # 如果配置中没有rtsp_url，尝试从配置管理器获取
            if 'rtsp_url' not in config:
                self.logger.info(f"[{channel_id}] 配置中无RTSP地址，尝试从配置文件读取...")
                # 导入配置管理器
                try:
                    from .config_manager import ConfigManager
                    config_manager = ConfigManager()
                    rtsp_config = config_manager.get_rtsp_config(channel_id)
                    if rtsp_config and rtsp_config.get('enabled', False):
                        config['rtsp_url'] = rtsp_config['rtsp_url']
                        self.logger.info(f"[{channel_id}] 从配置文件获取RTSP地址: {config['rtsp_url']}")
                    else:
                        self.logger.warning(f"[{channel_id}] 配置文件中未找到启用的RTSP配置")
                except Exception as e:
                    self.logger.warning(f"[{channel_id}] 无法从配置文件读取RTSP地址: {e}")
            else:
                self.logger.info(f"[{channel_id}] 使用配置中的RTSP地址: {config['rtsp_url']}")
            
            # 保存配置
            self.channel_configs[channel_id] = config.copy()
            self.logger.info(f"[{channel_id}] 通道配置已保存")
            
            # 配置检测引擎
            if channel_id in self.detection_engines:
                self.logger.info(f"[{channel_id}] 配置检测引擎参数...")
                engine = self.detection_engines[channel_id]
                
                boxes = config.get('boxes', [])
                fixed_bottoms = config.get('fixed_bottoms', [])
                fixed_tops = config.get('fixed_tops', [])
                actual_heights = config.get('actual_heights', [])
                annotation_initstatus = config.get('annotation_initstatus', [])
                
                self.logger.info(f"[{channel_id}] 检测区域框: {boxes}")
                self.logger.info(f"[{channel_id}] 容器底部: {fixed_bottoms}")
                self.logger.info(f"[{channel_id}] 容器顶部: {fixed_tops}")
                self.logger.info(f"[{channel_id}] 实际高度: {actual_heights}")
                self.logger.info(f"[{channel_id}] 初始状态: {annotation_initstatus}")
                
                engine.configure(
                    boxes=boxes,
                    fixed_bottoms=fixed_bottoms,
                    fixed_tops=fixed_tops,
                    actual_heights=actual_heights,
                    annotation_initstatus=annotation_initstatus
                )
                
                self.logger.info(f"[{channel_id}] 检测引擎配置成功 ✓")
                self.logger.info(f"[{channel_id}] === 通道配置完成 ===")
                return True
            else:
                self.logger.warning(f"[{channel_id}] 检测引擎未加载，无法配置")
                return False
                
        except Exception as e:
            self.logger.error(f"[{channel_id}] 通道配置异常: {e}")
            import traceback
            self.logger.error(f"[{channel_id}] 异常详情:\n{traceback.format_exc()}")
            return False
    
    def start_detection(self, channel_id: str) -> bool:
        """
        启动指定通道的液位检测
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 启动是否成功
        """
        try:
            self.logger.info(f"[{channel_id}] === 开始启动液位检测 ===")
            
            # 步骤1: 检查前置条件
            self.logger.info(f"[{channel_id}] 步骤1: 检查前置条件")
            
            if channel_id not in self.detection_engines:
                self.logger.error(f"[{channel_id}] 前置条件检查失败: 检测引擎未加载")
                return False
            else:
                self.logger.info(f"[{channel_id}] 前置条件检查: 检测引擎已加载 ✓")
            
            if channel_id not in self.channel_configs:
                self.logger.error(f"[{channel_id}] 前置条件检查失败: 通道未配置")
                return False
            else:
                self.logger.info(f"[{channel_id}] 前置条件检查: 通道已配置 ✓")
            
            if self.detection_status.get(channel_id, False):
                self.logger.warning(f"[{channel_id}] 前置条件检查: 检测已在运行")
                return True
            
            # 步骤2: 获取RTSP地址
            self.logger.info(f"[{channel_id}] 步骤2: 获取RTSP配置")
            config = self.channel_configs[channel_id]
            rtsp_url = config.get('rtsp_url')
            
            if not rtsp_url:
                # 尝试从配置管理器获取
                try:
                    from .config_manager import ConfigManager
                    config_manager = ConfigManager()
                    rtsp_config = config_manager.get_rtsp_config(channel_id)
                    if rtsp_config and rtsp_config.get('enabled', False):
                        rtsp_url = rtsp_config['rtsp_url']
                        self.logger.info(f"[{channel_id}] 从配置文件获取RTSP地址: {rtsp_url}")
                    else:
                        self.logger.warning(f"[{channel_id}] 配置文件中未找到启用的RTSP配置")
                except Exception as e:
                    self.logger.warning(f"[{channel_id}] 无法从配置文件读取RTSP地址: {e}")
            else:
                self.logger.info(f"[{channel_id}] 从通道配置获取RTSP地址: {rtsp_url}")
            
            if not rtsp_url:
                self.logger.error(f"[{channel_id}] RTSP地址获取失败: 地址为空")
                return False
            
            # 步骤3: 创建视频捕获
            self.logger.info(f"[{channel_id}] 步骤3: 创建视频捕获连接")
            self.logger.info(f"[{channel_id}] 正在连接RTSP流: {rtsp_url}")
            
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                self.logger.error(f"[{channel_id}] 视频捕获创建失败: 无法连接RTSP流")
                self.logger.error(f"[{channel_id}] RTSP地址: {rtsp_url}")
                return False
            else:
                self.logger.info(f"[{channel_id}] 视频捕获创建成功 ✓")
            
            # 测试读取一帧
            self.logger.info(f"[{channel_id}] 测试读取视频帧...")
            ret, frame = cap.read()
            if not ret or frame is None:
                self.logger.error(f"[{channel_id}] 视频帧读取失败: 无法从RTSP流获取数据")
                cap.release()
                return False
            else:
                self.logger.info(f"[{channel_id}] 视频帧读取成功: 分辨率 {frame.shape[1]}x{frame.shape[0]} ✓")
            
            self.video_captures[channel_id] = cap
            
            # 步骤4: 创建停止事件和检测线程
            self.logger.info(f"[{channel_id}] 步骤4: 创建检测线程")
            
            stop_event = threading.Event()
            self.stop_events[channel_id] = stop_event
            
            # 创建并启动检测线程
            detection_thread = threading.Thread(
                target=self._detection_worker,
                args=(channel_id, stop_event),
                daemon=True,
                name=f"Detection-{channel_id}"
            )
            
            self.detection_threads[channel_id] = detection_thread
            self.detection_status[channel_id] = True
            
            self.logger.info(f"[{channel_id}] 启动检测线程...")
            detection_thread.start()
            
            self.logger.info(f"[{channel_id}] === 液位检测启动成功 ===")
            return True
            
        except Exception as e:
            self.logger.error(f"[{channel_id}] 启动液位检测异常: {e}")
            import traceback
            self.logger.error(f"[{channel_id}] 异常详情:\n{traceback.format_exc()}")
            return False
    
    def stop_detection(self, channel_id: str) -> bool:
        """
        停止指定通道的液位检测
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 停止是否成功
        """
        try:
            self.logger.info(f"[{channel_id}] 停止液位检测")
            
            if not self.detection_status.get(channel_id, False):
                self.logger.warning(f"[{channel_id}] 检测未在运行")
                return True
            
            # 设置停止事件
            if channel_id in self.stop_events:
                self.stop_events[channel_id].set()
            
            # 等待线程结束
            if channel_id in self.detection_threads:
                thread = self.detection_threads[channel_id]
                thread.join(timeout=5.0)  # 最多等待5秒
                
                if thread.is_alive():
                    self.logger.warning(f"[{channel_id}] 检测线程未能正常结束")
                
                del self.detection_threads[channel_id]
            
            # 释放视频捕获
            if channel_id in self.video_captures:
                self.video_captures[channel_id].release()
                del self.video_captures[channel_id]
            
            # 清理停止事件
            if channel_id in self.stop_events:
                del self.stop_events[channel_id]
            
            # 更新状态
            self.detection_status[channel_id] = False
            
            self.logger.info(f"[{channel_id}] 液位检测停止成功")
            return True
            
        except Exception as e:
            self.logger.error(f"[{channel_id}] 停止液位检测失败: {e}")
            return False
    
    def _detection_worker(self, channel_id: str, stop_event: threading.Event):
        """
        检测工作线程
        
        Args:
            channel_id: 通道ID
            stop_event: 停止事件
        """
        self.logger.info(f"[{channel_id}] === 检测线程启动 ===")
        
        cap = self.video_captures[channel_id]
        engine = self.detection_engines[channel_id]
        stats = self.detection_stats[channel_id]
        
        frame_count = 0
        fps_start_time = time.time()
        
        try:
            self.logger.info(f"[{channel_id}] 检测线程开始主循环")
            
            while not stop_event.is_set():
                # 读取视频帧
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning(f"[{channel_id}] 读取视频帧失败，重试中...")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                stats['total_frames'] += 1
                
                # 每100帧输出一次状态
                if frame_count % 100 == 0:
                    self.logger.info(f"[{channel_id}] 已处理 {frame_count} 帧，总帧数: {stats['total_frames']}")
                
                try:
                    # 步骤1: 执行液位检测
                    if frame_count == 1:
                        self.logger.info(f"[{channel_id}] 开始执行第一帧液位检测...")
                    
                    detection_result = engine.detect(frame, channel_id=channel_id)
                    
                    if frame_count == 1:
                        self.logger.info(f"[{channel_id}] 第一帧检测完成，结果: {detection_result is not None}")
                        if detection_result:
                            self.logger.info(f"[{channel_id}] 检测结果键: {list(detection_result.keys())}")
                    
                    if detection_result and detection_result.get('success', False):
                        stats['detection_count'] += 1
                        stats['last_detection_time'] = datetime.now().isoformat()
                        
                        # 从liquid_line_positions提取液位高度数据
                        liquid_positions = detection_result.get('liquid_line_positions', {})
                        heights = []
                        areas = []
                        status = []
                        confidence = []
                        
                        for idx, position_data in liquid_positions.items():
                            if isinstance(position_data, dict):
                                heights.append(position_data.get('height_mm', 0.0))
                                areas.append({
                                    'area_id': idx,
                                    'left': position_data.get('left', 0),
                                    'right': position_data.get('right', 0),
                                    'top': position_data.get('top', 0),
                                    'bottom': position_data.get('bottom', 0),
                                    'y': position_data.get('y', 0),
                                    'height_px': position_data.get('height_px', 0),
                                    'is_full': position_data.get('is_full', False),
                                    'error_flag': position_data.get('error_flag')
                                })
                                status.append('normal' if position_data.get('error_flag') is None else 'error')
                                confidence.append(1.0)  # 默认置信度
                        
                        # 构造推送数据
                        push_data = {
                            'type': 'detection_result',
                            'channel_id': channel_id,
                            'timestamp': stats['last_detection_time'],
                            'frame_count': stats['total_frames'],
                            'heights': heights,  # 液位高度列表 (毫米)
                            'areas': areas,  # 区域信息
                            'status': status,  # 检测状态
                            'confidence': confidence,  # 置信度
                            'success': True,  # 检测成功
                            'camera_status': detection_result.get('camera_status', 'normal'),  # 相机状态
                            'camera_moved': detection_result.get('camera_moved', False)  # 相机是否移动
                        }
                        
                        # 异步推送到WebSocket客户端
                        if self.websocket_server:
                            asyncio.run_coroutine_threadsafe(
                                self.websocket_server.broadcast_to_channel(channel_id, push_data),
                                asyncio.get_event_loop()
                            )
                        
                        if frame_count <= 5 or frame_count % 50 == 0:
                            self.logger.info(f"[{channel_id}] 检测结果推送: {len(heights)}个区域, 高度={heights}")
                    else:
                        if frame_count <= 5:
                            self.logger.warning(f"[{channel_id}] 第{frame_count}帧检测失败或无结果")
                
                except Exception as e:
                    self.logger.error(f"[{channel_id}] 第{frame_count}帧检测处理异常: {e}")
                    if frame_count <= 5:
                        import traceback
                        self.logger.error(f"[{channel_id}] 异常详情:\n{traceback.format_exc()}")
                
                # 计算FPS
                if frame_count % 30 == 0:  # 每30帧计算一次FPS
                    current_time = time.time()
                    elapsed = current_time - fps_start_time
                    if elapsed > 0:
                        stats['fps'] = 30 / elapsed
                        if frame_count % 150 == 0:  # 每150帧输出一次FPS
                            self.logger.info(f"[{channel_id}] 当前FPS: {stats['fps']:.2f}")
                    fps_start_time = current_time
                
                # 控制帧率（避免过度消耗CPU）
                time.sleep(0.04)  # 约25fps
                
        except Exception as e:
            self.logger.error(f"[{channel_id}] 检测线程异常: {e}")
            import traceback
            self.logger.error(f"[{channel_id}] 线程异常详情:\n{traceback.format_exc()}")
        finally:
            self.logger.info(f"[{channel_id}] === 检测线程结束 ===")
            self.logger.info(f"[{channel_id}] 线程统计: 总帧数={frame_count}, 检测成功={stats.get('detection_count', 0)}")
    
    def get_detection_status(self, channel_id: str) -> dict:
        """
        获取通道检测状态
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 状态信息
        """
        return {
            'channel_id': channel_id,
            'is_running': self.detection_status.get(channel_id, False),
            'has_engine': channel_id in self.detection_engines,
            'has_config': channel_id in self.channel_configs,
            'stats': self.detection_stats.get(channel_id, {})
        }
    
    def get_all_status(self) -> dict:
        """
        获取所有通道的检测状态
        
        Returns:
            dict: 所有通道状态
        """
        all_channels = set()
        all_channels.update(self.detection_engines.keys())
        all_channels.update(self.channel_configs.keys())
        all_channels.update(self.detection_status.keys())
        
        return {
            channel_id: self.get_detection_status(channel_id)
            for channel_id in all_channels
        }
    
    def cleanup(self):
        """清理所有资源"""
        self.logger.info("开始清理检测服务资源")
        
        # 停止所有检测
        for channel_id in list(self.detection_status.keys()):
            if self.detection_status[channel_id]:
                self.stop_detection(channel_id)
        
        # 清理检测引擎
        for engine in self.detection_engines.values():
            try:
                engine.cleanup()
            except:
                pass
        
        self.detection_engines.clear()
        self.channel_configs.clear()
        self.detection_stats.clear()
        
        self.logger.info("检测服务资源清理完成")