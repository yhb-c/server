# -*- coding: utf-8 -*-

"""
配置管理模块

模仿labelme的配置系统，提供配置加载、验证和更新功能
"""

import os
import os.path as osp
import shutil
import sys
import yaml


def get_resource_path(relative_path):
    """
    获取资源文件的绝对路径，兼容开发环境和PyInstaller打包后的环境
    
    Args:
        relative_path: 相对于 config 目录的路径
    
    Returns:
        str: 资源文件的绝对路径
    """
    # PyInstaller创建临时文件夹，并把路径存储在_MEIPASS中
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe运行
        # sys._MEIPASS 指向 _internal/ 目录
        base_path = sys._MEIPASS
        return osp.join(base_path, 'config', relative_path)
    else:
        # 如果是开发环境运行，使用 get_config_dir() 获取配置目录
        config_dir = get_config_dir()
        return osp.join(config_dir, relative_path)


here = osp.dirname(osp.abspath(__file__))


def get_project_root():
    """
    动态获取项目根目录
    
    通过查找标志性文件（app.py、__main__.py等）来定位项目根目录
    
    Returns:
        str: 项目根目录的绝对路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后：使用 _internal 目录作为项目根目录
        # 所有配置文件、模型等都从这里读取（只读）
        return sys._MEIPASS
    else:
        # 开发环境：从当前文件位置开始向上查找
        current_dir = osp.dirname(osp.abspath(__file__))
        
        # 标志性文件列表（用于识别项目根目录）
        marker_files = ['app.py', '__main__.py', 'requirements_simple.txt', 'exe.spec']
        
        # 最多向上查找5层
        for _ in range(5):
            # 检查当前目录是否包含标志性文件
            for marker in marker_files:
                if osp.exists(osp.join(current_dir, marker)):
                    return current_dir
            
            # 向上移动一层
            parent_dir = osp.dirname(current_dir)
            if parent_dir == current_dir:  # 已到达根目录
                break
            current_dir = parent_dir
        
        # 如果找不到，返回当前文件的上上级目录作为后备方案
        return osp.dirname(osp.dirname(here))


def get_config_dir():
    """
    获取配置文件目录的绝对路径 (config)

    Returns:
        str: 配置文件目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后从 _MEIPASS 读取
        # sys._MEIPASS 指向 _internal/ 目录
        return osp.join(sys._MEIPASS, 'config')
    else:
        # 开发环境：基于项目根目录动态构建路径
        project_root = get_project_root()
        config_path = osp.join(project_root, 'config')

        # 调试信息：如果配置目录不存在，打印警告
        if not osp.exists(config_path):
            print(f"警告: 配置目录不存在: {config_path}")
            print(f"      项目根目录: {project_root}")
            # 后备方案：返回当前目录
            return here

        return config_path


def get_temp_models_dir():
    """
    获取临时模型目录的绝对路径 (database/model/temp_models)
    
    在打包环境和开发环境中都是可写目录，用于存储临时解码的模型文件
    
    Returns:
        str: 临时模型目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：在exe所在目录创建可写目录
        exe_dir = osp.dirname(sys.executable)
        temp_models_path = osp.join(exe_dir, 'database', 'model', 'temp_models')
    else:
        # 开发环境：基于项目根目录动态构建路径
        project_root = get_project_root()
        temp_models_path = osp.join(project_root, 'database', 'model', 'temp_models')
    
    # 确保目录存在
    if not osp.exists(temp_models_path):
        try:
            os.makedirs(temp_models_path, exist_ok=True)
        except Exception as e:
            print(f"警告: 无法创建临时模型目录 {temp_models_path}: {e}")
    
    return temp_models_path


def get_train_dir():
    """
    获取训练输出目录的绝对路径 (database/train)
    
    在打包环境和开发环境中都是可写目录，用于存储YOLO训练结果
    
    Returns:
        str: 训练输出目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：在exe所在目录创建可写目录
        exe_dir = osp.dirname(sys.executable)
        train_path = osp.join(exe_dir, 'database', 'train')
    else:
        # 开发环境：基于项目根目录动态构建路径
        project_root = get_project_root()
        train_path = osp.join(project_root, 'database', 'train')
    
    # 确保目录存在
    if not osp.exists(train_path):
        try:
            os.makedirs(train_path, exist_ok=True)
            print(f"已创建训练输出目录: {train_path}")
        except Exception as e:
            print(f"警告: 无法创建训练输出目录 {train_path}: {e}")
    
    return train_path


