# -*- coding: utf-8 -*-
"""
Detection module - 液位检测引擎

模块结构：
    - model_detect.py: 模型加载和验证函数
    - init_error.py: 模型推理异常后处理函数
    - space_logic.py: 空间后处理逻辑函数
    - detection.py: LiquidDetectionEngine 类 - 液位检测引擎（对外接口）
"""

from .detection import (
    LiquidDetectionEngine,
    get_class_color,
    calculate_foam_boundary_lines,
    analyze_multiple_foams,
    stable_median,
)

__all__ = [
    'LiquidDetectionEngine',
    'get_class_color',
    'calculate_foam_boundary_lines',
    'analyze_multiple_foams',
    'stable_median',
]
