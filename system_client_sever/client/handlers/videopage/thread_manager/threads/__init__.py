# -*- coding: utf-8 -*-

"""
线程模块

包含所有类型的通道线程实现

注意：捕获线程已删除，解码渲染由PlayCtrl SDK内部管理
"""

from .display_thread import DisplayThread
from .detection_thread import DetectionThread
from .curve_thread import CurveThread
from .storage_thread import StorageThread
from .global_detection_thread import GlobalDetectionThread

__all__ = [
    'DisplayThread',
    'DetectionThread',
    'CurveThread',
    'StorageThread',
    'GlobalDetectionThread'
]
