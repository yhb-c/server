# -*- coding: utf-8 -*-
"""
配置API模块
"""

import requests
from typing import Dict


class ConfigAPI:
    """配置API客户端"""
    
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
    
    def get_all_configs(self) -> Dict:
        """
        获取所有配置
        
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/configs"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def get_config(self, config_key: str) -> Dict:
        """
        获取单个配置
        
        Args:
            config_key: 配置键
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/configs/{config_key}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def update_config(self, config_key: str, config_value: str) -> Dict:
        """
        更新配置
        
        Args:
            config_key: 配置键
            config_value: 配置值(JSON字符串)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/configs/{config_key}"
        
        try:
            response = requests.put(url, headers=self.headers, 
                                   json={'config_value': config_value}, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
