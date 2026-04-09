# -*- coding: utf-8 -*-

"""
通用表格视图组件

只负责UI控件设计和发送信号，业务逻辑由handler处理
提供可复用的表格显示和编辑功能
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt

# 导入图标工具（支持相对导入和独立运行）
try:
    # 从父目录（widgets）导入
    from ..style_manager import newIcon, createTextButton, applyTextButtonStyle, applyGlobalBackground
    from ..style_manager import FontManager, applyDialogFont  # 导入字体管理器
    from ..style_manager import DialogManager  # 导入对话框管理器
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h  # 导入响应式布局
except (ImportError, ValueError):
    # 独立运行时的处理
    import sys
    import os.path as osp
    # 添加父目录到路径
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from style_manager import newIcon, createTextButton, applyTextButtonStyle, applyGlobalBackground
    from style_manager import FontManager  # 导入字体管理器
    from style_manager import DialogManager  # 导入对话框管理器
    from responsive_layout import ResponsiveLayout, scale_w, scale_h  # 导入响应式布局


class MissionPanel(QtWidgets.QWidget):
    """
    任务管理表格组件（专用）
    
    专门用于任务管理，固定了列名、列宽和曲线按钮
    修改此处的配置会自动同步到所有使用的地方
    """
    
    # ========== 固定配置（修改这里即可全局同步） ==========
    DEFAULT_COLUMNS = ['任务编号', '任务名称', '状态', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '曲线']
    DEFAULT_WIDTHS = [80, 140, 70, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 50]
    CURVE_BUTTON_COLUMN = 19  # 曲线按钮所在列（使用动态曲线图标）
    CHANNEL_START_COLUMN = 3  # 通道列开始索引
    CHANNEL_COUNT = 16  # 通道数量
    # ====================================================
    
    # 自定义信号
    itemChanged = QtCore.Signal(int, int, object)  # 行、列、新值
    itemSelected = QtCore.Signal(int)  # 选中行索引
    itemDoubleClicked = QtCore.Signal(int)  # 双击行索引
    buttonClicked = QtCore.Signal(int, int)  # 按钮点击信号：行索引、列索引
    channelManageClicked = QtCore.Signal()  # 通道管理按钮点击信号
    
    #  调试按钮信号
    debugLeftClicked = QtCore.Signal()  # 左键：一键启动检测
    debugRightClicked = QtCore.Signal()  # 右键：标注配置

    # 一键启动信号
    startAllClicked = QtCore.Signal()  # 一键启动所有通道检测
    
    # 分页信号
    pageChanged = QtCore.Signal(int)  # 页码改变信号，参数为新页码
    pageSizeChanged = QtCore.Signal(int)  # 每页大小改变信号，参数为新的每页行数
    
    # 新增信号 - 用于与handler交互
    addTaskRequested = QtCore.Signal()  # 请求添加任务
    removeTaskRequested = QtCore.Signal(int)  # 请求删除任务（行索引）
    clearTableRequested = QtCore.Signal()  # 请求清空表格
    taskConfirmed = QtCore.Signal(dict)  # 任务确认信号（传递任务信息）
    taskCancelled = QtCore.Signal()  # 任务取消信号
    taskSelected = QtCore.Signal(dict)  # 任务被选中信号（传递任务信息）
    channelConfirmed = QtCore.Signal(dict)  # 通道确认信号（传递通道信息）
    channelCancelled = QtCore.Signal()  # 通道取消信号
    channelDebugRequested = QtCore.Signal(int, str)  # 通道调试信号（通道ID，地址）
    
    def __init__(self, parent=None):
        """
        初始化任务面板
        
        Args:
            parent: 父组件
        """
        super(MissionPanel, self).__init__(parent)
        self._parent = parent
        self._column_names = []  # 列名列表
        
        # 分页相关属性
        self._current_page = 1  # 当前页码（从1开始）
        self._page_size = 24  # 每页显示行数（固定为24）
        self._all_rows_data = []  # 存储所有行的数据（用于分页）
        self._filtered_rows_data = []  # 存储过滤后的数据（用于搜索）
        self._search_text = ""  # 当前搜索文本
        
        self._initUI()
        self._connectSignals()
        
        # 自动应用默认配置
        self._applyDefaultConfig()
    
    def _initUI(self):
        """初始化UI"""
        
        # 🔥 使用响应式布局替代固定宽度
        ResponsiveLayout.apply_to_widget(self, max_width=550)
        
        # 设置整体尺寸策略，避免不必要的拉伸
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        # 创建主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        #  使用 QStackedWidget 支持界面切换
        self.stacked_widget = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # === 页面1：任务列表视图 ===
        self._createTableView()
        
        # === 页面2：新建任务视图 ===
        self._createNewTaskView()
        
        # === 页面3：通道管理视图 ===
        self._createChannelManageView()
        
        # 默认显示任务列表
        self.stacked_widget.setCurrentIndex(0)
        
        # 应用全局背景颜色到整个面板
        applyGlobalBackground(self)
    
    def _createTableView(self):
        """创建任务列表视图"""
        table_page = QtWidgets.QWidget()
        # 背景色由全局背景管理器统一管理
        table_layout = QtWidgets.QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)
        
        # 设置布局的尺寸策略，避免底部留白
        table_page.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        # === 创建顶部工具栏 ===
        self._createToolbar()
        table_layout.addWidget(self.toolbar)
        
        # === 创建表格 ===
        self.table = QtWidgets.QTableWidget()
        
        # 设置表格基本属性
        self.table.setAlternatingRowColors(False)  # 统一使用白色背景，不使用交替行颜色
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)  # 整行选择
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)  # 禁用Qt默认选择
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # 默认不可编辑
        
        # 🔥 当前选中的行索引（手动管理）
        self._current_selected_row = -1
        
        # 清除所有选择样式
        self.table.setStyleSheet("""
            QTableWidget {
                selection-background-color: transparent;
                selection-color: inherit;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border: 1px solid transparent;
                padding: 2px;
            }
        """)
        
        # 🔥 启用右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._showContextMenu)
        
        # 🔥 待高亮的行索引（用于延迟高亮，等待用户确认）
        self._pending_highlight_row = None
        
        #  安装事件过滤器，处理键盘事件
        self.table.viewport().installEventFilter(self)
        
        # 设置表格的尺寸策略
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        # 设置表头
        self.table.horizontalHeader().setStretchLastSection(False)  # 禁用最后一列拉伸（因为最后一列是按钮）
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)  # 固定列宽模式
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.table.verticalHeader().setVisible(False)  # 隐藏行号
        
        # 设置默认行高（可以根据需要调整这个值）
        self.table.verticalHeader().setDefaultSectionSize(35)  # 默认行高：35像素
        
        # 禁用垂直滚动条（使用分页代替滚动），启用水平滚动条
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 🔥 计算表格内容总宽度，确保水平滚动条能正常工作
        # 列宽：80+140+70+30*16+50 = 820像素
        total_content_width = sum(self.DEFAULT_WIDTHS) + 20  # 额外边距
        self.table.setMinimumWidth(400)  # 设置最小可视宽度
        
        # 🔥 使用响应式布局计算表格高度
        # 基准高度：表头(30) + 24行*35 + 边框(4) = 874像素
        base_table_height = 30 + (self._page_size * 35) + 4
        table_height = scale_h(base_table_height)
        self.table.setMinimumHeight(table_height)
        self.table.setMaximumHeight(table_height)
        
        # 设置表格样式
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f5f5f5;
                gridline-color: #d0d0d0;
                border: 1px solid #c0c0c0;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)
        
        table_layout.addWidget(self.table)
        
        # === 创建分页控件 ===
        self._createPaginationWidget()
        table_layout.addWidget(self.pagination_widget)
        
        # 添加到 stacked_widget
        self.stacked_widget.addWidget(table_page)
    
    def _createNewTaskView(self):
        """创建新建任务视图"""
        new_task_page = QtWidgets.QWidget()
        # 背景色由全局背景管理器统一管理
        applyGlobalBackground(new_task_page)
        
        new_task_layout = QtWidgets.QVBoxLayout(new_task_page)
        new_task_layout.setContentsMargins(10, 10, 10, 10)
        new_task_layout.setSpacing(10)
        
        # === 任务编号（第一行）===
        task_id_layout = QtWidgets.QHBoxLayout()
        task_id_layout.setSpacing(0)
        
        task_id_label = QtWidgets.QLabel("任务编号：")
        # 使用全局字体管理器应用字体
        FontManager.applyToWidget(task_id_label)
        task_id_layout.addWidget(task_id_label)
        
        self.new_task_id_input = QtWidgets.QLineEdit()
        self.new_task_id_input.setFixedHeight(30)
        # 使用全局字体管理器应用字体
        FontManager.applyToWidget(self.new_task_id_input)
        task_id_layout.addWidget(self.new_task_id_input)
        
        new_task_layout.addLayout(task_id_layout)
        new_task_layout.addSpacing(5)
        
        # === 任务名称（第二行）===
        task_name_layout = QtWidgets.QHBoxLayout()
        task_name_layout.setSpacing(0)
        
        task_name_label = QtWidgets.QLabel("任务名称：")
        # 使用全局字体管理器应用字体
        FontManager.applyToWidget(task_name_label)
        task_name_layout.addWidget(task_name_label)
        
        self.new_task_name_input = QtWidgets.QLineEdit()
        self.new_task_name_input.setFixedHeight(30)
        # 使用全局字体管理器应用字体
        FontManager.applyToWidget(self.new_task_name_input)
        task_name_layout.addWidget(self.new_task_name_input)
        
        new_task_layout.addLayout(task_name_layout)
        new_task_layout.addSpacing(10)
        
        # === 使用通道（横向排列的复选框，支持16个通道）===
        channel_layout = QtWidgets.QHBoxLayout()
        channel_layout.setSpacing(0)
        
        channel_label = QtWidgets.QLabel("使用通道：")
        # 使用全局字体管理器应用字体
        FontManager.applyToWidget(channel_label)
        channel_layout.addWidget(channel_label)
        
        # 创建复选框（横向排列，8个通道）
        self.new_task_channel_checkboxes = {}
        for i in range(1, 9):
            channel_name = f"{i}"
            checkbox = QtWidgets.QCheckBox(channel_name)
            
            # 使用全局字体管理器应用字体
            FontManager.applyToWidget(checkbox)
            
            # 只设置复选框指示器样式，字体由全局管理器控制
            checkbox.setStyleSheet("""
                QCheckBox {
                    spacing: 2px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
            """)
            self.new_task_channel_checkboxes[f"通道{i}"] = checkbox
            channel_layout.addWidget(checkbox)
            
            # 在每个复选框后添加间距（最后一个除外）
            if i < 16:
                channel_layout.addSpacing(5)
        
        channel_layout.addStretch()
        
        new_task_layout.addLayout(channel_layout)
        new_task_layout.addSpacing(20)
        
        # === 确认和取消按钮（底部右对齐）===
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        # 确认按钮 - 使用全局文本按钮样式管理器
        self.new_task_confirm_btn = createTextButton("确认", parent=self, slot=self._onNewTaskConfirm)
        button_layout.addWidget(self.new_task_confirm_btn)
        
        button_layout.addSpacing(10)
        
        # 取消按钮 - 使用全局文本按钮样式管理器
        self.new_task_cancel_btn = createTextButton("取消", parent=self, slot=self._onNewTaskCancel)
        button_layout.addWidget(self.new_task_cancel_btn)
        
        new_task_layout.addLayout(button_layout)
        new_task_layout.addStretch()
        
        # 在页面创建完成后，递归应用字体管理器到所有子控件
        FontManager.applyToWidgetRecursive(new_task_page)
        
        # 添加到 stacked_widget
        self.stacked_widget.addWidget(new_task_page)
    
    def _createChannelManageView(self):
        """创建通道管理视图（支持16个通道，带滚动条）"""
        channel_page = QtWidgets.QWidget()
        # 背景色由全局背景管理器统一管理
        channel_layout = QtWidgets.QVBoxLayout(channel_page)
        channel_layout.setContentsMargins(5, 5, 5, 5)
        channel_layout.setSpacing(5)
        
        # === 创建滚动区域 ===
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 滚动区域内容容器
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(5)
        
        # === 通道地址输入区域 ===
        channels_grid = QtWidgets.QGridLayout()
        channels_grid.setContentsMargins(0, 0, 0, 0)
        channels_grid.setHorizontalSpacing(0)  # 水平间距设为0
        channels_grid.setVerticalSpacing(5)
        
        # 设置地址标签列和地址输入框列之间的间距为0
        channels_grid.setColumnMinimumWidth(2, 0)  # 地址标签列最小宽度
        
        # 创建16个通道的输入框
        self.channel_name_edits = {}  # 通道名称输入框
        self.channel_addr_edits = {}  # 地址输入框
        self.channel_file_path_edits = {}  # 文件路径输入框
        self.channel_debug_btns = {}  # 调试按钮
        
        for i in range(1, 9):
            # 通道标签
            label = QtWidgets.QLabel(f"通道{i}：")
            # 使用全局字体管理器应用字体
            FontManager.applyToWidget(label)
            # 不设置最小宽度，让标签自适应
            
            # 通道名称输入框
            name_edit = QtWidgets.QLineEdit()
            name_edit.setPlaceholderText(f"通道{i}名称")
            name_edit.setFixedWidth(80)
            name_edit.setFixedHeight(30)
            # 使用全局字体管理器应用字体
            FontManager.applyToWidget(name_edit)
            
            # 地址标签
            addr_label = QtWidgets.QLabel("地址：")
            # 使用全局字体管理器应用字体
            FontManager.applyToWidget(addr_label)
            # 设置右边距为0，确保与地址输入框紧贴
            addr_label.setContentsMargins(0, 0, 0, 0)
            addr_label.setStyleSheet("margin-right: 0px; padding-right: 0px;")
            
            # 地址输入框（改为普通文本框）
            addr_edit = QtWidgets.QLineEdit()
            addr_edit.setPlaceholderText("username:password@ip:port/stream")
            addr_edit.setMinimumWidth(200)
            addr_edit.setFixedHeight(30)
            # 使用全局字体管理器应用字体
            FontManager.applyToWidget(addr_edit)
            # 设置左边距为0，文本从最左边开始显示，垂直居中
            addr_edit.setContentsMargins(0, 0, 0, 0)
            addr_edit.setStyleSheet("""
                QLineEdit {
                    margin-left: 0px; 
                    padding-left: 2px;
                    padding-right: 2px;
                    padding-top: 0px;
                    padding-bottom: 0px;
                    text-align: left;
                    border: 1px solid #CCCCCC;
                }
            """)
            
            # 调试按钮 - 使用全局文本按钮样式管理器
            debug_btn = createTextButton("调试", parent=self, slot=lambda checked, ch=i: self._onChannelDebug(ch))
            self.channel_debug_btns[i] = debug_btn
            
            # === 添加文件路径输入行 ===
            # 文件路径标签
            file_path_label = QtWidgets.QLabel("文件：")
            FontManager.applyToWidget(file_path_label)
            file_path_label.setContentsMargins(0, 0, 0, 0)
            file_path_label.setStyleSheet("margin-right: 0px; padding-right: 0px;")
            
            # 文件路径输入框
            file_path_edit = QtWidgets.QLineEdit()
            file_path_edit.setPlaceholderText("选择本地视频文件路径")
            file_path_edit.setMinimumWidth(200)
            file_path_edit.setFixedHeight(30)
            FontManager.applyToWidget(file_path_edit)
            file_path_edit.setContentsMargins(0, 0, 0, 0)
            file_path_edit.setStyleSheet("""
                QLineEdit {
                    margin-left: 0px; 
                    padding-left: 2px;
                    padding-right: 2px;
                    padding-top: 0px;
                    padding-bottom: 0px;
                    text-align: left;
                    border: 1px solid #CCCCCC;
                }
            """)
            
            # 浏览按钮
            browse_btn = createTextButton("浏览", parent=self, slot=lambda checked, ch=i: self._onBrowseVideoFile(ch))
            
            # 添加到布局
            # 第一行：通道标签、名称、地址标签、地址输入、调试按钮
            row1 = (i - 1) * 2
            channels_grid.addWidget(label, row1, 0)
            channels_grid.addWidget(name_edit, row1, 1)
            channels_grid.addWidget(addr_label, row1, 2)
            channels_grid.addWidget(addr_edit, row1, 3)
            channels_grid.addWidget(debug_btn, row1, 4)
            
            # 第二行：空、空、文件标签、文件路径输入、浏览按钮
            row2 = row1 + 1
            channels_grid.addWidget(file_path_label, row2, 2)
            channels_grid.addWidget(file_path_edit, row2, 3)
            channels_grid.addWidget(browse_btn, row2, 4)
            
            self.channel_name_edits[i] = name_edit
            self.channel_addr_edits[i] = addr_edit
            self.channel_file_path_edits[i] = file_path_edit
        
        # 设置列拉伸因子：让地址输入框占据剩余空间
        channels_grid.setColumnStretch(0, 0)  # 通道标签列不拉伸
        channels_grid.setColumnStretch(1, 0)  # 名称输入框列不拉伸
        channels_grid.setColumnStretch(2, 0)  # 地址标签列不拉伸
        channels_grid.setColumnStretch(3, 1)  # 地址输入框列拉伸
        channels_grid.setColumnStretch(4, 0)  # 调试按钮列不拉伸
        
        scroll_layout.addLayout(channels_grid)
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        channel_layout.addWidget(scroll_area)
        
        # === 确认和取消按钮（底部右对齐）===
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        # 确认按钮 - 使用全局文本按钮样式管理器
        self.channel_confirm_btn = createTextButton("确认", parent=self, slot=self._onChannelConfirm)
        button_layout.addWidget(self.channel_confirm_btn)
        
        button_layout.addSpacing(5)
        
        # 取消按钮 - 使用全局文本按钮样式管理器
        self.channel_cancel_btn = createTextButton("取消", parent=self, slot=self._onChannelCancel)
        button_layout.addWidget(self.channel_cancel_btn)
        
        channel_layout.addLayout(button_layout)
        
        # 在页面创建完成后，递归应用字体管理器到所有子控件
        FontManager.applyToWidgetRecursive(channel_page)
        
        # 添加到 stacked_widget
        self.stacked_widget.addWidget(channel_page)
    
    def _createToolbar(self):
        """创建顶部工具栏"""
        self.toolbar = QtWidgets.QWidget()
        toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(5)
        
        #  左侧：搜索框
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(" 搜索任务名称...")
        self.search_input.setFixedWidth(200)
        self.search_input.setFixedHeight(30)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 5px 10px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #4682B4;
            }
        """)
        toolbar_layout.addWidget(self.search_input)
        
        # 添加一些间距
        toolbar_layout.addSpacing(10)
        
        # 创建按钮 - 使用全局文本按钮样式管理器
        self.btn_add = createTextButton("新建任务", parent=self)
        self.btn_channel_manage = createTextButton("通道管理", parent=self)
        self.btn_start_all = createTextButton("一键启动", parent=self)
        self.btn_debug = createTextButton(" 调试", parent=self)

        # 🔥 调试按钮默认隐藏（只有在debug模式下才显示）
        # 初始状态设置为隐藏和禁用，等待_handler根据编译模式更新
        self.btn_debug.setVisible(False)
        self.btn_debug.setEnabled(False)

        toolbar_layout.addWidget(self.btn_add)
        toolbar_layout.addWidget(self.btn_channel_manage)
        toolbar_layout.addWidget(self.btn_start_all)
        toolbar_layout.addWidget(self.btn_debug)
        toolbar_layout.addStretch()
    
    def _createPaginationWidget(self):
        """创建分页控件"""
        self.pagination_widget = QtWidgets.QWidget()
        self.pagination_widget.setMaximumWidth(470)
        pagination_layout = QtWidgets.QHBoxLayout(self.pagination_widget)
        pagination_layout.setContentsMargins(5, 5, 5, 5)
        pagination_layout.setSpacing(3)
        
        # 弹性空间（居中显示分页控件）
        pagination_layout.addStretch()
        
        # 获取Qt标准图标样式
        style = QtWidgets.QApplication.style()
        
        # 分页按钮 - 使用Qt标准图标
        self.btn_first_page = QtWidgets.QPushButton()
        self.btn_first_page.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaSeekBackward))
        self.btn_first_page.setToolTip("首页")
        self.btn_first_page.setFixedWidth(35)
        pagination_layout.addWidget(self.btn_first_page)
        
        self.btn_prev_page = QtWidgets.QPushButton()
        self.btn_prev_page.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowLeft))
        self.btn_prev_page.setToolTip("上一页")
        self.btn_prev_page.setFixedWidth(35)
        pagination_layout.addWidget(self.btn_prev_page)
        
        # 页码显示
        self.page_label = QtWidgets.QLabel("1 / 1")
        self.page_label.setFixedWidth(55)
        self.page_label.setAlignment(Qt.AlignCenter)
        pagination_layout.addWidget(self.page_label)
        
        self.btn_next_page = QtWidgets.QPushButton()
        self.btn_next_page.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowRight))
        self.btn_next_page.setToolTip("下一页")
        self.btn_next_page.setFixedWidth(35)
        pagination_layout.addWidget(self.btn_next_page)
        
        self.btn_last_page = QtWidgets.QPushButton()
        self.btn_last_page.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaSeekForward))
        self.btn_last_page.setToolTip("末页")
        self.btn_last_page.setFixedWidth(35)
        pagination_layout.addWidget(self.btn_last_page)
        
        # 跳转页码 - 使用全局文本按钮样式管理器
        self.btn_goto = createTextButton("跳转至", parent=self)
        pagination_layout.addWidget(self.btn_goto)
        
        self.page_input = QtWidgets.QLineEdit()
        self.page_input.setFixedWidth(40)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setPlaceholderText("页")
        pagination_layout.addWidget(self.page_input)
        
        # 弹性空间
        pagination_layout.addStretch()
    
    def _connectSignals(self):
        """连接信号槽"""
        #  搜索框信号
        self.search_input.textChanged.connect(self._onSearchTextChanged)
        
        # 工具栏按钮信号
        self.btn_add.clicked.connect(self._onAddTask)
        self.btn_channel_manage.clicked.connect(self._onChannelManage)
        self.btn_start_all.clicked.connect(self._onStartAll)

        #  调试按钮需要使用事件过滤器来区分左右键
        self.btn_debug.installEventFilter(self)
        
        # 表格信号
        self.table.itemClicked.connect(self._onItemClicked)
        self.table.cellChanged.connect(self._onCellChanged)
        
        #  安装键盘事件过滤器（处理Delete键删除任务）
        self.table.installEventFilter(self)
        
        #  分页信号
        self.btn_first_page.clicked.connect(self._onFirstPage)
        self.btn_prev_page.clicked.connect(self._onPrevPage)
        self.btn_next_page.clicked.connect(self._onNextPage)
        self.btn_last_page.clicked.connect(self._onLastPage)
        self.btn_goto.clicked.connect(self._onGoToPage)
        self.page_input.returnPressed.connect(self._onGoToPage)
    
    def setColumns(self, column_names):
        """
        设置列名
        
        Args:
            column_names: 列名列表，如 ['ID', '名称', '状态', '时间']
        """
        self._column_names = column_names
        self.table.setColumnCount(len(column_names))
        self.table.setHorizontalHeaderLabels(column_names)
    
    def addRow(self, row_data, user_data=None, button_callback=None, update_display=True):
        """
        添加一行数据（自动添加曲线按钮）
        
        Args:
            row_data: 行数据列表，长度应与列数一致
            user_data: 用户自定义数据，可以存储在第一个单元格
            button_callback: 曲线按钮点击回调（可选）
            update_display: 是否立即更新显示（批量加载时设为False）
        
        Returns:
            int: 新添加行的索引
        """
        #  存储数据到 _all_rows_data（用于分页）
        self._all_rows_data.append({
            'row_data': row_data,
            'user_data': user_data,
            'button_callback': button_callback
        })
        
        #  更新分页显示（如果需要）
        if update_display:
            # 🔥 检查新行是否在当前页，如果是则直接添加到表格，否则更新分页
            display_data = self._filtered_rows_data if self._search_text else self._all_rows_data
            total_rows = len(display_data)
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            
            # 新行的索引
            new_row_index = len(self._all_rows_data) - 1
            
            # 如果新行在当前页范围内，直接添加到表格
            if start_index <= new_row_index < end_index and self.table.rowCount() < self._page_size:
                self._addRowToTable(row_data, user_data, button_callback)
                # 只更新页码标签，不刷新整个表格
                total_pages = (total_rows + self._page_size - 1) // self._page_size if total_rows > 0 else 1
                self.page_label.setText(f"{self._current_page} / {total_pages}")
            else:
                # 新行不在当前页，需要完整刷新分页
                self._updatePagination()
        
        # 返回在全部数据中的索引
        return len(self._all_rows_data) - 1
    
    def refreshDisplay(self):
        """手动刷新显示（用于批量操作后）"""
        self._updatePagination()
    
    def setCellTextColor(self, row, col, color):
        """
        设置指定单元格的文本颜色
        
        Args:
            row: 行索引（在全部数据中的索引）
            col: 列索引
            color: 颜色（QColor或颜色字符串，如'#00FF00'）
        """
        # 检查行索引是否有效
        if row < 0 or row >= len(self._all_rows_data):
            return
        
        # 计算在当前页面中的行索引
        start_idx = (self._current_page - 1) * self._page_size
        end_idx = start_idx + self._page_size
        
        # 检查该行是否在当前页面中
        if start_idx <= row < end_idx:
            table_row = row - start_idx
            item = self.table.item(table_row, col)
            if item:
                if isinstance(color, str):
                    item.setForeground(QtGui.QColor(color))
                else:
                    item.setForeground(color)
    
    def _addRowToTable(self, row_data, user_data=None, button_callback=None):
        """
        实际添加一行到表格（内部方法）- 使用纯QTableWidgetItem方案
        
        Args:
            row_data: 行数据列表
            user_data: 用户自定义数据
            button_callback: 曲线按钮点击回调
        
        Returns:
            int: 新添加行的表格索引
        """
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        
        # 检查是否为未启动状态
        is_unconfigured = len(row_data) > 2 and str(row_data[2]) == "未启动"
        
        for col_index, value in enumerate(row_data):
            # 跳过曲线列（将由按钮占据）
            if col_index == self.CURVE_BUTTON_COLUMN:
                continue
                
            item = QtWidgets.QTableWidgetItem(str(value))
            
            # 在第一个单元格存储用户数据
            if col_index == 0 and user_data is not None:
                item.setData(Qt.UserRole, user_data)
            
            # 🔥 通道列始终设置为灰色字体
            if self.CHANNEL_START_COLUMN <= col_index < self.CHANNEL_START_COLUMN + self.CHANNEL_COUNT:
                item.setForeground(QtGui.QColor(128, 128, 128))  # 设置灰色文字
            # 🔥 如果是未启动状态且不是通道列，设置灰色前景色
            elif is_unconfigured:
                item.setForeground(QtGui.QColor(128, 128, 128))  # 设置灰色文字
            
            # 设置到表格
            self.table.setItem(row_index, col_index, item)
        
        # 自动为曲线列添加图标按钮
        self.setCellButton(row_index, self.CURVE_BUTTON_COLUMN, button_callback)
        
        return row_index
    
    def _setRowDefaultColor(self, row_index, row_data):
        """
        设置指定行为默认颜色（用于已启动状态）- 纯QTableWidgetItem方案
        
        Args:
            row_index: 行索引
            row_data: 行数据列表
        """
        
        # 设置所有列的字体颜色为默认色（黑色）
        for col_index in range(len(row_data)):
            # 跳过曲线列（按钮列）
            if col_index == self.CURVE_BUTTON_COLUMN:
                continue
                
            item = self.table.item(row_index, col_index)
            if item:
                item.setForeground(QtGui.QColor(0, 0, 0))  # 设置黑色文字
    
    def _setRowGrayColor(self, row_index, row_data):
        """
        设置指定行为灰色字体（用于未启动状态）- 纯QTableWidgetItem方案
        
        Args:
            row_index: 行索引
            row_data: 行数据列表
        """
        
        # 设置所有列的字体颜色为灰色
        for col_index in range(len(row_data)):
            # 跳过曲线列（按钮列）
            if col_index == self.CURVE_BUTTON_COLUMN:
                continue
                
            item = self.table.item(row_index, col_index)
            if item:
                item.setForeground(QtGui.QColor(128, 128, 128))  # 设置灰色文字
    
    
    def _testFontException(self):
        """
        测试字体例外机制是否正常工作
        """
        pass
    
    
    def updateRow(self, row_index, row_data):
        """
        更新指定行的数据
        
        Args:
            row_index: 行索引
            row_data: 新的行数据列表
        
        Returns:
            bool: 是否成功
        """
        if row_index < 0 or row_index >= self.table.rowCount():
            return False
        
        for col_index, value in enumerate(row_data):
            if col_index < self.table.columnCount():
                item = self.table.item(row_index, col_index)
                if item:
                    item.setText(str(value))
                else:
                    self.table.setItem(row_index, col_index, 
                                QtWidgets.QTableWidgetItem(str(value)))
        
        return True
    
    def removeRow(self, row_index):
        """
        删除指定行
        
        Args:
            row_index: 行索引（当前页面的行索引，不是全局索引）
        
        Returns:
            bool: 是否成功
        """
        if row_index < 0 or row_index >= self.table.rowCount():
            return False
        
        # 🔥 计算全局索引（考虑分页）
        global_index = (self._current_page - 1) * self._page_size + row_index
        
        # 🔥 从分页数据中删除
        if 0 <= global_index < len(self._filtered_rows_data):
            # 从过滤数据中删除
            removed_item = self._filtered_rows_data.pop(global_index)
            
            # 从全部数据中删除（需要找到对应项）
            if removed_item in self._all_rows_data:
                self._all_rows_data.remove(removed_item)
        
        # 🔥 从表格UI中删除
        self.table.removeRow(row_index)
        
        # 🔥 更新分页显示
        self._updatePagination()
        
        return True
    
    def getRowData(self, row_index):
        """
        获取指定行的数据
        
        Args:
            row_index: 行索引
        
        Returns:
            list: 行数据列表，如果行不存在返回None
        """
        if row_index < 0 or row_index >= self.table.rowCount():
            return None
        
        row_data = []
        for col_index in range(self.table.columnCount()):
            item = self.table.item(row_index, col_index)
            row_data.append(item.text() if item else '')
        
        return row_data
    
    def getUserData(self, row_index):
        """
        获取指定行的用户数据
        
        Args:
            row_index: 行索引
        
        Returns:
            用户数据，如果不存在返回None
        """
        if row_index < 0 or row_index >= self.table.rowCount():
            return None
        
        item = self.table.item(row_index, 0)
        return item.data(Qt.UserRole) if item else None
    
    def rowCount(self):
        """
        获取表格行数
        
        Returns:
            int: 行数
        """
        return self.table.rowCount()
    
    def getSelectedRow(self):
        """
        获取当前选中的行索引（在全部数据中的索引）
        
        Returns:
            int: 全局行索引，如果没有选中返回-1
        """
        return self._current_selected_row
    
    def setSelectedRow(self, global_row_index):
        """
        设置选中的行（程序化选择）
        
        Args:
            global_row_index: 全局行索引
        """
        # 清除之前的选中状态
        self._clearRowHighlight()
        
        if global_row_index < 0 or global_row_index >= len(self._all_rows_data):
            self._current_selected_row = -1
            return
        
        # 设置当前选中行
        self._current_selected_row = global_row_index
        
        # 应用黑色边框高亮
        self._applyRowHighlight(global_row_index)
    
    def getSelectedRowData(self):
        """
        获取当前选中行的数据
        
        Returns:
            list: 行数据列表，如果没有选中返回None
        """
        row_index = self.getSelectedRow()
        if row_index == -1:
            return None
        
        return self.getRowData(row_index)
    
    def _clearRowHighlight(self):
        """清除所有行的高亮边框"""
        for row_idx in range(self.table.rowCount()):
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(row_idx, col_idx)
                if item:
                    # 恢复透明边框
                    item.setData(Qt.UserRole + 1, None)  # 清除高亮标记
                    self._updateItemStyle(item, False)
    
    def _applyRowHighlight(self, global_row_index):
        """应用黑色边框高亮到指定行"""
        # 计算该行在当前页面中的索引
        start_idx = (self._current_page - 1) * self._page_size
        end_idx = start_idx + self._page_size
        
        # 检查该行是否在当前页面中
        if start_idx <= global_row_index < end_idx:
            table_row = global_row_index - start_idx
            
            # 为该行的所有单元格添加黑色边框
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(table_row, col_idx)
                if item:
                    # 标记为高亮状态
                    item.setData(Qt.UserRole + 1, True)
                    self._updateItemStyle(item, True)
    
    def _updateItemStyle(self, item, is_highlighted):
        """更新单元格样式"""
        if is_highlighted:
            # 使用深灰色背景表示选中状态（类似黑色边框的效果）
            item.setBackground(QtGui.QBrush(QtGui.QColor(220, 220, 220)))  # 深灰色背景表示选中
        else:
            # 恢复默认样式
            item.setBackground(QtGui.QBrush(QtGui.QColor(255, 255, 255)))  # 白色背景
    
    def clearTable(self):
        """清空表格所有数据"""
        self._all_rows_data.clear()
        self._current_page = 1
        self.table.setRowCount(0)
        self._updatePagination()
    
    def setEditable(self, editable):
        """
        设置表格是否可编辑
        
        Args:
            editable: True为可编辑，False为不可编辑
        """
        if editable:
            self.table.setEditTriggers(
                QtWidgets.QAbstractItemView.DoubleClicked |
                QtWidgets.QAbstractItemView.EditKeyPressed
            )
        elif not editable:
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    
    def setColumnWidths(self, widths):
        """
        设置各列的宽度
        
        Args:
            widths: 宽度列表，如 [100, 200, 150]
        """
        for col_index, width in enumerate(widths):
            if col_index < self.table.columnCount():
                self.table.setColumnWidth(col_index, width)
    
    def resizeColumnsToContents(self):
        """自动调整列宽以适应内容"""
        for col_index in range(self.table.columnCount()):
            self.table.resizeColumnToContents(col_index)
    
    def findRow(self, column_index, value):
        """
        根据指定列的值查找行
        
        Args:
            column_index: 列索引
            value: 要查找的值
        
        Returns:
            int: 第一个匹配的行索引，未找到返回-1
        """
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, column_index)
            if item and item.text() == str(value):
                return row_index
        
        return -1
    
    def setCellButton(self, row_index, column_index, callback=None):
        """
        在指定单元格中设置图标按钮
        
        Args:
            row_index: 行索引
            column_index: 列索引
            callback: 按钮点击回调函数（可选），函数签名为 callback(row, col)
        
        Returns:
            QPushButton: 创建的按钮对象
        """
        if row_index < 0 or row_index >= self.table.rowCount():
            return None
        if column_index < 0 or column_index >= self.table.columnCount():
            return None
        
        # 创建图标按钮（使用动态曲线图标）
        button = QtWidgets.QPushButton()
        button.setIcon(newIcon("动态曲线"))
        button.setIconSize(QtCore.QSize(20, 20))  # 图标大小
        button.setFixedSize(32, 24)  # 固定大小
        button.setToolTip("查看曲线")  # 添加工具提示
        
        # 设置透明背景样式，移除浅灰色框
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
            }
        """)
        
        # 连接点击事件
        def on_button_clicked():
            self.buttonClicked.emit(row_index, column_index)
            if callback:
                callback(row_index, column_index)
        
        button.clicked.connect(on_button_clicked)
        
        # 创建容器widget来居中显示按钮
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(button)
        layout.addStretch()
        
        # 将容器放入单元格
        self.table.setCellWidget(row_index, column_index, container)
        
        return button
    
    def setCellButtons(self, column_index, callback=None):
        """
        为指定列的所有行设置图标按钮
        
        Args:
            column_index: 列索引
            callback: 按钮点击回调函数（可选）
        
        Returns:
            list: 创建的按钮对象列表
        """
        buttons = []
        for row_index in range(self.table.rowCount()):
            btn = self.setCellButton(row_index, column_index, callback)
            if btn:
                buttons.append(btn)
        
        return buttons
    
    def _applyDefaultConfig(self):
        """
        应用默认配置（自动调用）
        
        这个方法在初始化时自动调用，应用固定的列配置
        修改类常量 DEFAULT_COLUMNS 和 DEFAULT_WIDTHS 即可全局同步
        """
        # 设置列名
        self.setColumns(self.DEFAULT_COLUMNS)
        
        # 设置列宽（所有列使用固定宽度）
        self.setColumnWidths(self.DEFAULT_WIDTHS)
        
        # 🔥 合并通道列的表头（第一行显示"通道"，覆盖16个子列）
        self._mergeChannelHeader()
    
    def _mergeChannelHeader(self):
        """
        合并通道列的表头
        
        将"1"到"16"的表头合并显示为"通道"
        """
        # 🔥 创建自定义表头标签
        # 由于QTableWidget不支持直接合并表头单元格，我们使用一个技巧：
        # 在表头上方放置一个QLabel来显示"通道"
        
        # 获取表头
        header = self.table.horizontalHeader()
        
        # 计算通道列的总宽度
        channel_total_width = sum(self.DEFAULT_WIDTHS[self.CHANNEL_START_COLUMN:self.CHANNEL_START_COLUMN + self.CHANNEL_COUNT])
        
        # 计算通道列的起始位置
        channel_start_pos = sum(self.DEFAULT_WIDTHS[:self.CHANNEL_START_COLUMN])
        
        # 创建一个QLabel显示"通道"
        if not hasattr(self, '_channel_header_label'):
            self._channel_header_label = QtWidgets.QLabel("通道", self.table)
            self._channel_header_label.setAlignment(Qt.AlignCenter)
            self._channel_header_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border: 1px solid #d0d0d0;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            # 应用全局字体
            FontManager.applyToWidget(self._channel_header_label)
        
        # 设置位置和大小
        self._channel_header_label.setGeometry(
            channel_start_pos,
            0,
            channel_total_width,
            header.height()
        )
        self._channel_header_label.show()
        self._channel_header_label.raise_()  # 确保在最上层
        
        # 🔥 连接水平滚动条信号，滚动时更新通道标签位置
        self.table.horizontalScrollBar().valueChanged.connect(self._updateChannelHeaderPosition)
    
    def _updateChannelHeaderPosition(self, scroll_value):
        """更新通道表头标签位置（跟随水平滚动）"""
        if hasattr(self, '_channel_header_label'):
            # 计算通道列的起始位置（考虑滚动偏移）
            channel_start_pos = sum(self.DEFAULT_WIDTHS[:self.CHANNEL_START_COLUMN]) - scroll_value
            channel_total_width = sum(self.DEFAULT_WIDTHS[self.CHANNEL_START_COLUMN:self.CHANNEL_START_COLUMN + self.CHANNEL_COUNT])
            
            header = self.table.horizontalHeader()
            self._channel_header_label.setGeometry(
                channel_start_pos,
                0,
                channel_total_width,
                header.height()
            )
    
  
    
    def _onItemClicked(self, item):
        """单元格被单击 - 任务分配功能"""
        if item:
            # 获取表格中的行索引
            table_row = item.row()
            
            # 转换为全局行索引
            start_idx = (self._current_page - 1) * self._page_size
            global_row = start_idx + table_row
            
            # 🔥 手动设置选中行（黑色边框高亮）
            self.setSelectedRow(global_row)
            
            # 发送选中信号
            self.itemSelected.emit(global_row)
            
            # 获取任务信息并发送任务选中信号给handler
            user_data = self.getUserData(table_row)
            if user_data:
                # 🔥 保存当前单击的行索引，等待handler确认后再置黑
                self._pending_highlight_row = global_row
                self.taskSelected.emit(user_data)
    
    def _assignTaskToChannels(self, row):
        """
        将指定行的任务分配给通道
        
        这个方法可以通过其他方式触发（如右键菜单、按钮等），
        而不是双击事件，避免意外的任务分配。
        
        Args:
            row: 任务行索引
        """
        # 获取任务信息并发送taskSelected信号
        user_data = self.getUserData(row)
        if user_data:
            # 发送任务选中信号给handler
            self.taskSelected.emit(user_data)
    
    def confirmTaskAssignment(self):
        """
        确认任务分配（由handler调用）
        
        当用户在确认对话框中点击"确认"后，handler调用此方法来高亮选中的行
        """
        if self._pending_highlight_row is not None:
            self._highlightSelectedRow(self._pending_highlight_row)
            self._pending_highlight_row = None
    
    def cancelTaskAssignment(self):
        """
        取消任务分配（由handler调用）
        
        当用户在确认对话框中点击"取消"后，handler调用此方法来清除待高亮状态
        """
        if self._pending_highlight_row is not None:
            self._pending_highlight_row = None
    
    def _highlightSelectedRow(self, selected_row):
        """简化高亮逻辑：只将单击行文字颜色置黑（跳过通道列）"""
        try:
            # 只处理选中的行，将文字颜色置黑
            for col in range(self.table.columnCount()):
                # 跳过按钮列
                if col == self.CURVE_BUTTON_COLUMN:
                    continue
                
                # 🔥 跳过通道列（通道列颜色由 channelmission 状态控制）
                if self.CHANNEL_START_COLUMN <= col < self.CHANNEL_START_COLUMN + self.CHANNEL_COUNT:
                    continue
                
                item = self.table.item(selected_row, col)
                if item:
                    # 单击行：非通道列设置为黑色文字
                    item.setForeground(QtGui.QColor(0, 0, 0))  # 黑色文字
                    # 不设置背景色，保持原有背景
            
        except Exception as e:
            pass
    
    def _onCellChanged(self, row, column):
        """单元格内容改变"""
        item = self.table.item(row, column)
        if item:
            self.itemChanged.emit(row, column, item.text())
    
    # ========== 工具栏按钮槽函数 ==========
    
    def _onAddTask(self):
        """新建任务按钮点击 - 切换到新建任务界面"""
        # 清空输入
        self.new_task_id_input.clear()
        self.new_task_name_input.clear()
        for checkbox in self.new_task_channel_checkboxes.values():
            checkbox.setChecked(False)
        
        # 切换到新建任务界面
        self.showNewTaskView()
    
    def _onDeleteKeyPressed(self):
        """Delete键按下 - 删除选中的任务"""
        row_index = self.getSelectedRow()
        if row_index != -1:
            # 发送删除任务请求信号给handler
            self.removeTaskRequested.emit(row_index)
        else:
            # 如果没有选中行，不显示警告（静默处理）
            pass
    
    def _onSearchTextChanged(self, text):
        """搜索框文本改变 - 过滤任务列表"""
        self._search_text = text.strip().lower()
        
        #  过滤数据
        if not self._search_text:
            # 如果搜索框为空，显示所有数据
            self._filtered_rows_data = self._all_rows_data.copy()
        else:
            # 根据任务编号和任务名称过滤
            self._filtered_rows_data = []
            for row_info in self._all_rows_data:
                row_data = row_info['row_data']
                task_id = str(row_data[0]).lower() if len(row_data) > 0 else ""
                task_name = str(row_data[1]).lower() if len(row_data) > 1 else ""
                
                # 如果任务编号或任务名称包含搜索关键字，则加入过滤结果
                if self._search_text in task_id or self._search_text in task_name:
                    self._filtered_rows_data.append(row_info)
        
        #  重置到第1页并更新显示
        self._current_page = 1
        self._updatePagination()
    
    def _onChannelManage(self):
        """通道管理按钮点击 - 发出信号"""
        pass
        self.channelManageClicked.emit()

    def _onStartAll(self):
        """一键启动按钮点击 - 发出信号"""
        self.startAllClicked.emit()
    
    def _showContextMenu(self, pos):
        """
        显示右键菜单
        
        Args:
            pos: 鼠标位置
        """
        # 获取点击位置的item
        item = self.table.itemAt(pos)
        if not item:
            return
        
        # 获取行索引
        row = item.row()
        
        # 创建右键菜单
        menu = QtWidgets.QMenu(self)
        
        # 添加删除任务选项
        delete_action = menu.addAction("删除任务")
        delete_action.setIcon(newIcon("删除"))
        
        # 显示菜单并获取选中的动作
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        
        # 处理选中的动作
        if action == delete_action:
            self._deleteTaskAtRow(row)
    
    def _deleteTaskAtRow(self, row):
        """
        删除指定行的任务
        
        Args:
            row: 行索引
        """
        # 获取任务信息
        task_id_item = self.table.item(row, 0)
        task_name_item = self.table.item(row, 1)
        
        if not task_id_item or not task_name_item:
            return
        
        task_id = task_id_item.text()
        task_name = task_name_item.text()
        
        # 🔥 使用全局对话框管理器显示警告询问对话框
        message = f"确定要删除任务 [{task_id}_{task_name}] 吗？\n\n此操作将删除任务配置文件和所有相关数据，且无法恢复！"
        
        if DialogManager.show_question_warning(
            self,
            "确认删除",
            message,
            yes_text="是",
            no_text="否"
        ):
            # 发射删除任务信号，由handler处理实际的删除逻辑
            self.removeTaskRequested.emit(row)
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理Delete键删除 + 调试按钮的左右键点击 + 拦截表格单击"""
        #  处理表格的键盘事件（Delete键删除选中行）
        if obj == self.table:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == Qt.Key_Delete:
                    # Delete键：删除选中的任务
                    self._onDeleteKeyPressed()
                    return True
        
        # 不再拦截单击事件，允许单击触发任务分配
        # 移除了双击事件的特殊处理，改为使用标准的 itemClicked 信号
        
        # 调试按钮的左右键处理
        if obj == self.btn_debug:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    # 左键：一键启动检测
                    self.debugLeftClicked.emit()
                    return True
                elif event.button() == Qt.RightButton:
                    # 右键：标注配置
                    self.debugRightClicked.emit()
                    return True
        
        return super().eventFilter(obj, event)
    
    # ========== 新建任务界面相关方法 ==========
    
    def showNewTaskView(self):
        """显示新建任务界面"""
        self.stacked_widget.setCurrentIndex(1)
    
    def showChannelManageView(self):
        """显示通道管理界面"""
        self.stacked_widget.setCurrentIndex(2)
    
    def showTableView(self):
        """显示任务列表界面"""
        self.stacked_widget.setCurrentIndex(0)
    
    def _onNewTaskConfirm(self):
        """新建任务确认按钮点击"""
        # 获取输入值
        task_id = self.new_task_id_input.text().strip()
        task_name = self.new_task_name_input.text().strip()
        
        # 验证必填字段
        if not task_id:
            DialogManager.show_warning(self, "提示", "请输入任务编号")
            return
        
        if not task_name:
            DialogManager.show_warning(self, "提示", "请输入任务名称")
            return
        
        # 获取选中的通道
        selected_channels = []
        for channel_key, checkbox in self.new_task_channel_checkboxes.items():
            if checkbox.isChecked():
                selected_channels.append(channel_key)
        
        if not selected_channels:
            DialogManager.show_warning(self, "提示", "请至少选择一个通道")
            return
        
        # 构建任务信息
        task_info = {
            'task_id': task_id,
            'task_name': task_name,
            'selected_channels': selected_channels,
            'status': '未启动'
        }
        
        # 发送任务确认信号
        self.taskConfirmed.emit(task_info)
        
        # 切换回列表界面
        self.showTableView()
    
    def _onNewTaskCancel(self):
        """新建任务取消按钮点击"""
        # 发送任务取消信号
        self.taskCancelled.emit()
        
        # 切换回列表界面
        self.showTableView()
    
    def _onChannelConfirm(self):
        """通道管理确认按钮点击"""
        # 收集通道数据
        channels = {}
        for i in range(1, 5):
            name = self.channel_name_edits[i].text().strip()
            addr = self.channel_addr_edits[i].text().strip()
            file_path = self.channel_file_path_edits[i].text().strip()
            # 如果地址或文件路径非空，则保存该通道
            if addr or file_path:
                channels[i] = {
                    'channel_id': i,
                    'name': name or f'通道{i}',
                    'address': addr,
                    'file_path': file_path
                }
        
        # 发送通道确认信号
        self.channelConfirmed.emit({'channels': channels})
        
        # 切换回列表界面
        self.showTableView()
    
    def _onBrowseVideoFile(self, channel_id):
        """浏览选择本地视频文件"""
        try:
            # 定义支持的视频文件格式
            video_formats = "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.m4v *.mpg *.mpeg);;所有文件 (*.*)"
            
            # 打开文件选择对话框
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                f"选择通道{channel_id}的视频文件",
                "",  # 默认目录为空，使用系统默认
                video_formats
            )
            
            # 如果用户选择了文件，则设置到输入框
            if file_path:
                self.channel_file_path_edits[channel_id].setText(file_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            DialogManager.show_warning(
                self,
                "文件选择失败",
                f"选择视频文件时发生错误：\n{str(e)}"
            )
    
    def _onChannelCancel(self):
        """通道管理取消按钮点击"""
        # 发送通道取消信号
        self.channelCancelled.emit()
        
        # 切换回列表界面
        self.showTableView()
    
    def _onChannelDebug(self, channel_id):
        """通道调试按钮点击"""
        # 获取当前通道的地址
        addr = self.channel_addr_edits[channel_id].text().strip()
        
        if not addr:
            DialogManager.show_warning(self, "警告", f"通道{channel_id}地址为空，无法测试连接")
            return
        
        # 如果地址不以 rtsp:// 开头，自动添加
        if not addr.startswith('rtsp://'):
            addr = 'rtsp://' + addr
        
        # 发送调试信号给handler处理
        self.channelDebugRequested.emit(channel_id, addr)
    
    def updateDebugButtonStatus(self, channel_id, success, message=""):
        """更新调试按钮状态（由handler调用）"""
        if channel_id not in self.channel_debug_btns:
            return
        
        btn = self.channel_debug_btns[channel_id]
        
        if success:
            btn.setText("成功")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-size: 10pt;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            btn.setText("失败")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-size: 10pt;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
        
        # 3秒后恢复原状
        QtCore.QTimer.singleShot(5000, lambda: self._resetDebugButton(channel_id))
    
    def loadChannelData(self, channel_data):
        """加载通道数据到UI（由handler调用）"""
        if not channel_data:
            return
        
        channels = channel_data.get('channels', {})
        for i in range(1, 5):
            if i in channels:
                channel = channels[i]
                self.channel_name_edits[i].setText(channel.get('name', f'通道{i}'))
                addr = channel.get('address', '')
                if addr:
                    # 去掉 rtsp:// 前缀，只显示从 username 开始的部分
                    if addr.startswith('rtsp://'):
                        addr = addr[7:]  # 去掉 "rtsp://"
                    self.channel_addr_edits[i].setText(addr)
                    
                    # 立即重置文本显示位置到开头
                    QtCore.QTimer.singleShot(10, lambda edit=self.channel_addr_edits[i]: (
                        edit.setCursorPosition(0),
                        edit.home(False),
                        edit.update()
                    ))
                
                # 加载文件路径
                file_path = channel.get('file_path', '')
                if file_path:
                    self.channel_file_path_edits[i].setText(file_path)
                else:
                    self.channel_file_path_edits[i].clear()
    
    def _resetDebugButton(self, channel_id):
        """重置调试按钮状态"""
        if channel_id not in self.channel_debug_btns:
            return
        
        btn = self.channel_debug_btns[channel_id]
        btn.setText("调试")
        btn.setStyleSheet("font-size: 10pt;")
    
    def addTaskRow(self, task_info):
        """添加任务行（由handler调用）"""
        # 获取选中的通道列表
        selected_channels = task_info.get('selected_channels', [])
        
        # 初始化4个通道列的数据（默认为空）
        channel_data = ['', '', '', '']
        
        # 将选中的通道填充到对应的列
        for channel in selected_channels:
            if channel == '通道1':
                channel_data[0] = '通道1'
            elif channel == '通道2':
                channel_data[1] = '通道2'
            elif channel == '通道3':
                channel_data[2] = '通道3'
            elif channel == '通道4':
                channel_data[3] = '通道4'
        
        # 构建行数据：任务编号、任务名称、状态、通道1、通道2、通道3、通道4、曲线
        row_data = [
            task_info.get('task_id', ''),
            task_info.get('task_name', ''),
            task_info.get('status', '未启动'),
            channel_data[0],  # 通道1列
            channel_data[1],  # 通道2列
            channel_data[2],  # 通道3列
            channel_data[3],  # 通道4列
            ''  # 曲线列（按钮会自动添加）
        ]
        self.addRow(row_data, task_info)
    
    def removeTaskRow(self, row_index):
        """删除任务行（由handler调用）"""
        self.removeRow(row_index)
    
    def _showWarningDialog(self, title, message):
        """显示警告对话框（内部使用）"""
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)  # 不显示内容区域图标
        
        # 设置左上角图标为系统警告图标
        warning_icon = msg_box.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
        msg_box.setWindowIcon(warning_icon)
        
        # 移除帮助按钮
        msg_box.setWindowFlags(
            msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        # 设置文字水平和垂直居中
        msg_box.setStyleSheet("""
            QMessageBox {
                min-height: 100px;
            }
            QLabel {
                min-height: 50px;
                qproperty-alignment: 'AlignCenter';
            }
        """)
        
        msg_box.exec_()
    
    def showConfirmDialog(self, title, message):
        """显示确认对话框（由handler调用）"""
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)  # 内容区域不显示图标
        
        # 设置左上角图标为系统警告图标
        msg_box.setWindowIcon(
            msg_box.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
        )
        
        # 移除帮助按钮
        msg_box.setWindowFlags(
            msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        # 设置按钮
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        # 设置中文按钮文本
        yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
        no_btn = msg_box.button(QtWidgets.QMessageBox.No)
        if yes_btn:
            yes_btn.setText("是")
        if no_btn:
            no_btn.setText("否")
        
        # 设置文字居中样式
        msg_box.setStyleSheet("""
            QMessageBox {
                min-height: 100px;
            }
            QLabel {
                min-height: 50px;
                qproperty-alignment: 'AlignCenter';
            }
        """)
        
        result = msg_box.exec_()
        return result == QtWidgets.QMessageBox.Yes
    
    # ========== 分页功能实现 ==========
    
    def _updatePagination(self):
        """更新分页显示"""
        #  使用过滤后的数据（如果有搜索条件）
        display_data = self._filtered_rows_data if self._search_text else self._all_rows_data
        total_rows = len(display_data)
        total_pages = (total_rows + self._page_size - 1) // self._page_size if total_rows > 0 else 1
        
        # 确保当前页在有效范围内
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1
        
        # 更新页码显示
        self.page_label.setText(f"{self._current_page} / {total_pages}")
        
        # 更新按钮状态
        self.btn_first_page.setEnabled(self._current_page > 1)
        self.btn_prev_page.setEnabled(self._current_page > 1)
        self.btn_next_page.setEnabled(self._current_page < total_pages)
        self.btn_last_page.setEnabled(self._current_page < total_pages)
        
        # 刷新表格显示
        self._refreshTableDisplay()
    
    def _refreshTableDisplay(self):
        """刷新表格显示当前页的数据"""
        #  临时禁用cellChanged信号（避免批量操作时触发大量信号）
        self.table.blockSignals(True)
        
        # 清空表格
        self.table.setRowCount(0)
        
        #  使用过滤后的数据（如果有搜索条件）
        display_data = self._filtered_rows_data if self._search_text else self._all_rows_data
        total_rows = len(display_data)
        start_index = (self._current_page - 1) * self._page_size
        end_index = min(start_index + self._page_size, total_rows)
        
        # 显示当前页的数据
        for i in range(start_index, end_index):
            row_info = display_data[i]
            self._addRowToTable(
                row_info['row_data'],
                row_info['user_data'],
                row_info['button_callback']
            )
        
        #  重新启用信号
        self.table.blockSignals(False)
    
    def _getTotalPages(self):
        """获取总页数"""
        #  使用过滤后的数据（如果有搜索条件）
        display_data = self._filtered_rows_data if self._search_text else self._all_rows_data
        total_rows = len(display_data)
        return (total_rows + self._page_size - 1) // self._page_size if total_rows > 0 else 1
    
    def _onFirstPage(self):
        """跳转到首页"""
        if self._current_page > 1:
            self._current_page = 1
            self._updatePagination()
    
    def _onPrevPage(self):
        """上一页"""
        if self._current_page > 1:
            self._current_page -= 1
            self._updatePagination()
    
    def _onNextPage(self):
        """下一页"""
        total_pages = self._getTotalPages()
        if self._current_page < total_pages:
            self._current_page += 1
            self._updatePagination()
    
    def _onLastPage(self):
        """跳转到末页"""
        total_pages = self._getTotalPages()
        if self._current_page != total_pages:
            self._current_page = total_pages
            self._updatePagination()
    
    def _onGoToPage(self):
        """跳转到指定页"""
        try:
            page_num = int(self.page_input.text())
            total_pages = self._getTotalPages()
            
            if 1 <= page_num <= total_pages:
                self._current_page = page_num
                self._updatePagination()
                self.page_input.clear()
            else:
                self._showWarningDialog(
                    "提示", f"页码超出范围！有效范围: 1-{total_pages}"
                )
                self.page_input.clear()
        except ValueError:
            self.page_input.clear()


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("MissionPanel 组件测试")
    window.resize(800, 600)
    
    # 创建表格视图（自动应用配置）
    table = MissionPanel()
    # 注意：列名、列宽已自动配置，无需手动设置
    
    # 添加测试数据
    test_data = [
        (['1', '前门通道', 'RTSP', '已连接', ''], {'channel_id': 'channel1'}),
        (['2', '后门通道', 'RTSP', '未连接', ''], {'channel_id': 'channel2'}),
        (['3', 'USB通道', 'USB', '未连接', ''], {'channel_id': 'channelUSB'}),
        (['4', '任务A', '目标检测', '运行中', ''], {'mission_id': 'mission_1'}),
        (['5', '任务B', '目标跟踪', '已停止', ''], {'mission_id': 'mission_2'}),
    ]
    
    # 曲线按钮点击处理
    def on_curve_button_clicked(row, col):
        row_data = table.getRowData(row)
        pass
    
    # 添加数据（按钮会自动添加）
    for row_data, user_data in test_data:
        table.addRow(row_data, user_data, button_callback=on_curve_button_clicked)
    
    # 连接按钮点击信号
    def on_button_signal(row, col):
        pass
    
    table.buttonClicked.connect(on_button_signal)
    
    # 连接信号测试
    def on_item_selected(row_index):
        row_data = table.getRowData(row_index)
        user_data = table.getUserData(row_index)
        pass
    
    def on_item_double_clicked(row_index):
        row_data = table.getRowData(row_index)
        pass
    
    def on_item_changed(row, col, new_value):
        pass
    
    table.itemSelected.connect(on_item_selected)
    table.itemDoubleClicked.connect(on_item_double_clicked)
    table.itemChanged.connect(on_item_changed)
    
    # 注意：按钮已经集成到 MissionPanel 组件中，无需额外创建
    # 直接将 table 设置为中央部件
    window.setCentralWidget(table)
    
    window.show()
    sys.exit(app.exec_())

