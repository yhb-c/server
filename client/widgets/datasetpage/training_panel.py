# -*- coding: utf-8 -*-

"""
模型训练面板

提供模型训练功能，包括训练参数配置、训练过程监控和训练结果展示
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy.QtCore import Qt
import os

# 导入响应式布局
try:
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    try:
        from widgets.responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x


class TrainingPanel(QtWidgets.QWidget):
    """
    模型训练面板
    
    提供模型训练参数配置和训练过程监控
    """
    
    # 自定义信号
    startTrainingClicked = QtCore.Signal(dict)    # 开始训练（携带训练参数）
    stopTrainingClicked = QtCore.Signal()         # 停止训练
    browsBaseModelClicked = QtCore.Signal()       # 浏览基础模型
    browseDatasetClicked = QtCore.Signal()        # 浏览数据集
    
    def __init__(self, parent=None):
        """
        Args:
            parent: 父窗口
        """
        super(TrainingPanel, self).__init__(parent)
        self._parent = parent
        
        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI"""
        # 创建主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 标题
        title_label = QtWidgets.QLabel("模型训练")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #0078d7;
                padding: 10px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # 创建滚动区域（防止内容过多时显示不完整）
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # 创建内容容器
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        # 基础配置组
        basic_group = self._createBasicConfigGroup()
        content_layout.addWidget(basic_group)
        
        # 训练参数组
        params_group = self._createTrainingParamsGroup()
        content_layout.addWidget(params_group)
        
        # 高级选项组
        advanced_group = self._createAdvancedOptionsGroup()
        content_layout.addWidget(advanced_group)
        
        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        
        # 定义统一的按钮样式
        button_style = """
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #f0f0f0;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f8f8f8;
                color: #a0a0a0;
                border: 1px solid #d0d0d0;
            }
        """
        
        self.start_train_btn = QtWidgets.QPushButton("开始训练")
        self.start_train_btn.setStyleSheet(button_style)
        
        self.stop_train_btn = QtWidgets.QPushButton("停止训练")
        self.stop_train_btn.setStyleSheet(button_style)
        self.stop_train_btn.setEnabled(False)
        
        control_layout.addStretch()
        control_layout.addWidget(self.start_train_btn)
        control_layout.addWidget(self.stop_train_btn)
        control_layout.addStretch()
        content_layout.addLayout(control_layout)
        
        # 训练日志区域
        log_group = QtWidgets.QGroupBox("训练日志")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        log_layout = QtWidgets.QVBoxLayout()
        
        self.train_log_text = QtWidgets.QTextEdit()
        self.train_log_text.setReadOnly(True)
        self.train_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.train_log_text.setMinimumHeight(scale_h(300))  # 🔥 响应式高度
        self.train_log_text.setPlainText("等待开始训练...\n")
        
        log_layout.addWidget(self.train_log_text)
        log_group.setLayout(log_layout)
        content_layout.addWidget(log_group)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def _createBasicConfigGroup(self):
        """创建基础配置组"""
        group = QtWidgets.QGroupBox("基础配置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(15)
        
        # 定义统一的按钮样式（用于浏览按钮）
        browse_button_style = """
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """
        
        # 基础模型
        base_model_layout = QtWidgets.QHBoxLayout()
        self.base_model_edit = QtWidgets.QLineEdit()
        self.base_model_edit.setPlaceholderText("选择基础模型文件 (.pt, .pth, .onnx, .engine)")
        self.base_model_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
        """)
        self.btn_browse_model = QtWidgets.QPushButton("浏览...")
        self.btn_browse_model.setStyleSheet(browse_button_style)
        self.btn_browse_model.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        base_model_layout.addWidget(self.base_model_edit)
        base_model_layout.addWidget(self.btn_browse_model)
        layout.addRow("基础模型:", base_model_layout)
        
        # 数据集路径
        dataset_layout = QtWidgets.QHBoxLayout()
        self.save_liquid_data_path_edit = QtWidgets.QLineEdit()
        self.save_liquid_data_path_edit.setPlaceholderText("选择数据集配置文件 (data.yaml)")
        self.save_liquid_data_path_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
        """)
        self.btn_browse_dataset = QtWidgets.QPushButton("浏览...")
        self.btn_browse_dataset.setStyleSheet(browse_button_style)
        self.btn_browse_dataset.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        dataset_layout.addWidget(self.save_liquid_data_path_edit)
        dataset_layout.addWidget(self.btn_browse_dataset)
        layout.addRow("数据集:", dataset_layout)
        
        # 实验名称
        self.exp_name_edit = QtWidgets.QLineEdit()
        self.exp_name_edit.setPlaceholderText("输入实验名称...")
        self.exp_name_edit.setText("liquid_level_training")
        self.exp_name_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
        """)
        layout.addRow("实验名称:", self.exp_name_edit)
        
        group.setLayout(layout)
        return group
    
    def _createTrainingParamsGroup(self):
        """创建训练参数组"""
        group = QtWidgets.QGroupBox("训练参数")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(15)
        
        # 图像尺寸
        self.imgsz_spin = QtWidgets.QSpinBox()
        self.imgsz_spin.setRange(320, 1280)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(640)
        self.imgsz_spin.setSuffix(" px")
        self.imgsz_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        layout.addRow("图像尺寸:", self.imgsz_spin)
        
        # 训练轮数
        self.epochs_spin = QtWidgets.QSpinBox()
        self.epochs_spin.setRange(1, 1000)
        self.epochs_spin.setSingleStep(10)
        self.epochs_spin.setValue(100)
        self.epochs_spin.setSuffix(" epochs")
        self.epochs_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        layout.addRow("训练轮数:", self.epochs_spin)
        
        # 批次大小
        self.batch_spin = QtWidgets.QSpinBox()
        self.batch_spin.setRange(1, 128)
        self.batch_spin.setSingleStep(1)
        self.batch_spin.setValue(16)
        self.batch_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        layout.addRow("批次大小:", self.batch_spin)
        
        # 工作线程数
        self.workers_spin = QtWidgets.QSpinBox()
        self.workers_spin.setRange(0, 16)
        self.workers_spin.setSingleStep(1)
        self.workers_spin.setValue(8)
        self.workers_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        layout.addRow("工作线程:", self.workers_spin)
        
        # 设备选择
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItems(["cpu", "0", "1", "2", "3"])
        self.device_combo.setCurrentText("cpu")
        # 使用Qt默认样式，不设置复杂的自定义样式
        layout.addRow("训练设备:", self.device_combo)
        
        # 优化器选择
        self.optimizer_combo = QtWidgets.QComboBox()
        self.optimizer_combo.addItems(["SGD", "Adam", "AdamW"])
        self.optimizer_combo.setCurrentText("SGD")
        # 使用Qt默认样式，不设置复杂的自定义样式
        layout.addRow("优化器:", self.optimizer_combo)
        
        group.setLayout(layout)
        return group
    
    def _createAdvancedOptionsGroup(self):
        """创建高级选项组"""
        group = QtWidgets.QGroupBox("高级选项")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(15)
        
        # Close Mosaic
        self.close_mosaic_spin = QtWidgets.QSpinBox()
        self.close_mosaic_spin.setRange(0, 100)
        self.close_mosaic_spin.setSingleStep(1)
        self.close_mosaic_spin.setValue(10)
        self.close_mosaic_spin.setSuffix(" epochs")
        self.close_mosaic_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        layout.addRow("Close Mosaic:", self.close_mosaic_spin)
        
        # 恢复训练
        self.resume_check = QtWidgets.QCheckBox("从上次训练继续")
        self.resume_check.setStyleSheet("""
            QCheckBox {
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        layout.addRow("", self.resume_check)
        
        # 缓存选项
        self.cache_check = QtWidgets.QCheckBox("缓存图像以加速训练")
        self.cache_check.setStyleSheet("""
            QCheckBox {
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        layout.addRow("", self.cache_check)
        
        # 单类别模式
        self.single_cls_check = QtWidgets.QCheckBox("单类别模式")
        self.single_cls_check.setStyleSheet("""
            QCheckBox {
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        layout.addRow("", self.single_cls_check)
        
        group.setLayout(layout)
        return group
    
    def _connectSignals(self):
        """连接信号"""
        self.btn_browse_model.clicked.connect(self._onBrowseBaseModel)
        self.btn_browse_dataset.clicked.connect(self._onBrowseDataset)
        self.start_train_btn.clicked.connect(self._onStartTraining)
        self.stop_train_btn.clicked.connect(self._onStopTraining)
    
    def _onBrowseBaseModel(self):
        """浏览基础模型文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择基础模型文件", "",
            "模型文件 (*.pt *.pth *.onnx *.dat *.engine);;TensorRT模型 (*.engine);;所有文件 (*.*)"
        )
        if file_path:
            self.base_model_edit.setText(file_path)
            self.browsBaseModelClicked.emit()
    
    def _onBrowseDataset(self):
        """浏览数据集配置文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择数据集配置文件", "",
            "配置文件 (*.yaml *.yml);;所有文件 (*.*)"
        )
        if file_path:
            self.save_liquid_data_path_edit.setText(file_path)
            self.browseDatasetClicked.emit()
    
    def _onStartTraining(self):
        """开始训练"""
        # 获取训练参数
        training_params = self.getTrainingParams()
        
        # 简单验证
        if not training_params['base_model']:
            QtWidgets.QMessageBox.warning(self, "警告", "请选择基础模型文件")
            return
        
        if not training_params['save_liquid_data_path']:
            QtWidgets.QMessageBox.warning(self, "警告", "请选择数据集配置文件")
            return
        
        if not training_params['exp_name']:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入实验名称")
            return
        
        # 发射信号
        self.startTrainingClicked.emit(training_params)
    
    def _onStopTraining(self):
        """停止训练"""
        self.stopTrainingClicked.emit()
    
    def getTrainingParams(self):
        """获取训练参数"""
        return {
            'base_model': self.base_model_edit.text().strip(),
            'save_liquid_data_path': self.save_liquid_data_path_edit.text().strip(),
            'imgsz': self.imgsz_spin.value(),
            'epochs': self.epochs_spin.value(),
            'batch': self.batch_spin.value(),
            'workers': self.workers_spin.value(),
            'device': self.device_combo.currentText(),
            'optimizer': self.optimizer_combo.currentText(),
            'close_mosaic': self.close_mosaic_spin.value(),
            'exp_name': self.exp_name_edit.text().strip(),
            'resume': self.resume_check.isChecked(),
            'cache': self.cache_check.isChecked(),
            'single_cls': self.single_cls_check.isChecked(),
            'pretrained': False
        }
    
    def append_training_log(self, message):
        """追加训练日志"""
        self.train_log_text.append(message.rstrip('\n'))
        # 自动滚动到底部
        scrollbar = self.train_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_training_log(self):
        """清空训练日志"""
        self.train_log_text.clear()
    
    def set_training_active(self, active):
        """设置训练状态"""
        self.start_train_btn.setEnabled(not active)
        self.stop_train_btn.setEnabled(active)


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("模型训练面板测试")
    window.resize(900, 800)
    
    # 创建训练面板
    panel = TrainingPanel()
    window.setCentralWidget(panel)
    
    def on_start_training(params):
        panel.append_training_log("训练已开始...\n")
        panel.set_training_active(True)
    
    def on_stop_training():
        panel.append_training_log("训练已停止\n")
        panel.set_training_active(False)
    
    panel.startTrainingClicked.connect(on_start_training)
    panel.stopTrainingClicked.connect(on_stop_training)
    
    window.show()
    sys.exit(app.exec_())

