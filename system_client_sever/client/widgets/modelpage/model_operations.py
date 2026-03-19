# -*- coding: utf-8 -*-
"""
模型操作管理插件接口
将功能委托给 handlers/modelpage/model_set_handler.py 中的 ModelSetHandler
此文件只作为兼容性接口，不包含实际功能实现
"""

try:
    from qtpy import QtWidgets
except ImportError:
    from PyQt5 import QtWidgets


class ModelOperations:
    """
    模型操作管理插件类
    
    作为插件接口，所有实际功能都委托给 handlers 中的 ModelSetHandler
    """
    
    def __init__(self, parent=None, model_set_page=None, handler=None):
        """
        初始化模型操作管理插件
        
        Args:
            parent: 父窗口（已弃用，保留以保持兼容性）
            model_set_page: 模型集页面引用（已弃用，保留以保持兼容性）
            handler: ModelSetHandler 实例（如果提供，直接使用）
        """
        self._handler = handler
        self._parent = parent
        self._model_set_page = model_set_page
    
    def set_handler(self, handler):
        """
        设置实际的处理器
        
        Args:
            handler: ModelSetHandler 实例
        """
        self._handler = handler
        if handler:
            self._parent = handler
            if hasattr(handler, 'modelSetPage'):
                self._model_set_page = handler.modelSetPage
    
    def add_model_dialog(self):
        """
        显示添加模型对话框（委托给 handler）
        
        Returns:
            bool: 是否成功添加
        """
        if self._handler:
            return self._handler._addModelDialog()
        return False
    
    def edit_model(self):
        """编辑模型（委托给 handler）"""
        if self._handler:
            return self._handler._onEditModelSet()
        return False
    
    def delete_model(self):
        """
        删除模型（委托给 handler）
        
        Returns:
            bool: 是否成功删除
        """
        if self._handler:
            self._handler._onDeleteModelSet()
            return True
        return False


