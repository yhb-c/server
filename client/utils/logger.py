# -*- coding: utf-8 -*-
"""
日志管理
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


class FixedLogHandler(logging.FileHandler):
    """固定文件名的日志处理器，每次启动覆盖旧日志"""

    def __init__(self, filename, mode='w', encoding='utf-8', delay=False):
        """
        初始化日志处理器

        Args:
            filename: 日志文件路径
            mode: 文件打开模式，默认'w'表示覆盖
            encoding: 文件编码
            delay: 是否延迟打开文件
        """
        super().__init__(filename, mode=mode, encoding=encoding, delay=delay)


def setup_logging(log_type='client', log_level='INFO', console_output=False):
    """
    配置日志系统

    Args:
        log_type: 日志类型 ('client', 'server', 'api', 'websocket')
        log_level: 日志级别
        console_output: 是否输出到控制台，默认False

    Returns:
        logger: 配置好的日志记录器
    """
    # 检查全局日志开关
    try:
        import sys
        main_module = sys.modules.get('__main__')
        enable_logging = getattr(main_module, 'ENABLE_LOGGING', True)
    except:
        enable_logging = True

    # 创建日志记录器
    logger = logging.getLogger(log_type)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 清除已有的处理器
    logger.handlers.clear()

    # 如果日志开关关闭，只添加NullHandler
    if not enable_logging:
        logger.addHandler(logging.NullHandler())
        return logger

    # 创建日志目录
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / 'logs'
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件映射
    log_files = {
        'client': log_dir / 'client.log',
        'server': log_dir / 'server.log',
        'api': log_dir / 'api.log',
        'websocket': log_dir / 'websocket.log'
    }

    log_file = log_files.get(log_type, log_dir / 'client.log')

    # 配置日志格式
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    formatter = logging.Formatter(log_format)

    # 添加文件处理器（覆盖模式）
    file_handler = FixedLogHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 只在需要时添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.info(f"{log_type}日志系统初始化完成，日志文件: {log_file}")

    return logger


def get_logger(log_type='client'):
    """
    获取指定类型的日志记录器

    Args:
        log_type: 日志类型 ('client', 'server', 'api', 'websocket')

    Returns:
        logger: 日志记录器
    """
    logger = logging.getLogger(log_type)
    if not logger.handlers:
        setup_logging(log_type)
    return logger
