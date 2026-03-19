# -*- coding: utf-8 -*-

import os
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy.QtCore import Qt

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    # 从父目录（widgets）导入
    from ..style_manager import newIcon, createTextButton, applyTextButtonStyle
    from ..style_manager import FontManager, applyDefaultFont, applyTitleTextBoxStyle, applyDialogFont
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    # 独立运行时的处理
    import sys
    import os.path as osp
    # 添加父目录到路径
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from style_manager import newIcon, createTextButton, applyTextButtonStyle
    from style_manager import FontManager, applyDefaultFont, applyTitleTextBoxStyle, applyDialogFont
    from responsive_layout import ResponsiveLayout, scale_w, scale_h


class ModelSettingDialog(QtWidgets.QDialog):
    """
    模型设置对话框
    
    只负责UI控件设计和发送信号，业务逻辑由handler处理
    用于配置检测模型参数，模仿labelme的对话框设计模式
    """
    
    # 信号定义
    refreshModelListRequested = QtCore.Signal()  # 请求刷新模型列表
    modelSelected = QtCore.Signal(str)           # 模型被选择（传递模型路径）
    
    # 新增信号 - 用于与handler交互
    readModelDescriptionRequested = QtCore.Signal(str)  # 请求读取模型描述
    
    def __init__(self, parent=None, model_config=None, channel_id=None):
        """
        Args:
            parent: 父窗口
            model_config: 模型配置字典
            channel_id: 通道ID（如 'channel1'），用于显示通道特定的模型配置
        """
        super(ModelSettingDialog, self).__init__(parent)
        self._model_config = model_config or {}
        self._channel_id = channel_id
        self._current_model_path = model_config.get('model_path', '') if model_config else ''  # 存储当前选中的模型路径
        
        # 预训练模型信息
        self._pretrained_models = {
            "预训练模型1": {
                "name": "预训练模型1",
                "size": "14.1 MB",
                "classes": 80,
                "input": "640×640"
            },
            "预训练模型2": {
                "name": "预训练模型2", 
                "size": "49.7 MB",
                "classes": 80,
                "input": "640×640"
            },
            "预训练模型3": {
                "name": "预训练模型3",
                "size": "136.7 MB",
                "classes": 80,
                "input": "1280×1280"
            }
        }
        
        # 设置窗口标题（包含通道信息）
        title = self.tr("模型设置")
        if self._channel_id:
            title += f" - {self._channel_id}"
        self.setWindowTitle(title)
        self.setMinimumSize(scale_w(600), scale_h(550))  # 🔥 响应式尺寸
        
        # 应用全局字体到对话框
        applyDialogFont(self)
        
        self._initUI()
        self._loadConfig()
        self._connectSignals()
        self._refreshModelList()  # 初始化时扫描可用模型
    
    def _initUI(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout()
        
        # 只创建模型选择面板，不使用选项卡
        modelPanel = self._createModelTab()
        layout.addWidget(modelPanel)
        
        # 按钮组
        buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)
        
        self.setLayout(layout)
    
    def _createModelTab(self):
        """创建模型选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # 模型描述信息组 - 使用统一样式管理器
        infoGroup = QtWidgets.QGroupBox(self.tr("模型描述"))
        infoLayout = QtWidgets.QVBoxLayout()
        
        # 模型描述信息（从txt文件读取）
        self.lblModelDescription = QtWidgets.QTextEdit()
        self.lblModelDescription.setReadOnly(True)
        self.lblModelDescription.setMaximumHeight(scale_h(100))  # 🔥 响应式高度
        self.lblModelDescription.setPlaceholderText(self.tr("模型描述信息（从同文件夹下的txt文件读取）"))
        
        # 应用统一的标题文本框样式
        applyTitleTextBoxStyle(infoGroup, self.lblModelDescription)
        
        # 直接添加文本框，不需要额外的标签
        infoLayout.addWidget(self.lblModelDescription)
        
        infoGroup.setLayout(infoLayout)
        
        # 可用模型列表
        availableGroup = QtWidgets.QGroupBox(self.tr("检测模型列表"))
        availableLayout = QtWidgets.QVBoxLayout()
        
        # 模型列表控件
        self.modelListWidget = QtWidgets.QListWidget()
        self.modelListWidget.setMinimumHeight(scale_h(150))  # 🔥 响应式高度
        self.modelListWidget.setToolTip(self.tr("双击选择模型"))
        
        # 设置列表样式，支持蓝色高亮选中项
        self.modelListWidget.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #CCCCCC;
                selection-background-color: #0078D4;
                selection-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
            }
            QListWidget::item:selected {
                background-color: #0078D4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #E5F3FF;
            }
        """)
        availableLayout.addWidget(self.modelListWidget)
        
        # 🔥 刷新按钮已删除（用户要求）
        
        availableGroup.setLayout(availableLayout)
        
        layout.addWidget(availableGroup)
        layout.addWidget(infoGroup)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    
    def _connectSignals(self):
        """连接信号槽"""
        # 可用模型列表
        self.modelListWidget.itemDoubleClicked.connect(self._onModelListDoubleClicked)
        # self.btnRefreshModels.clicked.connect(self._refreshModelList)  # 🔥 已删除刷新按钮
    
    def _refreshModelList(self):
        """刷新可用模型列表 - 发射信号请求handler处理"""
        # 发射信号请求handler处理，由handler调用 setModelList 更新UI
        self.refreshModelListRequested.emit()
    
    def setModelList(self, model_list):
        """设置模型列表数据（由外部调用）"""
        self.modelListWidget.clear()
        
        for model_info in model_list:
            # 检查是否为模型管理面板的模型
            if model_info.get('source') == 'model_panel':
                # 来自模型管理面板的模型，使用更友好的显示格式
                display_name = f"[模型管理] {model_info.get('name', model_info.get('display_name', '未知模型'))}"
                size_info = model_info.get('size', '')
                if size_info:
                    display_name += f" ({size_info})"
                
                # 创建列表项
                item = QtWidgets.QListWidgetItem(display_name)
                item.setData(QtCore.Qt.UserRole, model_info)
                
                # 设置图标（区分模型类型）
                if 'DAT' in model_info.get('type', ''):
                    item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
                elif 'PT' in model_info.get('type', ''):
                    item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))
                else:
                    item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DriveHDIcon))
                
                # 详细的tooltip信息
                tooltip_parts = [
                    f"模型名称: {model_info.get('display_name', '未知')}",
                    f"模型类型: {model_info.get('type', '未知')}",
                    f"文件大小: {model_info.get('size', '未知')}",
                    f"输入尺寸: {model_info.get('input_size', '未知')}",
                    f"置信度: {model_info.get('confidence', 0.5)}",
                    f"IOU阈值: {model_info.get('iou', 0.45)}",
                    f"检测类别: {model_info.get('classes', '未知')}",
                    f"设备: {model_info.get('device', 'CPU')}",
                    f"文件路径: {model_info.get('path', '未知')}",
                    "",
                    f"描述: {model_info.get('description', '无描述')[:100]}..."
                ]
                item.setToolTip("\n".join(tooltip_parts))
                
            else:
                # 来自文件系统扫描的模型，使用原有格式
                rel_path = model_info.get('rel_path', f"{model_info.get('folder', '')}/{model_info.get('name', '')}")
                size_info = model_info.get('size', '')
                
                if size_info:
                    display_name = f"{rel_path} ({size_info})"
                else:
                    display_name = rel_path
                
                item = QtWidgets.QListWidgetItem(display_name)
                item.setData(QtCore.Qt.UserRole, model_info)
                
                # 详细的tooltip信息
                tooltip_parts = [
                    f"文件名: {model_info.get('name', '未知')}",
                    f"文件夹: {model_info.get('folder', '未知')}",
                    f"完整路径: {model_info.get('full_path', '未知')}"
                ]
                if size_info:
                    tooltip_parts.insert(1, f"文件大小: {size_info}")
                
                item.setToolTip('\n'.join(tooltip_parts))
            
            self.modelListWidget.addItem(item)
    
    def _onModelListDoubleClicked(self, item):
        """双击模型列表项时选择模型 - 发送信号"""
        model_info = item.data(QtCore.Qt.UserRole)
        if not model_info:
            return
        
        # 根据模型来源获取路径
        if model_info.get('source') == 'model_panel':
            # 来自模型管理面板的模型
            model_path = model_info.get('path', '')
        else:
            # 来自文件系统扫描的模型
            model_path = model_info.get('full_path', '')
        
        # 更新当前模型信息显示（内部会保存 _current_model_path）
        self._updateCurrentModelInfo(model_path)
        
        # 发送模型选择信号
        self.modelSelected.emit(model_path)
        
        # 发送读取模型描述请求信号给handler
        if model_path:
            self.readModelDescriptionRequested.emit(model_path)
    
    def _updateCurrentModelInfo(self, model_path):
        """
        更新当前模型信息显示
        
        Args:
            model_path: 模型文件路径
        """
        # 保存当前模型路径
        self._current_model_path = model_path
        
        # 在模型列表中高亮选中当前模型
        if model_path:
            self._highlightCurrentModelInList(model_path)
        else:
            # 清除所有选择
            self.modelListWidget.clearSelection()
            self.lblModelDescription.setPlainText("模型文件不存在")
    
    def _highlightCurrentModelInList(self, model_path):
        """在模型列表中高亮显示当前模型"""
        for i in range(self.modelListWidget.count()):
            item = self.modelListWidget.item(i)
            item_data = item.data(QtCore.Qt.UserRole)
            
            if item_data and item_data.get('full_path') == model_path:
                # 选中当前模型项
                self.modelListWidget.setCurrentItem(item)
                item.setSelected(True)
                break
    
    def _readModelDescription(self, model_path):
        """
        读取模型同文件夹下的txt文件内容（发送信号给handler处理）
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            str: 模型描述文本
        """
        # 发送读取模型描述请求信号给handler
        self.readModelDescriptionRequested.emit(model_path)
        return "正在读取模型描述..."
    
    def updateCurrentModelDisplay(self, model_path):
        """更新当前选择模型的显示信息（公共方法）"""
        # 更新当前模型信息显示
        self._updateCurrentModelInfo(model_path)
    
    def setModelPath(self, file_path):
        """设置模型路径（由handler调用）"""
        self._current_model_path = file_path
        self._updateCurrentModelInfo(file_path)
    
    def setModelDescription(self, description):
        """设置模型描述（由handler调用）"""
        self.lblModelDescription.setPlainText(description)
    
    
    def getModelConfig(self):
        """获取当前模型配置
        
        Returns:
            dict: 模型配置字典，包含 model_path 等信息
        """
        config = {
            'model_path': self._current_model_path,
        }
        return config
    
    
    def _loadConfig(self):
        """加载配置"""
        # 加载模型路径
        model_path = self._model_config.get('model_path', '')
        self._current_model_path = model_path
        
        # 显示当前模型路径和描述
        if model_path:
            self._updateCurrentModelInfo(model_path)
        else:
            # 清除模型列表选择
            self.modelListWidget.clearSelection()
    
    
    def _updateModelInfo(self, model_path):
        """更新模型信息（从文件）- 已废弃，使用 _updateCurrentModelInfo 代替"""
        # 调用新的方法
        self._updateCurrentModelInfo(model_path)
    
    
    def getModelConfig(self):
        """
        获取模型配置
        
        Returns:
            dict: 模型配置字典
        """
        return {
            # 模型
            'model_path': self._current_model_path,
        }


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    test_config = {
        'model_path': '',
    }
    
    dialog = ModelSettingDialog(model_config=test_config)
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        config = dialog.getModelConfig()
        for key, value in config.items():
            pass
    
    sys.exit(0)

