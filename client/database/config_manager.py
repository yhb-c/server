# -*- coding: utf-8 -*-

import os
import json
import yaml
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime


class ConfigManager:
    """
    客户端配置管理器
    负责配置的本地缓存、服务器同步、离线支持
    """

    def __init__(self, user_id: str = "user", api_base_url: str = "http://192.168.0.121:8084"):
        """
        初始化配置管理器

        Args:
            user_id: 用户ID，默认为公用账户"user"
            api_base_url: API服务器地址
        """
        self.user_id = user_id
        self.api_base_url = api_base_url

        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent

        # 本地配置缓存目录
        self.cache_dir = self.project_root / "config" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 本地配置文件路径
        self.local_config_file = self.cache_dir / f"user_{self.user_id}_config.json"

        # 配置缓存
        self.config_cache: Dict[str, Any] = {}

        # 加载本地缓存配置
        self._load_local_cache()

    def _load_local_cache(self):
        """从本地文件加载配置缓存"""
        if self.local_config_file.exists():
            try:
                with open(self.local_config_file, 'r', encoding='utf-8') as f:
                    self.config_cache = json.load(f)
                print(f"已加载本地配置缓存: {len(self.config_cache)} 项")
            except Exception as e:
                print(f"加载本地配置缓存失败: {e}")
                self.config_cache = {}
        else:
            print("本地配置缓存不存在，将创建新缓存")
            self.config_cache = {}

    def _save_local_cache(self):
        """保存配置到本地文件"""
        try:
            with open(self.local_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_cache, f, ensure_ascii=False, indent=2)
            print(f"配置已保存到本地缓存")
        except Exception as e:
            print(f"保存本地配置缓存失败: {e}")

    def fetch_all_configs_from_server(self) -> bool:
        """
        从服务器拉取用户的所有配置

        Returns:
            bool: 是否成功
        """
        try:
            url = f"{self.api_base_url}/api/users/{self.user_id}/configs"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    configs = data.get('data', [])

                    # 更新本地缓存
                    for config in configs:
                        config_key = config.get('config_key')
                        self.config_cache[config_key] = {
                            'config_value': config.get('config_value'),
                            'config_type': config.get('config_type'),
                            'description': config.get('description'),
                            'updated_at': config.get('updated_at')
                        }

                    # 保存到本地文件
                    self._save_local_cache()
                    print(f"从服务器拉取配置成功: {len(configs)} 项")
                    return True
                else:
                    print(f"服务器返回错误: {data.get('message')}")
                    return False
            else:
                print(f"请求失败，状态码: {response.status_code}")
                return False

        except Exception as e:
            print(f"从服务器拉取配置失败: {e}")
            return False

    def get_config(self, config_key: str, config_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取配置项

        Args:
            config_key: 配置键
            config_type: 配置类型（可选）

        Returns:
            配置值，如果不存在返回None
        """
        if config_key in self.config_cache:
            config = self.config_cache[config_key]
            if config_type is None or config.get('config_type') == config_type:
                return config.get('config_value')
        return None

    def get_configs_by_type(self, config_type: str) -> Dict[str, Any]:
        """
        获取指定类型的所有配置

        Args:
            config_type: 配置类型

        Returns:
            配置字典
        """
        result = {}
        for key, value in self.config_cache.items():
            if value.get('config_type') == config_type:
                result[key] = value.get('config_value')
        return result

    def update_config(self, config_key: str, config_value: Dict[str, Any],
                     config_type: str, description: str = "") -> bool:
        """
        更新配置（立即更新本地并同步到服务器）

        Args:
            config_key: 配置键
            config_value: 配置值
            config_type: 配置类型
            description: 配置描述

        Returns:
            bool: 是否成功
        """
        # 1. 立即更新本地缓存
        self.config_cache[config_key] = {
            'config_value': config_value,
            'config_type': config_type,
            'description': description,
            'updated_at': datetime.now().isoformat()
        }

        # 2. 保存到本地文件
        self._save_local_cache()

        # 3. 同步到服务器
        return self._sync_to_server(config_key, config_value, config_type, description)

    def _sync_to_server(self, config_key: str, config_value: Dict[str, Any],
                       config_type: str, description: str) -> bool:
        """
        同步配置到服务器

        Args:
            config_key: 配置键
            config_value: 配置值
            config_type: 配置类型
            description: 配置描述

        Returns:
            bool: 是否成功
        """
        try:
            url = f"{self.api_base_url}/api/users/{self.user_id}/configs"
            payload = {
                'config_key': config_key,
                'config_value': config_value,
                'config_type': config_type,
                'description': description
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    print(f"配置同步到服务器成功: {config_key}")
                    return True
                else:
                    print(f"服务器返回错误: {data.get('message')}")
                    return False
            else:
                print(f"同步失败，状态码: {response.status_code}")
                return False

        except Exception as e:
            print(f"同步配置到服务器失败: {e}")
            return False

    def batch_update_configs(self, configs: List[Dict[str, Any]]) -> bool:
        """
        批量更新配置

        Args:
            configs: 配置列表，每项包含config_key, config_value, config_type, description

        Returns:
            bool: 是否全部成功
        """
        success_count = 0

        for config in configs:
            config_key = config.get('config_key')
            config_value = config.get('config_value')
            config_type = config.get('config_type')
            description = config.get('description', '')

            if self.update_config(config_key, config_value, config_type, description):
                success_count += 1

        print(f"批量更新配置: 成功 {success_count}/{len(configs)}")
        return success_count == len(configs)

    def sync_offline_changes(self) -> bool:
        """
        同步离线期间的配置修改到服务器

        Returns:
            bool: 是否成功
        """
        if not self.config_cache:
            print("没有需要同步的配置")
            return True

        success_count = 0
        for config_key, config_data in self.config_cache.items():
            if self._sync_to_server(
                config_key,
                config_data.get('config_value'),
                config_data.get('config_type'),
                config_data.get('description', '')
            ):
                success_count += 1

        print(f"离线配置同步: 成功 {success_count}/{len(self.config_cache)}")
        return success_count == len(self.config_cache)

    def export_to_yaml(self, config_type: str, output_path: str) -> bool:
        """
        导出指定类型的配置到YAML文件

        Args:
            config_type: 配置类型
            output_path: 输出文件路径

        Returns:
            bool: 是否成功
        """
        try:
            configs = self.get_configs_by_type(config_type)
            if not configs:
                print(f"没有找到类型为 {config_type} 的配置")
                return False

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(configs, f, allow_unicode=True, default_flow_style=False)

            print(f"配置已导出到: {output_path}")
            return True

        except Exception as e:
            print(f"导出配置失败: {e}")
            return False

    def import_from_yaml(self, config_type: str, yaml_path: str) -> bool:
        """
        从YAML文件导入配置

        Args:
            config_type: 配置类型
            yaml_path: YAML文件路径

        Returns:
            bool: 是否成功
        """
        try:
            yaml_file = Path(yaml_path)
            if not yaml_file.exists():
                print(f"文件不存在: {yaml_path}")
                return False

            with open(yaml_file, 'r', encoding='utf-8') as f:
                configs = yaml.safe_load(f)

            if not configs:
                print("YAML文件为空")
                return False

            # 批量更新配置
            config_list = []
            for key, value in configs.items():
                config_list.append({
                    'config_key': key,
                    'config_value': value,
                    'config_type': config_type,
                    'description': f'从{yaml_path}导入'
                })

            return self.batch_update_configs(config_list)

        except Exception as e:
            print(f"导入配置失败: {e}")
            return False

    def get_all_configs(self) -> Dict[str, Any]:
        """
        获取所有配置

        Returns:
            所有配置的字典
        """
        return self.config_cache.copy()

    def clear_local_cache(self):
        """清空本地配置缓存"""
        self.config_cache = {}
        self._save_local_cache()
        print("本地配置缓存已清空")
