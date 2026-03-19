# -*- coding: utf-8 -*-
"""
认证API客户端
"""

import logging
import requests


class AuthAPI:
    """认证API客户端"""
    
    def __init__(self, base_url):
        """
        初始化认证API客户端
        
        Args:
            base_url: API基础URL
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url
        self.token = None
    
    def login(self, username, password=""):
        """
        用户登录 - 支持免密码登录
        
        Args:
            username: 用户名
            password: 密码（可选，支持免密码登录）
            
        Returns:
            dict: 登录结果
                {
                    'success': bool,
                    'message': str,
                    'token': str,
                    'user': dict
                }
        """
        try:
            url = f"{self.base_url}/api/v1/auth/login"
            data = {
                'username': username
            }
            # 只有当密码不为空时才添加密码字段
            if password:
                data['password'] = password
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                # 直接检查success字段，因为API返回格式已更新
                if result.get('success', False):
                    self.token = result.get('token')
                    self.logger.info(f"登录成功: {username}")
                    return {
                        'success': True,
                        'message': result.get('message', '登录成功'),
                        'token': self.token,
                        'user': result.get('user', {})
                    }
                else:
                    error_msg = result.get('message', '登录失败')
                    self.logger.warning(f"登录失败: {error_msg}")
                    return {
                        'success': False,
                        'message': error_msg
                    }
            else:
                error_msg = '登录失败'
                try:
                    error_msg = response.json().get('message', error_msg)
                except:
                    pass
                self.logger.warning(f"登录失败: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except requests.exceptions.ConnectionError:
            self.logger.error("无法连接到服务器")
            return {
                'success': False,
                'message': '无法连接到服务器,请检查网络或服务器地址'
            }
        except Exception as e:
            self.logger.error(f"登录异常: {e}")
            return {
                'success': False,
                'message': f'登录异常: {str(e)}'
            }
    
    def register(self, username, email, password):
        """
        用户注册
        
        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            
        Returns:
            dict: 注册结果
        """
        try:
            url = f"{self.base_url}/api/auth/register"
            data = {
                'username': username,
                'email': email,
                'password': password
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(f"注册成功: {username}")
                return {
                    'success': True,
                    'message': '注册成功'
                }
            else:
                error_msg = response.json().get('message', '注册失败')
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except Exception as e:
            self.logger.error(f"注册异常: {e}")
            return {
                'success': False,
                'message': f'注册异常: {str(e)}'
            }
    
    def logout(self):
        """用户登出"""
        try:
            if not self.token:
                return {'success': True}
            
            url = f"{self.base_url}/api/v1/auth/logout"
            headers = {'Authorization': f'Bearer {self.token}'}
            
            response = requests.post(url, headers=headers, timeout=10)
            self.token = None
            
            return {'success': True, 'message': '登出成功'}
        
        except Exception as e:
            self.logger.error(f"登出异常: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_headers(self):
        """获取带Token的请求头"""
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        return {}
