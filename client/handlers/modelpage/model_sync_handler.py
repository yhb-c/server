# -*- coding: utf-8 -*-

"""
模型同步处理器

处理模型管理面板与模型设置之间的同步功能
"""

from qtpy import QtWidgets


class ModelSyncHandler:
    """
    模型同步处理器
    
    处理模型管理面板与模型设置之间的同步功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型同步处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self = None
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self = main_window
    
    def _setupModelSync(self):
        """建立模型管理面板与模型设置的同步"""
        try:
            if hasattr(self, 'modelPanel'):
                # 将模型管理面板的模型信息同步到模型设置处理器
                self.modelPanel.syncWithModelSettings(self)
        except Exception as e:
            pass
    
    def refreshModelSync(self):
        """刷新模型同步（当模型发生变化时调用）"""
        try:
            if hasattr(self, 'modelPanel'):
                self.modelPanel.syncWithModelSettings(self)
        except Exception as e:
            pass
    
    def getModelPanelModels(self):
        """
        获取模型管理面板中的所有模型信息
        
        Returns:
            list: 模型信息列表
        """
        if hasattr(self, 'modelPanel'):
            return self.modelPanel.getAvailableModels()
        return []
    
    def getModelPanelModelByPath(self, model_path):
        """
        根据路径从模型管理面板获取模型信息
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            dict: 模型信息，如果未找到返回None
        """
        if hasattr(self, 'modelPanel'):
            return self.modelPanel.getModelByPath(model_path)
        return None
