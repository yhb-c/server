# -*- coding: utf-8 -*-
"""
API 基类
"""

import requests
import logging


class BaseAPI:
    """API 基类，提供通用的 HTTP 请求方法"""
    
    def __init__(self, base_url, token_manager=None):
        """
        初始化 API 客户端
        
        Args:
            base_url: API 基础 URL
            token_manager: Token 管理器
        """
        self.base_url = base_url.rstrip('/')
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)
        self.timeout = 30
    
    def _get_headers(self):
        """获取请求头"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # 添加认证 Token
        if self.token_manager:
            token = self.token_manager.get_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'
        
        return headers
    
    def _handle_response(self, response):
        """处理响应"""
        try:
            # 检查 HTTP 状态码
            if response.status_code == 401:
                # Token 过期，尝试刷新
                if self.token_manager:
                    self.token_manager.refresh_token()
                return {'success': False, 'message': 'Token 已过期，请重新登录'}
            
            if response.status_code >= 400:
                return {
                    'success': False,
                    'message': f'请求失败: HTTP {response.status_code}'
                }
            
            # 解析 JSON 响应
            try:
                data = response.json()
                return data
            except ValueError:
                # 非 JSON 响应
                return {
                    'success': True,
                    'data': response.content,
                    'message': 'OK'
                }
        
        except Exception as e:
            self.logger.error(f'处理响应失败: {e}')
            return {'success': False, 'message': str(e)}
    
    def get(self, endpoint, params=None, **kwargs):
        """
        GET 请求
        
        Args:
            endpoint: API 端点
            params: 查询参数
            
        Returns:
            dict: 响应数据
        """
        try:
            url = f'{self.base_url}{endpoint}'
            headers = self._get_headers()
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            
            return self._handle_response(response)
        
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '请求超时'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '连接失败，请检查网络'}
        except Exception as e:
            self.logger.error(f'GET 请求失败: {e}')
            return {'success': False, 'message': str(e)}
    
    def post(self, endpoint, json=None, data=None, files=None, **kwargs):
        """
        POST 请求
        
        Args:
            endpoint: API 端点
            json: JSON 数据
            data: 表单数据
            files: 文件数据
            
        Returns:
            dict: 响应数据
        """
        try:
            url = f'{self.base_url}{endpoint}'
            headers = self._get_headers()
            
            # 如果有文件上传，移除 Content-Type 让 requests 自动设置
            if files:
                headers.pop('Content-Type', None)
            
            response = requests.post(
                url,
                json=json,
                data=data,
                files=files,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            
            return self._handle_response(response)
        
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '请求超时'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '连接失败，请检查网络'}
        except Exception as e:
            self.logger.error(f'POST 请求失败: {e}')
            return {'success': False, 'message': str(e)}
    
    def put(self, endpoint, json=None, data=None, **kwargs):
        """
        PUT 请求
        
        Args:
            endpoint: API 端点
            json: JSON 数据
            data: 表单数据
            
        Returns:
            dict: 响应数据
        """
        try:
            url = f'{self.base_url}{endpoint}'
            headers = self._get_headers()
            
            response = requests.put(
                url,
                json=json,
                data=data,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            
            return self._handle_response(response)
        
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '请求超时'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '连接失败，请检查网络'}
        except Exception as e:
            self.logger.error(f'PUT 请求失败: {e}')
            return {'success': False, 'message': str(e)}
    
    def delete(self, endpoint, **kwargs):
        """
        DELETE 请求
        
        Args:
            endpoint: API 端点
            
        Returns:
            dict: 响应数据
        """
        try:
            url = f'{self.base_url}{endpoint}'
            headers = self._get_headers()
            
            response = requests.delete(
                url,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            
            return self._handle_response(response)
        
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '请求超时'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '连接失败，请检查网络'}
        except Exception as e:
            self.logger.error(f'DELETE 请求失败: {e}')
            return {'success': False, 'message': str(e)}
