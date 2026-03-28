# -*- coding: utf-8 -*-
"""
日志管理
"""

import logging
import os
from pathlib import Path


def setup_logging(log_level='INFO'):
    """
    配置日志
    
    Args:
        log_level: 日志级别
    """
    # 创建日志目录
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / 'logs'
    os.makedirs(log_dir, exist_ok=True)

    log_file = log_dir / 'client.log'
    
    # 配置日志格式
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    
    # 配置日志处理器
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("日志系统初始化完成")
