# -*- coding: utf-8 -*-

"""
模型信号处理器

处理模型管理页面的信号连接和组件间通信
"""

from qtpy import QtWidgets


class ModelSignalHandler:
    """
    模型信号处理器
    
    负责建立模型管理页面各组件之间的信号连接
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型信号处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self.main_window = None
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self.main_window = main_window
    
    def setupModelPageConnections(self):
        """
        建立模型管理页面的组件间连接
        
        连接以下组件：
        1. ModelSetPage（模型集管理页面）
           - UI交互信号
           - 业务逻辑信号（连接到 model_set_handler）
        """
        try:
            # 连接 ModelSetPage 的信号
            if hasattr(self, 'modelSetPage'):
                # ========== UI交互信号 ==========
                # 当模型列表选择变化时，更新右侧显示
                if hasattr(self.modelSetPage, 'modelSelected'):
                    self.modelSetPage.modelSelected.connect(self._onModelSetPageModelSelected)
                
                # 当模型被添加/删除时的处理
                if hasattr(self.modelSetPage, 'modelAdded'):
                    self.modelSetPage.modelAdded.connect(self._onModelAdded)
                
                if hasattr(self.modelSetPage, 'modelDeleted'):
                    self.modelSetPage.modelDeleted.connect(self._onModelDeleted)
                
                # ========== 业务逻辑信号（连接到 model_set_handler） ==========
                if hasattr(self, 'model_set_handler'):
                    # 重命名模型请求
                    if hasattr(self.modelSetPage, 'renameModelRequested'):
                        self.modelSetPage.renameModelRequested.connect(
                            self.model_set_handler.renameModel
                        )
                    
                    # 复制模型请求
                    if hasattr(self.modelSetPage, 'duplicateModelRequested'):
                        self.modelSetPage.duplicateModelRequested.connect(
                            self.model_set_handler.duplicateModel
                        )
                    
                    # 删除模型数据请求
                    if hasattr(self.modelSetPage, 'deleteModelDataRequested'):
                        self.modelSetPage.deleteModelDataRequested.connect(
                            self.model_set_handler.deleteModelData
                        )
                    
                    # 设置默认模型请求
                    # 注意：setAsDefaultModel 方法不存在，已注释
                    # if hasattr(self.modelSetPage, 'setDefaultRequested'):
                    #     self.modelSetPage.setDefaultRequested.connect(
                    #         self.model_set_handler.setAsDefaultModel
                    #     )
                    if hasattr(self.modelSetPage, 'modelSetClicked'):
                        self.modelSetPage.modelSetClicked.connect(self._onModelSetPageModelSelected)
            
            # ========== 连接模型列表变化信号到训练页面 ==========
            # 当模型列表变化时（添加/删除/重命名），自动刷新训练页面的下拉菜单
            if hasattr(self, 'modelSetPage') and hasattr(self, 'trainingPage'):
                if hasattr(self.modelSetPage, 'modelListChanged') and hasattr(self.trainingPage, 'connectModelListChangeSignal'):
                    self.trainingPage.connectModelListChangeSignal(self.modelSetPage)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _onModelSetPageModelSelected(self, model_name):
        """
        当 ModelSetPage 选中模型时的处理
        
        Args:
            model_name: 选中的模型名称
        """
        # 这里可以添加额外的处理逻辑，比如更新状态栏
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"当前选中模型: {model_name}")
    
    def _onModelAdded(self, model_name):
        """
        当添加新模型时的处理
        
        Args:
            model_name: 新添加的模型名称
        """
        pass
    
    def _onModelDeleted(self, model_name):
        """
        当删除模型时的处理
        
        Args:
            model_name: 删除的模型名称
        """
        pass
