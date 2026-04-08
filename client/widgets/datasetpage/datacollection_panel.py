# -*- coding: utf-8 -*-

"""
数据采集面板

左侧：目录管理（可新增/删除文件夹）
右侧：文件夹内容预览和通道控制
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp

# 导入图标工具和响应式布局
try:
    from ..style_manager import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, osp.join(osp.dirname(__file__), '..'))
    try:
        from style_manager import newIcon
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        def newIcon(icon):
            return QtGui.QIcon()
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x

# 导入对话框管理器（独立导入，不受icons影响）
try:
    from ..style_manager import DialogManager
except (ImportError, ValueError) as e:
    try:
        from style_manager import DialogManager
    except ImportError as e2:
        DialogManager = None

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


class DataCollectionPanel(QtWidgets.QWidget):
    """
    数据采集面板
    
    两栏布局：左侧目录管理，右侧内容预览和控制
    """
    
    # 自定义信号
    folderSelected = QtCore.Signal(str)         # 文件夹被选中
    folderAdded = QtCore.Signal(str)            # 文件夹被添加
    folderDeleted = QtCore.Signal(str)          # 文件夹被删除
    channelStarted = QtCore.Signal()             # 通道启动
    channelStopped = QtCore.Signal()             # 通道停止
    videoUploaded = QtCore.Signal(str)          # 视频上传（文件路径）
    
    def __init__(self, parent=None, root_path=None):
        """
        Args:
            parent: 父窗口
            root_path: 根目录路径（默认为项目 database/data）
        """
        super(DataCollectionPanel, self).__init__(parent)
        self._parent = parent
        
        # 设置根目录
        if root_path is None:
            project_root = get_project_root()
            self._root_path = osp.join(project_root, 'database', 'data')
        else:
            self._root_path = root_path
        
        # 确保根目录存在
        os.makedirs(self._root_path, exist_ok=True)
        
        # 当前选中的文件夹
        self._current_folder = None
        
        # 通道状态（现在由父窗口的DataCollectionChannelHandler管理）
        # 这里只保留UI状态标志
        self._channel_running = False
        
        self._initUI()
        self._connectSignals()
        self._loadFolders()
    
    def _showWarning(self, title, message):
        """显示警告对话框"""
        if DialogManager:
            DialogManager.show_warning(self, title, message)
        else:
            QtWidgets.QMessageBox.warning(self, title, message)
    
    def _showInformation(self, title, message):
        """显示信息对话框"""
        if DialogManager:
            DialogManager.show_information(self, title, message)
        else:
            QtWidgets.QMessageBox.information(self, title, message)
    
    def _showCritical(self, title, message):
        """显示错误对话框"""
        if DialogManager:
            DialogManager.show_critical(self, title, message)
        else:
            QtWidgets.QMessageBox.critical(self, title, message)
    
    def _showQuestion(self, title, message):
        """显示询问对话框"""
        if DialogManager:
            return DialogManager.show_question(self, title, message)
        else:
            reply = QtWidgets.QMessageBox.question(self, title, message)
            return reply == QtWidgets.QMessageBox.Yes
    
    def _showQuestionWarning(self, title, message):
        """显示警告询问对话框（用于删除确认等危险操作）"""
        if DialogManager:
            return DialogManager.show_question_warning(self, title, message)
        else:
            reply = QtWidgets.QMessageBox.question(self, title, message)
            return reply == QtWidgets.QMessageBox.Yes
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QHBoxLayout(self)
        ResponsiveLayout.apply_to_layout(main_layout, base_spacing=0, base_margins=0)
        
        # 创建可调整大小的分割器
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # === 左侧：目录管理面板 ===
        self.left_panel = self._createLeftPanel()
        self.splitter.addWidget(self.left_panel)
        
        # === 右侧：内容预览和控制面板 ===
        self.right_panel = self._createRightPanel()
        self.splitter.addWidget(self.right_panel)
        
        # 设置分割器比例 (左:右 = 1:3)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(self.splitter)
    
    def _createLeftPanel(self):
        """创建左侧目录管理面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        ResponsiveLayout.apply_to_layout(layout, base_spacing=5, base_margins=5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("数据采集")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 根目录显示（已删除）
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
        # self.btn_add_folder.setIcon(newIcon("add"))  # 删除图标，只使用文本
        # 使用Qt默认样式
        button_layout.addWidget(self.btn_add_folder)
        
        self.btn_delete_folder = QtWidgets.QPushButton("删除文件夹")
        self.btn_delete_folder.setIcon(newIcon("关闭"))
        # 使用Qt默认样式
        button_layout.addWidget(self.btn_delete_folder)
        
        layout.addLayout(button_layout)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _createRightPanel(self):
        """创建右侧内容预览和控制面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        ResponsiveLayout.apply_to_layout(layout, base_spacing=5, base_margins=5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("内容预览")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 控制按钮组（三个按钮）
        control_layout = QtWidgets.QHBoxLayout()
        
        # 通道选择下拉框
        channel_select_layout = QtWidgets.QHBoxLayout()
        # 增加5px间距
        from ..responsive_layout import scale_spacing
        channel_select_layout.setSpacing(scale_spacing(5))
        channel_label = QtWidgets.QLabel("选择通道:")
        channel_label.setFixedWidth(scale_w(75))  # 响应式宽度
        
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.setFixedWidth(scale_w(90))  # 响应式宽度
        # 向右移动5px
        from ..responsive_layout import scale_margin
        margin = scale_margin(5)
        self.channel_combo.setContentsMargins(margin, 0, 0, 0)
        # 使用Qt默认样式，不设置复杂的自定义样式
        
        # 填充通道选项
        self._populateChannelOptions()
        
        # 默认选择第一个RTSP通道（如果有的话）
        self._selectDefaultChannel()
        
        channel_select_layout.addWidget(channel_label)
        channel_select_layout.addWidget(self.channel_combo)
        channel_select_layout.addStretch()
        
        control_layout.addLayout(channel_select_layout)
        
        # 定义统一的按钮样式（与任务管理面板保持一致）
        button_style = """
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
            QPushButton:disabled {
                background-color: #f8f8f8;
                color: #a0a0a0;
                border: 1px solid #d0d0d0;
            }
        """
        
        self.btn_start_channel = QtWidgets.QPushButton("启动通道")
        # self.btn_start_channel.setIcon(newIcon("开始"))  # 删除图标
        # self.btn_start_channel.setStyleSheet(button_style)  # 使用Qt默认样式
        control_layout.addWidget(self.btn_start_channel)
        
        self.btn_record_video = QtWidgets.QPushButton("录制视频")
        # self.btn_record_video.setIcon(newIcon("视频直播"))  # 删除图标
        self.btn_record_video.setEnabled(False)  # 初始禁用，需要先启动通道
        # self.btn_record_video.setStyleSheet(button_style)  # 使用Qt默认样式
        control_layout.addWidget(self.btn_record_video)
        
        self.btn_stop_channel = QtWidgets.QPushButton("关闭通道")
        # self.btn_stop_channel.setIcon(newIcon("停止1"))  # 删除图标
        self.btn_stop_channel.setEnabled(False)  # 初始禁用
        # self.btn_stop_channel.setStyleSheet(button_style)  # 使用Qt默认样式
        control_layout.addWidget(self.btn_stop_channel)
        
        self.btn_upload_video = QtWidgets.QPushButton("上传本地视频")
        # self.btn_upload_video.setIcon(newIcon("文件夹"))  # 删除图标
        # self.btn_upload_video.setStyleSheet(button_style)  # 使用Qt默认样式
        control_layout.addWidget(self.btn_upload_video)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 当前文件夹信息
        self.lbl_current_folder = QtWidgets.QLabel("未选择文件夹")
        self.lbl_current_folder.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #e8f4f8;
                border: 1px solid #0078d7;
                border-radius: 3px;
                font-weight: bold;
                color: #0078d7;
            }
        """)
        layout.addWidget(self.lbl_current_folder)
        
        # === 内容区域：左右布局（左侧文件列表 + 右侧通道预览） ===
        content_layout = QtWidgets.QHBoxLayout()
        from ..responsive_layout import scale_spacing
        content_layout.setSpacing(scale_spacing(10))
        
        # 左侧：内容预览区域（文件列表 - 中等图标模式）
        self.content_list = QtWidgets.QListWidget()
        self.content_list.setViewMode(QtWidgets.QListWidget.IconMode)  # 图标模式
        self.content_list.setIconSize(QtCore.QSize(100, 75))  # 中等图标尺寸
        self.content_list.setGridSize(QtCore.QSize(160, 130))  # 增大网格尺寸以显示完整文件名
        self.content_list.setResizeMode(QtWidgets.QListWidget.Adjust)  # 自动调整
        self.content_list.setMovement(QtWidgets.QListWidget.Static)  # 固定位置
        from ..responsive_layout import scale_spacing
        self.content_list.setSpacing(scale_spacing(8))
        self.content_list.setWordWrap(True)  # 文字换行
        self.content_list.setStyleSheet("""
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
                color: #000;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                border: 2px solid #c0c0c0;
            }
        """)
        # 启用右键菜单
        self.content_list.setContextMenuPolicy(Qt.CustomContextMenu)
        content_layout.addWidget(self.content_list)
        
        # 右侧：通道预览区域 - 响应式布局
        self.channel_preview = QtWidgets.QLabel()
        self.channel_preview.setFixedSize(scale_w(640), scale_h(480))  # 响应式尺寸
        self.channel_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.channel_preview.setStyleSheet("""
            QLabel {
                border: 2px solid #0078d7;
                background-color: black;
                color: white;
                font-size: 14pt;
            }
        """)
        self.channel_preview.setText("通道预览\n点击\"启动通道\"开始预览")
        content_layout.addWidget(self.channel_preview)
        
        # 将内容布局添加到主布局
        layout.addLayout(content_layout)
        
        # 底部统计信息
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.lbl_content_stats = QtWidgets.QLabel("文件数: 0")
        self.lbl_content_stats.setStyleSheet("color: #666; padding: 5px;")
        stats_layout.addWidget(self.lbl_content_stats)
        
        stats_layout.addStretch()
        
        self.lbl_channel_status = QtWidgets.QLabel("通道状态: 未启动")
        self.lbl_channel_status.setStyleSheet("color: #666; padding: 5px;")
        stats_layout.addWidget(self.lbl_channel_status)
        
        layout.addLayout(stats_layout)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _connectSignals(self):
        """连接信号槽"""
        # 左侧面板
        self.folder_list.itemClicked.connect(self._onFolderClicked)
        self.folder_list.itemDoubleClicked.connect(self._onFolderDoubleClicked)
        self.folder_list.customContextMenuRequested.connect(self._onFolderListContextMenu)
        self.btn_add_folder.clicked.connect(self._onAddFolder)
        self.btn_delete_folder.clicked.connect(self._onDeleteFolder)
        
        # 文件列表信号
        self.content_list.itemDoubleClicked.connect(self._onFileDoubleClicked)
        self.content_list.customContextMenuRequested.connect(self._onContentListContextMenu)
        
        # 右侧面板
        self.btn_start_channel.clicked.connect(self._onStartChannel)
        self.btn_record_video.clicked.connect(self._onRecordVideo)
        self.btn_stop_channel.clicked.connect(self._onStopChannel)
        self.btn_upload_video.clicked.connect(self._onUploadVideo)
    
    # ========== 公共方法 ==========
    
    def setRootPath(self, path):
        """设置根目录"""
        if osp.exists(path) and osp.isdir(path):
            self._root_path = path
            self._loadFolders()
            return True
        else:
            return False
    
    def getRootPath(self):
        """获取根目录"""
        return self._root_path
    
    def getCurrentFolder(self):
        """获取当前选中的文件夹"""
        return self._current_folder
    
    def refreshFolders(self):
        """刷新文件夹列表"""
        self._loadFolders()
    
    def refreshContent(self):
        """刷新内容列表"""
        if self._current_folder:
            self._loadFolderContent(self._current_folder)
    
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
            
        except Exception as e:
            pass
    
    def _loadFolderContent(self, folder_name):
        """加载文件夹内容"""
        self.content_list.clear()
        
        folder_path = osp.join(self._root_path, folder_name)
        
        if not osp.exists(folder_path):
            print(f"[数据采集] 文件夹不存在: {folder_path}")
            return
        
        try:
            # 获取所有文件
            files = [f for f in os.listdir(folder_path) 
                    if osp.isfile(osp.join(folder_path, f))]
            files.sort()
            
            print(f"[数据采集] 在文件夹 {folder_name} 中找到 {len(files)} 个文件")
            
            # 添加到列表
            for file in files:
                file_path = osp.join(folder_path, file)
                
                # 检查文件是否正在被录制，如果是则跳过显示
                if self._isFileBeingRecorded(file_path):
                    continue
                    
                item = QtWidgets.QListWidgetItem(self.content_list)
                
                # 根据文件类型设置不同的图标和文本
                file_ext = osp.splitext(file)[1].lower()
                
                # 显示文件名（适当截断以适应显示）
                display_name = file
                if len(display_name) > 25:  # 增加截断长度
                    display_name = display_name[:22] + "..."
                
                if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.mpg', '.mpeg']:
                    # 视频文件 - 生成第一帧缩略图
                    thumbnail = self._generateVideoThumbnail(file_path)
                    if thumbnail:
                        item.setIcon(QtGui.QIcon(thumbnail))
                    else:
                        # 缩略图生成失败，使用默认视频图标
                        icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
                        item.setIcon(icon)
                    item.setText(f"\n{display_name}")
                elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    # 图片文件 - 加载图片作为缩略图
                    thumbnail = self._generateImageThumbnail(file_path)
                    if thumbnail:
                        item.setIcon(QtGui.QIcon(thumbnail))
                    else:
                        icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
                        item.setIcon(icon)
                    item.setText(f"\n{display_name}")
                else:
                    # 其他文件
                    icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
                    item.setIcon(icon)
                    item.setText(f"\n{display_name}")
                
                item.setData(Qt.UserRole, file_path)  # 存储完整路径
                item.setToolTip(file)  # 完整文件名作为提示
                item.setTextAlignment(Qt.AlignCenter)  # 文本居中对齐
            
            # 更新统计
            self.lbl_content_stats.setText(f"文件数: {len(files)}")
            
        except Exception as e:
            pass
    
    def _generateVideoThumbnail(self, video_path):
        """生成视频缩略图（提取第一帧）"""
        try:
            import cv2
            import time
            
            # 尝试多次打开视频文件（刚录制完成的文件可能需要等待）
            cap = None
            for attempt in range(3):
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    break
                if cap:
                    cap.release()
                time.sleep(0.1)  # 等待100ms后重试
            
            if not cap or not cap.isOpened():
                return None
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None
            
            # 检查 QGuiApplication 是否存在（避免应用关闭时出错）
            from qtpy.QtWidgets import QApplication
            if not QApplication.instance():
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
                100, 75,  # 与 setIconSize 设置的尺寸一致
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            return scaled_pixmap
            
        except Exception as e:
            return None
    
    def _generateImageThumbnail(self, image_path):
        """生成图片缩略图"""
        try:
            # 检查 QGuiApplication 是否存在（避免应用关闭时出错）
            from qtpy.QtWidgets import QApplication
            if not QApplication.instance():
                return None
            
            # 加载图片
            pixmap = QtGui.QPixmap(image_path)
            
            if pixmap.isNull():
                return None
            
            # 缩放到缩略图尺寸
            scaled_pixmap = pixmap.scaled(
                100, 75,  # 与 setIconSize 设置的尺寸一致
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            return scaled_pixmap
            
        except Exception as e:
            return None
    
    def _isFileBeingRecorded(self, file_path):
        """检查文件是否正在被录制"""
        try:
            # 检查父窗口是否有录制状态信息
            if not hasattr(self._parent, '_dc_video_recording'):
                return False
            
            # 如果没有在录制，返回False
            if not getattr(self._parent, '_dc_video_recording', False):
                return False
            
            # 检查是否是当前录制的文件
            current_video_path = getattr(self._parent, '_dc_video_path', None)
            if current_video_path and osp.abspath(file_path) == osp.abspath(current_video_path):
                return True
            
            # 额外检查：如果文件正在被写入（文件被占用）
            # 这可以捕获到正在录制但路径不匹配的情况
            try:
                # 尝试以独占模式打开文件，如果失败说明文件被占用
                with open(file_path, 'r+b'):
                    pass
                return False  # 文件可以打开，说明没有被占用
            except (IOError, OSError):
                # 文件被占用，可能正在录制
                # 但只有在确实在录制状态时才返回True
                return getattr(self._parent, '_dc_video_recording', False)
                
        except Exception as e:
            # 发生异常时，为安全起见不隐藏文件
            return False
    
    # _updateChannelFrame 方法已移除
    # 现在由 DataCollectionChannelHandler 直接更新 channel_preview 控件
    
    # ========== 槽函数 ==========
    
    def _onFolderClicked(self, item):
        """文件夹被点击"""
        folder_name = item.data(Qt.UserRole)
        self._current_folder = folder_name
        
        # 更新显示
        self.lbl_current_folder.setText(f"当前文件夹: {folder_name}")
        
        # 加载文件夹内容
        self._loadFolderContent(folder_name)
        
        # 发射信号
        folder_path = osp.join(self._root_path, folder_name)
        self.folderSelected.emit(folder_path)
    
    def _onFolderDoubleClicked(self, item):
        """文件夹被双击"""
        folder_name = item.data(Qt.UserRole)
        folder_path = osp.join(self._root_path, folder_name)
        
        # 在系统文件管理器中打开
        try:
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # macOS, Linux
                import subprocess
                subprocess.Popen(['open', folder_path])
            
        except Exception as e:
            pass
    
    def _onFileDoubleClicked(self, item):
        """文件被双击 - 播放视频文件"""
        # 从item的UserRole中获取完整路径
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return
        
        file_name = osp.basename(file_path)
        
        # 检查文件是否存在
        if not osp.exists(file_path):
            self._showWarning("警告", f"文件不存在: {file_name}\n路径: {file_path}")
            return
        
        # 检查是否为视频文件
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.mpg', '.mpeg']
        file_ext = osp.splitext(file_name)[1].lower()
        
        if file_ext in video_extensions:
            # 播放视频文件
            self._playVideoFile(file_path)
        else:
            # 非视频文件，用系统默认程序打开
            self._openFileWithSystem(file_path)
    
    def _playVideoFile(self, file_path):
        """播放视频文件"""
        try:
            import subprocess
            import sys
            
            if os.name == 'nt':  # Windows
                # 尝试使用系统默认视频播放器
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
                
        except Exception as e:
            self._showWarning(
                "播放失败", 
                f"无法播放视频文件:\n{file_path}\n\n错误: {str(e)}"
            )
    
    def _openFileWithSystem(self, file_path):
        """用系统默认程序打开文件"""
        try:
            import subprocess
            import sys
            
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
                
        except Exception as e:
            self._showWarning(
                "打开失败", 
                f"无法打开文件:\n{file_path}\n\n错误: {str(e)}"
            )
    
    def _onContentListContextMenu(self, position):
        """显示内容列表的右键菜单"""
        # 获取当前选中的项
        item = self.content_list.itemAt(position)
        
        if not item:
            return
        
        # 获取文件路径
        file_path = item.data(Qt.UserRole)
        
        if not file_path:
            return
        
        # 创建右键菜单
        menu = QtWidgets.QMenu(self)
        
        # 添加菜单项
        action_rename = menu.addAction(newIcon("设置"), "重命名")
        action_delete = menu.addAction(newIcon("关闭"), "删除")
        
        # 显示菜单并获取选择的动作
        action = menu.exec_(self.content_list.mapToGlobal(position))
        
        # 处理选择的动作
        if action == action_rename:
            self._onRenameFile(item)
        elif action == action_delete:
            self._onDeleteFile(item)
    
    def _onRenameFile(self, item):
        """重命名文件"""
        if not item:
            return
        
        # 获取文件路径
        file_path = item.data(Qt.UserRole)
        
        if not file_path or not osp.exists(file_path):
            self._showWarning("警告", "文件不存在")
            return
        
        # 获取当前文件名（不含扩展名）和扩展名
        file_dir = osp.dirname(file_path)
        file_name = osp.basename(file_path)
        file_name_no_ext, file_ext = osp.splitext(file_name)
        
        # 弹出输入对话框
        dialog = QtWidgets.QInputDialog(self)
        dialog.setWindowTitle("重命名文件")
        dialog.setLabelText("请输入新的文件名（不含扩展名）:")
        dialog.setTextValue(file_name_no_ext)
        dialog.setInputMode(QtWidgets.QInputDialog.TextInput)
        # 隐藏问号按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # 设置中文按钮文本
        dialog.setOkButtonText("确定")
        dialog.setCancelButtonText("取消")
        # 应用全局字体管理
        if DialogManager:
            from ..style_manager import FontManager
            FontManager.applyToWidgetRecursive(dialog)
            # 应用统一按钮样式
            DialogManager.applyButtonStylesToDialog(dialog)
        
        ok = dialog.exec_()
        new_name = dialog.textValue()
        
        if not ok or not new_name.strip():
            return
        
        # 构建新的文件路径
        new_file_name = new_name.strip() + file_ext
        new_file_path = osp.join(file_dir, new_file_name)
        
        # 检查新文件名是否已存在
        if osp.exists(new_file_path):
            self._showWarning("警告", f"文件 '{new_file_name}' 已存在")
            return
        
        # 重命名文件
        try:
            os.rename(file_path, new_file_path)
            
            # 刷新内容列表
            if self._current_folder:
                self._loadFolderContent(self._current_folder)
            
            self._showInformation("成功", f"文件已重命名为: {new_file_name}")
            
        except Exception as e:
            self._showCritical("错误", f"重命名文件失败:\n{str(e)}")
    
    def _onFolderListContextMenu(self, position):
        """显示文件夹列表的右键菜单"""
        # 获取点击位置的项
        item = self.folder_list.itemAt(position)
        
        # 创建右键菜单
        menu = QtWidgets.QMenu(self)
        
        if item:
            # 在文件夹上右键：显示删除选项
            action_delete = menu.addAction(newIcon("删除"), "删除当前文件夹")
            
            # 显示菜单并获取选择的动作
            action = menu.exec_(self.folder_list.mapToGlobal(position))
            
            # 处理选择的动作
            if action == action_delete:
                self._onDeleteFolder()
        else:
            # 在空白处右键：显示新建和刷新选项
            action_new_folder = menu.addAction(newIcon("add"), "新建文件夹")
            action_refresh = menu.addAction(newIcon("刷新"), "刷新列表")
            
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
            self._loadFolderContent(self._current_folder)
    
    def _onDeleteFile(self, item):
        """删除文件"""
        if not item:
            return
        
        # 获取文件路径
        file_path = item.data(Qt.UserRole)
        
        if not file_path or not osp.exists(file_path):
            self._showWarning("警告", "文件不存在")
            return
        
        file_name = osp.basename(file_path)
        
        # 确认删除
        if self._showQuestionWarning(
            "确认删除", 
            f"确定要删除文件 '{file_name}' 吗？\n\n文件将被移动到回收站"
        ):
            try:
                # 使用Windows回收站删除
                if delete_file_to_recycle_bin:
                    delete_file_to_recycle_bin(file_path)
                
                # 刷新内容列表
                if self._current_folder:
                    self._loadFolderContent(self._current_folder)
                
              
                
            except Exception as e:
                self._showCritical("错误", f"删除文件失败:\n{str(e)}")
        else:
            pass
    
    def _onAddFolder(self):
        """新增文件夹"""
        # 创建自定义对话框（移除帮助按钮，使用中文按钮）
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("新增文件夹")
        
        # 设置左上角图标为系统自带的文件夹图标
        dialog.setWindowIcon(
            dialog.style().standardIcon(QtWidgets.QStyle.SP_DirIcon)
        )
        
        # 移除帮助按钮（问号按钮）
        dialog.setWindowFlags(
            dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
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
        
        # 应用全局字体管理和按钮样式
        if DialogManager:
            from ..style_manager import FontManager, TextButtonStyleManager
            FontManager.applyToWidgetRecursive(dialog)
            # 应用统一按钮样式
            TextButtonStyleManager.applyToButton(ok_btn)
            TextButtonStyleManager.applyToButton(cancel_btn)
        
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
                
                # 刷新列表
                self._loadFolders()
                
                # 发射信号
                self.folderAdded.emit(folder_path)
                
            except Exception as e:
                self._showCritical("错误", f"创建文件夹失败: {e}")
    
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
            message = f"确定要删除文件夹“{folder_name}”吗？文件夹内含有{file_info_text}，所有内容将被移动到回收站。"
        else:
            message = f"确定要删除文件夹“{folder_name}”吗？文件夹为空，将被移动到回收站。"
        
        # 确认删除
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
                    self.lbl_current_folder.setText("未选择文件夹")
                    self.content_list.clear()
                    self.lbl_content_stats.setText("文件数: 0")
                
                # 刷新列表
                self._loadFolders()
                
                # 发射信号
                self.folderDeleted.emit(folder_path)
                
            except Exception as e:
                self._showCritical("错误", f"删除文件夹失败: {e}")
    
    def _onStartChannel(self):
        """启动通道 - 使用新的数据采集通道系统"""
        if not self._current_folder:
            self._showWarning("警告", "请先选择一个文件夹用于保存采集数据")
            return
        
        # 获取保存文件夹路径
        save_folder = osp.join(self._root_path, self._current_folder)
        
        # 获取选择的通道
        selected_channel = self._getSelectedChannel()
        
        if selected_channel is None:
            self._showWarning("警告", "请先选择一个通道")
            return
        
        # 通过父窗口的通道处理器启动通道
        if hasattr(self._parent, 'startDataCollectionChannel'):
            # 启动通道（在后台线程中连接）
            # 连接成功或失败的通知会通过handler的回调自动处理
            self._parent.startDataCollectionChannel(
                save_folder=save_folder,
                channel_source=selected_channel
            )
        else:
            # 如果父窗口没有通道处理器，显示错误
            self._showCritical(
                "错误", 
                "数据采集通道系统未初始化\n\n请确保主窗口已正确集成DataCollectionChannelHandler"
            )
    
    def _onRecordVideo(self):
        """录制视频"""
        if not self._current_folder:
            self._showWarning("警告", "请先选择一个文件夹用于保存录制的视频")
            return
        
        # 检查通道是否正在运行
        if hasattr(self._parent, 'getDataCollectionChannelStatus'):
            status = self._parent.getDataCollectionChannelStatus()
            if not status.get('running', False):
                self._showWarning("警告", "请先启动通道后再开始录制视频")
                return
        
        # 获取保存文件夹路径
        save_folder = osp.join(self._root_path, self._current_folder)
        
        # 生成视频文件名
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        video_filename = f"采集视频_{timestamp}.mp4"
        video_path = osp.join(save_folder, video_filename)
        
        # 通过父窗口的通道处理器开始录制视频
        if hasattr(self._parent, 'startDataCollectionVideoRecording'):
            success = self._parent.startDataCollectionVideoRecording(video_path)
            
            if success:
                # 更新按钮状态
                self.btn_record_video.setText("停止录制")
                # 使用Qt默认样式，不动态设置
                
                # 断开原有信号，连接停止录制信号
                self.btn_record_video.clicked.disconnect()
                self.btn_record_video.clicked.connect(self._onStopRecording)
                
                self._showInformation("录制开始", f"开始录制视频\n保存路径: {video_filename}")
            else:
                self._showWarning("警告", "开始录制失败，请检查通道状态")
        else:
            self._showCritical("错误", "录制功能未实现\n\n请确保通道处理器支持视频录制功能")
    
    def _onStopRecording(self):
        """停止录制视频"""
        # 通过父窗口的通道处理器停止录制视频
        if hasattr(self._parent, 'stopDataCollectionVideoRecording'):
            success = self._parent.stopDataCollectionVideoRecording()
            
            # 恢复按钮状态
            self.btn_record_video.setText("录制视频")
            # 使用Qt默认样式，不动态设置
            
            # 断开停止录制信号，重新连接录制信号
            self.btn_record_video.clicked.disconnect()
            self.btn_record_video.clicked.connect(self._onRecordVideo)
            
            if success:
                print(f"[数据采集] 录制停止成功，准备刷新文件列表")
                print(f"[数据采集] 当前文件夹: {self._current_folder}")
                # 刷新内容列表（显示新录制的视频）
                if self._current_folder:
                    self._loadFolderContent(self._current_folder)
                    print(f"[数据采集] 文件列表已刷新")
            else:
                self._showWarning("录制失败", "录制时间过短，未能保存任何视频帧\n请确保录制时间足够长")
        else:
            self._showCritical("错误", "录制功能未实现")
    
    def _onStopChannel(self):
        """关闭通道 - 使用新的数据采集通道系统"""
        # 通过父窗口的通道处理器停止通道
        if hasattr(self._parent, 'stopDataCollectionChannel'):
            success = self._parent.stopDataCollectionChannel()
            
            if success:
                # 发射信号
                self.channelStopped.emit()
                
                # 刷新内容列表（显示新保存的图像）
                if self._current_folder:
                    self._loadFolderContent(self._current_folder)
                
                # 不再显示图片采集统计，因为现在主要功能是视频录制
            else:
                # 检查是否因为正在录制而被阻止（如果是，则不显示第二个提示框）
                if not (hasattr(self._parent, '_dc_close_blocked_by_recording') and self._parent._dc_close_blocked_by_recording):
                    self._showWarning("警告", "停止通道失败")
                else:
                    # 清除标志位，为下次做准备
                    self._parent._dc_close_blocked_by_recording = False
        else:
            # 如果父窗口没有通道处理器，显示错误
            self._showCritical(
                "错误", 
                "数据采集通道系统未初始化\n\n请确保主窗口已正确集成DataCollectionChannelHandler"
            )
    
    def _onUploadVideo(self):
        """上传本地视频"""
        if not self._current_folder:
            self._showWarning("警告", "请先选择一个目标文件夹")
            return
        
        # 选择视频文件
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv);;所有文件 (*.*)"
        )
        
        if not file_paths:
            return
        
        # 目标文件夹
        target_folder = osp.join(self._root_path, self._current_folder)
        
        # 复制文件
        try:
            import shutil
            copied_files = []
            
            for file_path in file_paths:
                file_name = osp.basename(file_path)
                target_path = osp.join(target_folder, file_name)
                
                # 检查是否已存在
                if osp.exists(target_path):
                    if not self._showQuestion(
                        "文件已存在", 
                        f"文件 '{file_name}' 已存在，是否覆盖？"
                    ):
                        continue
                
                # 复制文件
                shutil.copy2(file_path, target_path)
                copied_files.append(file_name)
                
                # 发射信号
                self.videoUploaded.emit(target_path)
            
            # 刷新内容列表
            self._loadFolderContent(self._current_folder)
            
            if copied_files:
                self._showInformation(
                    "上传成功", 
                    f"成功上传 {len(copied_files)} 个视频文件:\n\n" + 
                    "\n".join(copied_files[:5]) + 
                    ("\n..." if len(copied_files) > 5 else "")
                )
            
        except Exception as e:
            self._showCritical("错误", f"上传视频失败: {e}")


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("数据采集面板测试")
    window.resize(1200, 700)
    
    # 创建数据采集面板
    panel = DataCollectionPanel()
    window.setCentralWidget(panel)
    
    # 连接信号测试
    def on_folder_selected(folder_path):
        pass
    
    def on_folder_added(folder_path):
        pass
    
    def on_folder_deleted(folder_path):
        pass
    
    def on_channel_started():
        pass
    
    def on_channel_stopped():
        pass
    
    def on_video_uploaded(file_path):
        pass
    
    panel.folderSelected.connect(on_folder_selected)
    panel.folderAdded.connect(on_folder_added)
    panel.folderDeleted.connect(on_folder_deleted)
    panel.channelStarted.connect(on_channel_started)
    panel.channelStopped.connect(on_channel_stopped)
    panel.videoUploaded.connect(on_video_uploaded)
    
    window.show()
    sys.exit(app.exec_())


