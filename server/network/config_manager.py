# 配置管理器模块
# 负责管理通道配置、检测参数和系统设置

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class ConfigManager:
    """
    配置管理器
    
    职责：
    - 管理通道配置
    - 加载和保存检测参数
    - 处理RTSP流配置
    - 管理模型路径配置
    """
    
    def __init__(self, config_dir: str = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为server/config
        """
        self.logger = logging.getLogger(__name__)
        
        # 设置配置目录
        if config_dir is None:
            current_dir = Path(__file__).parent
            server_dir = current_dir.parent
            config_dir = server_dir / "config"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # 配置文件路径
        self.system_config_file = self.config_dir / "system_config.yaml"
        self.rtsp_config_file = self.config_dir / "rtsp_config.yaml"

        # 内存中的配置缓存
        self.system_config: dict = {}
        self.rtsp_configs: Dict[str, dict] = {}

        # 加载配置
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有配置文件"""
        try:
            self._load_system_config()
            self._load_rtsp_configs()
            self.logger.info("所有配置加载完成")
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
    
    
    def _load_system_config(self):
        """加载系统配置"""
        try:
            if self.system_config_file.exists():
                with open(self.system_config_file, 'r', encoding='utf-8') as f:
                    self.system_config = yaml.safe_load(f) or {}
            else:
                self.system_config = self._get_default_system_config()
                self._save_system_config()
            self.logger.info("系统配置加载完成")
        except Exception as e:
            self.logger.error(f"加载系统配置失败: {e}")
            self.system_config = self._get_default_system_config()
    
    def _load_rtsp_configs(self):
        """加载RTSP配置"""
        try:
            if self.rtsp_config_file.exists():
                with open(self.rtsp_config_file, 'r', encoding='utf-8') as f:
                    self.rtsp_configs = yaml.safe_load(f) or {}
            else:
                self.rtsp_configs = self._get_default_rtsp_configs()
                self._save_rtsp_configs()
            self.logger.info(f"加载RTSP配置: {len(self.rtsp_configs)} 个流")
        except Exception as e:
            self.logger.error(f"加载RTSP配置失败: {e}")
            self.rtsp_configs = self._get_default_rtsp_configs()
    
    def _get_default_system_config(self) -> dict:
        """获取默认系统配置"""
        return {
            'detection': {
                'default_device': 'cuda',
                'batch_size': 1,
                'fps_limit': 25,
                'confidence_threshold': 0.5,
                'kalman_enabled': True
            },
            'websocket': {
                'host': '0.0.0.0',
                'port': 8085,
                'max_connections': 100,
                'heartbeat_interval': 30
            },
            'logging': {
                'level': 'INFO',
                'file_enabled': True,
                'console_enabled': True
            },
            'model': {
                'default_model_dir': '/home/lqj/liquid/server/database/model/detection_model',
                'model_cache_size': 3
            }
        }
    
    def _get_default_rtsp_configs(self) -> dict:
        """获取默认RTSP配置"""
        return {
            'channel1': {
                'name': '通道1',
                'rtsp_url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
                'username': 'admin',
                'password': 'cei345678',
                'ip': '192.168.0.27',
                'port': 8000,
                'stream_path': 'stream1',
                'enabled': True,
                'retry_count': 3,
                'timeout': 10
            },
            'channel2': {
                'name': '通道2',
                'rtsp_url': 'rtsp://admin:cei345678@192.168.0.28:8000/stream1',
                'username': 'admin',
                'password': 'cei345678',
                'ip': '192.168.0.28',
                'port': 8000,
                'stream_path': 'stream1',
                'enabled': False,
                'retry_count': 3,
                'timeout': 10
            }
        }
    
    def get_channel_config(self, channel_id: str) -> Optional[dict]:
        """
        获取通道配置（从default_config.yaml）

        Args:
            channel_id: 通道ID

        Returns:
            dict: 通道配置，如果不存在返回None
        """
        # 从default_config.yaml读取通道配置
        config_path = self.config_dir / "default_config.yaml"
        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            return config.get(channel_id)
        except Exception as e:
            self.logger.error(f"读取通道配置失败: {e}")
            return None
    
    def set_channel_config(self, channel_id: str, config: dict) -> bool:
        """
        设置通道配置（保存到default_config.yaml）

        Args:
            channel_id: 通道ID
            config: 配置数据

        Returns:
            bool: 设置是否成功
        """
        try:
            config_path = self.config_dir / "default_config.yaml"

            # 读取现有配置
            existing_config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_config = yaml.safe_load(f) or {}

            # 更新通道配置
            existing_config[channel_id] = config

            # 保存到文件
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False)

            self.logger.info(f"通道配置已更新: {channel_id}")
            return True

        except Exception as e:
            self.logger.error(f"设置通道配置失败: {e}")
            return False
    
    def get_detection_config(self, channel_id: str) -> dict:
        """
        获取通道的检测配置
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 检测配置
        """
        channel_config = self.get_channel_config(channel_id)
        if not channel_config:
            return {}
        
        # 合并系统默认配置和通道特定配置
        detection_config = self.system_config.get('detection', {}).copy()
        if 'detection' in channel_config:
            detection_config.update(channel_config['detection'])
        
        return detection_config
    
    def get_rtsp_config(self, channel_id: str) -> Optional[dict]:
        """
        获取RTSP配置（兼容原单机版格式）
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: RTSP配置，如果不存在返回None
        """
        # 尝试从rtsp_configs中获取
        if channel_id in self.rtsp_configs:
            config = self.rtsp_configs[channel_id]
            # 转换为统一格式
            return {
                'rtsp_url': config.get('address', ''),
                'username': config.get('username', ''),
                'password': config.get('password', ''),
                'ip': config.get('ip', ''),
                'port': config.get('port', 0),
                'stream_path': config.get('stream_path', ''),
                'enabled': config.get('enabled', False),
                'retry_count': config.get('retry_count', 3),
                'timeout': config.get('timeout', 10)
            }
        
        # 尝试从系统配置中获取（原单机版格式）
        system_channel_key = f'channel{channel_id}' if channel_id.isdigit() else channel_id
        if system_channel_key in self.system_config:
            channel_config = self.system_config[system_channel_key]
            address = channel_config.get('address', '')
            if address:
                return {
                    'rtsp_url': address,
                    'username': 'admin',  # 默认用户名
                    'password': 'cei345678',  # 默认密码
                    'ip': '',
                    'port': 0,
                    'stream_path': '',
                    'enabled': True,
                    'retry_count': 3,
                    'timeout': 10
                }
        
        return None
    
    def set_rtsp_config(self, channel_id: str, config: dict) -> bool:
        """
        设置RTSP配置
        
        Args:
            channel_id: 通道ID
            config: RTSP配置
            
        Returns:
            bool: 设置是否成功
        """
        try:
            config['last_updated'] = datetime.now().isoformat()
            self.rtsp_configs[channel_id] = config
            self._save_rtsp_configs()
            
            self.logger.info(f"RTSP配置已更新: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置RTSP配置失败: {e}")
            return False
    
    def get_model_path(self, channel_id: str) -> Optional[str]:
        """
        获取通道的模型路径（兼容原单机版格式）
        
        Args:
            channel_id: 通道ID
            
        Returns:
            str: 模型路径，如果不存在返回None
        """
        # 尝试从通道配置中获取
        channel_config = self.get_channel_config(channel_id)
        if channel_config and 'model' in channel_config:
            model_path = channel_config['model'].get('model_path')
            if model_path:
                return model_path
        
        # 尝试从系统配置中获取（原单机版格式）
        system_model_key = f'channel{channel_id}_model_path' if channel_id.isdigit() else f'{channel_id}_model_path'
        if system_model_key in self.system_config:
            model_path = self.system_config[system_model_key]
            if model_path:
                # 转换为绝对路径
                if not os.path.isabs(model_path):
                    # 相对于服务器项目根目录
                    server_root = Path(__file__).parent.parent
                    model_path = str(server_root / model_path)
                return model_path
        
        # 返回默认模型路径
        default_model_dir = self.system_config.get('model_base_path', 'database/model/detection_model')
        if not os.path.isabs(default_model_dir):
            server_root = Path(__file__).parent.parent
            default_model_dir = str(server_root / default_model_dir)
        
        return os.path.join(default_model_dir, 'bestmodel', 'tensor.pt')
    
    def set_model_path(self, channel_id: str, model_path: str) -> bool:
        """
        设置通道的模型路径
        
        Args:
            channel_id: 通道ID
            model_path: 模型路径
            
        Returns:
            bool: 设置是否成功
        """
        try:
            if channel_id not in self.channel_configs:
                self.channel_configs[channel_id] = {}
            
            if 'model' not in self.channel_configs[channel_id]:
                self.channel_configs[channel_id]['model'] = {}
            
            self.channel_configs[channel_id]['model']['model_path'] = model_path
            self.channel_configs[channel_id]['last_updated'] = datetime.now().isoformat()
            
            self._save_channel_configs()
            
            self.logger.info(f"模型路径已更新: {channel_id} -> {model_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置模型路径失败: {e}")
            return False
    
    def get_annotation_config(self, channel_id: str) -> dict:
        """
        获取通道的标注配置
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 标注配置
        """
        channel_config = self.get_channel_config(channel_id)
        if channel_config and 'annotation' in channel_config:
            return channel_config['annotation']
        
        return {}
    
    def set_annotation_config(self, channel_id: str, annotation_config: dict) -> bool:
        """
        设置通道的标注配置
        
        Args:
            channel_id: 通道ID
            annotation_config: 标注配置
                - boxes: 检测区域框 [(cx, cy, size), ...]
                - fixed_bottoms: 底部线条 [y1, y2, ...]
                - fixed_tops: 顶部线条 [y1, y2, ...]
                - actual_heights: 实际高度 [h1, h2, ...] (毫米)
                - annotation_initstatus: 初始状态 [0, 1, 2, ...]
                
        Returns:
            bool: 设置是否成功
        """
        try:
            if channel_id not in self.channel_configs:
                self.channel_configs[channel_id] = {}
            
            self.channel_configs[channel_id]['annotation'] = annotation_config
            self.channel_configs[channel_id]['last_updated'] = datetime.now().isoformat()
            
            self._save_channel_configs()
            
            self.logger.info(f"标注配置已更新: {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置标注配置失败: {e}")
            return False
    
    def get_all_channels(self) -> list:
        """获取所有通道ID列表"""
        all_channels = set()

        # 从default_config.yaml读取
        config_path = self.config_dir / "default_config.yaml"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                for key in config.keys():
                    if key.startswith('channel') and isinstance(config[key], dict):
                        all_channels.add(key)
            except Exception as e:
                self.logger.error(f"读取通道列表失败: {e}")

        all_channels.update(self.rtsp_configs.keys())
        return list(all_channels)
    
    
    def _save_system_config(self):
        """保存系统配置到文件"""
        try:
            with open(self.system_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.system_config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"保存系统配置失败: {e}")
    
    def _save_rtsp_configs(self):
        """保存RTSP配置到文件"""
        try:
            with open(self.rtsp_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.rtsp_configs, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"保存RTSP配置失败: {e}")
    
    def reload_configs(self):
        """重新加载所有配置"""
        self.logger.info("重新加载配置...")
        self._load_all_configs()
    
    def get_system_info(self) -> dict:
        """获取系统信息"""
        # 统计通道数量
        channel_count = 0
        config_path = self.config_dir / "default_config.yaml"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                for key in config.keys():
                    if key.startswith('channel') and isinstance(config[key], dict):
                        channel_count += 1
            except Exception as e:
                self.logger.error(f"统计通道数量失败: {e}")

        return {
            'config_dir': str(self.config_dir),
            'channel_count': channel_count,
            'rtsp_count': len(self.rtsp_configs),
            'system_config': self.system_config,
            'last_reload': datetime.now().isoformat()
        }