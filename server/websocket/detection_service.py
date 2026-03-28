#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测服务 - 重构版本
专注于WebSocket通信，接收客户端信号并执行检测，将检测结果推送到客户端
"""

import os
import sys
import json
import logging
import asyncio
import threading
import time
from typing import Dict, Optional, Any
import traceback

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from server.websocket.config_manager import ConfigManager
from server.detection.detection_task_manager import DetectionTaskManager

class DetectionService:
    """
    检测服务类 - 重构版本
    专注于WebSocket通信相关功能
    """
    
    def __init__(self, websocket_server=None):
        """初始化检测服务"""
        self.logger = logging.getLogger(__name__)
        self.websocket_server = websocket_server

        # 保存主线程的事件循环引用
        try:
            self.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.event_loop = None
            self.logger.warning("无法获取运行中的事件循环")

        # 配置管理器
        self.config_manager = ConfigManager()

        # 检测任务管理器
        self.task_manager = DetectionTaskManager()

        # 通道状态管理
        self.channel_status: Dict[str, Dict] = {}

        # 从配置文件初始化通道
        self._initialize_channels_from_config()

        self.logger.info("检测服务初始化完成")

    def _initialize_channels_from_config(self):
        """从配置文件初始化通道状态"""
        try:
            # 读取default_config.yaml文件
            default_config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'database', 'config', 'default_config.yaml'
            )

            if not os.path.exists(default_config_path):
                self.logger.warning(f"配置文件不存在: {default_config_path}")
                return

            # 加载配置文件
            import yaml
            with open(default_config_path, 'r', encoding='utf-8') as f:
                default_config = yaml.safe_load(f)

            # 遍历所有通道配置
            for key in default_config:
                if key.startswith('channel') and isinstance(default_config[key], dict):
                    channel_id = key
                    channel_config = default_config[key]

                    # 获取对应的模型路径配置
                    model_path_key = f"{channel_id}_model_path"
                    model_path = default_config.get(model_path_key, '')

                    # 初始化通道状态
                    self.channel_status[channel_id] = {
                        'model_loaded': False,
                        'configured': False,
                        'detecting': False,
                        'model_path': None,
                        'config_model_path': model_path,  # 保存配置文件中的模型路径
                        'device': None,
                        'rtsp_url': channel_config.get('address', ''),
                        'file_path': channel_config.get('file_path', ''),
                        'name': channel_config.get('name', channel_id),
                        'load_time': None,
                        'error': None
                    }

                    self.logger.info(f"初始化通道: {channel_id} - {channel_config.get('name')}, 模型: {model_path}")

            self.logger.info(f"从配置文件初始化了 {len(self.channel_status)} 个通道")

        except Exception as e:
            self.logger.error(f"从配置文件初始化通道失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def load_model(self, channel_id: str, model_path: str, device: str = 'cuda') -> bool:
        """
        加载检测模型
        
        Args:
            channel_id: 通道ID
            model_path: 模型文件路径
            device: 设备类型 ('cuda' 或 'cpu')
            
        Returns:
            bool: 加载是否成功
        """
        try:
            self.logger.info(f"开始加载模型 - 通道: {channel_id}, 路径: {model_path}")
            
            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                self.logger.error(f"模型文件不存在: {model_path}")
                return False
            
            # 初始化通道状态
            if channel_id not in self.channel_status:
                self.channel_status[channel_id] = {
                    'model_loaded': False,
                    'configured': False,
                    'detecting': False,
                    'model_path': None,
                    'device': None,
                    'load_time': None,
                    'error': None
                }

            # 创建检测任务（如果不存在）
            if channel_id not in self.task_manager.tasks:
                self.logger.info(f"创建检测任务 - 通道: {channel_id}")

                # 创建任务配置
                task_config = {
                    'rtsp_url': self.channel_status[channel_id].get('rtsp_url') or self.channel_status[channel_id].get('file_path', ''),
                    'model_path': model_path,
                    'device': device
                }

                # 创建任务（使用lambda作为临时回调）
                self.task_manager.create_task(
                    channel_id,
                    task_config,
                    lambda channel, results: self._on_detection_result(channel, results)
                )

            # 使用任务管理器加载模型
            success = self.task_manager.load_model(channel_id, model_path, device)
            
            if success:
                # 更新通道状态
                self.channel_status[channel_id].update({
                    'model_loaded': True,
                    'model_path': model_path,
                    'device': device,
                    'load_time': time.time(),
                    'error': None
                })
                
                self.logger.info(f"模型加载成功 - 通道: {channel_id}")
                
                # 通知客户端模型加载成功
                self._send_status_update(channel_id, 'model_loaded', {
                    'success': True,
                    'model_path': model_path,
                    'device': device
                })
                
            else:
                # 更新错误状态
                self.channel_status[channel_id]['error'] = '模型加载失败'
                self.logger.error(f"模型加载失败 - 通道: {channel_id}")
                
                # 通知客户端模型加载失败
                self._send_status_update(channel_id, 'model_load_error', {
                    'success': False,
                    'error': '模型加载失败'
                })
            
            return success
            
        except Exception as e:
            error_msg = f"加载模型异常 - 通道: {channel_id}, 错误: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            # 更新错误状态
            if channel_id in self.channel_status:
                self.channel_status[channel_id]['error'] = str(e)
            
            # 通知客户端异常
            self._send_status_update(channel_id, 'model_load_error', {
                'success': False,
                'error': str(e)
            })
            
            return False
    
    def configure_channel(self, channel_id: str, config: dict) -> bool:
        """
        配置检测通道
        
        Args:
            channel_id: 通道ID
            config: 配置参数
            
        Returns:
            bool: 配置是否成功
        """
        try:
            self.logger.info(f"开始配置通道 - 通道: {channel_id}")
            
            # 检查通道是否存在
            if channel_id not in self.channel_status:
                self.logger.error(f"通道不存在: {channel_id}")
                return False
            
            # 检查模型是否已加载
            if not self.channel_status[channel_id]['model_loaded']:
                self.logger.error(f"模型未加载 - 通道: {channel_id}")
                return False

            # 任务已在load_model时创建，这里只需配置检测参数
            # 配置检测参数
            detection_config = config.get('detection_config', {})
            if detection_config:
                success = self.task_manager.configure_detection(channel_id, detection_config)
                if not success:
                    self.logger.error(f"配置检测参数失败 - 通道: {channel_id}")
                    return False

            # 配置ROI标注信息
            annotation_config = config.get('annotation_config', {})
            if annotation_config:
                self.logger.info(f"配置ROI标注 - 通道: {channel_id}, 区域数: {annotation_config.get('annotation_count', 0)}")
                success = self.task_manager.configure_annotation(channel_id, annotation_config)
                if not success:
                    self.logger.error(f"配置ROI标注失败 - 通道: {channel_id}")
                    return False
                self.logger.info(f"ROI标注配置成功 - 通道: {channel_id}")
            else:
                self.logger.warning(f"未提供ROI标注配置 - 通道: {channel_id}")
            
            # 更新通道状态
            self.channel_status[channel_id].update({
                'configured': True,
                'config': config,
                'config_time': time.time(),
                'error': None
            })
            
            self.logger.info(f"通道配置成功 - 通道: {channel_id}")
            
            # 通知客户端配置成功
            self._send_status_update(channel_id, 'channel_configured', {
                'success': True,
                'config': config
            })
            
            return True
            
        except Exception as e:
            error_msg = f"配置通道异常 - 通道: {channel_id}, 错误: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            # 更新错误状态
            if channel_id in self.channel_status:
                self.channel_status[channel_id]['error'] = str(e)
            
            # 通知客户端异常
            self._send_status_update(channel_id, 'config_error', {
                'success': False,
                'error': str(e)
            })
            
            return False
    
    def start_detection(self, channel_id: str) -> bool:
        """
        开始检测
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 启动是否成功
        """
        try:
            self.logger.info(f"开始启动检测 - 通道: {channel_id}")
            
            # 检查通道状态
            if channel_id not in self.channel_status:
                self.logger.error(f"通道不存在: {channel_id}")
                return False
            
            channel_state = self.channel_status[channel_id]
            
            # 检查前置条件
            if not channel_state['model_loaded']:
                self.logger.error(f"模型未加载 - 通道: {channel_id}")
                self._send_status_update(channel_id, 'detection_error', {
                    'success': False,
                    'error': '模型未加载'
                })
                return False
            
            if not channel_state['configured']:
                self.logger.error(f"通道未配置 - 通道: {channel_id}")
                self._send_status_update(channel_id, 'detection_error', {
                    'success': False,
                    'error': '通道未配置'
                })
                return False
            
            if channel_state['detecting']:
                self.logger.warning(f"检测已在运行 - 通道: {channel_id}")
                return True
            
            # 启动检测任务
            success = self.task_manager.start_task(channel_id)
            
            if success:
                # 更新状态
                self.channel_status[channel_id].update({
                    'detecting': True,
                    'start_time': time.time(),
                    'error': None
                })
                
                self.logger.info(f"检测启动成功 - 通道: {channel_id}")
                
                # 通知客户端检测开始
                self._send_status_update(channel_id, 'detection_started', {
                    'success': True,
                    'channel_id': channel_id,
                    'start_time': time.time()
                })
                
            else:
                self.logger.error(f"检测启动失败 - 通道: {channel_id}")
                
                # 通知客户端启动失败
                self._send_status_update(channel_id, 'detection_error', {
                    'success': False,
                    'error': '检测启动失败'
                })
            
            return success
            
        except Exception as e:
            error_msg = f"启动检测异常 - 通道: {channel_id}, 错误: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            # 更新错误状态
            if channel_id in self.channel_status:
                self.channel_status[channel_id]['error'] = str(e)
            
            # 通知客户端异常
            self._send_status_update(channel_id, 'detection_error', {
                'success': False,
                'error': str(e)
            })
            
            return False

    def start_all_detections(self) -> dict:
        """
        启动所有通道的检测

        Returns:
            dict: 启动结果统计
        """
        try:
            self.logger.info("开始启动所有通道检测")

            results = {
                'success_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'channels': {}
            }

            # 获取所有通道
            all_channels = list(self.channel_status.keys())
            results['total_count'] = len(all_channels)

            # 遍历所有通道并启动
            for channel_id in all_channels:
                try:
                    success = self.start_detection(channel_id)

                    if success:
                        results['success_count'] += 1
                        results['channels'][channel_id] = {
                            'success': True,
                            'message': '启动成功'
                        }
                    else:
                        results['failed_count'] += 1
                        results['channels'][channel_id] = {
                            'success': False,
                            'message': '启动失败'
                        }

                except Exception as e:
                    results['failed_count'] += 1
                    results['channels'][channel_id] = {
                        'success': False,
                        'message': str(e)
                    }
                    self.logger.error(f"启动通道 {channel_id} 异常: {e}")

            self.logger.info(f"所有通道启动完成: 成功{results['success_count']}个, 失败{results['failed_count']}个")

            return results

        except Exception as e:
            self.logger.error(f"启动所有通道异常: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                'success_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'channels': {},
                'error': str(e)
            }

    def stop_detection(self, channel_id: str) -> bool:
        """
        停止检测
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 停止是否成功
        """
        try:
            self.logger.info(f"开始停止检测 - 通道: {channel_id}")
            
            # 检查通道状态
            if channel_id not in self.channel_status:
                self.logger.error(f"通道不存在: {channel_id}")
                return False
            
            if not self.channel_status[channel_id]['detecting']:
                self.logger.warning(f"检测未在运行 - 通道: {channel_id}")
                return True
            
            # 停止检测任务
            success = self.task_manager.stop_task(channel_id)
            
            if success:
                # 更新状态
                self.channel_status[channel_id].update({
                    'detecting': False,
                    'stop_time': time.time(),
                    'error': None
                })
                
                self.logger.info(f"检测停止成功 - 通道: {channel_id}")
                
                # 通知客户端检测停止
                self._send_status_update(channel_id, 'detection_stopped', {
                    'success': True,
                    'channel_id': channel_id,
                    'stop_time': time.time()
                })
                
            else:
                self.logger.error(f"检测停止失败 - 通道: {channel_id}")
                
                # 通知客户端停止失败
                self._send_status_update(channel_id, 'detection_error', {
                    'success': False,
                    'error': '检测停止失败'
                })
            
            return success
            
        except Exception as e:
            error_msg = f"停止检测异常 - 通道: {channel_id}, 错误: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            # 更新错误状态
            if channel_id in self.channel_status:
                self.channel_status[channel_id]['error'] = str(e)
            
            # 通知客户端异常
            self._send_status_update(channel_id, 'detection_error', {
                'success': False,
                'error': str(e)
            })
            
            return False

    def stop_all_detections(self) -> dict:
        """
        停止所有通道的检测

        Returns:
            dict: 停止结果统计
        """
        try:
            self.logger.info("开始停止所有通道检测")

            results = {
                'success_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'channels': {}
            }

            # 获取所有通道
            all_channels = list(self.channel_status.keys())
            results['total_count'] = len(all_channels)

            # 遍历所有通道并停止
            for channel_id in all_channels:
                try:
                    success = self.stop_detection(channel_id)

                    if success:
                        results['success_count'] += 1
                        results['channels'][channel_id] = {
                            'success': True,
                            'message': '停止成功'
                        }
                    else:
                        results['failed_count'] += 1
                        results['channels'][channel_id] = {
                            'success': False,
                            'message': '停止失败'
                        }

                except Exception as e:
                    results['failed_count'] += 1
                    results['channels'][channel_id] = {
                        'success': False,
                        'message': str(e)
                    }
                    self.logger.error(f"停止通道 {channel_id} 异常: {e}")

            self.logger.info(f"所有通道停止完成: 成功{results['success_count']}个, 失败{results['failed_count']}个")

            return results

        except Exception as e:
            self.logger.error(f"停止所有通道异常: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                'success_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'channels': {},
                'error': str(e)
            }

    def _on_detection_result(self, channel_id: str, detection_result: dict):
        """
        检测结果回调函数

        Args:
            channel_id: 通道ID
            detection_result: 检测结果数据
        """
        try:
            # 构建推送数据（保持完整的检测结果格式）
            push_data = {
                'type': 'detection_result',
                'channel_id': channel_id,
                'timestamp': time.time(),
                'data': detection_result
            }

            # 通过WebSocket推送结果
            self._send_detection_result(channel_id, push_data)

            # 记录调试信息
            self.logger.debug(f"推送检测结果 - 通道: {channel_id}, 帧: {detection_result.get('frame_count', 0)}")

        except Exception as e:
            self.logger.error(f"处理检测结果异常 - 通道: {channel_id}, 错误: {str(e)}")
    
    def _send_detection_result(self, channel_id: str, result_data: dict):
        """
        发送检测结果到客户端

        Args:
            channel_id: 通道ID
            result_data: 结果数据
        """
        try:
            self.logger.info(f"[{channel_id}] 准备推送检测结果: websocket_server={self.websocket_server is not None}, event_loop={self.event_loop is not None}")

            if self.websocket_server and self.event_loop:
                # 从同步线程安全地调度到异步事件循环
                future = asyncio.run_coroutine_threadsafe(
                    self.websocket_server.broadcast_to_channel(channel_id, result_data),
                    self.event_loop
                )
                self.logger.info(f"[{channel_id}] 检测结果已提交到事件循环")
            else:
                if not self.websocket_server:
                    self.logger.warning(f"[{channel_id}] WebSocket服务器未设置，无法发送检测结果")
                if not self.event_loop:
                    self.logger.warning(f"[{channel_id}] 事件循环未设置，无法发送检测结果")

        except Exception as e:
            self.logger.error(f"[{channel_id}] 发送检测结果失败: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _send_status_update(self, channel_id: str, status_type: str, status_data: dict):
        """
        发送状态更新到客户端
        
        Args:
            channel_id: 通道ID
            status_type: 状态类型
            status_data: 状态数据
        """
        try:
            update_data = {
                'type': 'status_update',
                'status_type': status_type,
                'channel_id': channel_id,
                'timestamp': time.time(),
                'data': status_data
            }
            
            if self.websocket_server:
                # 异步发送状态更新
                asyncio.create_task(
                    self.websocket_server.broadcast_to_channel(channel_id, update_data)
                )
            else:
                self.logger.warning("WebSocket服务器未设置，无法发送状态更新")
                
        except Exception as e:
            self.logger.error(f"发送状态更新失败 - 通道: {channel_id}, 错误: {str(e)}")
    
    def get_detection_status(self, channel_id: str) -> dict:
        """
        获取检测状态
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 状态信息
        """
        try:
            if channel_id not in self.channel_status:
                return {'error': '通道不存在'}
            
            # 获取基本状态
            status = self.channel_status[channel_id].copy()
            
            # 获取任务管理器状态
            task_status = self.task_manager.get_task_status(channel_id)
            if 'error' not in task_status:
                status.update(task_status)
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取检测状态异常 - 通道: {channel_id}, 错误: {str(e)}")
            return {'error': str(e)}
    
    def get_all_status(self) -> dict:
        """
        获取所有通道状态
        
        Returns:
            dict: 所有通道状态
        """
        try:
            all_status = {}
            
            for channel_id in self.channel_status:
                all_status[channel_id] = self.get_detection_status(channel_id)
            
            return all_status
            
        except Exception as e:
            self.logger.error(f"获取所有状态异常: {str(e)}")
            return {'error': str(e)}
    
    def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("开始清理检测服务资源")
            
            # 停止所有检测任务
            for channel_id in list(self.channel_status.keys()):
                if self.channel_status[channel_id]['detecting']:
                    self.stop_detection(channel_id)
            
            # 清理任务管理器
            self.task_manager.cleanup_all()
            
            # 清理状态
            self.channel_status.clear()
            
            self.logger.info("检测服务资源清理完成")
            
        except Exception as e:
            self.logger.error(f"清理资源异常: {str(e)}")