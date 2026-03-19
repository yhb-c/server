# -*- coding: utf-8 -*-

"""
模型升级（训练）页面

提供模型训练功能的UI界面
"""

import os
from pathlib import Path
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

# 尝试导入 PyQtGraph 用于曲线显示
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False

# 导入图标工具函数
try:
    from ..icons import newIcon, newButton
except (ImportError, ValueError):
    try:
        from widgets.icons import newIcon, newButton
    except ImportError:
        try:
            import sys
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))
            from widgets.icons import newIcon, newButton
        except ImportError:
            def newIcon(icon):
                from qtpy import QtGui
                return QtGui.QIcon()
            def newButton(text, icon=None, slot=None):
                btn = QtWidgets.QPushButton(text)
                if slot:
                    btn.clicked.connect(slot)
                return btn

# 导入样式管理器和响应式布局
try:
    from ..style_manager import FontManager, BackgroundStyleManager, TextButtonStyleManager
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    try:
        from widgets.style_manager import FontManager, BackgroundStyleManager, TextButtonStyleManager
        from widgets.responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        try:
            import sys
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))
            from widgets.style_manager import FontManager, BackgroundStyleManager, TextButtonStyleManager
            from widgets.responsive_layout import ResponsiveLayout, scale_w, scale_h
        except ImportError:
            # 如果导入失败，创建一个简单的替代类
            class FontManager:
                # 预定义字体粗细常量
                WEIGHT_LIGHT = 25
                WEIGHT_NORMAL = 50
                WEIGHT_DEMIBOLD = 63
                WEIGHT_BOLD = 75
                WEIGHT_BLACK = 87
                
                @staticmethod
                def getDefaultFont():
                    from qtpy import QtGui
                    return QtGui.QFont('Microsoft YaHei', 12)
                @staticmethod
                def applyToWidget(widget, size=None, weight=None):
                    from qtpy import QtGui
                    font = QtGui.QFont('Microsoft YaHei', size or 12)
                    if weight is not None:
                        font.setWeight(weight)
                    widget.setFont(font)


