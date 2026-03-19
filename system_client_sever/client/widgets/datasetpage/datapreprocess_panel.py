# -*- coding: utf-8 -*-

"""
数据预处理面板

三栏布局：
- 左侧：目录管理（可新增/删除文件夹）
- 中间：视频预览和区域裁剪控制
- 右侧：裁剪图片实时预览
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..style_manager import newIcon, TextButtonStyleManager, BackgroundStyleManager, FontManager, DialogManager
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
    from .crop_config_dialog import CropConfigDialog
    from .crop_preview_panel import CropPreviewPanel
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, osp.join(osp.dirname(__file__), '..'))
    try:
        from style_manager import newIcon, TextButtonStyleManager, BackgroundStyleManager, FontManager, DialogManager
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
        from crop_config_dialog import CropConfigDialog
        from crop_preview_panel import CropPreviewPanel
    except ImportError:
        def newIcon(icon): 
            return QtGui.QIcon()
        TextButtonStyleManager = None
        BackgroundStyleManager = None
        FontManager = None
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x
        CropConfigDialog = None
        CropPreviewPanel = None

# 导入回收站工具
try:
    from utils.recycle_bin_utils import delete_file_to_recycle_bin, delete_folder_to_recycle_bin
except ImportError:
    delete_file_to_recycle_bin = None
    delete_folder_to_recycle_bin = None

try:
    from database.config import get_project_root
except Exception:
    def get_project_root():
        return osp.abspath(osp.join(osp.dirname(__file__), '..', '..'))


class DataPreprocessPanel(QtWidgets.QWidget):
    """
    数据预处理面板
    
    三栏布局：
    - 左侧：目录管理（文件夹列表、新增/删除）
    - 中间：视频预览和裁剪控制（视频播放、画框裁剪）
    - 右侧：裁剪图片实时预览（多区域图片展示）
    """
    
    # 自定义信号
    folderSelected = QtCore.Signal(str)         # 文件夹被选中
    folderAdded = QtCore.Signal(str)            # 文件夹被添加
    folderDeleted = QtCore.Signal(str)          # 文件夹被删除
    videoSelected = QtCore.Signal(str)          # 视频被选中
    videoRenamed = QtCore.Signal(str, str)      # 视频被重命名 (old_path, new_path)
    cropStarted = QtCore.Signal(dict)           # 开始裁剪（携带配置）
    
    def __init__(self, parent=None, root_path=None):
        """
        Args:
            parent: 父窗口
            root_path: 根目录路径（默认为项目 database/data，与数据采集面板共用）
        """
        super(DataPreprocessPanel, self).__init__(parent)
        self._parent = parent
        
        # Handler 引用（由 DataPreprocessHandler 设置）
        self._handler = None
        
        # 设置根目录（与数据采集面板共用）
        if root_path is None:
            project_root = get_project_root()
            self._root_path = osp.join(project_root, 'database', 'data')
        else:
            self._root_path = root_path
        
        # 确保根目录存在
        os.makedirs(self._root_path, exist_ok=True)
        
        # 当前选中的文件夹和视频
        self._current_folder = None
        self._current_video = None
        
        # 视频播放相关
        self._video_playing = False
        self._video_timer = None
        self._video_capture = None
        
        self._initUI()
        self._connectSignals()
        self._loadFolders()
    
    def _showWarning(self, title, message):
        """显示警告对话框"""
        DialogManager.show_warning(self, title, message)
    
    def _showInformation(self, title, message):
        """显示信息对话框"""
        DialogManager.show_information(self, title, message)
    
    def _showCritical(self, title, message):
        """显示错误对话框"""
        DialogManager.show_critical(self, title, message)
    
    def _showQuestion(self, title, message):
        """显示询问对话框"""
        return DialogManager.show_question(self, title, message)
    
    def _showQuestionWarning(self, title, message):
        """显示警告询问对话框（用于删除确认等危险操作）"""
        return DialogManager.show_question_warning(self, title, message)
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QHBoxLayout(self)
        ResponsiveLayout.apply_to_layout(main_layout, base_spacing=0, base_margins=0)
        
        # === 左侧：目录管理面板 ===
        self.left_panel = self._createLeftPanel()
        self.left_panel.setMaximumWidth(scale_w(200))  # 🔥 响应式左侧最大宽度
        main_layout.addWidget(self.left_panel, stretch=0)
        
        # === 中间：视频预览和控制面板 ===
        self.middle_panel = self._createMiddlePanel()
        main_layout.addWidget(self.middle_panel, stretch=1)
        
        # === 中间和右侧之间的分割线 ===
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setLineWidth(1)
        separator.setStyleSheet("color: #c0c0c0;")
        main_layout.addWidget(separator, stretch=0)
        
        # === 右侧：裁剪图片预览面板 ===
        self.crop_preview_panel = self._createCropPreviewPanel()
        # 🔥 响应式右侧宽度
        ResponsiveLayout.apply_to_widget(self.crop_preview_panel, min_width=300, max_width=300)
        main_layout.addWidget(self.crop_preview_panel, stretch=0)
    
    def _createLeftPanel(self):
        """创建左侧目录管理面板"""
        panel = QtWidgets.QWidget()
        
        # 应用统一背景管理
        if BackgroundStyleManager:
            background_style = BackgroundStyleManager.getBackgroundStyle()
            panel.setStyleSheet(f"QWidget {{ {background_style} }}")
        
        layout = QtWidgets.QVBoxLayout(panel)
        ResponsiveLayout.apply_to_layout(layout, base_spacing=5, base_margins=5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("数据预处理")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 根目录显示（已删除，与数据采集界面一致）
        # root_info = QtWidgets.QLabel(f"根目录: {self._root_path}")
        # root_info.setStyleSheet("color: #666; font-size: 9pt;")
        # root_info.setWordWrap(True)
        # layout.addWidget(root_info)
        
        # 文件夹列表
        self.folder_list = QtWidgets.QListWidget()
        self.folder_list.setAlternatingRowColors(True)
        self.folder_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #c0c0c0;
                background-color: white;
                alternate-background-color: #f5f5f5;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        # 启用右键菜单
        self.folder_list.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.folder_list)
        
        # 统计信息
        self.lbl_folder_stats = QtWidgets.QLabel("文件夹数: 0")
        self.lbl_folder_stats.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.lbl_folder_stats)
        
        # 操作按钮组
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_add_folder = QtWidgets.QPushButton("新增文件夹")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(self.btn_add_folder, "新增文件夹")
        self.btn_add_folder.setVisible(False)
        button_layout.addWidget(self.btn_add_folder)
        
        self.btn_delete_folder = QtWidgets.QPushButton("删除文件夹")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(self.btn_delete_folder, "删除文件夹")
        self.btn_delete_folder.setVisible(False)
        button_layout.addWidget(self.btn_delete_folder)
        
        layout.addLayout(button_layout)
        
        return panel
    
    def _createMiddlePanel(self):
        """创建中间视频预览和控制面板"""
        panel = QtWidgets.QWidget()
        
        # 应用统一背景管理
        if BackgroundStyleManager:
            background_style = BackgroundStyleManager.getBackgroundStyle()
            panel.setStyleSheet(f"QWidget {{ {background_style} }}")
        
        layout = QtWidgets.QVBoxLayout(panel)
        ResponsiveLayout.apply_to_layout(layout, base_spacing=5, base_margins=5)
        
        # 标题栏和控制按钮
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("视频预览")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 区域裁剪按钮
        self.btn_crop = QtWidgets.QPushButton("区域裁剪")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(self.btn_crop, "区域裁剪")
        self.btn_crop.setEnabled(False)  # 初始禁用，选择视频后启用
        self.btn_crop.setVisible(False)  # 隐藏按钮
        title_layout.addWidget(self.btn_crop)
        
        layout.addLayout(title_layout)
        
        # 当前文件夹信息
        self.lbl_current_folder = QtWidgets.QLabel("未选择文件夹")
        self.lbl_current_folder.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.lbl_current_folder)
        
        # === 内容区域：左右布局（左侧视频网格 + 右侧视频预览） ===
        content_layout = QtWidgets.QHBoxLayout()
        from ..responsive_layout import scale_spacing
        content_layout.setSpacing(scale_spacing(10))
        
        # 左侧：视频网格显示区域（与数据采集界面样式一致）
        self.video_grid = QtWidgets.QListWidget()
        self.video_grid.setViewMode(QtWidgets.QListWidget.IconMode)  # 图标模式
        self.video_grid.setIconSize(QtCore.QSize(100, 75))  # 中等图标尺寸
        self.video_grid.setGridSize(QtCore.QSize(160, 130))  # 增大网格尺寸以显示完整文件名
        self.video_grid.setResizeMode(QtWidgets.QListWidget.Adjust)  # 自动调整
        self.video_grid.setMovement(QtWidgets.QListWidget.Static)  # 固定位置
        from ..responsive_layout import scale_spacing
        self.video_grid.setSpacing(scale_spacing(8))
        self.video_grid.setWordWrap(True)  # 文字换行
        self.video_grid.setStyleSheet("""
            QListWidget {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QListWidget::item {
                border: 2px solid transparent;
                border-radius: 5px;
                background-color: white;
                padding: 5px;
                text-align: center;
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 2px solid #0078d7;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                border: 2px solid #c0c0c0;
            }
        """)
        # 启用右键菜单
        self.video_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        content_layout.addWidget(self.video_grid, stretch=1)
        
        # 右侧：视频预览区域
        preview_container = QtWidgets.QWidget()
        preview_layout = QtWidgets.QVBoxLayout(preview_container)
        ResponsiveLayout.apply_to_layout(preview_layout, base_spacing=5, base_margins=0)
        content_layout.addWidget(preview_container, stretch=1)
        
        # === 功能说明框 ===

        instruction_container = QtWidgets.QWidget()
        instruction_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        instruction_container.setMaximumHeight(scale_h(150))  # 🔥 响应式高度
        
        instruction_layout = QtWidgets.QVBoxLayout(instruction_container)
        ResponsiveLayout.apply_to_layout(instruction_layout, base_spacing=0, base_margins=8)
        
        # 内容标签（删除标题）
        instruction_label = QtWidgets.QLabel()
        instruction_label.setText(
            "操作说明\n"
            "• 鼠标放置画面上即可绘制区域，最多可绘制三个区域\n"
            "• 按住鼠标右键拖拽绘制矩形框\n"
            "• 不同区域用不同颜色标识\n"
            "• 对裁剪区域右键可删除当前区域，按键盘R键可重置"
        )
        instruction_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #333; line-height: 1.6;")
        instruction_layout.addWidget(instruction_label)
        
        preview_layout.addWidget(instruction_container, stretch=0)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(instruction_label)
        
        # 保存引用以便后续更新
        self.instruction_label = instruction_label
        
        # 视频预览框容器 - 只保留最外层浅灰色边框，删去内部白色边框
        video_preview_container = QtWidgets.QWidget()
        video_preview_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 0px;
            }
        """)
        
        video_preview_layout = QtWidgets.QVBoxLayout(video_preview_container)
        self.video_preview = QtWidgets.QLabel()
        self.video_preview.setMinimumSize(scale_w(400), scale_h(320))
        self.video_preview.setStyleSheet("background-color: black; border: none;")
        self.video_preview.setAlignment(Qt.AlignCenter)
        self.video_preview.setText("请选择视频文件")
        
        # 🔥 将视频预览标签添加到容器布局中
        video_preview_layout.addWidget(self.video_preview)

        # 路径标签宽度: 70px
        preview_layout.addWidget(video_preview_container, stretch=1)  # 允许拉伸填充空间
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.video_preview)
        
        # === 裁剪配置面板（嵌入式） ===
        crop_config_widget = self._createCropConfigPanel()
        preview_layout.addWidget(crop_config_widget, stretch=0)  # 不拉伸，保持原有高度
        
        # 视频控制按钮（已集成到视频画面中，这里保留但隐藏以保持兼容性）
        video_control_layout = QtWidgets.QHBoxLayout()
        from ..responsive_layout import scale_spacing
        video_control_layout.setSpacing(scale_spacing(5))
        
        self.btn_play = QtWidgets.QPushButton("播放")
        self.btn_play.setIcon(newIcon("开始"))
        self.btn_play.setEnabled(False)
        self.btn_play.setVisible(False)  # 隐藏按钮
        video_control_layout.addWidget(self.btn_play)
        
        self.btn_pause = QtWidgets.QPushButton("暂停")
        self.btn_pause.setIcon(newIcon("停止1"))
        self.btn_pause.setEnabled(False)
        self.btn_pause.setVisible(False)  # 隐藏按钮
        video_control_layout.addWidget(self.btn_pause)
        
        self.btn_stop = QtWidgets.QPushButton("停止")
        self.btn_stop.setIcon(newIcon("关闭"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setVisible(False)  # 隐藏按钮
        video_control_layout.addWidget(self.btn_stop)
        
        video_control_layout.addStretch()
        # 不再添加控制按钮布局到预览布局中
        # preview_layout.addLayout(video_control_layout)
        
        # 将内容布局添加到主布局
        layout.addLayout(content_layout, stretch=1)
        
        # 底部统计信息框容器 - 无背景无边框
        stats_container = QtWidgets.QWidget()
        stats_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        
        stats_layout = QtWidgets.QHBoxLayout(stats_container)
        ResponsiveLayout.apply_to_layout(stats_layout, base_spacing=10, base_margins=8)
        
        self.lbl_video_stats = QtWidgets.QLabel("视频数: 0")
        stats_layout.addWidget(self.lbl_video_stats)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.lbl_video_stats)
        
        stats_layout.addStretch()
        
        self.lbl_current_video = QtWidgets.QLabel("未选择视频")
        stats_layout.addWidget(self.lbl_current_video)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.lbl_current_video)
        
        layout.addWidget(stats_container)
        
        return panel
    
    def _createCropConfigPanel(self):
        """创建裁剪配置面板（嵌入式，不是对话框）"""
        panel = QtWidgets.QWidget()
        
        # 应用统一背景管理，删除CSS样式表
        if BackgroundStyleManager:
            background_style = BackgroundStyleManager.getBackgroundStyle()
            panel.setStyleSheet(f"QWidget {{ {background_style} }}")
        
        main_layout = QtWidgets.QVBoxLayout(panel)
        ResponsiveLayout.apply_to_layout(main_layout, base_spacing=8, base_margins=10)
        
        # === 保存路径 (隐藏) ===
        path_layout = QtWidgets.QHBoxLayout()
        path_label = QtWidgets.QLabel("保存路径:")
        path_label.setFixedWidth(scale_w(70))  # 🔥 响应式宽度
        path_label.setVisible(False)  # 隐藏标签
        path_layout.addWidget(path_label)
        
        # 删除CSS样式表，改为纯控件方式
        self.crop_path_edit = QtWidgets.QLineEdit()
        self.crop_path_edit.setPlaceholderText("选择保存文件夹...")
        self.crop_path_edit.setVisible(False)  # 隐藏输入框
        path_layout.addWidget(self.crop_path_edit)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.crop_path_edit)
        
        self.btn_browse_crop = QtWidgets.QPushButton("浏览")
        self.btn_browse_crop.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        self.btn_browse_crop.setVisible(False)  # 隐藏按钮
        path_layout.addWidget(self.btn_browse_crop)
        
        # 不添加到主布局，完全隐藏
        # main_layout.addLayout(path_layout)
        
        # === 裁剪频率 ===
        freq_layout = QtWidgets.QHBoxLayout()
        freq_label = QtWidgets.QLabel("裁剪频率:")
        freq_label.setFixedWidth(scale_w(70))  # 🔥 响应式宽度
        freq_layout.addWidget(freq_label)
        
        self.crop_frequency_spinbox = QtWidgets.QSpinBox()
        self.crop_frequency_spinbox.setRange(1, 1000)
        self.crop_frequency_spinbox.setValue(1)
        self.crop_frequency_spinbox.setSuffix(" 帧")
        self.crop_frequency_spinbox.setFixedWidth(scale_w(80))  # 🔥 响应式宽度
        freq_layout.addWidget(self.crop_frequency_spinbox)
        
        # 快捷按钮 - 删除CSS样式表，改为纯控件方式 + 响应式布局
        for value, text in [(1, "每帧"), (5, "每5帧"), (10, "每10帧"), (30, "每30帧"), (60, "每60帧")]:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedSize(scale_w(60), scale_h(28))  # 🔥 响应式尺寸
            btn.clicked.connect(lambda checked, v=value: self.crop_frequency_spinbox.setValue(v))
            freq_layout.addWidget(btn)
            
            # 应用字体管理器
            if FontManager:
                FontManager.applyToWidget(btn)
        
        freq_layout.addStretch()
        main_layout.addLayout(freq_layout)
        
        # === 文件命名 ===
        naming_layout = QtWidgets.QHBoxLayout()
        naming_label = QtWidgets.QLabel("文件命名:")
        naming_label.setFixedWidth(scale_w(70))  # 🔥 响应式宽度
        naming_layout.addWidget(naming_label)
        
        self.crop_prefix_edit = QtWidgets.QLineEdit("frame")
        self.crop_prefix_edit.setPlaceholderText("文件名前缀")
        self.crop_prefix_edit.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        naming_layout.addWidget(self.crop_prefix_edit)
        
        naming_layout.addWidget(QtWidgets.QLabel("格式:"))
        
        self.crop_format_combo = QtWidgets.QComboBox()
        self.crop_format_combo.addItems(["jpg", "png", "bmp"])
        self.crop_format_combo.setFixedWidth(scale_w(80))  # 🔥 响应式宽度
        naming_layout.addWidget(self.crop_format_combo)
        
        naming_layout.addStretch()
        main_layout.addLayout(naming_layout)
        
        # === 按钮布局：左侧开始裁剪，右侧打开文件夹 ===
        button_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：开始裁剪按钮 - 删除CSS样式表，改为纯控件方式 + 响应式布局
        self.btn_start_crop = QtWidgets.QPushButton("开始裁剪")
        self.btn_start_crop.setFixedSize(scale_w(100), scale_h(32))  # 🔥 响应式尺寸
        self.btn_start_crop.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.btn_start_crop)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.btn_start_crop)
        
        # 中间空白
        button_layout.addStretch()
        
        # 右侧：打开文件夹按钮 - 删除CSS样式表，改为纯控件方式 + 响应式布局
        self.btn_open_crop_folder = QtWidgets.QPushButton("打开文件夹")
        self.btn_open_crop_folder.setFixedSize(scale_w(100), scale_h(32))  # 🔥 响应式尺寸
        button_layout.addWidget(self.btn_open_crop_folder)
        
        # 应用字体管理器
        if FontManager:
            FontManager.applyToWidget(self.btn_open_crop_folder)
        
        main_layout.addLayout(button_layout)

        self._loadCropConfig()
        
        return panel
    
    def _getDefaultCropFolder(self):
        """获取裁剪结果默认保存路径"""
        default_path = osp.join(get_project_root(), 'database', 'Corp_picture')
        os.makedirs(default_path, exist_ok=True)
        return default_path

    def _loadCropConfig(self):
        """加载裁剪配置"""
        try:
            settings = QtCore.QSettings("Detection", "CropConfig")
            saved_path = settings.value("save_path", "")
            if saved_path:
                self.crop_path_edit.setText(saved_path)
            else:
                self.crop_path_edit.setText(self._getDefaultCropFolder())
            
            saved_freq = settings.value("frequency", 1)
            try:
                self.crop_frequency_spinbox.setValue(int(saved_freq))
            except:
                pass
            
            saved_prefix = settings.value("prefix", "frame")
            if saved_prefix:
                self.crop_prefix_edit.setText(saved_prefix)
            
            saved_format = settings.value("format", "jpg")
            if saved_format:
                self.crop_format_combo.setCurrentText(saved_format)
        except Exception as e:
            pass
    
    def _saveCropConfig(self):
        """保存裁剪配置"""
        try:
            settings = QtCore.QSettings("Detection", "CropConfig")
            settings.setValue("save_path", self.crop_path_edit.text())
            settings.setValue("frequency", self.crop_frequency_spinbox.value())
            settings.setValue("prefix", self.crop_prefix_edit.text())
            settings.setValue("format", self.crop_format_combo.currentText())
        except Exception as e:
            pass
    
    def getCropConfig(self):
        """获取裁剪配置"""
        # 【强制修改】始终使用项目默认路径，忽略文本框内容
        # 确保图片保存在项目目录下
        default_path = self._getDefaultCropFolder()
        config = {
            'save_liquid_data_path': default_path,  # 强制使用默认路径
            'crop_frequency': self.crop_frequency_spinbox.value(),
            'file_prefix': self.crop_prefix_edit.text().strip(),
            'image_format': self.crop_format_combo.currentText()
        }
        print(f"[DataPreprocessPanel] getCropConfig返回的保存路径: {config['save_liquid_data_path']}")
        return config
    
    def _createCropPreviewPanel(self):
        """创建右侧裁剪图片预览面板"""
        if CropPreviewPanel is None:
            # 如果导入失败，返回一个占位面板
            placeholder = QtWidgets.QWidget()
            
            # 应用统一背景管理
            if BackgroundStyleManager:
                background_style = BackgroundStyleManager.getBackgroundStyle()
                placeholder.setStyleSheet(f"QWidget {{ {background_style} }}")
            
            layout = QtWidgets.QVBoxLayout(placeholder)
            label = QtWidgets.QLabel("裁剪预览面板\n（模块未加载）")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #999; font-size: 12pt;")
            layout.addWidget(label)
            return placeholder
        
        # 创建裁剪预览面板实例
        preview_panel = CropPreviewPanel(parent=self)
        
        # 设置初始提示
        preview_panel.lbl_save_liquid_data_path.setText("等待裁剪任务开始...")
        
        return preview_panel
    
    def _connectSignals(self):
        """连接信号槽"""
        # 左侧面板
        self.folder_list.itemClicked.connect(self._onFolderClicked)
        self.folder_list.itemDoubleClicked.connect(self._onFolderDoubleClicked)
        self.folder_list.customContextMenuRequested.connect(self._onFolderListContextMenu)
        self.btn_add_folder.clicked.connect(self._onAddFolder)
        self.btn_delete_folder.clicked.connect(self._onDeleteFolder)
        
        # 右侧面板
        self.video_grid.itemClicked.connect(self._onVideoClicked)
        self.video_grid.itemDoubleClicked.connect(self._onVideoDoubleClicked)
        self.video_grid.customContextMenuRequested.connect(self._onVideoGridContextMenu)
        self.btn_crop.clicked.connect(self._onCropClicked)
        
        # 视频控制按钮
        self.btn_play.clicked.connect(self._onPlayVideo)
        self.btn_pause.clicked.connect(self._onPauseVideo)
        self.btn_stop.clicked.connect(self._onStopVideo)
        
        # 裁剪配置面板
        self.btn_browse_crop.clicked.connect(self._onBrowseCropPath)
        self.btn_start_crop.clicked.connect(self._onStartCrop)
        self.btn_open_crop_folder.clicked.connect(self._onOpenCropFolder)
        self.crop_path_edit.textChanged.connect(self._saveCropConfig)
        self.crop_frequency_spinbox.valueChanged.connect(self._saveCropConfig)
        self.crop_prefix_edit.textChanged.connect(self._saveCropConfig)
        self.crop_format_combo.currentTextChanged.connect(self._saveCropConfig)
    
    # ========== 公共方法 ==========
    
    def setRootPath(self, path):
        """设置根目录"""
        if osp.exists(path) and osp.isdir(path):
            self._root_path = path
            self._loadFolders()
            pass
            return True
        else:
            pass
            return False
    
    def getRootPath(self):
        """获取根目录"""
        return self._root_path
    
    def getCurrentFolder(self):
        """获取当前选中的文件夹"""
        return self._current_folder
    
    def getCurrentVideo(self):
        """获取当前选中的视频"""
        return self._current_video
    
    def getCropPreviewPanel(self):
        """获取裁剪预览面板"""
        return self.crop_preview_panel
    
    def refreshFolders(self):
        """刷新文件夹列表"""
        self._loadFolders()
    
    def refreshVideos(self):
        """刷新视频列表"""
        if self._current_folder:
            self._loadVideos(self._current_folder)
    
    # ========== 私有方法 ==========
    
    def _loadFolders(self):
        """加载文件夹列表"""
        self.folder_list.clear()
        
        if not osp.exists(self._root_path):
            return
        
        # 获取所有子文件夹
        try:
            folders = [f for f in os.listdir(self._root_path) 
                      if osp.isdir(osp.join(self._root_path, f))]
            folders.sort()
            
            # 添加到列表
            for folder in folders:
                item = QtWidgets.QListWidgetItem(self.folder_list)
                item.setText(f" {folder}")
                item.setData(Qt.UserRole, folder)  # 存储文件夹名称
                
                # 设置图标
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon)
                item.setIcon(icon)
            
            # 更新统计
            self.lbl_folder_stats.setText(f"文件夹数: {len(folders)}")
            
            pass
            
        except Exception as e:
            pass
    
    def _loadVideos(self, folder_name):
        """加载视频网格"""
        self.video_grid.clear()
        
        folder_path = osp.join(self._root_path, folder_name)
        
        if not osp.exists(folder_path):
            return
        
        try:
            # 支持的视频格式
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.mpg', '.mpeg']
            
            # 获取所有文件
            all_files = os.listdir(folder_path)
            
            # 获取所有视频文件
            files = [f for f in all_files
                    if osp.isfile(osp.join(folder_path, f)) and
                    osp.splitext(f)[1].lower() in video_extensions]
            files.sort()
            
            # 添加到网格
            for file in files:
                item = QtWidgets.QListWidgetItem(self.video_grid)
                file_path = osp.join(folder_path, file)
                
                # 显示文件名（不带路径）
                # 如果文件名太长，截断显示
                display_name = file
                if len(display_name) > 20:
                    display_name = display_name[:17] + "..."
                
                item.setText(f"\n{display_name}")
                item.setData(Qt.UserRole, file_path)  # 存储完整路径
                item.setToolTip(file)  # 完整文件名作为提示
                
                # 生成视频第一帧缩略图
                thumbnail = self._generateVideoThumbnail(file_path)
                if thumbnail:
                    item.setIcon(QtGui.QIcon(thumbnail))
                else:
                    # 如果缩略图生成失败，使用系统标准图标
                    icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
                    item.setIcon(icon)
                
                # 设置文本居中对齐
                item.setTextAlignment(Qt.AlignCenter)
            
            # 更新统计
            self.lbl_video_stats.setText(f"视频数: {len(files)}")
            
            if len(files) == 0:
                pass
            
        except Exception as e:
            pass
    
    def _generateVideoThumbnail(self, video_path):
        """生成视频缩略图（提取第一帧）"""
        try:
            import cv2
            
            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return None
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None
            
            # 转换颜色空间 BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 转换为 QImage
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 创建 QPixmap 并缩放到缩略图尺寸
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                160, 120,  # 与 setIconSize 设置的尺寸一致
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            return scaled_pixmap
            
        except Exception as e:
            return None
    
    # ========== 槽函数 ==========
    
    def _onFolderClicked(self, item):
        """文件夹被点击"""
        folder_name = item.data(Qt.UserRole)
        self._current_folder = folder_name
        
        # 更新显示
        self.lbl_current_folder.setText(f"当前文件夹: {folder_name}")
        
        # 加载视频网格
        self._loadVideos(folder_name)
        
        # 清空当前选中的视频
        self._current_video = None
        self.lbl_current_video.setText("未选择视频")
        self.btn_crop.setEnabled(False)
        
        # 发射信号
        folder_path = osp.join(self._root_path, folder_name)
        self.folderSelected.emit(folder_path)
    
    def _onFolderDoubleClicked(self, item):
        """需求调整：双击目录不执行任何操作"""
        return
    
    def _onAddFolder(self):
        """新增文件夹"""
        # 创建自定义对话框（完全控制按钮和窗口标志）
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("新增文件夹")
        
        # 移除帮助按钮（问号按钮）
        old_flags = dialog.windowFlags()
        new_flags = old_flags & ~QtCore.Qt.WindowContextHelpButtonHint
        dialog.setWindowFlags(new_flags)
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout()
        
        # 添加标签
        label = QtWidgets.QLabel("请输入文件夹名称:")
        layout.addWidget(label)
        
        # 添加输入框
        input_edit = QtWidgets.QLineEdit()
        layout.addWidget(input_edit)
        
        # 创建按钮布局
        button_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("确定")
        cancel_btn = QtWidgets.QPushButton("取消")
        
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # 连接按钮信号
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # 设置输入框焦点
        input_edit.setFocus()
        
        # 显示对话框
        ok = dialog.exec_()
        text = input_edit.text()
        
        if ok and text:
            folder_path = osp.join(self._root_path, text)
            
            # 检查是否已存在
            if osp.exists(folder_path):
                self._showWarning("警告", f"文件夹 '{text}' 已存在")
                return
            
            # 创建文件夹
            try:
                os.makedirs(folder_path)
                pass
                
                # 刷新列表
                self._loadFolders()
                
                # 发射信号
                self.folderAdded.emit(folder_path)
                
                QtWidgets.QMessageBox.information(
                    self, "成功", f"文件夹 '{text}' 创建成功"
                )
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "错误", f"创建文件夹失败: {e}"
                )
                pass
    
    def _onDeleteFolder(self):
        """删除文件夹"""
        current_item = self.folder_list.currentItem()
        
        if not current_item:
            self._showWarning("警告", "请先选择要删除的文件夹")
            return
        
        folder_name = current_item.data(Qt.UserRole)
        folder_path = osp.join(self._root_path, folder_name)
        
        # 统计文件夹内的文件信息
        video_count = 0
        image_count = 0
        try:
            if osp.exists(folder_path):
                for file_name in os.listdir(folder_path):
                    file_path = osp.join(folder_path, file_name)
                    if osp.isfile(file_path):
                        ext = osp.splitext(file_name)[1].lower()
                        if ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']:
                            video_count += 1
                        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']:
                            image_count += 1
        except Exception as e:
            pass
        
        # 构建文件信息提示
        file_info = []
        if video_count > 0:
            file_info.append(f"{video_count}个视频文件")
        if image_count > 0:
            file_info.append(f"{image_count}个图片文件")
        
        if file_info:
            file_info_text = "、".join(file_info)
            message = f"确定要删除文件夹 '{folder_name}' 吗？\n\n文件夹内含有{file_info_text}\n\n所有内容将被移动到回收站"
        else:
            message = f"确定要删除文件夹 '{folder_name}' 吗？\n\n文件夹为空\n\n将被移动到回收站"
        
        # 确认删除 - 使用警告图标的统一对话框
        if self._showQuestionWarning("确认删除", message):
            try:
                # 使用Windows回收站删除
                if delete_folder_to_recycle_bin:
                    delete_folder_to_recycle_bin(folder_path)
                else:
                    raise ImportError("回收站工具未导入")
                
                # 清空右侧内容
                if self._current_folder == folder_name:
                    self._current_folder = None
                    self._current_video = None
                    self.lbl_current_folder.setText("未选择文件夹")
                    self.video_grid.clear()
                    self.lbl_video_stats.setText("视频数: 0")
                    self.lbl_current_video.setText("未选择视频")
                    self.btn_crop.setEnabled(False)
                
                # 刷新列表
                self._loadFolders()
                
                # 发射信号
                self.folderDeleted.emit(folder_path)
                
               
                
            except Exception as e:
                self._showCritical("错误", f"删除文件夹失败: {e}")
    
    def _onFolderListContextMenu(self, position):
        """显示文件夹列表的右键菜单"""
        # 获取点击位置的项
        item = self.folder_list.itemAt(position)
        
        # 创建右键菜单
        menu = QtWidgets.QMenu(self)
        
        if item:
            # 需求调整：不再提供右键删除入口，直接返回
            return
        else:
            # 在空白处右键：显示新建和刷新选项
            action_new_folder = menu.addAction("新建文件夹")
            action_refresh = menu.addAction("刷新列表")
            
            # 显示菜单并获取选择的动作
            action = menu.exec_(self.folder_list.mapToGlobal(position))
            
            # 处理选择的动作
            if action == action_new_folder:
                self._onAddFolder()
            elif action == action_refresh:
                self._onRefreshFolders()
    
    def _onRefreshFolders(self):
        """刷新文件夹列表"""
        # 保存当前选中的文件夹
        current_folder = self._current_folder
        
        # 重新加载文件夹列表
        self._loadFolders()
        
        # 如果之前有选中的文件夹，尝试重新选中
        if current_folder:
            for i in range(self.folder_list.count()):
                item = self.folder_list.item(i)
                if item.data(Qt.UserRole) == current_folder:
                    self.folder_list.setCurrentItem(item)
                    break
        
        # 刷新内容列表
        if self._current_folder:
            self._loadFolderVideos(self._current_folder)
    
    def _onVideoClicked(self, item):
        """视频被点击"""
        video_path = item.data(Qt.UserRole)
        
        # 先停止之前的播放
        self._onStopVideo()
        
        # 保存当前视频路径
        self._current_video = video_path
        
        # 更新当前视频显示
        video_name = osp.basename(video_path)
        self.lbl_current_video.setText(f"当前视频: {video_name}")
        
        # 启用裁剪按钮和播放按钮
        self.btn_crop.setEnabled(True)
        self.btn_play.setEnabled(True)
        
        # 加载视频的第一帧作为预览
        self._loadVideoFirstFrame(video_path)
        
        # 发射信号
        self.videoSelected.emit(video_path)
    
    def _onVideoDoubleClicked(self, item):
        """视频被双击 - 使用系统默认播放器打开"""
        video_path = item.data(Qt.UserRole)
        
        try:
            if os.name == 'nt':  # Windows
                os.startfile(video_path)
            elif os.name == 'posix':  # macOS, Linux
                import subprocess
                subprocess.Popen(['open', video_path])
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", f"无法打开视频: {e}"
            )
    
    def _onRefreshVideos(self):
        """刷新视频列表"""
        if self._current_folder:
            self._loadVideos(self._current_folder)
            
            # 刷新后，通知handler更新视频网格样式（恢复绿色标识）
            if hasattr(self, '_handler') and self._handler:
                if hasattr(self._handler, 'updateVideoGridStyles'):
                    # 使用QTimer延迟执行，确保视频列表已完全加载
                    from qtpy.QtCore import QTimer
                    QTimer.singleShot(100, self._handler.updateVideoGridStyles)
            
            # 隐藏刷新完成提示弹窗
            # self._showInformation("刷新完成", f"已刷新文件夹 '{self._current_folder}' 中的视频列表")
        else:
            self._showWarning("提示", "请先选择一个文件夹")
    
    def _onVideoGridContextMenu(self, position):
        """显示视频网格的右键菜单"""
        # 获取当前选中的项
        item = self.video_grid.itemAt(position)
        
        # 创建右键菜单
        menu = QtWidgets.QMenu(self)
        
        # 只在空白处点击时显示刷新菜单
        if not item:
            # 在空白处点击，显示刷新菜单
            action_refresh = menu.addAction(newIcon("刷新"), "刷新")
            
            # 显示菜单并获取选择的动作
            action = menu.exec_(self.video_grid.mapToGlobal(position))
            
            # 处理刷新动作
            if action == action_refresh:
                self._onRefreshVideos()
        
        # 在视频项上右键时不显示任何菜单（已删除重命名和删除功能）
    
    def _onRenameVideo(self, item):
        """重命名视频文件"""
        if not item:
            return
        
        # 获取视频路径
        video_path = item.data(Qt.UserRole)
        
        if not video_path or not osp.exists(video_path):
            QtWidgets.QMessageBox.warning(
                self, "警告", "视频文件不存在"
            )
            return
        
        # 在重命名之前，通知handler释放视频文件句柄
        # 这是为了避免 Windows 下的文件占用问题
        if hasattr(self, '_handler') and self._handler:
            if hasattr(self._handler, 'releaseVideoCapture'):
                self._handler.releaseVideoCapture()
        
        # 获取当前文件名（不含扩展名）和扩展名
        video_dir = osp.dirname(video_path)
        video_name = osp.basename(video_path)
        video_name_no_ext, video_ext = osp.splitext(video_name)
        
        # 弹出输入对话框
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "重命名视频文件", 
            "请输入新的文件名（不含扩展名）:",
            QtWidgets.QLineEdit.Normal,
            video_name_no_ext
        )
        
        if not ok or not new_name.strip():
            return
        
        # 构建新的文件路径
        new_video_name = new_name.strip() + video_ext
        new_video_path = osp.join(video_dir, new_video_name)
        
        # 检查新文件名是否已存在
        if osp.exists(new_video_path):
            self._showWarning("警告", f"视频文件 '{new_video_name}' 已存在")
            return
        
        # 稍微延迟，确保文件句柄完全释放
        import time
        time.sleep(0.1)
        
        # 重命名文件
        try:
            os.rename(video_path, new_video_path)
            
            # 如果重命名的是当前选中的视频，更新引用
            if self._current_video == video_path:
                self._current_video = new_video_path
                self.lbl_current_video.setText(f"当前视频: {new_video_name}")
            
            # 发射视频重命名信号（在刷新列表之前）
            self.videoRenamed.emit(video_path, new_video_path)
            
            # 刷新视频列表
            if self._current_folder:
                self._loadVideos(self._current_folder)
            
            QtWidgets.QMessageBox.information(
                self, "成功", 
                f"视频已重命名为: {new_video_name}"
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", 
                f"重命名视频失败:\n{str(e)}"
            )
    
    def _onDeleteVideo(self, item):
        """删除视频"""
        if not item:
            return
        
        # 获取视频路径
        video_path = item.data(Qt.UserRole)
        
        if not video_path or not osp.exists(video_path):
            self._showWarning("警告", "视频文件不存在")
            return
        
        video_name = osp.basename(video_path)
        
        # 确认删除 - 使用警告图标的统一对话框
        if self._showQuestionWarning(
            "确认删除", 
            f"确定要删除视频 '{video_name}' 吗？\n\n"
            f"视频文件将被移动到回收站"
        ):
            try:
                # 如果删除的是当前选中的视频，先停止播放
                if self._current_video == video_path:
                    self._onStopVideo()
                    self._current_video = None
                    self.lbl_current_video.setText("未选择视频")
                    self.btn_crop.setEnabled(False)
                    self.video_preview.clear()
                    self.video_preview.setText("视频预览\n点击视频文件开始预览")
                
                # 使用Windows回收站删除
                if delete_file_to_recycle_bin:
                    delete_file_to_recycle_bin(video_path)
                else:
                    raise ImportError("回收站工具未导入")
                
                # 刷新视频列表
                if self._current_folder:
                    self._loadVideos(self._current_folder)
                
            except Exception as e:
                self._showCritical("错误", f"删除视频失败:\n{str(e)}")
    
    def _onBrowseCropPath(self):
        """浏览裁剪保存路径"""
        current_path = self.crop_path_edit.text()
        if not current_path or not osp.exists(current_path):
            current_path = self._root_path if hasattr(self, '_root_path') else osp.expanduser("~")
        
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择裁剪图片保存文件夹", current_path
        )
        
        if folder:
            self.crop_path_edit.setText(folder)
    
    def _onCropClicked(self):
        """
        区域裁剪按钮点击
        
        注意：此方法为简化版实现
        如果使用 DataPreprocessHandler，会自动接管此按钮并提供可视化画框功能
        """
        if not self._current_video:
            self._showWarning("警告", "请先选择要裁剪的视频")
            return
        
        # 默认保存路径为当前文件夹
        default_save_liquid_data_path = osp.join(self._root_path, self._current_folder) if self._current_folder else self._root_path
        
        # 打开裁剪配置对话框
        try:
            dialog = CropConfigDialog(
                parent=self,
                default_save_liquid_data_path=default_save_liquid_data_path,
                default_frequency=10
            )
            
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 获取配置
                config = dialog.getConfig()
                
                # 添加视频路径信息
                config['video_path'] = self._current_video
                
                # 发射信号
                self.cropStarted.emit(config)
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", f"打开配置对话框失败:\n{e}"
            )
    
    def _loadVideoFirstFrame(self, video_path):
        """加载视频的第一帧作为预览"""
        try:
            import cv2
            
            # 打开视频
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                self.video_preview.setText("无法打开视频")
                return
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # 转换颜色空间 BGR -> RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 转换为 QImage
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qt_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                
                # 缩放到预览窗口大小
                pixmap = QtGui.QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_preview.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                
                # 显示
                self.video_preview.setPixmap(scaled_pixmap)
            else:
                self.video_preview.setText("无法读取视频帧")
        
        except ImportError:
            self.video_preview.setText("缺少 OpenCV 库\npip install opencv-python")
        except Exception as e:
            self.video_preview.setText(f"加载失败\n{str(e)}")
    
    def _onPlayVideo(self):
        """播放视频"""
        if not self._current_video:
            return
        
        try:
            import cv2
            
            # 如果已经在播放，不重复操作
            if self._video_playing:
                return
            
            # 打开视频
            self._video_capture = cv2.VideoCapture(self._current_video)
            
            if not self._video_capture.isOpened():
                self._showWarning("警告", "无法打开视频文件")
                return
            
            # 获取视频帧率
            fps = self._video_capture.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 25  # 默认fps
            
            # 更新状态
            self._video_playing = True
            self.btn_play.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            
            # 启动定时器更新画面
            self._video_timer = QtCore.QTimer(self)
            self._video_timer.timeout.connect(self._updateVideoFrame)
            self._video_timer.start(int(1000 / fps))  # 根据fps设置间隔
        
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self, "错误", "缺少 OpenCV 库\n\n请安装: pip install opencv-python"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", f"播放视频失败: {e}"
            )
    
    def _onPauseVideo(self):
        """暂停视频"""
        if self._video_timer:
            self._video_timer.stop()
        
        self._video_playing = False
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)
    
    def _onStopVideo(self):
        """停止视频"""
        # 停止定时器
        if self._video_timer:
            self._video_timer.stop()
            self._video_timer = None
        
        # 释放视频资源
        if self._video_capture:
            self._video_capture.release()
            self._video_capture = None
        
        # 更新状态
        self._video_playing = False
        self.btn_play.setEnabled(True if self._current_video else False)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        
        # 恢复第一帧预览
        if self._current_video:
            self._loadVideoFirstFrame(self._current_video)
    
    def _updateVideoFrame(self):
        """更新视频画面"""
        if not self._video_capture or not self._video_playing:
            return
        
        try:
            import cv2
            
            # 读取一帧
            ret, frame = self._video_capture.read()
            
            if ret:
                # 转换颜色空间 BGR -> RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 转换为 QImage
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qt_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                
                # 缩放到预览窗口大小
                pixmap = QtGui.QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_preview.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                
                # 显示
                self.video_preview.setPixmap(scaled_pixmap)
            else:
                # 视频播放结束，循环播放
                self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        except Exception as e:
            pass
    
    def _onBrowseCropPath(self):
        """浏览裁剪保存路径"""
        # 获取当前路径
        current_path = self.crop_path_edit.text().strip()
        if not current_path or not osp.exists(current_path):
            current_path = self._getDefaultCropFolder()
        
        # 打开文件夹选择对话框
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择裁剪图片保存文件夹",
            current_path,
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            self.crop_path_edit.setText(folder_path)
            print(f"[OK] 选择保存路径: {folder_path}")
    
    def _onOpenCropFolder(self):
        """打开裁剪图片保存文件夹"""
        # 无论当前设置为何，均打开默认的裁剪结果根目录
        save_path = self._getDefaultCropFolder()
        
        # 打开文件夹
        try:
            if os.name == 'nt':  # Windows
                os.startfile(save_path)
            elif os.name == 'posix':  # macOS, Linux
                import subprocess
                if sys.platform == 'darwin':
                    subprocess.call(['open', save_path])
                else:
                    subprocess.call(['xdg-open', save_path])
            
            print(f"[OK] 打开裁剪文件夹: {save_path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "提示", 
                f"无法自动打开文件夹，请手动打开：\n{save_path}\n\n错误：{str(e)}"
            )
    
    def _onStartCrop(self):
        """开始裁剪按钮点击"""
        # 验证配置
        config = self.getCropConfig()
        
        # 检查保存路径
        if not config['save_liquid_data_path']:
            self._showWarning("警告", "请先选择保存路径")
            return
        
        # 检查文件前缀
        if not config['file_prefix']:
            self._showWarning("警告", "请输入文件名前缀")
            return
        
        # 发射裁剪开始信号
        self.cropStarted.emit(config)
        print(f"[OK] 发射裁剪开始信号")
        print(f"   配置: {config}")


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("数据预处理面板测试")
    window.resize(1200, 700)
    
    test_root = osp.join(osp.expanduser("~"), "data_collection_test")
    panel = DataPreprocessPanel(root_path=test_root)
    window.setCentralWidget(panel)
    
    def setup_test_data():
        """创建测试数据"""
        test_folder = osp.join(test_root, "测试视频文件夹")
        if not osp.exists(test_folder):
            os.makedirs(test_folder, exist_ok=True)
            
            test_files = [
                "test_video_1.mp4",
                "test_video_2.avi",
                "sample_video.mkv"
            ]
            for fname in test_files:
                fpath = osp.join(test_folder, fname)
                if not osp.exists(fpath):
                    with open(fpath, 'w') as f:
                        f.write("# 这是一个测试文件，仅用于界面测试")
    
    QtCore.QTimer.singleShot(100, setup_test_data)
    QtCore.QTimer.singleShot(200, panel.refreshFolders)
    
    def on_folder_selected(folder_path):
        pass
    
    def on_folder_added(folder_path):
        pass
    
    def on_folder_deleted(folder_path):
        pass
    
    def on_video_selected(video_path):
        pass
    
    def on_crop_started(crop_config):
        pass
    
    panel.folderSelected.connect(on_folder_selected)
    panel.folderAdded.connect(on_folder_added)
    panel.folderDeleted.connect(on_folder_deleted)
    panel.videoSelected.connect(on_video_selected)
    panel.cropStarted.connect(on_crop_started)
    
    window.show()
    sys.exit(app.exec_())