def update_dict(target_dict, new_dict, validate_item=None):
    """
    递归更新字典
    
    Args:
        target_dict: 目标字典
        new_dict: 新字典
        validate_item: 验证函数
    """
    for key, value in new_dict.items():
        if validate_item:
            validate_item(key, value)
        
        if key not in target_dict:
            pass
            continue
        
        if isinstance(target_dict[key], dict) and isinstance(value, dict):
            update_dict(target_dict[key], value, validate_item=validate_item)
        else:
            target_dict[key] = value


def get_default_config():
    """
    获取默认配置
    
    Returns:
        dict: 默认配置字典
    """
    # 使用资源路径函数获取配置文件路径
    config_file = get_resource_path("default_config.yaml")
    
    try:
        with open(config_file, encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        pass
        raise
    
    # 不再自动保存到用户目录，直接使用项目中的 default_config.yaml
    # user_config_file = osp.join(osp.expanduser("~"), ".detectionrc")
    # if not osp.exists(user_config_file):
    #     try:
    #         shutil.copy(config_file, user_config_file)
    #         print(f"默认配置已保存到: {user_config_file}")
    #     except Exception as e:
    #         print(f"警告: 无法保存配置文件: {user_config_file}, 错误: {e}")
    
    return config


def validate_config_item(key, value):
    """
    验证配置项
    
    Args:
        key: 配置键
        value: 配置值
    
    Raises:
        ValueError: 如果配置值无效
    """
    # 验证语言
    if key == "language" and value not in ["zh_CN", "en_US", "ja_JP"]:
        raise ValueError(
            f"配置项 'language' 的值无效: {value}，应为 'zh_CN', 'en_US' 或 'ja_JP'"
        )
    
    # 验证日志级别
    if key == "logger_level" and value not in ["debug", "info", "warning", "error"]:
        raise ValueError(
            f"配置项 'logger_level' 的值无效: {value}，应为 'debug', 'info', 'warning' 或 'error'"
        )
    
    # 验证主题
    if key == "theme" and value not in ["light", "dark", "auto"]:
        raise ValueError(
            f"配置项 'theme' 的值无效: {value}，应为 'light', 'dark' 或 'auto'"
        )
    
    # 验证模型类型
    if key == "model_type" and value not in [
        "YOLOv5", "YOLOv8", "YOLOX", "Faster R-CNN", "SSD", "RetinaNet"
    ]:
        raise ValueError(
            f"配置项 'model_type' 的值无效: {value}"
        )
    
    # 验证传输协议
    if key == "transport" and value not in ["TCP", "UDP", "HTTP"]:
        raise ValueError(
            f"配置项 'transport' 的值无效: {value}，应为 'TCP', 'UDP' 或 'HTTP'"
        )
    
def get_config(config_file_or_yaml=None, config_from_args=None):
    """
    获取配置（三层级联）
    
    配置优先级（从低到高）：
    1. 默认配置 (default_config.yaml)
    2. 用户配置文件 (~/.detectionrc 或 --config 指定的文件)
    3. 命令行参数
    
    Args:
        config_file_or_yaml: 配置文件路径或YAML字符串
        config_from_args: 从命令行参数提取的配置字典
    
    Returns:
        dict: 最终配置字典
    """
    # 1. 加载默认配置
    config = get_default_config()
    
    # 2. 加载指定的配置文件或YAML
    if config_file_or_yaml is not None:
        try:
            # 尝试作为YAML字符串解析
            config_from_yaml = yaml.safe_load(config_file_or_yaml)
        except:
            config_from_yaml = None
        
        # 如果不是字典，则作为文件路径处理
        if not isinstance(config_from_yaml, dict):
            config_file = config_file_or_yaml
            if osp.exists(config_file):
                with open(config_file, encoding='utf-8') as f:
                    pass
                    config_from_yaml = yaml.safe_load(f)
            else:
                pass
                config_from_yaml = {}
        
        if config_from_yaml:
            update_dict(
                config, config_from_yaml, validate_item=validate_config_item
            )
    
    # 3. 加载命令行参数配置
    if config_from_args is not None:
        update_dict(
            config, config_from_args, validate_item=validate_config_item
        )
    
    return config


def save_config(config, config_file=None):
    """
    保存配置到文件
    
    Args:
        config: 配置字典
        config_file: 配置文件路径，如果为None则保存到 ~/.detectionrc
    """
    if config_file is None:
        config_file = osp.join(osp.expanduser("~"), ".detectionrc")
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        pass
        return True
    except Exception as e:
        pass
        return False




