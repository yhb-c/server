# -*- coding: utf-8 -*-
"""
模型API模块
"""

import requests
from typing import Dict, Optional


class ModelAPI:
    """模型API客户端"""
    
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
    
    def get_all_models(self, model_type: Optional[str] = None, 
                       status: Optional[str] = None) -> Dict:
        """
        获取所有模型
        
        Args:
            model_type: 模型类型过滤 (pt, dat, engine)
            status: 状态过滤 (active, archived, testing)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/models"
        params = {}
        if model_type:
            params['model_type'] = model_type
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
    
    def get_model(self, model_id: int) -> Dict:
        """
        获取单个模型
        
        Args:
            model_id: 模型ID
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/models/{model_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
    
    def get_default_model(self, model_type: str = "pt") -> Dict:
        """
        获取默认模型
        
        Args:
            model_type: 模型类型 (pt, dat, engine)
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/v1/models/default"
        params = {'model_type': model_type}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            return response.json()
        except Exception as e:
            return {
                'code': 1,
                'message': f'请求失败: {str(e)}',
                'data': None
            }
