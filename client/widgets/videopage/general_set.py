# -*- coding: utf-8 -*-

"""
常规设置面板组件（专用）

只负责UI控件设计和发送信号，业务逻辑由handler处理
用于配置任务信息、基本参数、检测区域、数据传输等
包含左侧菜单栏：通用设置、逻辑设置、模型设置
"""

import cv2
import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

# 导入图标工具和响应式布局
try:
    from ..style_manager import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
    from .modelsetting_dialogue import ModelSettingDialog
    from .logicsetting_dialogue import LogicSettingDialog
except (ImportError, ValueError):
    import sys
    import os.path as osp
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from style_manager import newIcon
    from responsive_layout import ResponsiveLayout, scale_w, scale_h
    from videopage.modelsetting_dialogue import ModelSettingDialog
    from videopage.logicsetting_dialogue import LogicSettingDialog


class GeneralSetPanel(QtWidgets.QWidget):
    """
    常规设置面板组件（专用）
    
    包含顶部菜单栏和三个设置页面：
    - 通用设置
    - 模型设置
    - 逻辑设置
    
    Architecture:
        ┌──────────────────────────────────────────┐
        │     GeneralSetPanel (主容器)              │
        ├──────────────────────────────────────────┤
        │ [通用设置] [模型设置] [逻辑设置]          │ ← 标签页式导航栏
        ├──────────────────────────────────────────┤
        │  Content Container (独立)                 │
        │  ┌───────────────────────────────────┐   │
        │  │  QStackedWidget                   │   │
        │  │  ├─ General Panel                 │   │
        │  │  ├─ Model Panel                   │   │
        │  │  └─ Logic Panel                   │   │
        │  └───────────────────────────────────┘   │
        └──────────────────────────────────────────┘
    """
    
    # 面板索引常量
    PANEL_GENERAL = 0  # 通用设置面板
    PANEL_MODEL = 1    # 模型设置面板
    PANEL_LOGIC = 2    # 逻辑设置面板
    
    # 自定义信号
    taskInfoChanged = QtCore.Signal(dict)  # 任务信息变化
    areaCountChanged = QtCore.Signal(int)  # 区域个数变化
    safetyParamsChanged = QtCore.Signal(dict)  # 安全参数变化
    systemSettingsChanged = QtCore.Signal(dict)  # 数据传输变化
    logicSettingsChanged = QtCore.Signal(dict)  # 逻辑设置变化
    modelSelected = QtCore.Signal(dict)  # 模型选择（传递dict包含model_path和channel_id）
    annotationRequested = QtCore.Signal()  # 请求标注
    annotationCompleted = QtCore.Signal(dict)  # 标注完成
    detectionStartRequested = QtCore.Signal()  # 请求开始检测
    settingsSaveRequested = QtCore.Signal(dict)  # 请求保存设置
    
    # 新增信号 - 用于与handler交互
    refreshModelListRequested = QtCore.Signal()  # 请求刷新模型列表（转发给ModelSettingDialog）
    resetRequested = QtCore.Signal()  # 请求重置设置
    loadTaskIdOptionsRequested = QtCore.Signal()  # 请求加载任务ID选项
    loadSettingsRequested = QtCore.Signal()  # 请求加载设置
    saveSettingsRequested = QtCore.Signal(dict)  # 请求保存设置
    createAnnotationEngineRequested = QtCore.Signal()  # 请求创建标注引擎
    showAnnotationImageRequested = QtCore.Signal(str)  # 请求显示标注图片
    getAreaCountRequested = QtCore.Signal()  # 请求获取区域数量
    loadChannelModelConfigRequested = QtCore.Signal(str)  # 请求加载通道模型配置(channel_id)
    autoSaveModelPathRequested = QtCore.Signal(str)  # 请求自动保存模型路径(model_path)
    
    def __init__(self, parent=None):
        super(GeneralSetPanel, self).__init__(parent)

        # 初始化日志
        from client.utils.logger import get_logger
        self.logger = get_logger('client')

        self.channel_name = None
        self.channel_id = None  # 新增：存储通道ID（如'channel1'）
        self.task_info = None
        self._current_model_config = {}  # 存储当前的模型配置
        self._current_logic_config = {}  # 存储当前的逻辑配置
        self._cached_area_count = 0  #  缓存区域数量（由handler设置）

        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI - 顶部菜单栏 + 下方内容容器"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部菜单栏
        menu_bar = self._createMenuBar()
        main_layout.addWidget(menu_bar)
        
        # 下方内容容器（独立的面板容器）
        self.content_container = self._createContentContainer()
        main_layout.addWidget(self.content_container, 1)
    
    def _createMenuBar(self):
        """创建顶部标签页样式的导航栏"""
        # 创建容器
        menu_container = QtWidgets.QWidget()
        menu_container.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-bottom: 1px solid #d0d0d0;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(menu_container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # 创建按钮样式 - 与 MenuBar 一致
        button_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 6px 20px;
                color: #000000;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked {
                background-color: #d0d0d0;
            }
        """
        
        # 通用设置按钮
        self.btn_general = QtWidgets.QPushButton("通用设置")
        self.btn_general.setCheckable(True)
        self.btn_general.setChecked(True)
        self.btn_general.setStyleSheet(button_style)
        self.btn_general.setCursor(Qt.PointingHandCursor)
        
        # 模型设置按钮
        self.btn_model = QtWidgets.QPushButton("模型设置")
        self.btn_model.setCheckable(True)
        self.btn_model.setStyleSheet(button_style)
        self.btn_model.setCursor(Qt.PointingHandCursor)
        
        # 逻辑设置按钮
        self.btn_logic = QtWidgets.QPushButton("逻辑设置")
        self.btn_logic.setCheckable(True)
        self.btn_logic.setStyleSheet(button_style)
        self.btn_logic.setCursor(Qt.PointingHandCursor)
        
        # 创建按钮组（确保只有一个按钮被选中）
        self.menu_button_group = QtWidgets.QButtonGroup()
        self.menu_button_group.setExclusive(True)
        self.menu_button_group.addButton(self.btn_general, 0)
        self.menu_button_group.addButton(self.btn_model, 1)
        self.menu_button_group.addButton(self.btn_logic, 2)
        
        # 连接信号
        self.menu_button_group.buttonClicked[int].connect(self._onMenuButtonClicked)
        
        # 添加按钮到布局
        layout.addWidget(self.btn_general)
        layout.addWidget(self.btn_model)
        layout.addWidget(self.btn_logic)
        layout.addStretch()
        
        return menu_container
    
    def _createContentContainer(self):
        """创建下方内容容器（独立的面板容器）"""
        # 创建容器widget
        container = QtWidgets.QWidget()
        container.setStyleSheet("QWidget { background-color: white; }")
        
        # 容器布局
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 创建堆叠窗口用于切换不同的设置面板
        self.stacked_widget = QtWidgets.QStackedWidget()
        self.stacked_widget.setStyleSheet("QStackedWidget { background-color: white; }")
        
        # 创建各个设置面板
        self.general_panel = self._createGeneralPanel()
        self.model_panel = self._createModelPanel()
        self.logic_panel = self._createLogicPanel()
        
        # 按照菜单按钮的顺序添加面板：通用设置(0)、模型设置(1)、逻辑设置(2)
        self.stacked_widget.addWidget(self.general_panel)
        self.stacked_widget.addWidget(self.model_panel)
        self.stacked_widget.addWidget(self.logic_panel)
        
        # 将堆叠窗口添加到容器
        container_layout.addWidget(self.stacked_widget)
        
        # 默认显示通用设置
        self.stacked_widget.setCurrentIndex(self.PANEL_GENERAL)
        
        return container
    
    def _onMenuButtonClicked(self, button_id):
        """菜单按钮点击事件"""
        self.stacked_widget.setCurrentIndex(button_id)
    
    def switchToPanel(self, panel_index):
        """
        切换到指定的面板
        
        Args:
            panel_index: 面板索引 (0=通用设置, 1=模型设置, 2=逻辑设置)
        """
        if 0 <= panel_index < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(panel_index)
            # 同步更新顶部按钮状态
            button = self.menu_button_group.button(panel_index)
            if button:
                button.setChecked(True)
    
    def getCurrentPanelIndex(self):
        """获取当前显示的面板索引"""
        return self.stacked_widget.currentIndex()
    
    def getPanelByIndex(self, panel_index):
        """
        获取指定索引的面板对象
        
        Args:
            panel_index: 面板索引 (使用 PANEL_* 常量)
            
        Returns:
            对应的面板对象，如果索引无效则返回None
        """
        if panel_index == self.PANEL_GENERAL:
            return self.general_panel
        elif panel_index == self.PANEL_MODEL:
            return self.model_panel
        elif panel_index == self.PANEL_LOGIC:
            return self.logic_panel
        return None
    
    def _createGeneralPanel(self):
        """创建通用设置面板"""
        panel = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(panel)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建滚动区域
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)
        
        # 1. 任务信息区域（合并任务信息、模型配置、数据传输）
        task_group = self._createTaskInfoGroup()
        content_layout.addWidget(task_group)
        
        # 4. 标注区域
        annotation_group = self._createAnnotationGroup()
        content_layout.addWidget(annotation_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        return panel
    
    def _createLogicPanel(self):
        """创建逻辑设置面板 - 直接嵌入 LogicSettingDialog 的内容"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建一个 LogicSettingDialog 实例（但不作为对话框使用，只用其UI内容）
        # 传入当前的逻辑配置和通道ID
        self.logic_setting_widget = LogicSettingDialog(
            parent=self,
            logic_config=self._current_logic_config,
            channel_id=self.channel_id
        )
        
        # 移除对话框的窗口标志，使其作为普通widget嵌入
        self.logic_setting_widget.setWindowFlags(Qt.Widget)
        
        # 隐藏对话框的按钮栏（Ok/Cancel）
        # 找到 QDialogButtonBox 并隐藏它
        for child in self.logic_setting_widget.children():
            if isinstance(child, QtWidgets.QDialogButtonBox):
                child.hide()
                break
        
        # 将 logic_setting_widget 添加到面板
        layout.addWidget(self.logic_setting_widget)
        
        return panel
    
    def _createModelPanel(self):
        """创建模型设置面板 - 直接嵌入 ModelSettingDialog 的内容"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建一个 ModelSettingDialog 实例（但不作为对话框使用，只用其UI内容）
        # 传入当前的模型配置和通道ID
        self.model_setting_widget = ModelSettingDialog(
            parent=self,
            model_config=self._current_model_config,
            channel_id=self.channel_id
        )
        
        # 移除对话框的窗口标志，使其作为普通widget嵌入
        self.model_setting_widget.setWindowFlags(Qt.Widget)
        
        # 隐藏对话框的按钮栏（Ok/Cancel）
        # 找到 QDialogButtonBox 并隐藏它
        for child in self.model_setting_widget.children():
            if isinstance(child, QtWidgets.QDialogButtonBox):
                child.hide()
                break
        
        # 将 model_setting_widget 添加到面板
        layout.addWidget(self.model_setting_widget)
        
        # 连接信号：当用户在模型设置中选择模型时
        self.model_setting_widget.modelSelected.connect(self._onModelSelected)
        self.model_setting_widget.refreshModelListRequested.connect(
            self.refreshModelListRequested.emit
        )
        
        # 连接信号：当模型路径改变时，自动保存到配置文件
        self.model_setting_widget.modelSelected.connect(self._autoSaveModelPath)
        
        #  重要：信号连接后立即刷新模型列表
        # 因为 ModelSettingDialog.__init__() 中的 _refreshModelList() 调用在信号连接之前
        # 需要在信号连接后再次触发刷新
        QtCore.QTimer.singleShot(0, self.model_setting_widget._refreshModelList)
        
        return panel
    
    def _createTaskInfoGroup(self):
        """创建任务信息组（合并任务信息、模型配置、数据传输）"""
        group = QtWidgets.QGroupBox("任务信息")
        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(10)
        
        # 第一行：任务编号、任务名称
        task_id_label = QtWidgets.QLabel("任务编号:")
        self.task_id_edit = QtWidgets.QLineEdit()
        self.task_id_edit.setReadOnly(True)
        self.task_id_edit.setPlaceholderText("任务编号")
        self.task_id_edit.setMinimumWidth(scale_w(140))  # 响应式宽度
        
        task_name_label = QtWidgets.QLabel("任务名称:")
        self.task_name_edit = QtWidgets.QLineEdit()
        self.task_name_edit.setReadOnly(True)
        self.task_name_edit.setPlaceholderText("任务名称")
        self.task_name_edit.setMinimumWidth(scale_w(140))  # 响应式宽度
        
        layout.addWidget(task_id_label, 0, 0)
        layout.addWidget(self.task_id_edit, 0, 1)
        layout.addWidget(task_name_label, 0, 2)
        layout.addWidget(self.task_name_edit, 0, 3)
        
        # 第二行：检测模型、地址
        model_path_label = QtWidgets.QLabel("检测模型:")
        self.model_path_display = QtWidgets.QLineEdit()
        self.model_path_display.setReadOnly(True)
        self.model_path_display.setPlaceholderText("未配置检测模型")
        self.model_path_display.setMinimumWidth(scale_w(140))  # 响应式宽度
        
        push_label = QtWidgets.QLabel("数据推送地址:")
        self.push_edit = QtWidgets.QLineEdit()
        self.push_edit.setReadOnly(True)
        self.push_edit.setPlaceholderText("数据推送功能开发中，敬请期待。")
        self.push_edit.setMinimumWidth(scale_w(140))  # 响应式宽度
        
        
        layout.addWidget(model_path_label, 1, 0)
        layout.addWidget(self.model_path_display, 1, 1)
        layout.addWidget(push_label, 1, 2)
        layout.addWidget(self.push_edit, 1, 3)
        
        group.setLayout(layout)
        return group
    
    
    def _createAnnotationGroup(self):
        """创建标注区域组"""
        group = QtWidgets.QGroupBox("检测区域预览")
        layout = QtWidgets.QVBoxLayout()
        
        # 标注结果显示区域（可显示文字或图片）
        self.annotation_display_label = QtWidgets.QLabel("尚未标注")
        self.annotation_display_label.setAlignment(Qt.AlignCenter)
        self.annotation_display_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                padding: 10px;
                font-size: 12pt;
                color: #666;
            }
        """)
        self.annotation_display_label.setMinimumHeight(scale_h(610))  # 响应式高度
        self.annotation_display_label.setScaledContents(False)  # 不拉伸图片
        
        # 保存标注状态标签的引用（为了兼容性）
        self.annotation_status_label = self.annotation_display_label
        
        # 标注按钮
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        #  使用Qt默认样式 + 响应式布局
        self.start_annotation_btn = QtWidgets.QPushButton("开始标注")
        self.start_annotation_btn.setMinimumSize(scale_w(120), scale_h(35))  # 响应式尺寸
        
        self.start_detection_btn = QtWidgets.QPushButton("开始检测")
        self.start_detection_btn.setMinimumSize(scale_w(120), scale_h(35))  # 响应式尺寸
        
        # 🔥 保存设置按钮已删除（用户要求）
        
        btn_layout.addWidget(self.start_annotation_btn)
        btn_layout.addWidget(self.start_detection_btn)
        btn_layout.addStretch()
        
        layout.addWidget(self.annotation_status_label)
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group
    
    
    def _connectSignals(self):
        """连接信号槽"""
        # 任务信息变化 - 已改为只读，不再连接信号
        # self.task_id_edit.textChanged.connect(self._onTaskInfoChanged)
        # self.task_name_edit.textChanged.connect(self._onTaskInfoChanged)
        
        # 数据传输变化
        self.push_edit.textChanged.connect(self._onSystemSettingsChanged)
        
        # 标注和检测按钮
        self.start_annotation_btn.clicked.connect(self._onStartAnnotation)
        self.start_detection_btn.clicked.connect(self._onStartDetection)
        
        # 🔥 保存设置按钮已删除
        # self.save_btn.clicked.connect(self._onSaveSettings)
    
    def _loadTaskIdOptions(self):
        """加载任务编号选项（发送信号给handler处理）"""
        # 发送加载任务ID选项请求信号给handler
        self.loadTaskIdOptionsRequested.emit()
    
    def setTaskIdOptions(self, task_ids):
        """设置任务编号选项（由handler调用）- 已废弃，改为直接设置文本"""
        # 只读文本框不需要选项列表
        pass
    
    def _onModelSelected(self, model_path):
        """
        模型设置面板中选择模型时的处理
        
        Args:
            model_path: 模型文件路径
        """
        # 获取当前的模型配置
        if hasattr(self, 'model_setting_widget'):
            config = self.model_setting_widget.getModelConfig()
            self._current_model_config = config
            
            # 发送模型选择信号
            model_data = {
                'model_path': model_path,
                'channel_id': self.channel_id,
                'model_config': config
            }
            self.modelSelected.emit(model_data)
    
    
    
    def _onTaskInfoChanged(self):
        """任务信息变化 - 已废弃，改为只读"""
        # 只读模式下不再触发变化信号
        pass
    
    def _onSystemSettingsChanged(self):
        """数据传输变化"""
        system_settings = {
            'push_address': self.push_edit.text()
        }
        self.systemSettingsChanged.emit(system_settings)
    
    
    def _onStartAnnotation(self):
        """开始标注按钮点击（发送信号给handler处理）"""
        # 发送创建标注引擎请求信号给handler
        self.createAnnotationEngineRequested.emit()
        # 发送标注请求信号
        self.annotationRequested.emit()
    
    def _onStartDetection(self):
        """开始检测按钮点击"""
        # 🔥 使用更长的延迟，确保UI完全响应
        QtCore.QTimer.singleShot(100, self._actualStartDetection)
    
    def _actualStartDetection(self):
        """实际执行检测启动"""
        # 🔥 分批处理，让UI保持响应
        self._processUIEvents()
        self.detectionStartRequested.emit()
    
    def _processUIEvents(self):
        """处理UI事件，保持界面响应"""
        QtWidgets.QApplication.processEvents()
        QtCore.QThread.msleep(1)  # 短暂休眠，让UI线程处理事件
    
    def getModelConfig(self):
        """获取当前模型配置
        
        Returns:
            dict: 模型配置字典
        """
        # 从嵌入的模型设置widget获取最新配置
        if hasattr(self, 'model_setting_widget'):
            config = self.model_setting_widget.getModelConfig()
            self._current_model_config = config
            return config.copy()
        return self._current_model_config.copy()

    def setModelPathDisplay(self, model_path):
        """设置模型路径显示文本（只显示文件名）"""
        if not hasattr(self, 'model_path_display'):
            return
        if model_path:
            # 只显示文件名，不显示完整路径
            import os
            text = os.path.basename(model_path)
        else:
            text = ""
        self.model_path_display.setText(text)
    
    def setModelConfig(self, config):
        """设置模型配置（由handler调用）
        
        Args:
            config: 模型配置字典
        """
        self._current_model_config = config.copy() if config else {}
        
        # 如果模型设置widget已创建，也更新其配置
        # 注意：由于widget是在面板创建时实例化的，可能还未创建
        # 这个方法主要用于从外部加载配置时使用
    
    def getLogicConfig(self):
        """获取当前逻辑配置
        
        Returns:
            dict: 逻辑配置字典
        """
        # 从嵌入的逻辑设置widget获取最新配置
        if hasattr(self, 'logic_setting_widget'):
            config = self.logic_setting_widget.getLogicConfig()
            self._current_logic_config = config
            return config.copy()
        return self._current_logic_config.copy()
    
    def setLogicConfig(self, config):
        """设置逻辑配置（由handler调用）
        
        Args:
            config: 逻辑配置字典
        """
        self._current_logic_config = config.copy() if config else {}
    
    def _onSaveSettings(self):
        """保存设置按钮点击（发送信号给handler处理）"""
        settings = self.getSettings()
        self.saveSettingsRequested.emit(settings)
    
    
    def showSavemission_result(self, success, message):
        """显示保存结果（由handler调用）"""
        icon = QtWidgets.QMessageBox.Information if success else QtWidgets.QMessageBox.Warning
        QtWidgets.QMessageBox.information(self, "保存设置", message)
    
    def showLoadmission_result(self, success, message):
        """显示加载结果（由handler调用）"""
        icon = QtWidgets.QMessageBox.Information if success else QtWidgets.QMessageBox.Warning
        QtWidgets.QMessageBox.information(self, "加载设置", message)
    
    def showAnnotationEngineCreated(self, success, message):
        """显示标注引擎创建结果（由handler调用）"""
        icon = QtWidgets.QMessageBox.Information if success else QtWidgets.QMessageBox.Warning
        QtWidgets.QMessageBox.information(self, "标注引擎", message)
    
    def showAnnotationImage(self, image_path):
        """显示标注图片（由handler调用）"""
        try:
            from qtpy import QtCore, QtGui
            import cv2
            
            # 读取图片
            img = cv2.imread(image_path)
            if img is not None:
                # 转换为RGB格式
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = img_rgb.shape
                bytes_per_line = ch * w
                
                # 创建QImage
                qt_image = QtGui.QImage(img_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qt_image)
                
                # 缩放图片以适应控件（保持宽高比）
                scaled_pixmap = pixmap.scaled(
                    self.annotation_display_label.width() - 20,
                    self.annotation_display_label.height() - 20,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                
                # 显示图片
                self.annotation_display_label.setPixmap(scaled_pixmap)
                self.annotation_display_label.setStyleSheet("""
                    QLabel {
                        background-color: #E8F5E9;
                        border: 2px solid #4CAF50;
                        border-radius: 5px;
                        padding: 10px;
                    }
                """)
            else:
                # 图片读取失败，显示文字
                self._showAnnotationText(0, True)
        except Exception as e:
            # 显示文字
            self._showAnnotationText(0, True)
    
    def setChannelInfo(self, channel_name, channel_id=None, task_info=None):
        """
        设置通道信息
        
        Args:
            channel_name: 通道显示名称，如"通道1"
            channel_id: 通道ID，如"channel1"（用于配置文件索引）
            task_info: 任务信息字典
        """
        self.channel_name = channel_name
        self.channel_id = channel_id or channel_name.lower().replace(' ', '')
        self.task_info = task_info
        
        # 更新模型设置widget的channel_id（如果已创建）
        if hasattr(self, 'model_setting_widget'):
            self.model_setting_widget._channel_id = self.channel_id
        
        if task_info:
            if 'task_id' in task_info:
                self.task_id_edit.setText(task_info['task_id'])
            if 'task_name' in task_info:
                self.task_name_edit.setText(task_info['task_name'])
        
        # 立即发送信号请求handler加载通道特定的模型配置
        # 这样可以在通用设置面板显示正确的模型路径
        if self.channel_id:
            self.loadChannelModelConfigRequested.emit(self.channel_id)
    
    def applyModelConfigFromHandler(self, model_config, absolute_path, channel_model_key):
        """
        应用从handler加载的模型配置（由handler调用）
        
        Args:
            model_config: 模型配置字典
            absolute_path: 模型文件的绝对路径
            channel_model_key: 配置键名
        """
        if not hasattr(self, 'model_setting_widget'):
            return
        
        try:
            # 更新widget的配置
            self._current_model_config = model_config
            self.model_setting_widget._model_config = model_config
            self.model_setting_widget._current_model_path = absolute_path
            
            # 刷新显示
            self.model_setting_widget._loadConfig()
            
            # 更新配置来源显示
            if hasattr(self.model_setting_widget, 'setConfigSource'):
                source_info = f"default_config.yaml → {channel_model_key}"
                self.model_setting_widget.setConfigSource(source_info)
            
            # 🔥 关键修复：加载模型配置后，立即读取模型描述
            if absolute_path and hasattr(self.model_setting_widget, 'readModelDescriptionRequested'):
                self.model_setting_widget.readModelDescriptionRequested.emit(absolute_path)
                
        except Exception as e:
            pass
    
    def _autoSaveModelPath(self, model_path):
        """
        自动保存模型路径 - 发送信号给handler处理
        
        Args:
            model_path: 新选择的模型路径（绝对路径）
        """
        if not self.channel_id:
            return
        
        #  发送信号给handler处理实际的文件保存逻辑
        self.autoSaveModelPathRequested.emit(model_path)
    
    def setAreaCount(self, area_count):
        """设置区域数量（由handler调用）"""
        self._cached_area_count = area_count
    
    def getSettings(self):
        """获取当前设置"""
        settings = {
            'channel_name': self.channel_name,
            'task_id': self.task_id_edit.text(),
            'task_name': self.task_name_edit.text(),
            'area_count': self._cached_area_count,  #  使用缓存值（由handler设置）
            'push_address': self.push_edit.text(),
            'areas': {},  # 区域信息从标注结果获取
            'area_heights': {},  # 区域高度从标注结果获取
            # 模型配置（从嵌入的widget获取最新配置）
            'model_config': self.getModelConfig(),
            # 逻辑配置（从嵌入的widget获取最新配置）
            'logic_config': self.getLogicConfig(),
        }
        
        return settings
    
    
    def setSettings(self, settings):
        """设置配置"""
        if 'task_id' in settings:
            self.task_id_edit.setText(settings['task_id'])
        
        if 'task_name' in settings:
            self.task_name_edit.setText(settings['task_name'])
        
        # area_count 不再从UI设置，由标注结果决定
        
        if 'push_address' in settings:
            self.push_edit.setText(settings['push_address'])
        
        # 设置模型配置
        if 'model_config' in settings:
            self.setModelConfig(settings['model_config'])
        
        # 设置逻辑配置
        if 'logic_config' in settings:
            self.setLogicConfig(settings['logic_config'])
        
        # 区域名称和高度不再在通用设置界面显示，由标注界面管理
    
    def setModelConfig(self, model_config):
        """设置模型配置
        
        Args:
            model_config: 模型配置字典
        """
        try:
            if not hasattr(self, 'model_setting_widget'):
                return
            
            # 设置模型路径
            if 'model_path' in model_config and model_config['model_path']:
                self.model_setting_widget.setModelPath(model_config['model_path'])
            
            # 设置其他模型参数（如果有的话）
            # 可以根据需要扩展
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def setLogicConfig(self, logic_config):
        """设置逻辑配置
        
        Args:
            logic_config: 逻辑配置字典
        """
        try:
            # TODO: 根据需要实现逻辑配置的UI设置
            # 目前暂时不需要设置，因为logic相关的UI控件可能还没有实现
            pass
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def showAnnotationmission_result(self, pixmap, area_count):
        """
        显示标注结果图像（由handler处理好的pixmap）
        
        Args:
            pixmap: QtGui.QPixmap 对象，已处理为600x450尺寸
            area_count: 标注区域数量
        """
        try:
            # 显示图片
            self.annotation_display_label.setPixmap(pixmap)
            self.annotation_display_label.setStyleSheet("""
                QLabel {
                    background-color: #000000;
                    border: 2px solid #4CAF50;
                    border-radius: 5px;
                    padding: 0px;
                }
            """)
            
        except Exception as e:
            # 显示失败时显示文字
            self._showAnnotationText(area_count, True)
    
    def updateAnnotationStatus(self, has_annotation, area_count=0, image_path=None):
        """
        更新标注状态，显示标注结果图片或文字
        
        Args:
            has_annotation: 是否有标注
            area_count: 标注区域数量
            image_path: 标注结果图片路径（如果提供则显示图片）
        """
        if has_annotation:
            if image_path:
                # 显示标注结果图片（发送信号给handler处理）
                self.showAnnotationImageRequested.emit(image_path)
            else:
                # 没有图片路径，显示文字
                self._showAnnotationText(area_count, True)
        else:
            # 未标注状态
            self._showAnnotationText(0, False)
    
    def _showAnnotationText(self, area_count, has_annotation):
        """显示标注状态文字"""
        if has_annotation:
            self.annotation_display_label.clear()  # 清除图片
            self.annotation_display_label.setText(f"已标注 {area_count} 个检测区域")
            self.annotation_display_label.setStyleSheet("""
                QLabel {
                    background-color: #E8F5E9;
                    border: 2px solid #4CAF50;
                    border-radius: 5px;
                    padding: 20px;
                    font-size: 12pt;
                    color: #2E7D32;
                    font-weight: bold;
                }
            """)
        else:
            self.annotation_display_label.clear()  # 清除图片
            self.annotation_display_label.setText("尚未标注")
            self.annotation_display_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border: 2px dashed #999;
                    border-radius: 5px;
                    padding: 20px;
                    font-size: 12pt;
                    color: #666;
                }
            """)


class GeneralSetDialog(QtWidgets.QDialog):
    """
    通道设置对话框
    
    将 GeneralSetPanel 包装成一个可以弹出的对话框
    """
    
    def __init__(self, parent=None, channel_name=None, channel_id=None, task_info=None):
        super(GeneralSetDialog, self).__init__(parent)
        
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.task_info = task_info
        
        # 设置左上角图标为设置图标
        self.setWindowIcon(newIcon("设置"))
        
        # 移除帮助按钮（问号按钮）
        self.setWindowFlags(
            self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        self._initUI()
        
        # 设置通道信息
        if channel_name:
            self.panel.setChannelInfo(channel_name, channel_id, task_info)
    
    def _initUI(self):
        """初始化UI"""
        self.setWindowTitle("通道设置")
        self.resize(1000, 1000)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加 GeneralSetPanel
        self.panel = GeneralSetPanel(self)
        layout.addWidget(self.panel)


    def getSettings(self):
        """获取设置"""
        return self.panel.getSettings()
    
    def setSettings(self, settings):
        """设置配置"""
        self.panel.setSettings(settings)
    
    def getPanel(self):
        """获取内部的 GeneralSetPanel 实例"""
        return self.panel


