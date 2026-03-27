# -*- coding: utf-8 -*-
"""
API管理器 - 统一管理所有API客户端
"""

from .auth_api import AuthAPI
from .channel_api import ChannelAPI
from .mission_api import MissionAPI
from .config_api import ConfigAPI
from .model_api import ModelAPI


class APIManager:
    """API管理器"""
    
    def __init__(self, base_url: str):
        """
        初始化
        
        Args:
            base_url: API基础URL
        """
        self.base_url = base_url
        self.token = None
        
        # 初始化认证API
        self.auth = AuthAPI(base_url)
        
        # 其他API在登录后初始化
        self.channel = None
        self.mission = None
        self.config = None
        self.model = None
    
    def login(self, username: str, password: str) -> dict:
        """
        登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            dict: 登录结果
        """
        result = self.auth.login(username, password)
        
        if result.get('code') == 0:
            # 保存token
            self.token = result['data']['token']
            
            # 初始化其他API客户端
            self.channel = ChannelAPI(self.base_url, self.token)
            self.mission = MissionAPI(self.base_url, self.token)
            self.config = ConfigAPI(self.base_url, self.token)
            self.model = ModelAPI(self.base_url, self.token)
        
        return result
    
    def logout(self) -> dict:
        """
        登出
        
        Returns:
            dict: 登出结果
        """
        if not self.token:
            return {'code': 1, 'message': '未登录', 'data': None}
        
        result = self.auth.logout(self.token)
        
        # 清除token和API客户端
        self.token = None
        self.channel = None
        self.mission = None
        self.config = None
        self.model = None
        
        return result
    
    def is_logged_in(self) -> bool:
        """
        检查是否已登录
        
        Returns:
            bool: 是否已登录
        """
        return self.token is not None
    
    def get_current_user(self) -> dict:
        """
        获取当前用户信息
        
        Returns:
            dict: 用户信息
        """
        if not self.token:
            return {'code': 1, 'message': '未登录', 'data': None}
        
        return self.auth.get_current_user(self.token)


# 全局API管理器实例
_api_manager = None


def get_api_manager(base_url: str = None) -> APIManager:
    """
    获取全局API管理器实例
    
    Args:
        base_url: API基础URL (首次调用时必须提供)
        
    Returns:
        APIManager: API管理器实例
    """
    global _api_manager
    
    if _api_manager is None:
        if base_url is None:
            raise ValueError("首次调用必须提供base_url")
        _api_manager = APIManager(base_url)
    
    return _api_manager
