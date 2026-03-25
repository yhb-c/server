# -*- coding: utf-8 -*-
"""
配置管理模块

功能说明:
- 提供统一的配置管理接口，支持本地和远程两种配置管理方式
- LocalConfigManager: 本地配置文件管理，读取本地YAML配置文件
- RemoteConfigManager: 远程配置管理，通过SSH从服务端读取配置文件
- 统一的配置加载函数，优先使用远程配置，本地配置作为备用

主要功能:
1. 本地配置文件的读取和保存
2. 远程配置文件的读取和保存（通过SSH）
3. 配置缓存机制，提高访问效率
4. 备用配置机制，确保系统稳定运行
5. 统一的配置接口，便于切换配置源

使用场景:
- 客户端启动时加载配置
- 通道配置修改后保存
- 多客户端共享统一配置源
- 离线模式下使用本地配置
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 导入SSH管理器
try:
    from ...ssh_connect.ssh_manager import SSHManager
except ImportError:
    try:
        from ssh_connect.ssh_manager import SSHManager
    except ImportError:
        try:
            from client.ssh_connect.ssh_manager import SSHManager
        except ImportError:
            # 如果SSH管理器不可用，设置为None
            SSHManager = None


class LocalConfigManager:
    """本地配置管理器 - 管理本地YAML配置文件"""
    
    def __init__(self, config_dir=None):
        """
        初始化本地配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为项目config目录
        """
        self.logger = logging.getLogger(__name__)
        
        if config_dir is None:
            # 默认配置文件目录
            self.config_dir = Path(__file__).parent.parent.parent / 'config'
        else:
            self.config_dir = Path(config_dir)
        
        self.client_config_path = self.config_dir / 'client_config.yaml'
        self.camera_config_path = self.config_dir / 'camera_config.yaml'
    
    def load_client_config(self) -> Dict[str, Any]:
        """
        加载客户端配置文件
        
        Returns:
            dict: 客户端配置数据
        """
        try:
            if self.client_config_path.exists():
                with open(self.client_config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                self.logger.info(f"成功加载本地客户端配置: {self.client_config_path}")
                return config
            else:
                self.logger.warning(f"本地客户端配置文件不存在: {self.client_config_path}")
                return self._get_default_client_config()
        except Exception as e:
            self.logger.error(f"加载本地客户端配置失败: {e}")
            return self._get_default_client_config()
    
    def save_client_config(self, config: Dict[str, Any]) -> bool:
        """
        保存客户端配置文件
        
        Args:
            config: 配置数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.client_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
            self.logger.info(f"成功保存本地客户端配置: {self.client_config_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存本地客户端配置失败: {e}")
            return False
    
    def load_camera_config(self) -> Dict[str, Any]:
        """
        加载相机配置文件
        
        Returns:
            dict: 相机配置数据
        """
        try:
            if self.camera_config_path.exists():
                with open(self.camera_config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                self.logger.info(f"成功加载本地相机配置: {self.camera_config_path}")
                return config
            else:
                self.logger.warning(f"本地相机配置文件不存在: {self.camera_config_path}")
                return self._get_default_camera_config()
        except Exception as e:
            self.logger.error(f"加载本地相机配置失败: {e}")
            return self._get_default_camera_config()
    
    def save_camera_config(self, config: Dict[str, Any]) -> bool:
        """
        保存相机配置文件
        
        Args:
            config: 配置数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.camera_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
            self.logger.info(f"成功保存本地相机配置: {self.camera_config_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存本地相机配置失败: {e}")
            return False
    
    def _get_default_client_config(self) -> Dict[str, Any]:
        """获取默认客户端配置"""
        return {
            'server': {
                'api_url': 'http://192.168.0.121:8084',
                'ws_url': 'ws://192.168.0.121:8085'
            },
            'ui': {
                'theme': 'light',
                'language': 'zh_CN'
            },
            'data': {
                'cache_dir': './cache',
                'log_dir': './logs'
            },
            'network': {
                'timeout': 30,
                'retry_times': 3,
                'api_server': '192.168.0.121',
                'ws_server': '192.168.0.121',
                'camera_rtsp': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'log_level': 'INFO'
        }
    
    def _get_default_camera_config(self) -> Dict[str, Any]:
        """获取默认相机配置"""
        return {
            'channels': {
                1: {
                    'channel_id': 1,
                    'name': '通道1',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                2: {
                    'channel_id': 2,
                    'name': '通道2',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                3: {
                    'channel_id': 3,
                    'name': '通道3',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                4: {
                    'channel_id': 4,
                    'name': '通道4',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                }
            }
        }


class RemoteConfigManager:
    """远程配置管理器 - 通过SSH从服务端读取配置文件"""
    
    def __init__(self, server_config_path=None):
        """
        初始化远程配置管理器
        
        Args:
            server_config_path: 服务端配置文件路径
        """
        self.logger = logging.getLogger(__name__)
        self.ssh_manager = None
        self._config_cache = {}
        
        if server_config_path is None:
            self._server_config_path = "/home/lqj/liquid/server/database/config"
        else:
            self._server_config_path = server_config_path
    
    def _get_ssh_manager(self) -> Optional['SSHManager']:
        """获取SSH管理器实例"""
        if SSHManager is None:
            self.logger.error("SSHManager模块不可用")
            return None
            
        if self.ssh_manager is None:
            try:
                self.ssh_manager = SSHManager()
                return self.ssh_manager
            except Exception as e:
                self.logger.error(f"初始化SSH管理器失败: {e}")
                return None
        return self.ssh_manager
    
    def load_channel_config(self) -> Dict[str, Any]:
        """
        从服务端加载通道配置文件
        
        Returns:
            dict: 通道配置数据
        """
        try:
            ssh_manager = self._get_ssh_manager()
            if not ssh_manager:
                self.logger.error("SSH连接不可用，无法读取远程配置")
                return self._get_fallback_channel_config()
            
            # 读取服务端的通道配置文件
            remote_file_path = f"{self._server_config_path}/channel_config.yaml"
            self.logger.info(f"正在从服务端读取配置文件: {remote_file_path}")
            
            # 通过SSH读取远程文件内容
            result = ssh_manager.execute_remote_command(f"cat {remote_file_path}")
            if result['success'] and result['stdout']:
                config_content = result['stdout']
                config_data = yaml.safe_load(config_content)
                
                self.logger.info("成功从服务端加载通道配置")
                self._config_cache['channel_config'] = config_data
                return config_data
            else:
                self.logger.error(f"读取远程配置文件失败: {result.get('stderr', '未知错误')}")
                return self._get_fallback_channel_config()
                
        except Exception as e:
            self.logger.error(f"加载远程通道配置失败: {e}")
            return self._get_fallback_channel_config()
    
    def load_default_config(self) -> Dict[str, Any]:
        """
        从服务端加载默认配置文件
        
        Returns:
            dict: 默认配置数据
        """
        try:
            ssh_manager = self._get_ssh_manager()
            if not ssh_manager:
                self.logger.error("SSH连接不可用，无法读取远程配置")
                return self._get_fallback_default_config()
            
            # 读取服务端的默认配置文件
            remote_file_path = f"{self._server_config_path}/default_config.yaml"
            self.logger.info(f"正在从服务端读取默认配置文件: {remote_file_path}")
            
            # 通过SSH读取远程文件内容
            result = ssh_manager.execute_remote_command(f"cat {remote_file_path}")
            if result['success'] and result['stdout']:
                config_content = result['stdout']
                config_data = yaml.safe_load(config_content)
                
                self.logger.info("成功从服务端加载默认配置")
                self._config_cache['default_config'] = config_data
                return config_data
            else:
                self.logger.error(f"读取远程默认配置文件失败: {result.get('stderr', '未知错误')}")
                return self._get_fallback_default_config()
                
        except Exception as e:
            self.logger.error(f"加载远程默认配置失败: {e}")
            return self._get_fallback_default_config()
    
    def save_channel_config(self, config_data: Dict[str, Any]) -> bool:
        """
        保存通道配置到服务端
        
        Args:
            config_data: 要保存的配置数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            ssh_manager = self._get_ssh_manager()
            if not ssh_manager:
                self.logger.error("SSH连接不可用，无法保存远程配置")
                return False
            
            # 将配置数据转换为YAML格式
            config_yaml = yaml.dump(config_data, default_flow_style=False, allow_unicode=True)
            
            # 创建临时文件
            temp_file = "/tmp/channel_config_temp.yaml"
            remote_file_path = f"{self._server_config_path}/channel_config.yaml"
            
            # 先写入临时文件
            write_cmd = f"cat > {temp_file} << 'EOF'\n{config_yaml}\nEOF"
            result = ssh_manager.execute_remote_command(write_cmd)
            
            if result['success']:
                # 备份原文件
                backup_cmd = f"cp {remote_file_path} {remote_file_path}.backup"
                ssh_manager.execute_remote_command(backup_cmd)
                
                # 移动临时文件到目标位置
                move_cmd = f"mv {temp_file} {remote_file_path}"
                move_result = ssh_manager.execute_remote_command(move_cmd)
                
                if move_result['success']:
                    self.logger.info("成功保存通道配置到服务端")
                    self._config_cache['channel_config'] = config_data
                    return True
                else:
                    self.logger.error(f"移动配置文件失败: {move_result.get('stderr', '未知错误')}")
                    return False
            else:
                self.logger.error(f"写入临时配置文件失败: {result.get('stderr', '未知错误')}")
                return False
                
        except Exception as e:
            self.logger.error(f"保存远程通道配置失败: {e}")
            return False
    
    def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """
        获取指定通道的配置信息
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 通道配置信息，如果不存在返回None
        """
        try:
            # 先尝试从缓存获取
            if 'channel_config' in self._config_cache:
                config_data = self._config_cache['channel_config']
            else:
                config_data = self.load_channel_config()
            
            # 查找通道配置
            channels = config_data.get('channels', {})
            if channel_id in channels:
                return channels[channel_id]
            
            # 尝试其他格式的通道配置
            channel_key = f'channel{channel_id}'
            if channel_key in config_data:
                return config_data[channel_key]
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取通道{channel_id}配置失败: {e}")
            return None
    
    def refresh_config_cache(self):
        """刷新配置缓存"""
        self._config_cache.clear()
        self.logger.info("配置缓存已清空")
    
    def is_config_cached(self, config_type: str) -> bool:
        """检查指定类型的配置是否已缓存"""
        return config_type in self._config_cache
    
    def _get_fallback_channel_config(self) -> Dict[str, Any]:
        """获取备用通道配置（当远程配置不可用时）"""
        return {
            'channels': {
                1: {
                    'channel_id': 1,
                    'name': '通道1',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                2: {
                    'channel_id': 2,
                    'name': '通道2',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                3: {
                    'channel_id': 3,
                    'name': '通道3',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                },
                4: {
                    'channel_id': 4,
                    'name': '通道4',
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                }
            }
        }
    
    def _get_fallback_default_config(self) -> Dict[str, Any]:
        """获取备用默认配置"""
        return {
            'channel1': {
                'name': '通道1',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel2': {
                'name': '通道2',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel3': {
                'name': '通道3',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel4': {
                'name': '通道4',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            }
        }
    
    def push_annotation_config(self, channel_id: str, annotation_config: Dict[str, Any]) -> bool:
        """
        推送标注配置到服务器（按照原系统格式保存到annotation_result.yaml）
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            annotation_config: 标注配置数据
            
        Returns:
            bool: 是否成功推送
        """
        try:
            print(f"[远程配置] 推送通道 {channel_id} 的标注配置到服务器")
            
            ssh_manager = self._get_ssh_manager()
            if not ssh_manager:
                print(f"[远程配置] SSH连接不可用")
                return False
            
            # 构建服务器端配置文件路径（按照原系统路径）
            server_config_dir = "/home/lqj/liquid/server/database/config"
            annotation_config_file = f"{server_config_dir}/annotation_result.yaml"
            
            # 读取现有配置
            existing_config = {}
            read_cmd = f"cat {annotation_config_file} 2>/dev/null || echo ''"
            result = ssh_manager.execute_remote_command(read_cmd)
            
            if result['success'] and result['stdout'].strip():
                try:
                    import yaml
                    existing_config = yaml.safe_load(result['stdout']) or {}
                except Exception as e:
                    print(f"[远程配置] 解析现有配置失败: {e}")
                    existing_config = {}
            
            # 更新配置（按照原系统格式）
            existing_config[channel_id] = annotation_config
            
            # 序列化配置
            import yaml
            config_yaml = yaml.dump(existing_config, allow_unicode=True, default_flow_style=False)
            
            # 创建临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(config_yaml)
                tmp_file_path = tmp_file.name
            
            try:
                # 上传配置文件
                upload_success = ssh_manager.upload_file(tmp_file_path, annotation_config_file)
                
                if upload_success:
                    print(f"[远程配置] 标注配置已成功推送到服务器: {annotation_config_file}")
                    return True
                else:
                    print(f"[远程配置] 上传标注配置文件失败")
                    return False
                    
            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            
        except Exception as e:
            print(f"[远程配置] 推送标注配置异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_annotation_config(self, channel_id: str = None) -> Dict[str, Any]:
        """
        从服务器加载标注配置（从annotation_result.yaml）
        
        Args:
            channel_id: 通道ID，如果为None则加载所有通道的配置
            
        Returns:
            dict: 标注配置数据
        """
        try:
            print(f"[远程配置] 从服务器加载标注配置")
            
            ssh_manager = self._get_ssh_manager()
            if not ssh_manager:
                print(f"[远程配置] SSH连接不可用")
                return {}
            
            # 服务器端配置文件路径（按照原系统路径）
            server_config_dir = "/home/lqj/liquid/server/database/config"
            annotation_config_file = f"{server_config_dir}/annotation_result.yaml"
            
            # 读取配置文件
            read_cmd = f"cat {annotation_config_file} 2>/dev/null || echo ''"
            result = ssh_manager.execute_remote_command(read_cmd)
            
            if result['success'] and result['stdout'].strip():
                try:
                    import yaml
                    config = yaml.safe_load(result['stdout']) or {}
                    
                    if channel_id:
                        # 返回指定通道的配置
                        return config.get(channel_id, {})
                    else:
                        # 返回所有配置
                        return config
                        
                except Exception as e:
                    print(f"[远程配置] 解析标注配置失败: {e}")
                    return {}
            else:
                print(f"[远程配置] 服务器上没有标注配置文件")
                return {}
                
        except Exception as e:
            print(f"[远程配置] 加载标注配置异常: {e}")
            import traceback
            traceback.print_exc()
            return {}


def load_config(config_path=None, use_remote=False):
    """
    加载配置文件 - 统一配置加载接口

    Args:
        config_path: 本地配置文件路径（备用）
        use_remote: 是否优先使用远程配置（默认False，不需要SSH）

    Returns:
        dict: 配置字典
    """
    # 首先尝试从服务端加载配置（如果启用）
    if use_remote:
        try:
            print("[DEBUG] 尝试从服务端加载配置...")
            
            remote_config_manager = RemoteConfigManager()
            
            # 从服务端加载配置
            channel_config = remote_config_manager.load_channel_config()
            default_config = remote_config_manager.load_default_config()
            
            # 合并配置
            server_config = {**default_config, **channel_config}
            
            if server_config:
                print("[DEBUG] 成功从服务端加载配置")
                
                # 添加客户端特定的配置
                client_config = {
                    'server': {
                        'api_url': 'http://192.168.0.121:8084',
                        'ws_url': 'ws://192.168.0.121:8085'
                    },
                    'ui': {
                        'theme': 'light',
                        'language': 'zh_CN'
                    },
                    'data': {
                        'cache_dir': './cache',
                        'log_dir': './logs'
                    },
                    'network': {
                        'timeout': 30,
                        'retry_times': 3,
                        'api_server': '192.168.0.121',
                        'ws_server': '192.168.0.121',
                        'camera_rtsp': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
                    },
                    'log_level': 'INFO'
                }
                
                # 合并服务端配置和客户端配置
                final_config = {**client_config, **server_config}
                return final_config
                
        except Exception as e:
            print(f"[DEBUG] 从服务端加载配置失败: {e}")
    
    # 如果服务端配置加载失败，尝试加载本地配置文件
    try:
        print("[DEBUG] 尝试从本地加载配置...")
        local_config_manager = LocalConfigManager()
        
        # 加载本地客户端配置
        client_config = local_config_manager.load_client_config()
        
        # 加载本地相机配置
        camera_config = local_config_manager.load_camera_config()
        
        # 合并配置
        final_config = {**client_config}
        
        # 将相机配置合并到主配置中
        for channel_id, channel_info in camera_config.get('channels', {}).items():
            channel_key = f'channel{channel_id}'
            final_config[channel_key] = {
                'name': channel_info.get('name', f'通道{channel_id}'),
                'address': channel_info.get('address', '')
            }
        
        print("[DEBUG] 成功从本地加载配置")
        return final_config
        
    except Exception as e:
        print(f"[DEBUG] 从本地加载配置失败: {e}")
    
    # 如果都失败了，返回默认配置
    print("[DEBUG] 使用默认配置")
    return {
        'server': {
            'api_url': 'http://192.168.0.121:8084',
            'ws_url': 'ws://192.168.0.121:8085'
        },
        'ui': {
            'theme': 'light',
            'language': 'zh_CN'
        },
        'data': {
            'cache_dir': './cache',
            'log_dir': './logs'
        },
        'network': {
            'timeout': 30,
            'retry_times': 3,
            'api_server': '192.168.0.121',
            'ws_server': '192.168.0.121',
            'camera_rtsp': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
        },
        'log_level': 'INFO',
        # 添加一些默认的通道配置
        'channel1': {
            'name': '通道1',
            'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
        },
        'channel2': {
            'name': '通道2',
            'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
        },
        'channel3': {
            'name': '通道3',
            'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
        },
        'channel4': {
            'name': '通道4',
            'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
        }
    }


def save_config(config, config_path=None, use_remote=False):
    """
    保存配置文件 - 统一配置保存接口

    Args:
        config: 配置字典
        config_path: 本地配置文件路径
        use_remote: 是否保存到远程（默认False，不需要SSH）

    Returns:
        bool: 保存是否成功
    """
    success = True
    
    # 保存到远程（如果启用）
    if use_remote:
        try:
            remote_config_manager = RemoteConfigManager()
            
            # 提取通道配置
            channel_config = {}
            for key, value in config.items():
                if key.startswith('channel') and isinstance(value, dict):
                    channel_config[key] = value
            
            if channel_config:
                remote_success = remote_config_manager.save_channel_config(channel_config)
                if not remote_success:
                    success = False
                    print("[DEBUG] 保存远程配置失败")
        except Exception as e:
            print(f"[DEBUG] 保存远程配置异常: {e}")
            success = False
    
    # 保存到本地
    try:
        local_config_manager = LocalConfigManager()
        
        # 分离客户端配置和相机配置
        client_config = {k: v for k, v in config.items() if not k.startswith('channel')}
        
        camera_config = {'channels': {}}
        for key, value in config.items():
            if key.startswith('channel') and isinstance(value, dict):
                # 提取通道编号
                channel_num = int(key.replace('channel', ''))
                camera_config['channels'][channel_num] = {
                    'channel_id': channel_num,
                    'name': value.get('name', f'通道{channel_num}'),
                    'address': value.get('address', '')
                }
        
        # 保存客户端配置
        local_client_success = local_config_manager.save_client_config(client_config)
        
        # 保存相机配置
        local_camera_success = local_config_manager.save_camera_config(camera_config)
        
        if not (local_client_success and local_camera_success):
            success = False
            print("[DEBUG] 保存本地配置失败")
            
    except Exception as e:
        print(f"[DEBUG] 保存本地配置异常: {e}")
        success = False
    
    return success


def get_project_root():
    """获取项目根目录"""
    # 从当前文件向上查找，直到找到包含 database 目录的路径
    current = Path(__file__).parent
    while current != current.parent:
        if (current / 'database').exists():
            return str(current)
        current = current.parent
    
    # 如果没找到，返回客户端根目录
    return str(Path(__file__).parent.parent.parent)