class TrainingPage(QtWidgets.QWidget):
    """
    模型升级（训练）页面
    
    提供模型训练的UI界面和参数配置
    """
    
    # 信号
    startTrainingClicked = QtCore.Signal()
    stopTrainingClicked = QtCore.Signal()
    continueTrainingClicked = QtCore.Signal()
    
    def __init__(self, parent=None):
        super(TrainingPage, self).__init__(parent)
        self._parent = parent
        self._is_training_stopped = False  # 标记训练是否被中断
        self._last_training_path = None  # 记录上次训练的路径
        self._log_font_size = 12  # 日志字体大小
        self._initUI()
        
        # 🔥 连接模板按钮组信号
        self.template_button_group.buttonClicked.connect(self._onTemplateChecked)
        
        self._loadBaseModelOptions()  # 🔥 加载基础模型选项
        self._loadTestModelOptions()  # 加载测试模型选项
        # self._loadTestFileList()  # 🔥 不再需要加载测试文件列表（改用浏览方式）
    
    def _increaseFontSize(self):
        """增加日志字体大小"""
        if self._log_font_size < 14:  # 最大字体大小限制
            self._log_font_size += 1
            self._updateLogFontSize()
    
    def _decreaseFontSize(self):
        """减少日志字体大小"""
        if self._log_font_size > 6:  # 最小字体大小限制
            self._log_font_size -= 1
            self._updateLogFontSize()
    
    def _updateLogFontSize(self):
        """更新日志字体大小"""
        self.train_log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: {self._log_font_size}pt;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 8px;
                line-height: 1.2;
            }}
        """)
    
    def clearLog(self):
        """清空日志内容"""
        self.train_log_text.clear()
        self.train_log_text.setPlainText("日志已清空...\n系统已就绪，请配置参数后点击\"开始升级\"按钮。")
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QVBoxLayout(self)
        ResponsiveLayout.apply_to_layout(main_layout, base_spacing=0, base_margins=(10, 0, 10, 10))
        
        # === 主内容区：左右分栏 ===
        content_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        
        # === 左侧：参数配置区 ===
        left_widget = QtWidgets.QWidget()
        # 🔥 应用统一背景颜色管理
        if BackgroundStyleManager:
            background_style = BackgroundStyleManager.getBackgroundStyle()
            left_widget.setStyleSheet(f"QWidget {{ {background_style} }}")
        
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        ResponsiveLayout.apply_to_layout(left_layout, base_spacing=0, base_margins=(0, 0, 5, 0))
        
        # 🔥 调整参数配置组高度 - 使用响应式布局
        params_group = self._createParametersGroup()
        ResponsiveLayout.apply_to_widget(params_group, min_height=380, max_height=420)
        left_layout.addWidget(params_group, 0)  # 不设置伸缩因子，保持固定尺寸
        
        # 模型测试区域
        test_group = QtWidgets.QWidget()
        
        test_group.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
        
        # 主布局：左右分栏（使用 QSplitter 实现固定比例）
        test_group_main_layout = QtWidgets.QVBoxLayout(test_group)
        test_group_main_layout.setContentsMargins(0, 0, 0, 0)
        test_group_main_layout.setSpacing(0)
        
        test_group_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        test_group_splitter.setChildrenCollapsible(False)
        test_group_splitter.setHandleWidth(1)  # 设置分隔条宽度
        test_group_main_layout.addWidget(test_group_splitter)
        
        # === 左侧：显示面板区域 ===
        left_display_widget = QtWidgets.QWidget()
        left_display_widget.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
            }
        """)
        # 设置最小宽度和高度，防止内容加载后自动扩展
        left_display_widget.setMinimumWidth(scale_w(400))
        left_display_widget.setMinimumHeight(scale_h(450))
        left_display_layout = QtWidgets.QVBoxLayout(left_display_widget)
        ResponsiveLayout.apply_to_layout(left_display_layout, base_spacing=0, base_margins=0)
        
        # 提示文本标签到显示面板内部
        hint_container = QtWidgets.QWidget()
        hint_layout = QtWidgets.QVBoxLayout(hint_container)
        ResponsiveLayout.apply_to_layout(hint_layout, base_spacing=0, base_margins=0)
        
        # 提示文本标签 - 居中显示
        hint_label = QtWidgets.QLabel("测试页面")
        hint_label.setAlignment(QtCore.Qt.AlignCenter)
        hint_label.setStyleSheet("color: #999; font-size: 11pt; padding: 20px;")
        FontManager.applyToWidget(hint_label)
        hint_layout.addWidget(hint_label)
        
        # 显示面板（统一使用白色背景）
        self.display_panel = QtWidgets.QTextEdit()
        self.display_panel.setReadOnly(True)
        self.display_panel.setPlaceholderText("")
        FontManager.applyToWidget(self.display_panel, size=FontManager.FONT_SIZE_SMALL)
        self.display_panel.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: none;
                padding: 10px;
                color: #333333;
            }
        """)
        
        # 创建显示面板容器，包含提示标签和内容
        display_container = QtWidgets.QWidget()
        display_layout = QtWidgets.QStackedLayout(display_container)
        from ..responsive_layout import scale_margin
        margin = scale_margin(0)
        display_layout.setContentsMargins(margin, margin, margin, margin)
        display_layout.setSpacing(0)
        
        # 添加提示标签作为初始显示
        display_layout.addWidget(hint_container)
        # 添加显示面板作为内容显示
        display_layout.addWidget(self.display_panel)
        
        # 初始显示提示标签
        display_layout.setCurrentIndex(0)
        
        # 保存布局引用，以便后续切换
        self.display_layout = display_layout
        
        left_display_layout.addWidget(display_container)
        
        # 创建视频面板容器 - 用于显示检测结果视频（统一使用白色背景）
        self.video_panel = QtWidgets.QTextEdit()
        self.video_panel.setReadOnly(True)
        self.video_panel.setPlaceholderText("")
        self.video_panel.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: none;
                padding: 10px;
                color: #333333;
            }
        """)
        
        # 将视频面板添加到显示布局中
        display_layout.addWidget(self.video_panel)
        
        # === 添加曲线显示面板 ===
        self._createCurvePanel()
        display_layout.addWidget(self.curve_panel)
        
        # 🔥 设置整体窗口的最小尺寸 - 使用响应式布局
        min_w, min_h = scale_w(1000), scale_h(700)
        self.setMinimumSize(min_w, min_h)
        
        # 将左侧显示面板添加到 splitter
        test_group_splitter.addWidget(left_display_widget)
        
        # === 右侧：控件区域 ===
        right_control_widget = QtWidgets.QWidget()
        # 只为容器本身设置样式，不影响子控件（特别是按钮）
        right_control_widget.setStyleSheet("""
            QWidget#right_control_widget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
            }
        """)
        right_control_widget.setObjectName("right_control_widget")  # 设置对象名以应用样式
        # 设置最小宽度，确保按钮和下拉框有足够空间
        right_control_widget.setMinimumWidth(scale_w(250))
        right_control_layout = QtWidgets.QVBoxLayout(right_control_widget)
        ResponsiveLayout.apply_to_layout(right_control_layout, base_spacing=12, base_margins=12)
        
        test_model_layout = QtWidgets.QVBoxLayout()
        from ..responsive_layout import scale_spacing
        test_model_layout.setSpacing(scale_spacing(5))
        
        test_model_label = QtWidgets.QLabel("测试模型")
        FontManager.applyToWidget(test_model_label)
        test_model_label.setStyleSheet("color: #495057; font-weight: bold;")
        test_model_layout.addWidget(test_model_label)
        
        self.test_model_combo = QtWidgets.QComboBox()
        FontManager.applyToWidget(self.test_model_combo)
        self.test_model_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 10px;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #0078d7;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        test_model_layout.addWidget(self.test_model_combo)
        right_control_layout.addLayout(test_model_layout)
        
        test_file_layout = QtWidgets.QVBoxLayout()
        from ..responsive_layout import scale_spacing
        test_file_layout.setSpacing(scale_spacing(5))
        
        test_file_label = QtWidgets.QLabel("测试文件")
        FontManager.applyToWidget(test_file_label)
        test_file_label.setStyleSheet("color: #495057; font-weight: bold;")
        test_file_layout.addWidget(test_file_label)
        
        # 测试文件路径输入框和浏览按钮
        test_file_input_layout = QtWidgets.QHBoxLayout()
        test_file_input_layout.setSpacing(scale_spacing(5))
        
        # 文件路径输入框（可编辑）
        self.test_file_input = QtWidgets.QLineEdit()
        self.test_file_input.setPlaceholderText("选择测试图片或视频文件...")
        FontManager.applyToWidget(self.test_file_input)
        self.test_file_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d7;
                outline: none;
            }
        """)
        test_file_input_layout.addWidget(self.test_file_input)
        
        # 浏览按钮（使用全局样式管理器）
        self.test_file_browse_btn = TextButtonStyleManager.createStandardButton(
            "浏览...", 
            parent=self,
            slot=self._browseTestFile
        )
        self.test_file_browse_btn.setMinimumWidth(scale_w(60))
        test_file_input_layout.addWidget(self.test_file_browse_btn)
        
        test_file_layout.addLayout(test_file_input_layout)
        right_control_layout.addLayout(test_file_layout)
        
        # 添加垂直间距
        right_control_layout.addSpacing(20)
        
        test_button_layout = QtWidgets.QHBoxLayout()
        ResponsiveLayout.apply_to_layout(test_button_layout, base_spacing=10, base_margins=0)
        
        # 使用全局样式管理器创建测试按钮
        self.start_annotation_btn = TextButtonStyleManager.createStandardButton(
            "开始标注", 
            parent=self
        )
        self.start_annotation_btn.setMinimumWidth(scale_w(80))
        test_button_layout.addWidget(self.start_annotation_btn)
        
        self.start_test_btn = TextButtonStyleManager.createStandardButton(
            "开始测试", 
            parent=self
        )
        self.start_test_btn.setMinimumWidth(scale_w(80))
        test_button_layout.addWidget(self.start_test_btn)
        
        # 查看曲线按钮（使用全局样式管理器）
        self.view_curve_btn = TextButtonStyleManager.createStandardButton(
            "查看曲线", 
            parent=self,
            slot=self._onViewCurveClicked
        )
        self.view_curve_btn.setMinimumWidth(scale_w(80))
        self.view_curve_btn.setEnabled(False)  # 初始状态禁用
        self.view_curve_btn.setToolTip("测试完成后可查看曲线结果")
        test_button_layout.addWidget(self.view_curve_btn)
        
        # 将按钮布局添加到主布局
        right_control_layout.addLayout(test_button_layout)
        
        # 底部弹性空间
        right_control_layout.addStretch()
        
        self._is_testing = False
        
        # 将右侧控件添加到 splitter
        test_group_splitter.addWidget(right_control_widget)
        
        # 设置固定的初始尺寸比例（左:右 = 600:100）
        # 左侧显示面板 600px，右侧控件区域 100px
        test_group_splitter.setSizes([scale_w(600), scale_w(100)])
        test_group_splitter.setStretchFactor(0, 6)  # 左侧伸缩因子（6:1 比例）
        test_group_splitter.setStretchFactor(1, 1)  # 右侧伸缩因子
        
        left_layout.addWidget(test_group, 1)
        
        # === 右侧：日志输出区 ===
        right_widget = QtWidgets.QWidget()
        # 🔥 应用统一背景颜色管理
        if BackgroundStyleManager:
            background_style = BackgroundStyleManager.getBackgroundStyle()
            right_widget.setStyleSheet(f"QWidget {{ {background_style} }}")
        
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        ResponsiveLayout.apply_to_layout(right_layout, base_spacing=8, base_margins=(5, 0, 0, 0))
        
        # 日志标题栏
        log_header = QtWidgets.QHBoxLayout()
        log_label = QtWidgets.QLabel("升级日志")
        # 使用系统默认样式
        FontManager.applyToWidget(log_label, weight=FontManager.WEIGHT_BOLD)
        log_header.addWidget(log_label)
        
        log_header.addStretch()
        
        # 自动滚动复选框（使用系统默认样式）
        self.auto_scroll_check = QtWidgets.QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)  # 默认启用
        FontManager.applyToWidget(self.auto_scroll_check)
        log_header.addWidget(self.auto_scroll_check)
        
        # 清空日志按钮（使用全局样式管理器）
        clear_log_btn = TextButtonStyleManager.createStandardButton(
            "清空日志", 
            parent=self,
            slot=self.clearLog
        )
        clear_log_btn.setMinimumWidth(scale_w(60))
        
        # 🔥 添加字体大小调整按钮
        font_size_label = QtWidgets.QLabel("字体:")
        FontManager.applyToWidget(font_size_label)
        log_header.addWidget(font_size_label)
        
        # 字体调整按钮（使用全局样式管理器）
        self.font_decrease_btn = TextButtonStyleManager.createStandardButton(
            "-", 
            parent=self,
            slot=self._decreaseFontSize
        )
        btn_size = scale_w(20)  # 响应式按钮尺寸
        self.font_decrease_btn.setFixedSize(btn_size, btn_size)
        log_header.addWidget(self.font_decrease_btn)
        
        self.font_increase_btn = TextButtonStyleManager.createStandardButton(
            "+", 
            parent=self,
            slot=self._increaseFontSize
        )
        self.font_increase_btn.setFixedSize(btn_size, btn_size)
        log_header.addWidget(self.font_increase_btn)
        
        log_header.addWidget(clear_log_btn)
        
        right_layout.addLayout(log_header)
        
        # 🔥 日志显示区 - 优化字体和尺寸以支持训练指标在同一行显示
        self.train_log_text = QtWidgets.QTextEdit()
        self.train_log_text.setReadOnly(True)
        
        # 使用全局字体管理器的字体参数（通过CSS设置，因为CSS优先级高于setFont）
        log_font_family = FontManager.DEFAULT_FONT_FAMILY
        log_font_size = 12  # 使用 11pt 字体大小
        self.train_log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: '{log_font_family}';
                font-size: {log_font_size}pt;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 8px;
                line-height: 1.2;
            }}
        """)
        
        # 设置文本换行模式，防止水平滚动条
        self.train_log_text.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.train_log_text.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        # 设置垂直滚动条始终显示，方便用户上下滚动查看日志
        self.train_log_text.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.train_log_text.setPlainText("等待开始升级...\n系统已就绪，请配置参数后点击\"开始升级\"按钮。")
        right_layout.addWidget(self.train_log_text)
        
        # 创建别名以保持向后兼容
        self.log_display = self.train_log_text
        
        # 添加到分割器
        content_splitter.addWidget(left_widget)
        content_splitter.addWidget(right_widget)
        
        # 🔥 设置分栏器的最小尺寸 - 使用响应式布局
        left_min_w = scale_w(400)
        right_min_w = scale_w(500)
        left_widget.setMinimumWidth(left_min_w)  # 左侧最小宽度，保证参数文字可读
        right_widget.setMinimumWidth(right_min_w)  # 增加右侧最小宽度，确保训练指标在同一行显示
        
        # 🔥 调整分栏器比例 - 给训练日志更多空间 (左:右 = 2:3)
        content_splitter.setStretchFactor(0, 2)  # 左侧测试区域
        content_splitter.setStretchFactor(1, 3)  # 右侧日志区域获得更多空间
        
        main_layout.addWidget(content_splitter)
        
        # 连接信号
        self.start_train_btn.clicked.connect(self.startTrainingClicked.emit)
        self.stop_train_btn.clicked.connect(self._onStopOrContinueClicked)
        
        pass
    
    def _createCurvePanel(self):
        """创建曲线显示面板"""
        self.curve_panel = QtWidgets.QWidget()
        curve_layout = QtWidgets.QVBoxLayout(self.curve_panel)
        curve_layout.setContentsMargins(5, 5, 5, 5)
        curve_layout.setSpacing(5)
        
        # 曲线面板标题
        curve_title_layout = QtWidgets.QHBoxLayout()
        curve_title = QtWidgets.QLabel("测试结果曲线")
        curve_title.setStyleSheet("color: #495057; font-weight: bold; font-size: 12pt;")
        FontManager.applyToWidget(curve_title, weight=FontManager.WEIGHT_BOLD)
        curve_title_layout.addWidget(curve_title)
        
        # 添加清空曲线按钮（使用全局样式管理器）
        self.clear_curve_btn = TextButtonStyleManager.createStandardButton(
            "清空曲线", 
            parent=self,
            slot=self._clearCurve
        )
        self.clear_curve_btn.setMinimumWidth(scale_w(80))
        curve_title_layout.addStretch()
        curve_title_layout.addWidget(self.clear_curve_btn)
        
        curve_layout.addLayout(curve_title_layout)
        
        # 检查 PyQtGraph 是否可用
        if PYQTGRAPH_AVAILABLE:
            # 创建 PyQtGraph 绘图控件
            self.curve_plot_widget = pg.PlotWidget()
            self.curve_plot_widget.setBackground('#ffffff')
            self.curve_plot_widget.showGrid(x=True, y=True, alpha=0.3)
            
            # 设置坐标轴标签
            self.curve_plot_widget.setLabel('left', '液位高度', units='mm')
            self.curve_plot_widget.setLabel('bottom', '帧序号')
            self.curve_plot_widget.setTitle('液位检测曲线', color='#495057', size='12pt')
            
            # 添加图例
            self.curve_plot_widget.addLegend()
            
            # 存储曲线数据
            self.curve_data_x = []  # X轴数据（帧序号）
            self.curve_data_y = []  # Y轴数据（液位高度）
            self.curve_line = None  # 曲线对象
            
            curve_layout.addWidget(self.curve_plot_widget)
        else:
            # PyQtGraph 不可用，显示提示信息
            placeholder = QtWidgets.QLabel(
                "曲线显示功能需要 PyQtGraph 库\n\n"
                "请安装: pip install pyqtgraph"
            )
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #999; font-size: 11pt; padding: 50px;")
            FontManager.applyToWidget(placeholder)
            curve_layout.addWidget(placeholder)
    
    def _clearCurve(self):
        """清空曲线数据并隐藏曲线面板"""
        try:
            # 总是清空数据（无论PyQtGraph是否可用）
            self.curve_data_x = []
            self.curve_data_y = []
            print("[曲线] 已清空曲线数据")
            
            # 如果PyQtGraph可用，清空图表
            if PYQTGRAPH_AVAILABLE and hasattr(self, 'curve_plot_widget') and self.curve_plot_widget:
                # 清空曲线
                if hasattr(self, 'curve_line') and self.curve_line:
                    self.curve_plot_widget.removeItem(self.curve_line)
                    self.curve_line = None
                print("[曲线] 已清空PyQtGraph曲线")
            
            # 自动隐藏曲线面板，返回到初始显示状态
            self.hideCurvePanel()
            print("[曲线] 曲线面板已隐藏，返回初始显示状态")
            
        except Exception as e:
            print(f"[曲线] 清空曲线失败: {e}")
            import traceback
            traceback.print_exc()
    
    def addCurvePoint(self, frame_index, height_mm):
        """添加曲线数据点
        
        Args:
            frame_index: 帧序号
            height_mm: 液位高度（毫米）
        """
        try:
            # 确保曲线数据列表存在
            if not hasattr(self, 'curve_data_x'):
                self.curve_data_x = []
            if not hasattr(self, 'curve_data_y'):
                self.curve_data_y = []
            
            # 总是添加数据点到列表中（无论PyQtGraph是否可用）
            self.curve_data_x.append(frame_index)
            self.curve_data_y.append(height_mm)
            print(f"[曲线] 添加数据点: 帧{frame_index}, 液位{height_mm:.1f}mm，当前数据点数: {len(self.curve_data_x)}")
            
            # 如果PyQtGraph可用且有curve_plot_widget，更新图表
            if PYQTGRAPH_AVAILABLE and hasattr(self, 'curve_plot_widget') and self.curve_plot_widget:
                # 如果曲线不存在，创建曲线
                if not hasattr(self, 'curve_line') or self.curve_line is None:
                    self.curve_line = self.curve_plot_widget.plot(
                        self.curve_data_x, 
                        self.curve_data_y,
                        pen=pg.mkPen(color='#1f77b4', width=2),
                        name='液位高度'
                    )
                else:
                    # 更新曲线数据
                    self.curve_line.setData(self.curve_data_x, self.curve_data_y)
            
        except Exception as e:
            print(f"[曲线] 添加数据点失败: {e}")
            import traceback
            traceback.print_exc()
    
    def showCurvePanel(self):
        """显示曲线面板"""
        if hasattr(self, 'curve_panel') and hasattr(self, 'stacked_widget'):
            self.stacked_widget.setCurrentWidget(self.curve_panel)
            print("[曲线] 显示曲线面板")
    
    def hideCurvePanel(self):
        """隐藏曲线面板，返回到初始显示"""
        if hasattr(self, 'display_panel') and hasattr(self, 'stacked_widget'):
            self.stacked_widget.setCurrentWidget(self.display_panel)
            print("[曲线] 隐藏曲线面板")
    
    def saveCurveData(self, csv_path):
        """保存曲线数据为CSV文件
        
        Args:
            csv_path: CSV文件保存路径
        
        Returns:
            bool: 是否成功保存
        """
        if not PYQTGRAPH_AVAILABLE or not hasattr(self, 'curve_data_x'):
            return False
        
        try:
            import csv
            
            # 检查是否有数据
            if len(self.curve_data_x) == 0:
                print("[曲线保存] 没有曲线数据可保存")
                return False
            
            # 写入CSV文件
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['帧序号', '液位高度(mm)'])
                # 写入数据
                for x, y in zip(self.curve_data_x, self.curve_data_y):
                    writer.writerow([x, y])
            
            print(f"[曲线保存] CSV数据已保存: {csv_path}")
            print(f"[曲线保存] 共保存 {len(self.curve_data_x)} 个数据点")
            return True
            
        except Exception as e:
            print(f"[曲线保存] 保存CSV失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def saveCurveImage(self, image_path):
        """保存曲线为图片文件
        
        Args:
            image_path: 图片文件保存路径（支持 .png, .jpg, .svg等格式）
        
        Returns:
            bool: 是否成功保存
        """
        if not PYQTGRAPH_AVAILABLE or not hasattr(self, 'curve_plot_widget'):
            return False
        
        try:
            # 检查是否有数据
            if len(self.curve_data_x) == 0:
                print("[曲线保存] 没有曲线数据可保存")
                return False
            
            # 使用PyQtGraph的导出功能
            exporter = pg.exporters.ImageExporter(self.curve_plot_widget.plotItem)
            
            # 设置导出参数
            exporter.parameters()['width'] = 1200  # 设置宽度
            exporter.parameters()['height'] = 600  # 设置高度
            
            # 导出图片
            exporter.export(image_path)
            
            print(f"[曲线保存] 曲线图片已保存: {image_path}")
            return True
            
        except Exception as e:
            print(f"[曲线保存] 保存图片失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _createParametersGroup(self):
        """创建参数配置组"""
        group = QtWidgets.QGroupBox("")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10pt;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin-top: 0px;
                padding-top: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: white;
            }
        """)
        
        # 🔥 导入字体管理器
        try:
            from ..style_manager import FontManager
        except (ImportError, ValueError):
            FontManager = None
        
        # 使用垂直布局包裹表单布局和按钮区域
        main_layout = QtWidgets.QVBoxLayout(group)
        ResponsiveLayout.apply_to_layout(main_layout, base_spacing=10, base_margins=(12, 15, 12, 12))
        
        # 创建表单布局
        layout = QtWidgets.QFormLayout()
        from ..responsive_layout import scale_spacing
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # 🔥 删除CSS样式表，改为纯控件方式，由字体管理器统一管理
        
        # 基础模型选择（下拉菜单）
        self.base_model_combo = QtWidgets.QComboBox()
        self.base_model_combo.setPlaceholderText("请选择基础模型")
        self.base_model_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout.addRow("基础模型:", self.base_model_combo)
        
        # 数据集文件夹选择（统一格式，支持多个文件夹）
        dataset_layout = QtWidgets.QHBoxLayout()
        dataset_layout.setSpacing(8)
        dataset_layout.setContentsMargins(0, 0, 0, 0)
        
        # 数据集路径显示文本框（可编辑，支持多个路径用分号分隔）
        self.dataset_paths_edit = QtWidgets.QLineEdit()
        self.dataset_paths_edit.setPlaceholderText("")
        self.dataset_paths_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # 移除自定义样式，使用全局字体管理器统一管理
        self.dataset_paths_edit.setStyleSheet("")
        # 连接文本变化信号，实时更新内部数据集列表
        self.dataset_paths_edit.textChanged.connect(self._onDatasetPathsChanged)
        dataset_layout.addWidget(self.dataset_paths_edit)
        
        # 浏览按钮（使用全局样式管理器）
        self.btn_browse_datasets = TextButtonStyleManager.createStandardButton(
            "浏览...", 
            parent=self,
            slot=self._onBrowseDatasets
        )
        self.btn_browse_datasets.setFixedWidth(100)
        self.btn_browse_datasets.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        dataset_layout.addWidget(self.btn_browse_datasets)
        
        layout.addRow("数据集:", dataset_layout)
        
        # 保持内部数据集文件夹列表（隐藏，用于兼容现有逻辑）
        self.dataset_folders_list = QtWidgets.QListWidget()
        self.dataset_folders_list.setVisible(False)  # 隐藏，仅用于内部数据管理
        
        # 保留旧的字段名以保持向后兼容（用于获取数据集路径）
        # 现在它将存储用分号分隔的多个文件夹路径
        self.save_liquid_data_path_edit = QtWidgets.QLineEdit()
        self.save_liquid_data_path_edit.setVisible(False)  # 隐藏，仅用于数据传递
        
        # 实验名称
        self.exp_name_edit = QtWidgets.QLineEdit()
        self.exp_name_edit.setPlaceholderText("输入模型名称")
        self.exp_name_edit.setText("train_exp")
        layout.addRow("模型名称:", self.exp_name_edit)
        
        # 训练轮数
        self.epochs_spin = QtWidgets.QSpinBox()
        self.epochs_spin.setMinimum(1)
        self.epochs_spin.setMaximum(1000)
        self.epochs_spin.setValue(100)
        self.epochs_spin.setSuffix(" 轮")
        layout.addRow("训练轮数:", self.epochs_spin)
        
        # 批次大小
        self.batch_spin = QtWidgets.QSpinBox()
        self.batch_spin.setMinimum(1)
        self.batch_spin.setMaximum(256)
        self.batch_spin.setValue(16)
        layout.addRow("批次大小:", self.batch_spin)
        
        # 图像尺寸
        self.imgsz_spin = QtWidgets.QSpinBox()
        self.imgsz_spin.setMinimum(32)
        self.imgsz_spin.setMaximum(1280)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(640)
        self.imgsz_spin.setSuffix(" px")
        layout.addRow("图像尺寸:", self.imgsz_spin)
        
        # 工作线程数
        self.workers_spin = QtWidgets.QSpinBox()
        self.workers_spin.setMinimum(0)
        self.workers_spin.setMaximum(16)
        self.workers_spin.setValue(4)
        self.workers_spin.setSuffix(" 线程")
        self.workers_spin.setToolTip("数据加载工作线程数。GPU显存不足时可降低此值。")
        layout.addRow("Workers:", self.workers_spin)
        
        # 设备选择（GPU或CPU）
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItems(["GPU", "CPU"])
        self.device_combo.setCurrentIndex(0)  # 默认选中GPU
        self.device_combo.setToolTip("如果没有NVIDIA GPU或CUDA未安装，请选择CPU")
        layout.addRow("训练设备:", self.device_combo)
        
        # 优化器选择
        self.optimizer_combo = QtWidgets.QComboBox()
        self.optimizer_combo.addItems(["SGD", "Adam", "AdamW"])
        layout.addRow("优化器:", self.optimizer_combo)
        
        # 训练笔记按钮（使用全局样式管理器）
        self.training_notes_btn = TextButtonStyleManager.createStandardButton(
            "训练笔记", 
            parent=self,
            slot=self._openNotesDialog
        )
        self.training_notes_btn.setToolTip("点击打开训练笔记编辑窗口")
        layout.addRow("训练笔记:", self.training_notes_btn)
        
        # 内部存储笔记内容的变量
        self._training_notes_content = ""
        
        # 高级选项分隔
        separator = QtWidgets.QLabel()
        separator.setStyleSheet("border-top: 1px solid #dee2e6; margin: 5px 0;")
        layout.addRow(separator)
        
        # 缓存数据选项（已隐藏）
        self.cache_check = QtWidgets.QCheckBox("启用数据缓存")
        self.cache_check.setChecked(False)
        self.cache_check.setToolTip("缓存数据可加快训练，但会占用更多显存")
        self.cache_check.setVisible(False)  # 隐藏控件
        layout.addRow("", self.cache_check)
        
        # 恢复训练选项（已隐藏）
        self.resume_check = QtWidgets.QCheckBox("从上次中断处恢复")
        self.resume_check.setChecked(False)
        self.resume_check.setToolTip("从上次训练中断的地方继续训练")
        self.resume_check.setVisible(False)  # 隐藏控件
        layout.addRow("", self.resume_check)
        
        # 将表单布局添加到主布局
        main_layout.addLayout(layout)
        
        # === 控制按钮区域（包含复选框和按钮） ===
        control_layout = QtWidgets.QHBoxLayout()
        from ..responsive_layout import scale_spacing, scale_margin
        control_layout.setSpacing(scale_spacing(10))
        top_margin = scale_margin(-10)
        control_layout.setContentsMargins(0, top_margin, 0, 0)  # 🔥 顶部边距改为-10，向上移动10px
        
        # 🔥 单选按钮模板1、2、3（一次只能选择一个）
        self.template_button_group = QtWidgets.QButtonGroup(self)
        self.template_button_group.setExclusive(False)  # 🔥 允许取消选择，实现都不选中的状态
        
        self.checkbox_template_1 = QtWidgets.QRadioButton("模板1")
        # 🔥 默认不选中任何模板，使用默认配置
        self.template_button_group.addButton(self.checkbox_template_1, 1)
        control_layout.addWidget(self.checkbox_template_1)
        
        self.checkbox_template_2 = QtWidgets.QRadioButton("模板2")
        self.template_button_group.addButton(self.checkbox_template_2, 2)
        control_layout.addWidget(self.checkbox_template_2)
        
        self.checkbox_template_3 = QtWidgets.QRadioButton("模板3")
        self.template_button_group.addButton(self.checkbox_template_3, 3)
        control_layout.addWidget(self.checkbox_template_3)
        
        # 🔥 恢复互斥模式（点击后只能选一个）
        self.template_button_group.setExclusive(True)
        
        control_layout.addStretch()  # 中间弹性空间，实现右对齐
        
        # 状态指示器（使用Qt默认样式 + 响应式布局）
        self.status_label = QtWidgets.QPushButton("状态: 就绪")
        self.status_label.setEnabled(False)  # 禁用点击
        self.status_label.setMinimumWidth(scale_w(100))  # 响应式最小宽度，防止文字变化时按钮大小改变
        control_layout.addWidget(self.status_label)
        
        # 创建别名以匹配训练处理器期望的名称
        self.train_status_label = self.status_label
        
        # 控制按钮（使用全局样式管理器）
        self.start_train_btn = TextButtonStyleManager.createStandardButton(
            "开始升级", 
            parent=self
        )
        self.start_train_btn.setMinimumWidth(scale_w(80))
        control_layout.addWidget(self.start_train_btn)
        
        self.stop_train_btn = TextButtonStyleManager.createStandardButton(
            "停止升级", 
            parent=self
        )
        self.stop_train_btn.setMinimumWidth(scale_w(80))
        self.stop_train_btn.setEnabled(False)
        control_layout.addWidget(self.stop_train_btn)
        
        # 将按钮布局添加到主布局
        main_layout.addLayout(control_layout)
        main_layout.addStretch()  # 🔥 添加弹性空间，防止按钮被推到底部
        
        # 🔥 应用全局字体管理器到所有文本框和控件
        if FontManager:
            # 应用到所有QLineEdit
            FontManager.applyToWidget(self.dataset_paths_edit)
            FontManager.applyToWidget(self.save_liquid_data_path_edit)
            FontManager.applyToWidget(self.exp_name_edit)
            
            # 应用到所有QSpinBox
            FontManager.applyToWidget(self.epochs_spin)
            FontManager.applyToWidget(self.batch_spin)
            FontManager.applyToWidget(self.imgsz_spin)
            FontManager.applyToWidget(self.workers_spin)
            
            # 应用到所有QComboBox
            FontManager.applyToWidget(self.base_model_combo)
            FontManager.applyToWidget(self.device_combo)
            FontManager.applyToWidget(self.optimizer_combo)
            
            # 应用到所有QCheckBox
            FontManager.applyToWidget(self.cache_check)
            FontManager.applyToWidget(self.resume_check)
            
            # 应用到所有QRadioButton（模板选择）
            FontManager.applyToWidget(self.checkbox_template_1)
            FontManager.applyToWidget(self.checkbox_template_2)
            FontManager.applyToWidget(self.checkbox_template_3)
            
            # 应用到状态标签（非按钮样式管理器创建的控件）
            FontManager.applyToWidget(self.status_label)
            
            # 应用到数据集列表
            FontManager.applyToWidget(self.dataset_folders_list)
            
            # 应用到笔记按钮
            FontManager.applyToWidget(self.training_notes_btn)
            
            # 应用到整个group（包括标签）
            FontManager.applyToWidgetRecursive(group)
        
        return group
    
    def _onBrowseDatasets(self):
        """浏览数据集文件夹（支持多选）"""
        # 使用简单的单选文件夹对话框，多次选择来实现多选效果
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择数据集文件夹",
            "database/dataset" if os.path.exists("database/dataset") else ""
        )
        
        if folder_path:
            # 获取当前已有的文件夹路径
            current_paths = self.dataset_paths_edit.text().strip()
            existing_folders = [p.strip() for p in current_paths.split(';') if p.strip()] if current_paths else []
            
            # 检查是否已经添加过这个文件夹
            if folder_path not in existing_folders:
                # 添加新文件夹
                if existing_folders:
                    # 如果已有文件夹，用分号连接
                    new_paths = current_paths + ';' + folder_path
                else:
                    # 如果是第一个文件夹
                    new_paths = folder_path
                
                self.dataset_paths_edit.setText(new_paths)
                print(f"[TrainingPage] 添加数据集文件夹: {folder_path}")
            else:
                # 使用style_manager中的对话框管理器显示提示
                try:
                    from ..style_manager import DialogManager
                    DialogManager.show_information(
                        self, "提示", 
                        f"文件夹已存在：\n{folder_path}"
                    )
                except ImportError:
                    QtWidgets.QMessageBox.information(
                        self, "提示", 
                        f"文件夹已存在：\n{folder_path}"
                    )
    
    def _onDatasetPathsChanged(self):
        """数据集路径文本变化时的处理"""
        # 更新内部数据集列表和隐藏的路径字段
        paths_text = self.dataset_paths_edit.text().strip()
        folders = [p.strip() for p in paths_text.split(';') if p.strip()]
        
        # 更新内部列表（用于兼容现有逻辑）
        self.dataset_folders_list.clear()
        for folder in folders:
            self.dataset_folders_list.addItem(folder)
        
        # 更新隐藏的路径字段
        self.save_liquid_data_path_edit.setText(paths_text)
        
        # 调试信息
        print(f"[TrainingPage] 数据集路径更新: {len(folders)} 个文件夹")
        for i, folder in enumerate(folders):
            print(f"  [{i+1}] {folder}")
    
    def _addDatasetFolder(self):
        """添加数据集文件夹（保留兼容性）"""
        self._onBrowseDatasets()
    
    def _removeSelectedDatasets(self):
        """删除选中的数据集文件夹"""
        selected_items = self.dataset_folders_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择要删除的文件夹")
            return
        
        for item in selected_items:
            row = self.dataset_folders_list.row(item)
            self.dataset_folders_list.takeItem(row)
        
        self._updateDatasetPath()
    
    def _clearAllDatasets(self):
        """清空所有数据集文件夹"""
        if self.dataset_folders_list.count() == 0:
            return
        
        reply = QtWidgets.QMessageBox.question(
            self, 
            "确认清空",
            f"确定要清空所有 {self.dataset_folders_list.count()} 个数据集文件夹吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.dataset_folders_list.clear()
            self._updateDatasetPath()
    
    def _updateDatasetPath(self):
        """更新隐藏的数据集路径字段（用分号分隔多个文件夹）"""
        folders = [self.dataset_folders_list.item(i).text() 
                  for i in range(self.dataset_folders_list.count())]
        # 使用分号分隔多个文件夹路径
        self.save_liquid_data_path_edit.setText(';'.join(folders))
    
    def getDatasetFolders(self):
        """获取所有数据集文件夹路径列表"""
        paths_text = self.dataset_paths_edit.text().strip()
        return [p.strip() for p in paths_text.split(';') if p.strip()]
    
    
    def getTrainingNotes(self):
        """获取训练笔记内容"""
        return self._training_notes_content.strip()
    
    def setTrainingNotes(self, notes):
        """设置训练笔记内容"""
        self._training_notes_content = notes if notes else ""
        self._updateNotesButtonText()
    
    def clearTrainingNotes(self):
        """清空训练笔记（不弹确认框）"""
        self._training_notes_content = ""
        self._updateNotesButtonText()
    
    def _openNotesDialog(self):
        """打开训练笔记编辑对话框"""
        dialog = TrainingNotesDialog(self._training_notes_content, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self._training_notes_content = dialog.getNotesContent()
            self._updateNotesButtonText()
    
    def _updateNotesButtonText(self):
        """更新笔记按钮的显示文本"""
        
        if self._training_notes_content.strip():
            # 不显示笔记内容预览，只显示标记
            new_text = "训练笔记 ●"
            
            # 使用全局样式管理器更新按钮文本和大小
            TextButtonStyleManager.updateButtonText(self.training_notes_btn, new_text)
            
            # 添加有内容的视觉提示（保持全局样式基础上的微调）
            current_style = self.training_notes_btn.styleSheet()
            self.training_notes_btn.setStyleSheet(current_style + """
                QPushButton {
                    background-color: #e3f2fd;
                    border: 1px solid #2196f3;
                }
            """)
        else:
            # 使用全局样式管理器重置按钮
            TextButtonStyleManager.updateButtonText(self.training_notes_btn, "训练笔记")
    
    def enableNotesButtons(self):
        """启用笔记按钮（训练完成后调用）"""
        # 训练笔记按钮始终可用，无需特殊处理
        pass
    
    def disableNotesButtons(self):
        """禁用笔记按钮（训练开始前调用）"""
        # 训练笔记按钮始终可用，无需特殊处理
        pass
    
    @QtCore.Slot(str)
    def appendLog(self, text):
        """追加日志（线程安全，使用装饰器确保可以从信号调用）
        
        支持进度条单行实时更新和每轮换行：
        - 如果文本包含 __PROGRESS_BAR__ 标记，则更新最后一行而不是追加新行（实时更新）
        - 如果文本包含 __PROGRESS_BAR_COMPLETE__ 标记（100%），则保留这一行并换行（一轮完成）
        - 这样可以实现进度条的单行实时更新，每轮训练完成后换行显示下一轮
        """
        try:
            import re
            
            
            # 检查是否是完成的进度条行（100%，需要换行）
            if "__PROGRESS_BAR_COMPLETE__" in text:
                # 移除标记
                progress_text = text.replace("__PROGRESS_BAR_COMPLETE__", "")
                progress_text = progress_text.rstrip('\n\r')
                
                if not progress_text.strip():
                    return
                
                # 获取当前文档和光标
                cursor = self.train_log_text.textCursor()
                document = self.train_log_text.document()
                
                # 移动到文档末尾
                cursor.movePosition(cursor.MoveOperation.End)
                
                # 检查最后一行是否是进度条行，如果是则替换它（不删除，直接替换）
                last_block = document.lastBlock()
                if last_block.isValid() and last_block.text().strip():
                    last_line_text = last_block.text()
                    # 如果最后一行包含进度条特征，则替换它
                    is_progress_line = (
                        ('%' in last_line_text and '|' in last_line_text) or  # 包含 %| 格式
                        (re.search(r'\d+/\d+', last_line_text) and '%' in last_line_text)  # 包含 epoch/batch 和 %
                    )
                    
                    if is_progress_line:
                        # 🔥 关键修复：只替换最后一行的内容，不删除整行
                        # 这样可以保留之前的所有训练信息
                        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
                        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.insertText(progress_text + "\n")  # 替换为完成的进度条，并换行
                    else:
                        # 最后一行不是进度条，直接追加新行
                        cursor.insertText("\n" + progress_text + "\n")
                else:
                    # 文档为空或最后一行为空，直接插入
                    cursor.insertText(progress_text + "\n")
                
                # 更新光标位置并滚动到底部
                self.train_log_text.setTextCursor(cursor)
            
            # 检查是否是普通进度条行（需要单行实时更新）
            elif "__PROGRESS_BAR__" in text:
                # 移除标记
                progress_text = text.replace("__PROGRESS_BAR__", "")
                progress_text = progress_text.rstrip('\n\r')
                
                if not progress_text.strip():
                    return
                
                # 获取当前文档
                document = self.train_log_text.document()
                last_block = document.lastBlock()
                
                # 检查最后一行是否是进度条行
                if last_block.isValid() and last_block.text().strip():
                    last_line_text = last_block.text()
                    # 如果最后一行包含进度条特征（%| 格式或 epoch/batch 格式），则替换它
                    is_progress_line = ('%|' in last_line_text or 
                                       (re.search(r'\d+/\d+', last_line_text) and '%' in last_line_text))
                    
                    if is_progress_line:
                        # 🔥 关键修复：使用 QTextCursor 在同一行进行原地替换
                        # 这样不会产生新行，而是真正地覆盖最后一行
                        cursor = QtGui.QTextCursor(last_block)  # QtGui 已在顶部导入
                        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
                        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.insertText(progress_text)
                        # 不更新光标位置，保持在最后一行
                    else:
                        # 最后一行不是进度条，直接追加新行
                        cursor = self.train_log_text.textCursor()
                        cursor.movePosition(cursor.MoveOperation.End)
                        cursor.insertText("\n" + progress_text)
                        self.train_log_text.setTextCursor(cursor)
                else:
                    # 文档为空或最后一行为空，直接插入
                    cursor = self.train_log_text.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    cursor.insertText(progress_text)
                    self.train_log_text.setTextCursor(cursor)
            else:
                # 普通日志，正常追加
                self.train_log_text.insertPlainText(text)
            
            # 自动滚动到底部（如果启用）
            if hasattr(self, 'auto_scroll_check') and self.auto_scroll_check.isChecked():
                scrollbar = self.train_log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            # 避免在日志输出时出错导致递归
            import sys
            if hasattr(sys, '__stderr__'):
                try:
                    sys.__stderr__.write(f"[ERROR] appendLog failed: {e}\n")
                except:
                    pass
    
    def clearLog(self):
        """清空日志"""
        self.train_log_text.clear()
        self.train_log_text.setPlainText("日志已清空\n等待开始升级...")
    
    def setStatus(self, text, color="#28a745"):
        """设置状态"""
        self.status_label.setText(f"状态: {text}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10pt;
                font-weight: bold;
                color: {color};
                padding: 5px 15px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
            }}
        """)
    
    def _onStopOrContinueClicked(self):
        """处理停止/继续按钮点击"""
        if self._is_training_stopped:
            # 当前是"继续训练"模式，发送继续训练信号
            self.continueTrainingClicked.emit()
            self._is_training_stopped = False
            self.switchToStopMode()
        else:
            # 当前是"停止升级"模式，发送停止训练信号
            self.stopTrainingClicked.emit()
    
    def switchToContinueMode(self, training_path=None):
        """切换到继续训练模式（使用系统默认样式）"""
        
        self._is_training_stopped = True
        self._last_training_path = training_path
        
        # 修改按钮文本，使用系统默认样式
        self.stop_train_btn.setText("继续训练")
        self.stop_train_btn.setStyleSheet("")  # 清除样式，恢复系统默认
        
        # 强制启用继续训练按钮，禁用开始训练按钮
        self.stop_train_btn.setEnabled(True)
        self.start_train_btn.setEnabled(False)
        
        # 强制刷新按钮显示
        self.stop_train_btn.update()
        self.start_train_btn.update()
    
    def switchToStopMode(self):
        """切换到停止升级模式（使用系统默认样式）"""
        self._is_training_stopped = False
        
        # 恢复按钮文本，使用系统默认样式
        self.stop_train_btn.setText("停止升级")
        self.stop_train_btn.setStyleSheet("")  # 清除样式，恢复系统默认
    
    def setTrainingState(self, is_training):
        """设置训练状态"""
        if not self._is_training_stopped:
            self.start_train_btn.setEnabled(not is_training)
            self.stop_train_btn.setEnabled(is_training)
        
        # 禁用参数输入
        self.base_model_combo.setEnabled(not is_training)
        self.dataset_folders_list.setEnabled(not is_training)
        self.add_dataset_btn.setEnabled(not is_training)
        self.remove_dataset_btn.setEnabled(not is_training)
        self.clear_dataset_btn.setEnabled(not is_training)
        self.exp_name_edit.setEnabled(not is_training)
        self.epochs_spin.setEnabled(not is_training)
        self.batch_spin.setEnabled(not is_training)
        self.imgsz_spin.setEnabled(not is_training)
        self.workers_spin.setEnabled(not is_training)
        self.device_combo.setEnabled(not is_training)
        self.optimizer_combo.setEnabled(not is_training)
        self.cache_check.setEnabled(not is_training)
        self.resume_check.setEnabled(not is_training)
    
    def showEvent(self, event):
        """页面显示时刷新模型列表和测试文件列表（确保与模型集管理页面同步）"""
        super(TrainingPage, self).showEvent(event)
        self._loadBaseModelOptions()  # 🔥 加载基础模型列表
        self._loadTestModelOptions()
        # self._loadTestFileList()  # 🔥 不再需要刷新测试文件列表（改用浏览方式）
    
    def _loadBaseModelOptions(self):
        """从detection_model目录加载基础模型选项"""
        # 使用统一的模型刷新方法
        self.refreshModelLists()
    
    def _loadTestModelOptions(self):
        """加载测试模型选项（从 detection_model 文件夹读取，与模型集管理页面同步）"""
        
        # 清空现有选项
        self.test_model_combo.clear()
        
        try:
            from ...database.config import get_project_root
            project_root = get_project_root()
        except ImportError as e:
            # 如果导入失败，使用相对路径
            project_root = Path(__file__).parent.parent.parent
        
        # 🔥 修改：从 detection_model 目录扫描模型，与模型集管理页面同步
        all_models = self._scanDetectionModelDirectory(project_root)
        
        # 添加到下拉框
        if not all_models:
            self.test_model_combo.addItem("未找到测试模型")
            return
        
        # 获取记忆的测试模型路径
        remembered_model = self._getRememberedTestModel(project_root)
        
        default_index = 0
        
        # 添加所有模型到下拉框
        for idx, model in enumerate(all_models):
            display_name = model['name']
            model_path = model['path']
            
            # 如果找到记忆的模型，设置为默认选择
            if remembered_model and model_path == remembered_model:
                default_index = idx
                display_name = f"{display_name} (上次使用)"
            
            self.test_model_combo.addItem(display_name, model_path)
        
        # 设置默认选择
        self.test_model_combo.setCurrentIndex(default_index)
    
    def _loadModelsFromConfig(self, project_root):
        """从配置文件加载通道模型"""
        models = []
        try:
            import yaml
            config_path = Path(project_root) / "database" / "config" / "default_config.yaml"
            
            if not config_path.exists():
                return models
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 遍历 channel1-4
            for i in range(1, 5):
                model_path = None
                channel_name = None
                
                # 尝试从根级别读取
                channel_model_key = f'channel{i}_model_path'
                if channel_model_key in config:
                    model_path = config[channel_model_key]
                
                # 尝试从通道配置字典读取
                channel_key = f'channel{i}'
                if channel_key in config and isinstance(config[channel_key], dict):
                    channel_config = config[channel_key]
                    if not model_path:
                        model_path = channel_config.get('model_path')
                    channel_name = channel_config.get('name', f'通道{i}')
                else:
                    channel_name = f'通道{i}'
                
                # 检查模型路径是否存在
                if model_path and os.path.exists(model_path):
                    models.append({
                        'name': f"{channel_name}模型",
                        'path': model_path,
                        'source': 'config',
                        # 🔥 关键修复：不在这里设置is_default，让_loadTestModelOptions中的逻辑决定
                        # 'is_default': i == 1  # 删除这行，避免与default_model字段冲突
                    })
        
        except Exception as e:
            pass
        
        return models
    
    def _scanDetectionModelDirectory(self, project_root):
        """扫描 detection_model 目录获取所有测试模型文件（增强版：按优先级选择模型）"""
        models = []
        
        try:
            import yaml
            # 🔥 修改：从 detection_model 文件夹读取，与模型集管理页面同步
            model_dir = Path(project_root) / "database" / "model" / "detection_model"
            
            if not model_dir.exists():
                return models
            
            # 扫描所有子目录（数字和非数字）
            all_subdirs = [d for d in model_dir.iterdir() if d.is_dir()]
            
            # 分离数字目录和非数字目录
            digit_subdirs = [d for d in all_subdirs if d.name.isdigit()]
            non_digit_subdirs = [d for d in all_subdirs if not d.name.isdigit()]
            
            # 数字目录按数字降序排序，非数字目录按字母排序
            sorted_digit_subdirs = sorted(digit_subdirs, key=lambda x: int(x.name), reverse=True)
            sorted_non_digit_subdirs = sorted(non_digit_subdirs, key=lambda x: x.name)
            
            # 合并：数字目录在前，非数字目录在后
            sorted_subdirs = sorted_digit_subdirs + sorted_non_digit_subdirs
            
            for subdir in sorted_subdirs:
                
                # 检查是否有weights子目录（优先检查train/weights，然后weights）
                train_weights_dir = subdir / "train" / "weights"
                weights_dir = subdir / "weights"
                
                if train_weights_dir.exists():
                    search_dir = train_weights_dir
                elif weights_dir.exists():
                    search_dir = weights_dir
                else:
                    search_dir = subdir
                
                # 按优先级查找模型文件：best > last > epoch1
                # 支持的扩展名：.dat, .pt, .template_*, .engine, .onnx, 无扩展名
                selected_model = None
                
                # 优先级1: best模型
                for file in search_dir.iterdir():
                    if file.is_file() and file.name.startswith('best.') and not file.name.endswith('.pt'):
                        selected_model = file
                        break
                
                # 优先级2: last模型（如果没有best）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.startswith('last.') and not file.name.endswith('.pt'):
                            selected_model = file
                            break
                
                # 优先级3: epoch1模型（如果没有best和last）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.startswith('epoch1.') and not file.name.endswith('.pt'):
                            selected_model = file
                            break
                
                # 优先级4: 查找.engine文件（TensorRT模型）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.endswith('.engine'):
                            selected_model = file
                            break
                
                # 优先级5: 查找.onnx文件
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.endswith('.onnx'):
                            selected_model = file
                            break
                
                # 如果都没找到，尝试查找任何非.pt文件
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and not file.name.endswith('.pt') and not file.name.endswith('.txt') and not file.name.endswith('.yaml'):
                            selected_model = file
                            break
                
                # 如果找到了模型文件，添加到列表
                if selected_model:
                    # 使用"文件夹名称/模型文件名"格式，与模型集管理页面保持一致
                    model_name = f"{subdir.name}/{selected_model.stem}"
                    description = f"来自目录 {subdir.name}"
                    training_date = ''
                    epochs = ''
                    
                    # 获取文件格式
                    file_ext = selected_model.suffix.lstrip('.')
                    if not file_ext:
                        # 处理无扩展名的情况（如 best.template_6543）
                        if '.' in selected_model.name:
                            file_ext = selected_model.name.split('.')[-1]
                        else:
                            file_ext = 'unknown'
                    
                    model_info = {
                        'name': model_name,
                        'path': str(selected_model),
                        'subdir': subdir.name,
                        'source': 'detection_model',
                        'format': file_ext,
                        'description': description,
                        'training_date': training_date,
                        'epochs': epochs,
                        'file_name': selected_model.name
                    }
                    models.append(model_info)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return models
    
    def _loadTestFileList(self):
        """加载测试文件列表（保留方法以保持向后兼容，但现在使用浏览方式）"""
        # 该方法现已改为使用浏览按钮选择文件，不再从固定目录加载
        # 保留此方法以防其他代码调用
        pass
    
    def _getRememberedTestModel(self, project_root):
        """从配置文件获取记忆的测试模型路径"""
        try:
            import yaml
            config_path = Path(project_root) / "database" / "config" / "default_config.yaml"
            
            if not config_path.exists():
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            remembered = config.get('test_model_memory')
            return remembered
            
        except Exception as e:
            return None
    
    def _saveTestModelMemory(self, model_path):
        """保存当前选择的测试模型到配置文件"""
        try:
            import yaml
            from ...database.config import get_project_root
            
            project_root = get_project_root()
            config_path = Path(project_root) / "database" / "config" / "default_config.yaml"
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            config['test_model_memory'] = model_path
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
        except Exception as e:
            pass
    
    def getSelectedTestModel(self):
        """获取选中的测试模型路径"""
        model_path = self.test_model_combo.currentData()
        
        # 🔥 关键修复：选择模型时自动保存到配置文件
        if model_path:
            self._saveTestModelMemory(model_path)
        
        return model_path
    
    def getTestFilePath(self):
        """获取选中的测试文件路径"""
        # 从 QLineEdit 获取文件路径
        return self.test_file_input.text().strip()
    
    def isTestingInProgress(self):
        """检查是否正在测试中"""
        return self._is_testing
    
    def setTestButtonState(self, is_testing):
        """设置测试按钮状态（开始测试 <-> 停止测试）"""
        self._is_testing = is_testing
        
        if is_testing:
            # 切换为"停止测试"状态
            TextButtonStyleManager.updateButtonText(self.start_test_btn, "停止测试")
            # 使用全局样式管理器的危险按钮样式
            TextButtonStyleManager.applyDangerStyle(self.start_test_btn)
        else:
            # 切换为"开始测试"状态
            TextButtonStyleManager.updateButtonText(self.start_test_btn, "开始测试")
            # 恢复标准样式
            TextButtonStyleManager.applyStandardStyle(self.start_test_btn)
    
    def _onTemplateChecked(self, button):
        """处理模板复选框选中事件"""
        template_num = self.template_button_group.id(button)
        
        # 加载并应用模板配置
        self._loadTemplateConfig(template_num)
    
    def _loadTemplateConfig(self, template_num):
        """从YAML文件加载模板配置"""
        import yaml
        
        # 获取项目根目录
        try:
            project_root = Path(__file__).parent.parent.parent
        except:
            project_root = Path.cwd()
        
        config_path = project_root / "database" / "config" / "train_configs" / f"template_{template_num}.yaml"
        
        if not config_path.exists():
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self._applyTemplateConfig(config, template_num)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _applyTemplateConfig(self, config, template_num):
        """应用模板配置到UI控件"""
        try:
            # 基础模型
            if 'model' in config:
                model_path = str(config['model'])
                # 在下拉菜单中查找匹配的模型
                for i in range(self.base_model_combo.count()):
                    item_data = self.base_model_combo.itemData(i)
                    if item_data and item_data == model_path:
                        self.base_model_combo.setCurrentIndex(i)
                        print(f"[模板] 设置基础模型: {model_path}")
                        break
            
            # 数据集配置 - 跳过，使用用户在UI中配置的数据集文件夹
            # 模板不再覆盖数据集配置，保持用户选择的数据集文件夹
            if 'data' in config:
                print(f"[模板] 跳过数据集配置，使用用户配置的数据集文件夹")
            
            # 实验名称
            if 'name' in config:
                self.exp_name_edit.setText(str(config['name']))
                print(f"[模板] 设置实验名称: {config['name']}")
            
            # 训练轮数
            if 'epochs' in config:
                self.epochs_spin.setValue(int(config['epochs']))
                print(f"[模板] 设置训练轮数: {config['epochs']}")
            
            # 批次大小
            if 'batch' in config:
                self.batch_spin.setValue(int(config['batch']))
                print(f"[模板] 设置批次大小: {config['batch']}")
            
            # 图像尺寸
            if 'imgsz' in config:
                self.imgsz_spin.setValue(int(config['imgsz']))
                print(f"[模板] 设置图像尺寸: {config['imgsz']}")
            
            # 工作线程数
            if 'workers' in config:
                self.workers_spin.setValue(int(config['workers']))
                print(f"[模板] 设置工作线程数: {config['workers']}")
            
            # 设备选择
            if 'device' in config:
                device_text = str(config['device']).upper()
                index = self.device_combo.findText(device_text)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                    print(f"[模板] 设置设备: {device_text}")
            
            # 优化器
            if 'optimizer' in config:
                optimizer_text = str(config['optimizer'])
                index = self.optimizer_combo.findText(optimizer_text)
                if index >= 0:
                    self.optimizer_combo.setCurrentIndex(index)
                    print(f"[模板] 设置优化器: {optimizer_text}")
            
            # 缓存选项
            if 'cache' in config:
                self.cache_check.setChecked(bool(config['cache']))
                print(f"[模板] 设置缓存: {config['cache']}")
            
            # 恢复训练
            if 'resume' in config:
                self.resume_check.setChecked(bool(config['resume']))
                print(f"[模板] 设置恢复训练: {config['resume']}")
            
            print(f"[模板] [成功] 模板{template_num}配置已成功应用到UI")
            
        except Exception as e:
            print(f"[模板] [错误] 应用配置失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _browseTestFile(self):
        """浏览选择测试文件（支持图片和视频）"""
        try:
            # 定义支持的文件类型
            image_formats = "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.webp)"
            video_formats = "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv)"
            all_formats = "所有支持的文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.webp *.mp4 *.avi *.mov *.mkv *.flv *.wmv)"
            
            # 构建文件过滤器
            file_filter = f"{all_formats};;{image_formats};;{video_formats};;所有文件 (*.*)"
            
            # 打开文件选择对话框
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "选择测试图片或视频文件",
                "",  # 默认目录为空，使用系统默认
                file_filter
            )
            
            # 如果用户选择了文件，则设置到输入框
            if file_path:
                self.test_file_input.setText(file_path)
                print(f"[测试文件] 已选择: {file_path}")
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(
                self,
                "文件选择失败",
                f"选择测试文件时发生错误：\n{str(e)}"
            )
    
    def _onViewCurveClicked(self):
        """查看曲线按钮点击处理"""
        try:
            # 检查是否有曲线数据
            if not hasattr(self, 'curve_data_x') or not hasattr(self, 'curve_data_y'):
                self._showNoCurveMessage()
                return
            
            if len(self.curve_data_x) == 0:
                self._showNoCurveMessage()
                return
            
            # 在当前测试页面中显示曲线，而不是切换面板
            self._showCurveInTestPage()
            
            # 显示曲线信息提示
            data_count = len(self.curve_data_x)
            if data_count == 1:
                # 图片测试
                liquid_level = self.curve_data_y[0]
                QtWidgets.QMessageBox.information(
                    self,
                    "曲线信息",
                    f"图片测试结果：\n液位高度: {liquid_level:.1f} mm\n\n"
                    f"曲线已显示在左侧测试页面中。"
                )
            else:
                # 视频测试
                min_level = min(self.curve_data_y)
                max_level = max(self.curve_data_y)
                avg_level = sum(self.curve_data_y) / len(self.curve_data_y)
                QtWidgets.QMessageBox.information(
                    self,
                    "曲线信息", 
                    f"视频测试结果：\n"
                    f"数据点数: {data_count} 个\n"
                    f"液位范围: {min_level:.1f} - {max_level:.1f} mm\n"
                    f"平均液位: {avg_level:.1f} mm\n\n"
                    f"曲线已显示在左侧测试页面中。"
                )
        
        except Exception as e:
            print(f"[查看曲线] 显示曲线失败: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "显示失败",
                f"显示曲线时发生错误：\n{str(e)}"
            )
    
    def _showCurveInTestPage(self):
        """在测试页面中显示曲线"""
        try:
            print(f"[曲线显示] 开始显示曲线，PyQtGraph可用: {PYQTGRAPH_AVAILABLE}")
            
            # 检查曲线数据
            if not hasattr(self, 'curve_data_x') or not hasattr(self, 'curve_data_y'):
                print("[曲线显示] 错误: 缺少曲线数据属性")
                self._showCurveAsText()
                return
            
            if len(self.curve_data_x) == 0 or len(self.curve_data_y) == 0:
                print(f"[曲线显示] 错误: 曲线数据为空，X数据点: {len(self.curve_data_x)}, Y数据点: {len(self.curve_data_y)}")
                self._showCurveAsText()
                return
            
            print(f"[曲线显示] 曲线数据检查通过，数据点数: {len(self.curve_data_x)}")
            
            if not PYQTGRAPH_AVAILABLE:
                print("[曲线显示] PyQtGraph不可用，使用文本显示")
                self._showCurveAsText()
                return
            
            # 生成曲线图表的HTML内容
            print("[曲线显示] 开始生成HTML内容")
            curve_html = self._generateCurveHTML()
            
            if not curve_html:
                print("[曲线显示] 错误: HTML内容生成失败")
                self._showCurveAsText()
                return
            
            # 在显示面板中显示曲线HTML
            if hasattr(self, 'display_panel') and hasattr(self, 'display_layout'):
                self.display_panel.setHtml(curve_html)
                self.display_layout.setCurrentWidget(self.display_panel)
                print("[曲线显示] 曲线已显示在测试页面中")
            else:
                print("[曲线显示] 错误: 缺少display_panel或display_layout属性")
                self._showCurveAsText()
        
        except Exception as e:
            print(f"[曲线显示] 在测试页面显示曲线失败: {e}")
            import traceback
            traceback.print_exc()
            # 降级到文本显示
            self._showCurveAsText()
    
    def _generateCurveHTML(self):
        """生成曲线的HTML内容"""
        try:
            print("[曲线HTML] 开始生成HTML内容")
            
            # 保存曲线图片到临时文件
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            curve_image_path = os.path.join(temp_dir, "test_curve_display.png")
            print(f"[曲线HTML] 临时图片路径: {curve_image_path}")
            
            # 优先尝试使用matplotlib生成曲线（更可靠）
            if self._createMatplotlibCurve(curve_image_path):
                print("[曲线HTML] matplotlib曲线生成成功")
            # 使用PyQtGraph导出曲线图片
            elif hasattr(self, 'curve_plot_widget') and self.curve_plot_widget:
                print("[曲线HTML] 使用现有的curve_plot_widget导出图片")
                try:
                    # 使用样式管理器的配置
                    from widgets.style_manager import CurveDisplayStyleManager
                    chart_width, chart_height = CurveDisplayStyleManager.getChartSize()
                    
                    exporter = pg.exporters.ImageExporter(self.curve_plot_widget.plotItem)
                    exporter.parameters()['width'] = chart_width
                    exporter.parameters()['height'] = chart_height
                    exporter.export(curve_image_path)
                    print("[曲线HTML] 现有widget图片导出成功")
                except Exception as e:
                    print(f"[曲线HTML] 现有widget图片导出失败: {e}")
                    self._createTempCurvePlot(curve_image_path)
            else:
                print("[曲线HTML] 没有现有的curve_plot_widget，创建临时plot")
                # 如果没有现有的plot widget，创建一个临时的
                self._createTempCurvePlot(curve_image_path)
            
            # 检查图片是否成功生成
            if not os.path.exists(curve_image_path):
                print(f"[曲线HTML] 错误: 图片文件未生成: {curve_image_path}")
                return self._getFallbackCurveHTML()
            
            print(f"[曲线HTML] 图片生成成功，文件大小: {os.path.getsize(curve_image_path)} bytes")
            
            # 生成统计信息
            data_count = len(self.curve_data_x)
            stats_html = ""
            
            if data_count == 1:
                # 图片测试
                liquid_level = self.curve_data_y[0]
                stats_html = f"""
                <div style="margin-bottom: 15px; padding: 10px; background: #e8f4fd; border: 1px solid #bee5eb; border-radius: 5px;">
                    <h4 style="margin: 0 0 8px 0; color: #0c5460;">图片测试结果</h4>
                    <p style="margin: 0; color: #0c5460;"><strong>液位高度:</strong> {liquid_level:.1f} mm</p>
                </div>
                """
            else:
                # 视频测试
                min_level = min(self.curve_data_y)
                max_level = max(self.curve_data_y)
                avg_level = sum(self.curve_data_y) / len(self.curve_data_y)
                stats_html = f"""
                <div style="margin-bottom: 15px; padding: 10px; background: #e8f4fd; border: 1px solid #bee5eb; border-radius: 5px;">
                    <h4 style="margin: 0 0 8px 0; color: #0c5460;">视频测试结果统计</h4>
                    <p style="margin: 2px 0; color: #0c5460;"><strong>数据点数:</strong> {data_count} 个</p>
                    <p style="margin: 2px 0; color: #0c5460;"><strong>液位范围:</strong> {min_level:.1f} - {max_level:.1f} mm</p>
                    <p style="margin: 2px 0; color: #0c5460;"><strong>平均液位:</strong> {avg_level:.1f} mm</p>
                </div>
                """
            
            # 使用统一的样式管理器生成HTML内容
            from widgets.style_manager import CurveDisplayStyleManager
            html_content = CurveDisplayStyleManager.generateCurveHTML(curve_image_path, stats_html)
            
            return html_content
            
        except Exception as e:
            print(f"[曲线HTML] 生成HTML失败: {e}")
            return self._getFallbackCurveHTML()
    
    def _createMatplotlibCurve(self, output_path):
        """使用matplotlib创建曲线图"""
        try:
            print("[matplotlib曲线] 开始使用matplotlib生成曲线")
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # 使用非交互式后端
            
            # 验证数据
            if not hasattr(self, 'curve_data_x') or not hasattr(self, 'curve_data_y'):
                print("[matplotlib曲线] 错误: 缺少曲线数据")
                return False
            
            if len(self.curve_data_x) == 0 or len(self.curve_data_y) == 0:
                print(f"[matplotlib曲线] 错误: 曲线数据为空")
                return False
            
            print(f"[matplotlib曲线] 数据验证通过，X点数: {len(self.curve_data_x)}, Y点数: {len(self.curve_data_y)}")
            
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 使用样式管理器的配置
            from widgets.style_manager import CurveDisplayStyleManager
            chart_width, chart_height = CurveDisplayStyleManager.getChartSize()
            chart_dpi = CurveDisplayStyleManager.getChartDPI()
            bg_color = CurveDisplayStyleManager.getPlotBackgroundColor()
            
            # 创建图形，使用统一的尺寸和DPI
            fig, ax = plt.subplots(figsize=(chart_width/100, chart_height/100), dpi=chart_dpi)
            
            # 绘制曲线
            ax.plot(self.curve_data_x, self.curve_data_y, 'b-', linewidth=2.5, marker='o', markersize=5, 
                   markerfacecolor='white', markeredgecolor='blue', markeredgewidth=1.5)
            
            # 设置标签和标题
            ax.set_xlabel('帧序号', fontsize=12)
            ax.set_ylabel('液位高度 (mm)', fontsize=12)
            ax.set_title('液位检测曲线', fontsize=14, fontweight='bold', pad=20)
            
            # 设置网格
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # 设置背景色，使用样式管理器的颜色
            ax.set_facecolor(bg_color)
            fig.patch.set_facecolor(bg_color)
            
            # 优化布局，减少边距
            plt.tight_layout(pad=1.0)
            
            # 保存图片，优化参数
            plt.savefig(output_path, 
                       bbox_inches='tight', 
                       pad_inches=0.2, 
                       facecolor=bg_color,
                       edgecolor='none',
                       dpi=100)
            plt.close(fig)
            
            print(f"[matplotlib曲线] 曲线图片已保存: {output_path}")
            return True
            
        except Exception as e:
            print(f"[matplotlib曲线] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _createTempCurvePlot(self, output_path):
        """创建临时曲线图并保存"""
        try:
            print("[临时曲线] 开始创建临时曲线图")
            import pyqtgraph as pg
            
            # 验证数据
            if not hasattr(self, 'curve_data_x') or not hasattr(self, 'curve_data_y'):
                print("[临时曲线] 错误: 缺少曲线数据")
                self._createPlaceholderImage(output_path)
                return
            
            if len(self.curve_data_x) == 0 or len(self.curve_data_y) == 0:
                print(f"[临时曲线] 错误: 曲线数据为空")
                self._createPlaceholderImage(output_path)
                return
            
            print(f"[临时曲线] 数据验证通过，X点数: {len(self.curve_data_x)}, Y点数: {len(self.curve_data_y)}")
            
            # 创建临时的plot widget
            temp_plot = pg.PlotWidget()
            temp_plot.setBackground('#f8f9fa')
            temp_plot.showGrid(x=True, y=True, alpha=0.3)
            temp_plot.setLabel('left', '液位高度', units='mm')
            temp_plot.setLabel('bottom', '帧序号')
            temp_plot.setTitle('液位检测曲线', color='#495057', size='12pt')
            
            print("[临时曲线] PlotWidget创建成功，开始绘制曲线")
            
            # 绘制曲线
            temp_plot.plot(
                self.curve_data_x, 
                self.curve_data_y,
                pen=pg.mkPen(color='#1f77b4', width=2),
                name='液位高度'
            )
            
            print("[临时曲线] 曲线绘制完成，开始导出图片")
            
            # 使用样式管理器的配置导出图片
            from widgets.style_manager import CurveDisplayStyleManager
            chart_width, chart_height = CurveDisplayStyleManager.getChartSize()
            bg_color = CurveDisplayStyleManager.getPlotBackgroundColor()
            
            # 导出图片（使用统一尺寸）
            exporter = pg.exporters.ImageExporter(temp_plot.plotItem)
            exporter.parameters()['width'] = chart_width
            exporter.parameters()['height'] = chart_height
            # 设置背景色
            temp_plot.setBackground(bg_color)
            exporter.export(output_path)
            
            print(f"[临时曲线] 曲线图片已保存: {output_path}")
            
        except Exception as e:
            print(f"[临时曲线] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            # 创建一个简单的占位图片
            self._createPlaceholderImage(output_path)
    
    def _createPlaceholderImage(self, output_path):
        """创建占位图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import matplotlib.pyplot as plt
            import numpy as np
            
            # 如果有曲线数据，尝试用matplotlib绘制
            if hasattr(self, 'curve_data_x') and hasattr(self, 'curve_data_y') and len(self.curve_data_x) > 0:
                print("[占位图片] 尝试使用matplotlib绘制曲线")
                try:
                    plt.figure(figsize=(10, 5), dpi=80)
                    plt.plot(self.curve_data_x, self.curve_data_y, 'b-', linewidth=2, marker='o', markersize=4)
                    plt.xlabel('帧序号')
                    plt.ylabel('液位高度 (mm)')
                    plt.title('液位检测曲线')
                    plt.grid(True, alpha=0.3)
                    plt.tight_layout()
                    plt.savefig(output_path, bbox_inches='tight', pad_inches=0.1, facecolor='#f8f9fa')
                    plt.close()
                    print(f"[占位图片] matplotlib曲线已保存: {output_path}")
                    return
                except Exception as e:
                    print(f"[占位图片] matplotlib绘制失败: {e}")
            
            # 创建简化的占位图片（更小的尺寸，减少白色背景）
            img = Image.new('RGB', (600, 300), '#f8f9fa')
            draw = ImageDraw.Draw(img)
            
            # 绘制边框
            draw.rectangle([0, 0, 599, 299], outline='#dee2e6', width=1)
            
            # 绘制文本
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
            except:
                font = ImageFont.load_default()
            
            text = "曲线生成失败，请检查数据"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (600 - text_width) // 2
            y = (300 - text_height) // 2
            draw.text((x, y), text, fill='#666666', font=font)
            
            img.save(output_path)
            print(f"[占位图片] 已创建: {output_path}")
            
        except Exception as e:
            print(f"[占位图片] 创建失败: {e}")
    
    def _getFallbackCurveHTML(self):
        """获取降级的曲线HTML内容"""
        data_count = len(self.curve_data_x)
        
        if data_count == 1:
            liquid_level = self.curve_data_y[0]
            return f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; background: #ffffff; color: #333333;">
                <h3>图片测试结果</h3>
                <p><strong>液位高度:</strong> {liquid_level:.1f} mm</p>
                <p style="color: #666; font-size: 12px;">注: 曲线图表生成失败，显示文本结果。</p>
            </div>
            """
        else:
            min_level = min(self.curve_data_y)
            max_level = max(self.curve_data_y)
            avg_level = sum(self.curve_data_y) / len(self.curve_data_y)
            return f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; background: #ffffff; color: #333333;">
                <h3>视频测试结果统计</h3>
                <p><strong>数据点数:</strong> {data_count} 个</p>
                <p><strong>液位范围:</strong> {min_level:.1f} - {max_level:.1f} mm</p>
                <p><strong>平均液位:</strong> {avg_level:.1f} mm</p>
                <p style="color: #666; font-size: 12px;">注: 曲线图表生成失败，显示文本结果。</p>
            </div>
            """
    
    def _showCurveAsText(self):
        """以文本形式显示曲线结果"""
        try:
            fallback_html = self._getFallbackCurveHTML()
            if hasattr(self, 'display_panel') and hasattr(self, 'display_layout'):
                self.display_panel.setHtml(fallback_html)
                self.display_layout.setCurrentWidget(self.display_panel)
                print("[曲线显示] 以文本形式显示曲线结果")
        except Exception as e:
            print(f"[曲线显示] 文本显示也失败: {e}")
    
    def _showNoCurveMessage(self):
        """显示无曲线数据的提示"""
        QtWidgets.QMessageBox.information(
            self,
            "无曲线数据",
            "当前没有可显示的曲线数据。\n\n"
            "请先进行模型测试：\n"
            "1. 选择测试模型\n"
            "2. 选择测试文件\n" 
            "3. 点击\"开始标注\"\n"
            "4. 点击\"开始测试\"\n\n"
            "测试完成后即可查看曲线结果。"
        )
    
    def _testCurveGeneration(self):
        """测试曲线生成功能（调试用）"""
        try:
            print("[曲线测试] 开始测试曲线生成功能")
            
            # 创建测试数据
            self.curve_data_x = [0, 1, 2, 3, 4]
            self.curve_data_y = [25.0, 26.5, 24.8, 27.2, 25.9]
            
            print(f"[曲线测试] 测试数据创建完成，X: {self.curve_data_x}, Y: {self.curve_data_y}")
            
            # 测试曲线显示
            self._showCurveInTestPage()
            
        except Exception as e:
            print(f"[曲线测试] 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    def enableViewCurveButton(self):
        """启用查看曲线按钮（测试完成后调用）"""
        try:
            self.view_curve_btn.setEnabled(True)
            self.view_curve_btn.setToolTip("点击查看测试结果曲线")
            
            # 检查曲线数据类型并更新按钮文本
            if hasattr(self, 'curve_data_x') and len(self.curve_data_x) > 0:
                data_count = len(self.curve_data_x)
                if data_count == 1:
                    self.view_curve_btn.setText("查看曲线(图)")
                else:
                    self.view_curve_btn.setText("查看曲线(视)")
            else:
                self.view_curve_btn.setText("查看曲线")
            
            print(f"[查看曲线] 按钮已启用，数据点数: {len(self.curve_data_x) if hasattr(self, 'curve_data_x') else 0}")
        
        except Exception as e:
            print(f"[查看曲线] 启用按钮失败: {e}")
    
    def disableViewCurveButton(self):
        """禁用查看曲线按钮（测试开始前调用）"""
        try:
            self.view_curve_btn.setEnabled(False)
            self.view_curve_btn.setText("查看曲线")
            self.view_curve_btn.setToolTip("测试完成后可查看曲线结果")
            print(f"[查看曲线] 按钮已禁用")
        
        except Exception as e:
            print(f"[查看曲线] 禁用按钮失败: {e}")
    
    def getTemplateConfig(self):
        """获取当前选中的模板配置名称"""
        if self.checkbox_template_1.isChecked():
            return "template_1"
        elif self.checkbox_template_2.isChecked():
            return "template_2"
        elif self.checkbox_template_3.isChecked():
            return "template_3"
        return None
    
    def refreshModelLists(self):
        """刷新模型下拉菜单列表（响应模型列表变化信号）"""
        try:
            # 导入模型集页面以获取模型列表
            from .modelset_page import ModelSetPage
            
            # 获取detection_model目录下的所有模型
            models = ModelSetPage.getDetectionModels()
            
            # 刷新基础模型下拉菜单
            if hasattr(self, 'base_model_combo'):
                current_base = self.base_model_combo.currentText()
                self.base_model_combo.clear()
                
                for model in models:
                    display_name = model['name']  # 只显示模型名称，不显示文件大小
                    self.base_model_combo.addItem(display_name, model['path'])
                
                # 尝试恢复之前的选择
                if current_base:
                    index = self.base_model_combo.findText(current_base)
                    if index >= 0:
                        self.base_model_combo.setCurrentIndex(index)
            
            # 刷新测试模型下拉菜单
            if hasattr(self, 'test_model_combo'):
                current_test = self.test_model_combo.currentText()
                self.test_model_combo.clear()
                
                for model in models:
                    display_name = model['name']  # 只显示模型名称，不显示文件大小
                    self.test_model_combo.addItem(display_name, model['path'])
                
                # 尝试恢复之前的选择
                if current_test:
                    index = self.test_model_combo.findText(current_test)
                    if index >= 0:
                        self.test_model_combo.setCurrentIndex(index)
            
        except Exception as e:
            print(f"[错误] 刷新模型列表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def connectModelListChangeSignal(self, modelset_page):
        """连接模型列表变化信号
        
        Args:
            modelset_page: ModelSetPage实例
        """
        try:
            if hasattr(modelset_page, 'modelListChanged'):
                # 连接信号到刷新方法
                modelset_page.modelListChanged.connect(self.refreshModelLists)
            else:
                print("[警告] ModelSetPage没有modelListChanged信号")
        except Exception as e:
            print(f"[错误] 连接模型列表变化信号失败: {e}")
    
    def refreshBaseModelList(self):
        """刷新基础模型下拉菜单（兼容旧接口）"""
        self.refreshModelLists()


# 测试代码
if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    page = TrainingPage()
    page.setWindowTitle("模型升级测试")
    page.resize(1200, 700)
    page.show()
    
    sys.exit(app.exec_())


class TrainingNotesDialog(QtWidgets.QDialog):
    """训练笔记编辑对话框"""
    
    def __init__(self, initial_content="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("训练笔记编辑")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        
        # 设置窗口图标（如果有的话）
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        # 应用全局样式管理器
        from ..style_manager import FontManager, BackgroundStyleManager
        BackgroundStyleManager.applyToWidget(self)
        
        self._setupUI()
        self.text_edit.setPlainText(initial_content)
        
        # 应用全局字体管理器到整个对话框
        FontManager.applyToDialog(self)
        
    def _setupUI(self):
        """设置UI界面"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题标签（使用全局字体管理器）
        from ..style_manager import FontManager
        title_label = QtWidgets.QLabel("训练笔记")
        title_label.setFont(FontManager.getTitleFont())
        title_label.setStyleSheet("""
            QLabel {
                color: #333;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title_label)
        
        # 说明文字（使用全局字体管理器）
        info_label = QtWidgets.QLabel("在此记录本次训练的相关信息，如数据集变化、参数调整原因、预期效果等...")
        info_label.setFont(FontManager.getSmallFont())
        info_label.setStyleSheet("""
            QLabel {
                color: #666;
                margin-bottom: 10px;
            }
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 文本编辑区域（使用全局字体管理器）
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setFont(FontManager.getMediumFont())
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                background-color: white;
                padding: 10px;
                line-height: 1.4;
            }
        """)
        self.text_edit.setPlaceholderText(
            "示例内容：\n"
            "• 数据集：新增了100张液位图片\n"
            "• 参数调整：学习率从0.01调整为0.005\n"
            "• 预期效果：提高小液位目标的检测精度\n"
            "• 其他备注：..."
        )
        layout.addWidget(self.text_edit)
        
        # 字符计数标签（使用全局字体管理器）
        self.char_count_label = QtWidgets.QLabel("字符数: 0")
        self.char_count_label.setFont(FontManager.getSmallFont())
        self.char_count_label.setStyleSheet("color: #666;")
        self.char_count_label.setAlignment(QtCore.Qt.AlignRight)
        layout.addWidget(self.char_count_label)
        
        # 按钮区域（使用全局样式管理器）
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        # 清空按钮
        clear_btn = TextButtonStyleManager.createStandardButton("清空", self, self._clearText)
        button_layout.addWidget(clear_btn)
        
        # 保存到模型按钮
        save_to_model_btn = TextButtonStyleManager.createStandardButton("保存到模型", self, self._saveToModel)
        save_to_model_btn.setToolTip("将笔记保存到最新训练的模型目录")
        button_layout.addWidget(save_to_model_btn)
        
        # 取消按钮
        cancel_btn = TextButtonStyleManager.createStandardButton("取消", self, self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 确定按钮（使用主要样式）
        ok_btn = TextButtonStyleManager.createPrimaryButton("确定", self, self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.text_edit.textChanged.connect(self._updateCharCount)
        self._updateCharCount()
        
    def _saveToModel(self):
        """保存笔记到最新训练的模型目录"""
        notes = self.text_edit.toPlainText().strip()
        if not notes:
            from ..style_manager import DialogManager
            DialogManager.show_information(self, "提示", "笔记内容为空，无需保存")
            return
        
        # 获取主窗口的训练处理器
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'model_training_handler'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'model_training_handler'):
                # 调用训练处理器的保存方法
                if main_window.model_training_handler.saveNotesToLatestModel(notes):
                    # 保存成功，清空文本框
                    self.text_edit.clear()
            else:
                from ..style_manager import DialogManager
                DialogManager.show_warning(self, "错误", "无法找到训练处理器")
        except Exception as e:
            from ..style_manager import DialogManager
            DialogManager.show_critical(self, "错误", f"保存失败:\n{str(e)}")
    
    def _clearText(self):
        """清空文本"""
        if self.text_edit.toPlainText().strip():
            from ..style_manager import DialogManager
            if DialogManager.show_question_warning(
                self,
                "确认清空",
                "确定要清空所有笔记内容吗？",
                "是", "否"
            ):
                self.text_edit.clear()
    
    def _updateCharCount(self):
        """更新字符计数"""
        text = self.text_edit.toPlainText()
        char_count = len(text)
        self.char_count_label.setText(f"字符数: {char_count}")
        
        # 字符数过多时显示警告颜色（保持全局字体设置）
        if char_count > 1000:
            self.char_count_label.setStyleSheet("color: #f44336;")
        elif char_count > 500:
            self.char_count_label.setStyleSheet("color: #ff9800;")
        else:
            self.char_count_label.setStyleSheet("color: #666;")
    
    def getNotesContent(self):
        """获取笔记内容"""
        return self.text_edit.toPlainText().strip()
    
