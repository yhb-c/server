# -*- coding: utf-8 -*-
"""
视频监控API客户端
"""

import logging
import requests


class VideoAPI:
    """视频监控API客户端"""
    
    def __init__(self, base_url, auth_api):
        """
        初始化视频API客户端
        
        Args:
            base_url: API基础URL
            auth_api: 认证API实例
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url
        self.auth_api = auth_api
    
    def get_channels(self):
        """
        获取通道列表
        
        Returns:
            dict: 通道列表
        """
        try:
            url = f"{self.base_url}/api/video/channels"
            headers = self.auth_api.get_headers()
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'message': '获取通道列表失败'
                }
        
        except Exception as e:
            self.logger.error(f"获取通道列表异常: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_missions(self):
        """
        获取任务列表
        
        Returns:
            dict: 任务列表
        """
        try:
            url = f"{self.base_url}/api/missions"
            headers = self.auth_api.get_headers()
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'message': '获取任务列表失败'
                }
        
        except Exception as e:
            self.logger.error(f"获取任务列表异常: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def create_mission(self, mission_data):
        """
        创建任务
        
        Args:
            mission_data: 任务数据
            
        Returns:
            dict: 创建结果
        """
        try:
            url = f"{self.base_url}/api/missions"
            headers = self.auth_api.get_headers()
            
            response = requests.post(url, json=mission_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': '任务创建成功'
                }
            else:
                return {
                    'success': False,
                    'message': '任务创建失败'
                }
        
        except Exception as e:
            self.logger.error(f"创建任务异常: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def start_mission(self, mission_id):
        """
        启动任务
        
        Args:
            mission_id: 任务ID
            
        Returns:
            dict: 启动结果
        """
        try:
            url = f"{self.base_url}/api/missions/{mission_id}/start"
            headers = self.auth_api.get_headers()
            
            response = requests.post(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': '任务启动成功'
                }
            else:
                return {
                    'success': False,
                    'message': '任务启动失败'
                }
        
        except Exception as e:
            self.logger.error(f"启动任务异常: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def stop_mission(self, mission_id):
        """
        停止任务
        
        Args:
            mission_id: 任务ID
            
        Returns:
            dict: 停止结果
        """
        try:
            url = f"{self.base_url}/api/missions/{mission_id}/stop"
            headers = self.auth_api.get_headers()
            
            response = requests.post(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': '任务停止成功'
                }
            else:
                return {
                    'success': False,
                    'message': '任务停止失败'
                }
        
        except Exception as e:
            self.logger.error(f"停止任务异常: {e}")
            return {
                'success': False,
                'message': str(e)
            }
