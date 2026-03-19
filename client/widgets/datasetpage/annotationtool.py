# -*- coding: utf-8 -*-

"""
数据标注工具组件

两栏布局：
- 左侧：标注数据列表（图片+JSON信息）
- 右侧：标注工具区域（预留给labelme）
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp
import sys

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..icons import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
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

# 导入业务逻辑处理器
try:
    from handlers.datasetpage import AnnotationHandler
except ImportError:
    # 如果在独立运行模式下，添加路径
    handlers_path = osp.abspath(osp.join(osp.dirname(__file__), '..', '..', 'handlers'))
    if handlers_path not in sys.path:
        sys.path.append(handlers_path)
    try:
        from datasetpage import AnnotationHandler
    except ImportError as e:
        AnnotationHandler = None

# 导入labelme
try:
    # 添加labelme路径到sys.path末尾，避免覆盖项目自己的模块
    labelme_path = osp.abspath(osp.join(osp.dirname(__file__), '..', '..', 'labelme'))
    if labelme_path not in sys.path:
        sys.path.append(labelme_path)  # 使用append而不是insert(0)
    
    from labelme.app import MainWindow as LabelmeMainWindow
    from labelme.config import get_config as labelme_get_config  # 重命名避免冲突
    LABELME_AVAILABLE = True
except ImportError as e:
    LABELME_AVAILABLE = False
    LabelmeMainWindow = None
    labelme_get_config = None


class ColorPreservingDelegate(QtWidgets.QStyledItemDelegate):
    """自定义委托，保持选中状态下的文字颜色"""
    
    def paint(self, painter, option, index):
        # 获取item的前景色（文字颜色）
        foreground = index.data(Qt.ForegroundRole)
        
        # 如果item被选中，修改选项的调色板以保持文字颜色
        if option.state & QtWidgets.QStyle.State_Selected:
            # 设置选中背景色为灰色
            option.palette.setBrush(QtGui.QPalette.Highlight, QtGui.QBrush(QtGui.QColor(208, 208, 208)))
            # 如果有自定义前景色，保持它
            if foreground:
                option.palette.setBrush(QtGui.QPalette.HighlightedText, foreground)
        
        # 调用父类的绘制方法
        super().paint(painter, option, index)


class AnnotationTool(QtWidgets.QWidget):
    """
    数据标注工具组件
    
    两栏布局界面：左侧标注数据列表，右侧标注工具区
    """
    
    # 自定义信号
    annotationSelected = QtCore.Signal(str, str)  # 图片路径, JSON路径
    annotationAdded = QtCore.Signal(str)          # 新增标注
    annotationDeleted = QtCore.Signal(str)        # 删除标注
    
    def __init__(self, parent=None):
        super(AnnotationTool, self).__init__(parent)
        self._parent = parent
        
        # 创建业务逻辑处理器
        self.annotation_handler = AnnotationHandler(self) if AnnotationHandler else None
        
        # Labelme实例
        self.labelme_widget = None
        
        # 监控状态
        self._last_labelme_dir = None  # 记录上次labelme打开的目录
        self._last_labelme_file = None  # 记录上次labelme打开的文件
        
        self._initUI()
        self._initLabelme()
        self._connectSignals()
        self._connectHandlerSignals()
        self._startMonitorLabelme()
    
    def _initUI(self):
        """初始化UI - 两栏布局"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建可调整大小的分割器
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # === 左侧：标注数据列表 ===
        self.left_panel = self._createLeftPanel()
        self.splitter.addWidget(self.left_panel)
        
        # === 右侧：标注工具区域 ===
        self.right_panel = self._createRightPanel()
        self.splitter.addWidget(self.right_panel)
        
        # 设置分割器比例 (左:右 = 1:3)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(self.splitter)
    
    def _createLeftPanel(self):
        """创建左侧标注数据列表面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("标注数据")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 当前文件夹路径显示
        folder_layout = QtWidgets.QHBoxLayout()
        folder_layout.addWidget(QtWidgets.QLabel("当前目录:"))
        self.lbl_current_folder = QtWidgets.QLabel("等待标注工具打开文件夹...")
        self.lbl_current_folder.setStyleSheet("color: #666; font-style: italic;")
        self.lbl_current_folder.setWordWrap(True)
        self.lbl_current_folder.setToolTip("当在右侧labelme中打开文件夹时，此处会自动同步显示")
        folder_layout.addWidget(self.lbl_current_folder, stretch=1)
        layout.addLayout(folder_layout)
        
        # 搜索框
        search_layout = QtWidgets.QHBoxLayout()
        
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索图片名称...")
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_edit)
        
        self.btn_search = QtWidgets.QPushButton("搜索")
        self.btn_search.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        search_layout.addWidget(self.btn_search)
        
        layout.addLayout(search_layout)
        
        # 筛选选项
        filter_layout = QtWidgets.QHBoxLayout()
        
        filter_layout.addWidget(QtWidgets.QLabel("状态:"))
        
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["全部", "已标注", "未标注", "待审核"])
        self.filter_combo.setFixedWidth(scale_w(100))  # 🔥 响应式宽度
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        
        self.btn_sort = QtWidgets.QPushButton("排序")
        self.btn_sort.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        filter_layout.addWidget(self.btn_sort)
        
        layout.addLayout(filter_layout)
        
        # 标注数据列表
        self.annotation_list = QtWidgets.QListWidget()
        self.annotation_list.setAlternatingRowColors(True)
        self.annotation_list.setIconSize(QtCore.QSize(80, 80))
        self.annotation_list.setSpacing(5)
        
        # 设置自定义委托以保持选中状态下的文字颜色
        self.annotation_list.setItemDelegate(ColorPreservingDelegate(self.annotation_list))
        
        self.annotation_list.setStyleSheet("""
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
                background-color: #d0d0d0;
            }
            QListWidget::item:hover {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(self.annotation_list)
        
        # 底部统计信息
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.lbl_total_stats = QtWidgets.QLabel("总数: 0")
        self.lbl_total_stats.setStyleSheet("color: #666; padding: 5px;")
        stats_layout.addWidget(self.lbl_total_stats)
        
        stats_layout.addStretch()
        
        self.lbl_annotated_stats = QtWidgets.QLabel("已标注: 0")
        self.lbl_annotated_stats.setStyleSheet("color: #2ca02c; padding: 5px; font-weight: bold;")
        stats_layout.addWidget(self.lbl_annotated_stats)
        
        layout.addLayout(stats_layout)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _createRightPanel(self):
        """创建右侧标注工具区域（预留给labelme）"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("标注工具")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 工具栏按钮 - 响应式布局
        self.btn_zoom_in = QtWidgets.QPushButton("放大")
        self.btn_zoom_in.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_zoom_in)
        
        self.btn_zoom_out = QtWidgets.QPushButton("缩小")
        self.btn_zoom_out.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_zoom_out)
        
        self.btn_fit_window = QtWidgets.QPushButton("适应窗口")
        self.btn_fit_window.setFixedWidth(scale_w(80))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_fit_window)
        
        layout.addLayout(title_layout)
        
        # Labelme工具容器（空容器，后续嵌入labelme）- 响应式布局
        self.labelme_container = QtWidgets.QFrame()
        self.labelme_container.setMinimumSize(scale_w(600), scale_h(400))  # 🔥 响应式尺寸
        self.labelme_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #c0c0c0;
            }
        """)
        
        # 容器内部布局（用于后续添加labelme组件）
        self.labelme_layout = QtWidgets.QVBoxLayout(self.labelme_container)
        self.labelme_layout.setContentsMargins(0, 0, 0, 0)
        
        # 占位提示（labelme嵌入后会移除）
        placeholder = QtWidgets.QLabel("Labelme 标注工具区域\n\n此区域预留给 labelme 组件")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14pt;
                padding: 100px;
            }
        """)
        self.labelme_layout.addWidget(placeholder)
        
        layout.addWidget(self.labelme_container, stretch=1)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _initLabelme(self):
        """初始化并嵌入Labelme标注工具"""
        if not LABELME_AVAILABLE:
            return
        
        try:
            # 清除占位符
            while self.labelme_layout.count():
                item = self.labelme_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 获取labelme配置
            config = labelme_get_config()
            
            # 设置dock面板显示状态（简化界面）
            # 隐藏标签列表：左侧可以管理标签
            if 'label_dock' not in config:
                config['label_dock'] = {}
            config['label_dock']['show'] = False
            
            # 隐藏文件列表：左侧已有文件列表
            if 'file_dock' not in config:
                config['file_dock'] = {}
            config['file_dock']['show'] = False
            
            # 隐藏标志面板：通常不需要
            if 'flag_dock' not in config:
                config['flag_dock'] = {}
            config['flag_dock']['show'] = False
            
            # 保留形状列表：便于查看和编辑当前图片的标注
            # config['shape_dock']['show'] 默认为 True
            
            # 创建labelme主窗口
            self.labelme_widget = LabelmeMainWindow(
                config=config,
                filename=None,
                output_file=None,
                output_dir=None
            )
            
            # 将labelme设置为嵌入式widget（去除窗口边框）
            self.labelme_widget.setWindowFlags(Qt.Widget)
            
            # 添加到容器中
            self.labelme_layout.addWidget(self.labelme_widget)
            
            # 使用定时器延迟优化标签列表显示，确保labelme完全加载
            QtCore.QTimer.singleShot(200, self._optimizeLabelDisplay)
            
            # 连接放大缩小按钮到labelme的功能
            self._connectLabelmeActions()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _optimizeLabelDisplay(self):
        """优化标签列表的显示效果"""
        if not self.labelme_widget:
            return
        
        try:
            # 优化形状列表（多边形标注列表）的显示
            if hasattr(self.labelme_widget, 'labelList'):
                label_list = self.labelme_widget.labelList
                
                # 设置合适的字体大小
                font = QtGui.QFont()
                font.setPointSize(10)  # 增加字体大小到10
                label_list.setFont(font)
                
                # 设置列表的最小宽度，确保长标签能完整显示 - 响应式布局
                label_list.setMinimumWidth(scale_w(200))  # 🔥 响应式宽度
                
                # 设置固定的行高，确保标签名称能完整显示
                label_list.setIconSize(QtCore.QSize(16, 16))
                # 通过设置样式表来控制项目的高度
                label_list.setStyleSheet("""
                    QListView::item {
                        height: 35px;
                        padding: 5px;
                    }
                """)
            
            # 优化唯一标签列表的显示
            if hasattr(self.labelme_widget, 'uniqLabelList'):
                uniq_list = self.labelme_widget.uniqLabelList
                
                # 设置合适的字体
                font = QtGui.QFont()
                font.setPointSize(10)  # 增加字体大小到10
                uniq_list.setFont(font)
                
                # 设置最小宽度，确保长标签能完整显示 - 响应式布局
                uniq_list.setMinimumWidth(scale_w(180))  # 🔥 响应式宽度
                
                # 设置每个标签项的最小高度
                # 遍历所有标签项并设置尺寸提示
                for i in range(uniq_list.count()):
                    item = uniq_list.item(i)
                    if item:
                        # 设置更大的尺寸提示，确保标签文本完整显示
                        item.setSizeHint(QtCore.QSize(180, 35))  # 宽度180，高度35
                
                # 设置样式表以确保足够的垂直空间
                uniq_list.setStyleSheet("""
                    QListWidget::item {
                        height: 35px;
                        padding: 5px;
                        margin: 2px 0px;
                    }
                """)
            
            # 调整dock面板的大小 - 这是关键！
            if hasattr(self.labelme_widget, 'shape_dock'):
                shape_dock = self.labelme_widget.shape_dock
                # 设置合适的最小宽度，确保标签文本能完整显示 - 响应式布局
                shape_dock.setMinimumWidth(scale_w(260))  # 🔥 响应式宽度
                
                # 获取当前dock的尺寸并尝试调整
                current_width = shape_dock.width()
                if current_width < 260:
                    shape_dock.resize(260, shape_dock.height())
            
            # 也调整标签dock面板（如果显示的话）
            if hasattr(self.labelme_widget, 'label_dock'):
                label_dock = self.labelme_widget.label_dock
                label_dock.setMinimumWidth(scale_w(220))  # 🔥 响应式宽度
                
        except Exception as e:
            pass
    
    def _connectLabelmeActions(self):
        """连接工具栏按钮到labelme的功能"""
        if self.labelme_widget is None:
            return
        
        try:
            # 连接放大按钮
            self.btn_zoom_in.clicked.connect(
                lambda: self.labelme_widget.addZoom(1.1)
            )
            
            # 连接缩小按钮
            self.btn_zoom_out.clicked.connect(
                lambda: self.labelme_widget.addZoom(0.9)
            )
            
            # 连接适应窗口按钮
            self.btn_fit_window.clicked.connect(
                self.labelme_widget.adjustScale
            )
        except Exception as e:
            pass
    
    def _connectSignals(self):
        """连接UI信号和槽"""
        # 列表项点击事件
        self.annotation_list.itemClicked.connect(self.onItemClicked)
        self.annotation_list.itemSelectionChanged.connect(self.onItemSelectionChanged)
        
        # 搜索按钮
        self.btn_search.clicked.connect(self.onSearch)
        self.search_edit.returnPressed.connect(self.onSearch)
        
        # 筛选下拉框
        self.filter_combo.currentIndexChanged.connect(self.onFilterChanged)
    
    def _connectHandlerSignals(self):
        """连接Handler的信号到UI更新"""
        if not self.annotation_handler:
            return
        
        # 连接handler的信号
        self.annotation_handler.fileListUpdated.connect(self.onFileListUpdated)
        self.annotation_handler.statisticsUpdated.connect(self.onStatisticsUpdated)
        self.annotation_handler.directoryChanged.connect(self.onDirectoryChanged)
    
    def _startMonitorLabelme(self):
        """启动定时器监控labelme的状态变化"""
        # 创建定时器，每500ms检查一次labelme状态
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.timeout.connect(self._checkLabelmeStatus)
        self.monitor_timer.start(500)  # 500ms间隔
    
    def _checkLabelmeStatus(self):
        """检查labelme的状态并自动同步"""
        if self.labelme_widget is None:
            return
        
        try:
            # 获取labelme当前打开的目录
            current_dir = self.labelme_widget.lastOpenDir
            current_file = self.labelme_widget.filename
            
            # 检查目录是否变化
            if current_dir and current_dir != self._last_labelme_dir:
                self._last_labelme_dir = current_dir
                # 自动更新左侧面板显示该目录下的文件
                self._syncWithLabelmeDir(current_dir)
            
            # 检查文件是否变化
            if current_file and current_file != self._last_labelme_file:
                self._last_labelme_file = current_file
                # 高亮显示当前文件
                self._highlightCurrentFile(current_file)
                
        except Exception as e:
            # 静默处理错误，避免干扰主程序
            pass
    
    def _syncWithLabelmeDir(self, dir_path):
        """同步labelme打开的目录到左侧面板"""
        if not dir_path or not osp.exists(dir_path):
            return
        
        # 使用handler加载目录
        if self.annotation_handler:
            self.annotation_handler.setDirectory(dir_path)
    
    def _highlightCurrentFile(self, file_path):
        """高亮显示当前正在标注的文件"""
        if not file_path:
            return
        
        # 在列表中查找并选中当前文件
        for i in range(self.annotation_list.count()):
            item = self.annotation_list.item(i)
            data = item.data(Qt.UserRole)
            
            if data and data['image_path'] == file_path:
                # 选中该项（不触发点击事件，避免循环）
                self.annotation_list.blockSignals(True)
                self.annotation_list.setCurrentItem(item)
                self.annotation_list.scrollToItem(item)
                self.annotation_list.blockSignals(False)
                
                # 更新详细信息
                self.updateDetailInfo(data)
                break
    
    def onOpenFolder(self):
        """打开文件夹对话框"""
        current_dir = self.annotation_handler.getCurrentDirectory() if self.annotation_handler else ""
        
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择标注数据文件夹",
            current_dir if current_dir else ""
        )
        
        if folder and self.annotation_handler:
            # 使用handler加载目录
            self.annotation_handler.setDirectory(folder)
    
    def onDirectoryChanged(self, dir_path):
        """目录变化时的UI更新（响应handler信号）"""
        # 只显示文件夹名称，不显示完整路径
        import os.path as osp
        folder_name = osp.basename(dir_path) if dir_path else ""
        self.lbl_current_folder.setText(folder_name)
        self.lbl_current_folder.setStyleSheet("color: #2ca02c; font-style: normal; font-weight: bold; font-size: 9pt;")
    
    def onFileListUpdated(self, file_info_list):
        """文件列表更新时的UI更新（响应handler信号）"""
        self.loadFileListToUI(file_info_list)
    
    def onStatisticsUpdated(self, statistics):
        """统计信息更新时的UI更新（响应handler信号）"""
        self.lbl_total_stats.setText(f"总数: {statistics['total']}")
        self.lbl_annotated_stats.setText(f"已标注: {statistics['annotated']}")
    
    def loadFileListToUI(self, file_info_list):
        """
        将文件信息列表加载到UI（纯UI更新，数据由handler提供）
        
        Args:
            file_info_list: handler提供的文件信息列表
        """
        self.annotation_list.clear()
        
        if not file_info_list:
            return
        
        for info in file_info_list:
            # 创建列表项
            item = QtWidgets.QListWidgetItem(self.annotation_list)
            
            # 设置图标（缩略图）
            if info.get('thumbnail'):
                item.setIcon(QtGui.QIcon(info['thumbnail']))
            else:
                # 使用默认图标
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
                item.setIcon(icon)
            
            # 设置文本 - 显示更多JSON信息
            status_text = "✓" if info['has_json'] else "○"
            
            # 构建显示文本
            display_text = f"{status_text} {info['file_name']}"
            
            # 如果有JSON文件，显示标注详情
            if info['has_json']:
                shapes_count = info.get('shapes_count', 0)
                modified_time = info.get('modified_time', '--')
                resolution = info.get('resolution', '--')
                
                # 添加详细信息到第二行
                detail_line = f"  对象: {shapes_count} | 分辨率: {resolution}"
                display_text += f"\n{detail_line}"
                
                # 添加修改时间到第三行
                if modified_time != '--':
                    time_line = f"  修改: {modified_time}"
                    display_text += f"\n{time_line}"
            else:
                # 未标注，显示提示
                resolution = info.get('resolution', '--')
                detail_line = f"  未标注 | 分辨率: {resolution}"
                display_text += f"\n{detail_line}"
            
            item.setText(display_text)
            
            # 根据标注状态设置不同的文本颜色
            if info['has_json']:
                # 已标注 - 深绿色加粗
                item.setForeground(QtGui.QBrush(QtGui.QColor(44, 160, 44)))  # #2ca02c
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                # 未标注 - 灰色
                item.setForeground(QtGui.QBrush(QtGui.QColor(128, 128, 128)))  # #808080
            
            # 存储数据
            item.setData(Qt.UserRole, info)
    
    def onItemClicked(self, item):
        """列表项点击事件"""
        data = item.data(Qt.UserRole)
        if data:
            # 强制设置选中项的颜色
            if data.get('has_json'):
                item.setForeground(QtGui.QBrush(QtGui.QColor(44, 160, 44)))  # 绿色
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(128, 128, 128)))  # 灰色
            
            image_path = data['image_path']
            self.loadImageForAnnotation(image_path)
    
    def onItemSelectionChanged(self):
        """列表项选择变化事件"""
        # 重新设置所有项目的颜色（因为选中状态会改变颜色）
        for i in range(self.annotation_list.count()):
            item = self.annotation_list.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('has_json'):
                # 已标注 - 保持深绿色
                item.setForeground(QtGui.QBrush(QtGui.QColor(44, 160, 44)))  # #2ca02c
            else:
                # 未标注 - 灰色
                item.setForeground(QtGui.QBrush(QtGui.QColor(128, 128, 128)))  # #808080
        
        items = self.annotation_list.selectedItems()
        if not items:
            return
        
        item = items[0]
        data = item.data(Qt.UserRole)
        
        if data:
            self.updateDetailInfo(data)
    
    def updateDetailInfo(self, data):
        """
        更新详细信息面板（数据已由handler处理好）
        
        Args:
            data: handler提供的文件信息字典
        """
        # 详细信息面板已移除，此方法保留以保持兼容性
        pass
    
    def onSearch(self):
        """搜索功能（使用handler进行筛选）"""
        if not self.annotation_handler:
            return
        
        search_text = self.search_edit.text().strip()
        filter_index = self.filter_combo.currentIndex()
        
        # 映射筛选类型
        filter_type_map = {
            0: 'all',
            1: 'annotated',
            2: 'unannotated',
            3: 'review'
        }
        filter_type = filter_type_map.get(filter_index, 'all')
        
        # 使用handler筛选
        filtered_list = self.annotation_handler.filterFiles(filter_type, search_text)
        
        # 更新UI显示
        self.loadFileListToUI(filtered_list)
    
    def onFilterChanged(self):
        """筛选功能（使用handler进行筛选）"""
        # 触发搜索，会同时应用筛选条件
        self.onSearch()
    
    def loadImageForAnnotation(self, image_path, json_path=None):
        """
        加载图片到labelme进行标注
        
        Args:
            image_path: 图片文件路径
            json_path: JSON标注文件路径（可选）
        """
        if self.labelme_widget is None:
            return
        
        try:
            # 使用labelme的loadFile方法加载图片
            self.labelme_widget.loadFile(image_path)
        except Exception as e:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("AnnotationTool 数据标注工具组件测试")
    window.resize(1400, 800)
    
    # 创建标注工具组件
    annotation_tool = AnnotationTool()
    window.setCentralWidget(annotation_tool)
    
    # 添加测试数据到标注列表
    test_images = [
        {
            "name": "image_001.jpg",
            "size": "2.5 MB",
            "resolution": "1920x1080",
            "json": "存在",
            "objects": "3 个对象",
            "time": "2025-10-16 10:30"
        },
        {
            "name": "image_002.jpg",
            "size": "1.8 MB",
            "resolution": "1280x720",
            "json": "存在",
            "objects": "5 个对象",
            "time": "2025-10-16 10:32"
        },
        {
            "name": "image_003.jpg",
            "size": "3.2 MB",
            "resolution": "1920x1080",
            "json": "不存在",
            "objects": "0 个对象",
            "time": "--"
        },
        {
            "name": "image_004.jpg",
            "size": "2.1 MB",
            "resolution": "1280x720",
            "json": "存在",
            "objects": "2 个对象",
            "time": "2025-10-16 10:35"
        },
    ]
    
    for img_data in test_images:
        item = QtWidgets.QListWidgetItem(annotation_tool.annotation_list)
        
        # 设置图标（使用默认图标）
        icon = annotation_tool.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        item.setIcon(icon)
        
        # 设置文本
        status_emoji = "" if img_data["json"] == "存在" else "⏳"
        item.setText(f"{status_emoji} {img_data['name']}\n{img_data['resolution']} | {img_data['objects']}")
        
        # 存储数据
        item.setData(Qt.UserRole, img_data)
    
    # 选中第一项
    if annotation_tool.annotation_list.count() > 0:
        annotation_tool.annotation_list.setCurrentRow(0)
    
    # 更新统计信息
    total = len(test_images)
    annotated = sum(1 for img in test_images if img["json"] == "存在")
    annotation_tool.lbl_total_stats.setText(f"总数: {total}")
    annotation_tool.lbl_annotated_stats.setText(f"已标注: {annotated}")
    
    window.show()
    sys.exit(app.exec_())

