# -*- coding: utf-8 -*-

"""
裁剪配置对话框

用于设置视频裁剪的保存路径和裁剪频率
可以独立运行测试，也可以被其他模块导入使用
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..icons import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, osp.join(osp.dirname(__file__), '..'))
    try:
        from icons import newIcon
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        def newIcon(icon): 
            return QtGui.QIcon()
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x

try:
    from database.config import get_project_root
except Exception:
    def get_project_root():
        return osp.abspath(osp.join(osp.dirname(__file__), '..', '..'))


DEFAULT_CROP_SAVE_DIR = osp.join(get_project_root(), 'database', 'Corp_picture')
os.makedirs(DEFAULT_CROP_SAVE_DIR, exist_ok=True)




class CropConfigDialog(QtWidgets.QDialog):
    """
    裁剪配置对话框
    
    功能：
    - 设置保存路径（文件夹选择）
    - 设置裁剪频率（每隔多少帧裁剪一次）
    - 设置文件名前缀
    - 设置图片格式
    """
    
    def __init__(self, parent=None, default_save_liquid_data_path=None, default_frequency=1):
        """
        Args:
            parent: 父窗口
            default_save_liquid_data_path: 默认保存路径
            default_frequency: 默认裁剪频率（每隔多少帧裁剪一次）
        """
        super(CropConfigDialog, self).__init__(parent)
        
        # 【强制修改】始终使用项目默认路径，忽略传入的参数
        # 这样可以确保图片始终保存在项目目录下
        self._save_liquid_data_path = DEFAULT_CROP_SAVE_DIR
        print(f"[CropConfigDialog] 强制使用默认路径: {DEFAULT_CROP_SAVE_DIR}")
        
        self._crop_frequency = default_frequency
        self._file_prefix = "frame"
        self._image_format = "jpg"
        
        self._initUI()
        self._connectSignals()
        self._loadSettings()
    
    def _initUI(self):
        """初始化UI"""
        self.setWindowTitle("裁剪配置")
        # 🔥 响应式对话框尺寸
        ResponsiveLayout.apply_to_widget(self, min_width=600, min_height=400)
        
        # 设置窗口图标
        self.setWindowIcon(newIcon("文件夹"))
        
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title_label = QtWidgets.QLabel("视频裁剪配置")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16pt;
                font-weight: bold;
                color: #0078d7;
                padding: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # === 保存路径设置 ===
        path_group = self._createPathGroup()
        main_layout.addWidget(path_group)
        
        # === 裁剪频率设置 ===
        frequency_group = self._createFrequencyGroup()
        main_layout.addWidget(frequency_group)
        
        # === 文件命名设置 ===
        naming_group = self._createNamingGroup()
        main_layout.addWidget(naming_group)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        # === 底部按钮 ===
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_cancel.setIcon(newIcon("关闭"))
        self.btn_cancel.setFixedSize(scale_w(100), scale_h(35))  # 🔥 响应式尺寸
        # 使用Qt默认样式
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_confirm = QtWidgets.QPushButton("确定")
        self.btn_confirm.setIcon(newIcon("完成"))
        self.btn_confirm.setFixedSize(scale_w(100), scale_h(35))  # 🔥 响应式尺寸
        # 使用Qt默认样式
        button_layout.addWidget(self.btn_confirm)
        
        main_layout.addLayout(button_layout)
        
        # 设置对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
    
    def _createPathGroup(self):
        """创建保存路径设置组"""
        group = QtWidgets.QGroupBox(" 保存路径")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        # 路径显示和浏览按钮
        path_layout = QtWidgets.QHBoxLayout()
        
        self.path_edit = QtWidgets.QLineEdit(self._save_liquid_data_path)
        self.path_edit.setPlaceholderText("选择保存裁剪图片的文件夹...")
        self.path_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
        """)
        path_layout.addWidget(self.path_edit)
        
        self.btn_browse = QtWidgets.QPushButton("浏览...")
        self.btn_browse.setIcon(newIcon("文件夹"))
        self.btn_browse.setFixedSize(scale_w(100), scale_h(35))  # 🔥 响应式尺寸
        # 使用Qt默认样式
        path_layout.addWidget(self.btn_browse)
        
        layout.addLayout(path_layout)
        
        # 路径说明
        path_hint = QtWidgets.QLabel(" 提示：裁剪后的图片将保存到此文件夹")
        path_hint.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        layout.addWidget(path_hint)
        
        return group
    
    def _createFrequencyGroup(self):
        """创建裁剪频率设置组"""
        group = QtWidgets.QGroupBox(" 裁剪频率")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        # 频率设置
        freq_layout = QtWidgets.QHBoxLayout()
        
        freq_label = QtWidgets.QLabel("每隔")
        freq_label.setStyleSheet("font-size: 11pt; font-weight: normal;")
        freq_layout.addWidget(freq_label)
        
        self.frequency_spinbox = QtWidgets.QSpinBox()
        self.frequency_spinbox.setRange(1, 1000)
        self.frequency_spinbox.setValue(self._crop_frequency)
        self.frequency_spinbox.setSuffix(" 帧")
        self.frequency_spinbox.setFixedWidth(scale_w(120))  # 🔥 响应式宽度
        self.frequency_spinbox.setStyleSheet("""
            QSpinBox {
                padding: 8px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: white;
                font-size: 11pt;
            }
            QSpinBox:focus {
                border-color: #0078d7;
            }
        """)
        freq_layout.addWidget(self.frequency_spinbox)
        
        freq_label2 = QtWidgets.QLabel("裁剪一次")
        freq_label2.setStyleSheet("font-size: 11pt; font-weight: normal;")
        freq_layout.addWidget(freq_label2)
        
        freq_layout.addStretch()
        
        layout.addLayout(freq_layout)
        
        # 快捷设置按钮
        quick_layout = QtWidgets.QHBoxLayout()
        quick_label = QtWidgets.QLabel("快捷设置：")
        quick_label.setStyleSheet("font-size: 9pt; font-weight: normal; color: #666;")
        quick_layout.addWidget(quick_label)
        
        for value, text in [(1, "每帧"), (5, "每5帧"), (10, "每10帧"), (30, "每30帧"), (60, "每60帧")]:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedSize(scale_w(70), scale_h(28))  # 🔥 响应式尺寸
            # 使用Qt默认样式
            btn.clicked.connect(lambda checked, v=value: self.frequency_spinbox.setValue(v))
            quick_layout.addWidget(btn)
        
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        # 频率说明
        freq_hint = QtWidgets.QLabel(" 提示：频率越小，裁剪的图片越多；频率为1表示裁剪每一帧")
        freq_hint.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        layout.addWidget(freq_hint)
        
        return group
    
    def _createNamingGroup(self):
        """创建文件命名设置组"""
        group = QtWidgets.QGroupBox(" 文件命名")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        # 文件名前缀
        prefix_layout = QtWidgets.QHBoxLayout()
        prefix_label = QtWidgets.QLabel("文件名前缀：")
        prefix_label.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        prefix_label.setStyleSheet("font-size: 10pt; font-weight: normal;")
        prefix_layout.addWidget(prefix_label)
        
        self.prefix_edit = QtWidgets.QLineEdit(self._file_prefix)
        self.prefix_edit.setPlaceholderText("输入文件名前缀，如: frame")
        self.prefix_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
        """)
        prefix_layout.addWidget(self.prefix_edit)
        
        layout.addLayout(prefix_layout)
        
        # 图片格式
        format_layout = QtWidgets.QHBoxLayout()
        format_label = QtWidgets.QLabel("图片格式：")
        format_label.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        format_label.setStyleSheet("font-size: 10pt; font-weight: normal;")
        format_layout.addWidget(format_label)
        
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["jpg", "png", "bmp", "tiff"])
        self.format_combo.setCurrentText(self._image_format)
        self.format_combo.setFixedWidth(scale_w(150))  # 🔥 响应式宽度
        # 使用Qt默认样式，不设置复杂的自定义样式
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        
        layout.addLayout(format_layout)
        
        # 命名示例
        naming_hint = QtWidgets.QLabel(" 文件命名示例：文件_0001.jpg, 文件_0002.jpg, ...")
        naming_hint.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        layout.addWidget(naming_hint)
        
        return group
    
    def _connectSignals(self):
        """连接信号槽"""
        self.btn_browse.clicked.connect(self._onBrowse)
        self.btn_confirm.clicked.connect(self._onConfirm)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _loadSettings(self):
        """加载上次的设置（从QSettings）"""
        try:
            settings = QtCore.QSettings("Detection", "CropConfigDialog")
            
            # 【强制修改】清除旧的保存路径设置，不再记住保存路径
            # 检查是否有旧设置
            old_path = settings.value("save_liquid_data_path", "")
            if old_path:
                print(f"[CropConfigDialog] 检测到旧的保存路径: {old_path}")
                settings.remove("save_liquid_data_path")
                print(f"[CropConfigDialog] 已清除旧的保存路径设置")
            
            # 强制使用项目默认路径
            # 这样可以确保图片始终保存在项目目录下，避免用户找不到图片
            self.path_edit.setText(self._save_liquid_data_path)
            print(f"[CropConfigDialog] 对话框路径已设置为: {self._save_liquid_data_path}")
            print(f"[CropConfigDialog] 文本框内容: {self.path_edit.text()}")
            
            saved_freq = settings.value("crop_frequency", 1)
            try:
                self.frequency_spinbox.setValue(int(saved_freq))
            except:
                pass
            
            saved_prefix = settings.value("file_prefix", "frame")
            if saved_prefix:
                self.prefix_edit.setText(saved_prefix)
            
            saved_format = settings.value("image_format", "jpg")
            if saved_format:
                self.format_combo.setCurrentText(saved_format)
                
        except Exception as e:
            pass
    
    def _saveSettings(self):
        """保存当前设置"""
        try:
            settings = QtCore.QSettings("Detection", "CropConfigDialog")
            # 【修改】不再保存路径，每次都使用默认路径
            # settings.setValue("save_liquid_data_path", self.path_edit.text())
            settings.setValue("crop_frequency", self.frequency_spinbox.value())
            settings.setValue("file_prefix", self.prefix_edit.text())
            settings.setValue("image_format", self.format_combo.currentText())
        except Exception as e:
            pass
    
    def _onBrowse(self):
        """浏览文件夹"""
        current_path = self.path_edit.text()
        if not current_path or not osp.exists(current_path):
            current_path = osp.expanduser("~")
        
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择保存文件夹", current_path
        )
        
        if folder:
            self.path_edit.setText(folder)
            self._save_liquid_data_path = folder
    
    def _onConfirm(self):
        """确认按钮点击"""
        # 验证路径
        save_liquid_data_path = self.path_edit.text().strip()
        if not save_liquid_data_path:
            QtWidgets.QMessageBox.warning(
                self, "警告", "请选择保存路径"
            )
            return
        
        # 验证文件名前缀
        prefix = self.prefix_edit.text().strip()
        if not prefix:
            QtWidgets.QMessageBox.warning(
                self, "警告", "请输入文件名前缀"
            )
            return
        
        # 创建保存目录（如果不存在）
        try:
            os.makedirs(save_liquid_data_path, exist_ok=True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", f"无法创建保存目录:\n{e}"
            )
            return
        
        # 保存设置
        self._saveSettings()
        
        # 关闭对话框
        self.accept()
    
    # ========== 公共方法 ==========
    
    def getConfig(self):
        """
        获取配置信息
        
        Returns:
            dict: 配置字典，包含以下键：
                - save_liquid_data_path: 保存路径
                - crop_frequency: 裁剪频率
                - file_prefix: 文件名前缀
                - image_format: 图片格式
        """
        # 【强制修改】始终返回默认路径，忽略文本框内容
        # 确保图片保存在项目目录下
        config = {
            'save_liquid_data_path': DEFAULT_CROP_SAVE_DIR,  # 强制使用默认路径
            'crop_frequency': self.frequency_spinbox.value(),
            'file_prefix': self.prefix_edit.text().strip(),
            'image_format': self.format_combo.currentText()
        }
        print(f"[CropConfigDialog] getConfig返回的保存路径: {config['save_liquid_data_path']}")
        return config
    
    def setConfig(self, config):
        """
        设置配置信息
        
        Args:
            config (dict): 配置字典
        """
        if 'save_liquid_data_path' in config:
            self.path_edit.setText(config['save_liquid_data_path'])
        
        if 'crop_frequency' in config:
            self.frequency_spinbox.setValue(config['crop_frequency'])
        
        if 'file_prefix' in config:
            self.prefix_edit.setText(config['file_prefix'])
        
        if 'image_format' in config:
            self.format_combo.setCurrentText(config['image_format'])


if __name__ == "__main__":
    """独立运行测试"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建对话框
    dialog = CropConfigDialog(
        default_save_liquid_data_path=osp.join(osp.expanduser("~"), "crop_test"),
        default_frequency=10
    )
    
    mission_result = dialog.exec_()
    
    sys.exit(0)

