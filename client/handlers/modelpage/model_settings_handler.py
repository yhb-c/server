# -*- coding: utf-8 -*-

from qtpy import QtWidgets


class ModelSettingsHandler:
    """
    模型设置处理器
    
    处理模型设置对话框和相关功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型设置处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self = None
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self = main_window
    
    def _onModelSettings(self):
        """模型设置"""
        try:
            # 检查是否有选中的模型
            if hasattr(self, 'modelSetPage'):
                current_model = self.modelSetPage.getCurrentModel()
                if not current_model:
                    QtWidgets.QMessageBox.warning(self, "警告", "请先选择一个模型")
                    return
                
                # 移除"（默认）"标记获取实际模型名
                model_name = current_model.replace("（默认）", "").strip()
                
                # 获取模型参数
                all_params = self.modelSetPage.getAllModelParams()
                if model_name not in all_params:
                    QtWidgets.QMessageBox.warning(self, "错误", f"未找到模型 '{model_name}' 的参数信息")
                    return
                
                model_params = all_params[model_name]
                
                # 创建模型设置对话框
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle(f"模型设置 - {model_name}")
                dialog.setModal(True)
                dialog.resize(600, 500)
                
                # 创建滚动区域
                scroll_area = QtWidgets.QScrollArea()
                scroll_area.setWidgetResizable(True)
                
                # 创建内容widget
                content_widget = QtWidgets.QWidget()
                layout = QtWidgets.QVBoxLayout(content_widget)
                
                # 基本信息
                info_group = QtWidgets.QGroupBox("基本信息")
                info_layout = QtWidgets.QFormLayout(info_group)
                
                name_edit = QtWidgets.QLineEdit(model_params.get('name', ''))
                name_edit.setReadOnly(True)
                info_layout.addRow("模型名称:", name_edit)
                
                type_edit = QtWidgets.QLineEdit(model_params.get('type', ''))
                info_layout.addRow("模型类型:", type_edit)
                
                path_edit = QtWidgets.QLineEdit(model_params.get('path', ''))
                path_edit.setReadOnly(True)
                info_layout.addRow("模型路径:", path_edit)
                
                size_edit = QtWidgets.QLineEdit(model_params.get('size', ''))
                size_edit.setReadOnly(True)
                info_layout.addRow("模型大小:", size_edit)
                
                layout.addWidget(info_group)
                
                # 检测参数
                detect_group = QtWidgets.QGroupBox("检测参数")
                detect_layout = QtWidgets.QFormLayout(detect_group)
                
                confidence_spin = QtWidgets.QDoubleSpinBox()
                confidence_spin.setRange(0.0, 1.0)
                confidence_spin.setSingleStep(0.05)
                confidence_spin.setValue(model_params.get('confidence', 0.5))
                detect_layout.addRow("置信度阈值:", confidence_spin)
                
                iou_spin = QtWidgets.QDoubleSpinBox()
                iou_spin.setRange(0.0, 1.0)
                iou_spin.setSingleStep(0.05)
                iou_spin.setValue(model_params.get('iou', 0.45))
                detect_layout.addRow("IoU阈值:", iou_spin)
                
                classes_spin = QtWidgets.QSpinBox()
                classes_spin.setRange(1, 1000)
                classes_spin.setValue(model_params.get('classes', 80))
                detect_layout.addRow("类别数量:", classes_spin)
                
                input_edit = QtWidgets.QLineEdit(model_params.get('input', '640x640'))
                detect_layout.addRow("输入尺寸:", input_edit)
                
                layout.addWidget(detect_group)
                
                # 设备设置
                device_group = QtWidgets.QGroupBox("设备设置")
                device_layout = QtWidgets.QFormLayout(device_group)
                
                device_combo = QtWidgets.QComboBox()
                device_combo.addItems(["CPU", "CUDA:0 (GPU)", "CUDA:1 (GPU)", "CUDA:2 (GPU)", "CUDA:3 (GPU)"])
                device_combo.setCurrentText(model_params.get('device', 'CUDA:0 (GPU)'))
                device_layout.addRow("运行设备:", device_combo)
                
                batch_spin = QtWidgets.QSpinBox()
                batch_spin.setRange(1, 128)
                batch_spin.setValue(model_params.get('batch_size', 16))
                device_layout.addRow("批处理大小:", batch_spin)
                
                workers_spin = QtWidgets.QSpinBox()
                workers_spin.setRange(1, 32)
                workers_spin.setValue(model_params.get('workers', 8))
                device_layout.addRow("工作线程数:", workers_spin)
                
                layout.addWidget(device_group)
                
                # 训练参数（如果适用）
                train_group = QtWidgets.QGroupBox("训练参数")
                train_layout = QtWidgets.QFormLayout(train_group)
                
                epochs_spin = QtWidgets.QSpinBox()
                epochs_spin.setRange(1, 10000)
                epochs_spin.setValue(model_params.get('epochs', 300))
                train_layout.addRow("训练轮数:", epochs_spin)
                
                blur_spin = QtWidgets.QSpinBox()
                blur_spin.setRange(0, 1000)
                blur_spin.setValue(model_params.get('blur_training', 100))
                train_layout.addRow("模糊训练:", blur_spin)
                
                layout.addWidget(train_group)
                
                # 描述
                desc_group = QtWidgets.QGroupBox("模型描述")
                desc_layout = QtWidgets.QVBoxLayout(desc_group)
                
                desc_edit = QtWidgets.QTextEdit()
                desc_edit.setPlainText(model_params.get('description', ''))
                desc_edit.setMaximumHeight(100)
                desc_layout.addWidget(desc_edit)
                
                layout.addWidget(desc_group)
                
                # 设置滚动区域内容
                scroll_area.setWidget(content_widget)
                
                # 主布局
                main_layout = QtWidgets.QVBoxLayout(dialog)
                main_layout.addWidget(scroll_area)
                
                # 按钮
                button_layout = QtWidgets.QHBoxLayout()
                cancel_btn = QtWidgets.QPushButton("取消")
                reset_btn = QtWidgets.QPushButton("重置")
                
                button_layout.addWidget(reset_btn)
                button_layout.addWidget(cancel_btn)
                main_layout.addLayout(button_layout)
                
                # 连接按钮事件
                def reset_settings():
                    # 重置所有设置到原始值
                    type_edit.setText(model_params.get('type', ''))
                    confidence_spin.setValue(model_params.get('confidence', 0.5))
                    iou_spin.setValue(model_params.get('iou', 0.45))
                    classes_spin.setValue(model_params.get('classes', 80))
                    input_edit.setText(model_params.get('input', '640x640'))
                    device_combo.setCurrentText(model_params.get('device', 'CUDA:0 (GPU)'))
                    batch_spin.setValue(model_params.get('batch_size', 16))
                    workers_spin.setValue(model_params.get('workers', 8))
                    epochs_spin.setValue(model_params.get('epochs', 300))
                    blur_spin.setValue(model_params.get('blur_training', 100))
                    desc_edit.setPlainText(model_params.get('description', ''))
                
                reset_btn.clicked.connect(reset_settings)
                cancel_btn.clicked.connect(dialog.reject)
                
                # 显示对话框
                dialog.exec_()
                
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "模型集页面未初始化")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"模型设置失败: {e}")
