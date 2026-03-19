# -*- coding: utf-8 -*-
"""
模型加载器插件接口
将功能委托给 handlers/modelpage/model_load_handler.py 中的 ModelLoadHandler
"""


class ModelLoader:
    """
    模型加载器插件类
    
    作为插件接口，所有实际功能都委托给 handlers 中的 ModelLoadHandler
    此文件只作为兼容性接口，不包含实际功能实现
    """
    
    def __init__(self, config=None, handler=None):
        """
        初始化模型加载器插件
        
        Args:
            config: 配置字典（已弃用，保留以保持兼容性）
            handler: ModelLoadHandler 实例（如果提供，直接使用）
        """
        self._handler = handler
        self._config = config or {}
    
    def set_handler(self, handler):
        """
        设置实际的处理器
        
        Args:
            handler: ModelLoadHandler 实例
        """
        self._handler = handler
        if handler and hasattr(handler, '_config'):
            self._config = handler._config
    
    def load_model(self, model_name, model_params):
        """
        加载模型到系统中（委托给 handler）
        
        Args:
            model_name: 模型名称
            model_params: 模型参数字典
            
        Returns:
            bool: 加载是否成功
        """
        if self._handler:
            return self._handler._loadModelToSystem(model_name, model_params)
        return False
    
    def get_loaded_models(self):
        """
        获取已加载的模型列表（委托给 handler）
        
        Returns:
            dict: 已加载的模型信息
        """
        if self._handler:
            return self._handler.getLoadedModels()
        return {}
    
    def is_model_loaded(self, model_name):
        """
        检查模型是否已加载（委托给 handler）
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 是否已加载
        """
        if self._handler:
            return self._handler.isModelLoaded(model_name)
        return False
    
    def get_model_load_statistics(self):
        """
        获取模型加载统计信息（委托给 handler）
        
        Returns:
            dict: 包含统计信息的字典
        """
        if self._handler:
            return self._handler.getModelLoadStatistics()
        return {
            'total_loaded': 0,
            'type_counts': {},
            'loaded_models': [],
            'load_times': {}
        }


