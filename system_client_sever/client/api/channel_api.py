# -*- coding: utf-8 -*-
"""
通道API模块
"""

import requests
from typing import List, Dict, Optional


class ChannelAPI:
    """通道API客户端"""
    
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
    
    def get_all_channels(self, status: Optional[str] = None) -> Dict:
        """
        获取所有通道
        
        Args:
            status: 通道状态过滤 (online, offline, error)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/channels"
        params = {}
        if status:
            params['status'] = status
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def get_channel(self, channel_code: str) -> Dict:
        """
        获取单个通道
        
        Args:
            channel_code: 通道编码
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/channels/{channel_code}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def update_channel(self, channel_code: str, config: Dict) -> Dict:
        """
        更新通道配置
        
        Args:
            channel_code: 通道编码
            config: 通道配置
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/channels/{channel_code}"
        
        try:
            response = requests.put(url, headers=self.headers, json=config, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def update_channel_status(self, channel_code: str, status: str) -> Dict:
        """
        更新通道状态
        
        Args:
            channel_code: 通道编码
            status: 状态 (online, offline, error)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/channels/{channel_code}/status"
        
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
