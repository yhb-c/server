# -*- coding: utf-8 -*-

"""
模型管理页面组件包

包含模型管理相关的所有页面和组件

当前架构：
- ModelSetPage: 模型集管理页面（索引0，纯UI组件）
- TrainingPage: 模型升级页面（索引1，纯UI组件）
- ModelLoader: 模型加载器插件接口
- ModelOperations: 模型操作插件接口

注意：
- ModelPageHandler 已移至 handlers/modelpage/model_page_handler.py
- 业务逻辑现在由 handlers/modelpage/ 中的各个 handler 处理
"""

# 核心页面组件
from .modelset_page import ModelSetPage
from .training_page import TrainingPage

# 插件接口
from .model_loader import ModelLoader
from .model_operations import ModelOperations

# 兼容性保留（已弃用，已移至 handlers）
# ModelPageHandler 已移至 handlers/modelpage/model_page_handler.py
# 如需使用，请直接从 handlers.modelpage 导入

__all__ = [
    # 核心页面
    'ModelSetPage',
    'TrainingPage',
    # 插件接口
    'ModelLoader',
    'ModelOperations',
]