# 添加通道选择功能的方法
def _populateChannelOptions(self):
    """填充通道选择选项 - 硬编码显示固定通道"""
    try:
        self.channel_combo.clear()
        
        # 硬编码显示固定的通道1、通道2、通道3、通道4
        self.channel_combo.addItem("通道1", 1)
        self.channel_combo.addItem("通道2", 2)
        self.channel_combo.addItem("通道3", 3)
        self.channel_combo.addItem("通道4", 4)
        
    except Exception as e:
        pass

def _loadRTSPConfig(self):
    """从 default_config.yaml 加载RTSP配置"""
    try:
        import yaml
        import os
        
        # 从 default_config.yaml 读取配置
        try:
            from database.config import get_project_root
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return None
            
            # 读取 YAML 配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
            
            # 提取通道配置并转换为预期格式
            channels = {}
            for key, value in full_config.items():
                if key.startswith('channel') and isinstance(value, dict):
                    # 提取通道号码（如 "channel1" -> "1"）
                    channel_num = key.replace('channel', '')
                    
                    # 转换格式：address -> rtsp_url
                    channels[key] = {
                        'name': value.get('name', f'通道{channel_num}'),
                        'rtsp_url': value.get('address', ''),
                        'device_type': f'Channel{channel_num}'  # 使用通道号码作为设备类型
                    }
            
            # 返回标准化的配置结构
            return {
                'channels': channels
            } if channels else None
            
        except Exception as e:
            return None
        
    except Exception as e:
        return None

