# -*- coding: utf-8 -*-
"""
临时配置模块 - 提供路径管理功能
注意：这只是临时方案，用于兼容从exe迁移过来的代码
最终应该移除对database的依赖，所有配置从服务端获取
"""

import os
import sys
from pathlib import Path


def get_project_root():
    """
    获取项目根目录
    
    Returns:
        str: 项目根目录的绝对路径
    """
    # 从当前文件位置向上查找到client目录
    current_dir = Path(__file__).parent.parent.parent
    return str(current_dir)


def get_config_dir():
    """
    获取配置文件目录
    
    Returns:
        str: 配置文件目录路径
    """
    project_root = get_project_root()
    # 使用client/config目录，而不是database/config
    config_path = os.path.join(project_root, 'config')
    
    if not os.path.exists(config_path):
        os.makedirs(config_path, exist_ok=True)
    
    return config_path


def get_temp_models_dir():
    """
    获取临时模型目录
    
    Returns:
        str: 临时模型目录路径
    """
    project_root = get_project_root()
    temp_models_path = os.path.join(project_root, 'cache', 'models')
    
    if not os.path.exists(temp_models_path):
        os.makedirs(temp_models_path, exist_ok=True)
    
    return temp_models_path


def get_train_dir():
    """
    获取训练输出目录
    
    Returns:
        str: 训练输出目录路径
    """
    project_root = get_project_root()
    train_path = os.path.join(project_root, 'cache', 'train')
    
    if not os.path.exists(train_path):
        os.makedirs(train_path, exist_ok=True)
    
    return train_path


def is_debug_mode(config=None):
    """
    检查是否为调试模式
    
    Args:
        config: 配置字典
        
    Returns:
        bool: 是否为调试模式
    """
    if config and isinstance(config, dict):
        return config.get('debug', False)
    return False


def get_resource_path(relative_path):
    """
    获取资源文件路径
    
    Args:
        relative_path: 相对路径
        
    Returns:
        str: 资源文件的绝对路径
    """
    project_root = get_project_root()
    return os.path.join(project_root, 'resources', relative_path)
