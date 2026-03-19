# -*- coding: utf-8 -*-
"""
模型页面处理器插件接口
将功能委托给 handlers/modelpage/ 中的各个 Handler
此文件只作为兼容性接口，不包含实际功能实现

注意：此文件已弃用，推荐直接使用 app.py 中的 _createModelPage() 方法
"""

try:
    from qtpy import QtWidgets, QtCore
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5 import QtCore

# 导入插件接口（从 widgets.modelpage）
try:
    from ...widgets.modelpage.model_loader import ModelLoader
    from ...widgets.modelpage.model_operations import ModelOperations
except ImportError:
    try:
        from widgets.modelpage.model_loader import ModelLoader
        from widgets.modelpage.model_operations import ModelOperations
    except ImportError:
        # 如果都失败，创建占位类
        class ModelLoader:
            def __init__(self, handler=None):
                pass
        class ModelOperations:
            def __init__(self, handler=None):
                pass


class ModelPageHandler:
    """
    模型页面处理器插件类
    
    作为插件接口，所有实际功能都委托给 handlers 中的各个 Handler
    """
    
    def __init__(self, parent=None, handlers=None):
        """
        初始化模型页面处理器插件
        
        Args:
            parent: 父窗口（MainWindow）
            handlers: 包含所有 handler 实例的字典，格式为：
                {
                    'model_loader': ModelLoader实例（插件接口）,
                    'model_operations': ModelOperations实例（插件接口）,
                    'model_load_handler': ModelLoadHandler实例（实际功能）,
                    'model_set_handler': ModelSetHandler实例（实际功能）,
                    'model_signal_handler': ModelSignalHandler实例（实际功能）
                }
        """
        self._parent = parent
        self._handlers = handlers or {}
        self._model_loader = None
        self._model_operations = None
        
        # 初始化插件接口
        if handlers:
            if 'model_load_handler' in handlers:
                self._model_loader = ModelLoader(handler=handlers['model_load_handler'])
            if 'model_set_handler' in handlers:
                self._model_operations = ModelOperations(handler=handlers['model_set_handler'])
    
    def set_handlers(self, handlers):
        """
        设置实际的处理器
        
        Args:
            handlers: 包含所有 handler 实例的字典
        """
        self._handlers = handlers
        if 'model_load_handler' in handlers:
            self._model_loader = ModelLoader(handler=handlers['model_load_handler'])
        if 'model_set_handler' in handlers:
            self._model_operations = ModelOperations(handler=handlers['model_set_handler'])
    
    def create_model_page(self):
        """创建模型页面（已弃用，保留以兼容旧代码）"""
        pass
        
    def _createModelPage(self):
        """创建模型页面的实际实现"""
        # 导入页面组件（从 widgets.modelpage）
        try:
            from ...widgets.modelpage.modelset_page import ModelSetPage
            from ...widgets.modelpage.training_page import TrainingPage
        except ImportError:
            try:
                from widgets.modelpage.modelset_page import ModelSetPage
                from widgets.modelpage.training_page import TrainingPage
            except ImportError as e:
                return None
        
        # 导入训练处理器
        try:
            # 优先使用相对导入（同一包内）
            from .model_training_handler import ModelTrainingHandler
        except ImportError:
            try:
                # 备用：绝对导入
                from handlers.modelpage.model_training_handler import ModelTrainingHandler
            except ImportError:
                ModelTrainingHandler = None
        
        # 创建主页面容器
        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(10, 10, 10, 10)
        page_layout.setSpacing(10)
        
        # 创建堆叠容器
        self._parent.modelStackWidget = QtWidgets.QStackedWidget()
        
        # 创建模型集管理页面（索引0）
        self._parent.modelSetPage = ModelSetPage(model_params=None, parent=self._parent)
        self._parent.modelStackWidget.addWidget(self._parent.modelSetPage)
        
        # 创建训练处理器
        if ModelTrainingHandler:
            self._parent.training_handler = ModelTrainingHandler()
            self._parent.training_handler.connectSignals()
        else:
            self._parent.training_handler = None
        
        # 创建模型升级页面（索引1）
        self._parent.trainingPage = TrainingPage(parent=self._parent)
        self._parent.modelStackWidget.addWidget(self._parent.trainingPage)
        
        # 默认显示第一个页面（模型集管理）
        self._parent.modelStackWidget.setCurrentIndex(0)
        
        page_layout.addWidget(self._parent.modelStackWidget)
        
        # 初始化模型加载器和操作管理器（通过 handlers）
        if self._handlers:
            if 'model_load_handler' in self._handlers:
                self._model_loader = ModelLoader(handler=self._handlers['model_load_handler'])
            if 'model_set_handler' in self._handlers:
                self._model_operations = ModelOperations(handler=self._handlers['model_set_handler'])
        
        # 建立组件间的连接
        self.connect_model_page_components()
        
        return page
    
    def connect_model_page_components(self):
        """连接模型页面组件之间的信号（委托给 handler）"""
        # 委托给 ModelSignalHandler 处理
        if 'model_signal_handler' in self._handlers:
            self._handlers['model_signal_handler'].setupModelPageConnections()
    
    def add_test_models_to_list(self):
        """添加测试模型到列表（已弃用）"""
        pass
    
    # ==================== 信号处理方法 ====================
    
    def on_run_model_test(self, test_config):
        """运行模型测试"""
        try:
            QtWidgets.QMessageBox.information(
                self._parent, 
                "模型测试", 
                f"模型测试请求已接收\n模型: {test_config.get('model_name', '未指定')}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self._parent, "错误", f"运行模型测试失败: {e}")
    
    def on_browse_test_file(self):
        """浏览测试文件（已弃用）"""
        pass
    
    def on_browse_save_liquid_data_path(self):
        """浏览保存路径（已弃用）"""
        pass
    
    def on_add_model_set(self):
        """添加模型集"""
        if self._model_operations:
            success = self._model_operations.add_model_dialog()
            # 不再需要同步到测试页面（已移除）
    
    def on_edit_model_set(self):
        """编辑模型集"""
        if self._model_operations:
            self._model_operations.edit_model()
    
    def on_delete_model_set(self):
        """删除模型集"""
        if self._model_operations:
            success = self._model_operations.delete_model()
            # 不再需要同步到测试页面（已移除）
    
    def on_load_model_set(self):
        """加载模型集（委托给 handler）"""
        if 'model_set_handler' in self._handlers:
            self._handlers['model_set_handler']._onLoadModelSet()
    
    def on_model_settings(self):
        """模型设置（委托给 handler）"""
        if 'model_settings_handler' in self._handlers:
            self._handlers['model_settings_handler']._onModelSettings()
    
    def show_model_load_statistics(self):
        """显示模型加载统计信息对话框（委托给 handler）"""
        if 'model_load_handler' in self._handlers:
            self._handlers['model_load_handler'].showModelLoadStatistics()
    
    def get_model_loader(self):
        """获取模型加载器实例"""
        return self._model_loader
    
    def get_model_operations(self):
        """获取模型操作实例"""
        return self._model_operations


