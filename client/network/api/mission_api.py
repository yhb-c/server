# -*- coding: utf-8 -*-
"""
任务API模块
"""

import requests
from typing import List, Dict, Optional


class MissionAPI:
    """任务API客户端"""
    
    def __init__(self, base_url: str, token: str):
        """
        初始化
        
        Args:
            base_url: API基础URL
            token: 认证token
        """
        self.base_url = base_url
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def get_all_missions(self) -> Dict:
        """
        获取所有任务
        
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def get_mission(self, mission_id: int) -> Dict:
        """
        获取单个任务
        
        Args:
            mission_id: 任务ID
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions/{mission_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def create_mission(self, mission_data: Dict) -> Dict:
        """
        创建任务
        
        Args:
            mission_data: 任务数据
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions"
        
        try:
            response = requests.post(url, headers=self.headers, 
                                    json=mission_data, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def update_mission(self, mission_id: int, mission_data: Dict) -> Dict:
        """
        更新任务
        
        Args:
            mission_id: 任务ID
            mission_data: 任务数据
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions/{mission_id}"
        
        try:
            response = requests.put(url, headers=self.headers, 
                                   json=mission_data, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def delete_mission(self, mission_id: int) -> Dict:
        """
        删除任务
        
        Args:
            mission_id: 任务ID
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions/{mission_id}"
        
        try:
            response = requests.delete(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def update_mission_status(self, mission_id: int, status: str) -> Dict:
        """
        更新任务状态
        
        Args:
            mission_id: 任务ID
            status: 状态 (running, stopped, paused, error)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/missions/{mission_id}/status"
        
        try:
            response = requests.put(url, headers=self.headers, 
                                   json={'status': status}, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