# 获取选择的通道方法
def _getSelectedChannel(self):
    """获取用户选择的通道"""
    try:
        current_data = self.channel_combo.currentData()
        
        if current_data == "custom":
            # 自定义RTSP地址
            dialog = QtWidgets.QInputDialog(self)
            dialog.setWindowTitle("自定义RTSP地址")
            dialog.setLabelText("请输入RTSP地址:\n(格式: rtsp://username:password@ip:port/path)")
            dialog.setInputMode(QtWidgets.QInputDialog.TextInput)
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            dialog.setOkButtonText("确定")
            dialog.setCancelButtonText("取消")
            # 应用全局字体管理
            if DialogManager:
                from style_manager import FontManager
                FontManager.applyToWidgetRecursive(dialog)
                # 应用统一按钮样式
                DialogManager.applyButtonStylesToDialog(dialog)
            
            ok = dialog.exec_()
            rtsp_url = dialog.textValue()
            
            if ok and rtsp_url.strip():
                return rtsp_url.strip()
            else:
                return None
        else:
            return current_data
            
    except Exception as e:
        return None

# 选择默认通道的方法
def _selectDefaultChannel(self):
    """选择默认通道（优先选择RTSP通道）"""
    try:
        # 查找第一个RTSP通道
        for i in range(self.channel_combo.count()):
            item_text = self.channel_combo.itemText(i)
            if "(RTSP)" in item_text:
                self.channel_combo.setCurrentIndex(i)
                return
        
        # 如果没有RTSP通道，保持默认选择（USB通道 0）
        
    except Exception as e:
        pass

# 将方法添加到类中
DataCollectionPanel._populateChannelOptions = _populateChannelOptions
DataCollectionPanel._loadRTSPConfig = _loadRTSPConfig
DataCollectionPanel._getSelectedChannel = _getSelectedChannel
DataCollectionPanel._selectDefaultChannel = _selectDefaultChannel

