# -*- coding: utf-8 -*-

"""
视频浏览器组件

提供文件夹浏览和视频预览功能
左侧：目录树显示
右侧：视频预览区域
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..style_manager import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, osp.dirname(__file__))
    try:
        from style_manager import newIcon
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        def newIcon(icon): 
            return QtGui.QIcon()
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x


class VideoBrowser(QtWidgets.QWidget):
    """
    视频浏览器组件
    
    左侧显示文件夹结构，右侧预览视频文件
    """
    
    # 自定义信号
    folderSelected = QtCore.Signal(str)  # 文件夹被选中
    videoSelected = QtCore.Signal(str)   # 视频文件被选中
    videoPlayed = QtCore.Signal(str)     # 视频开始播放
    
    def __init__(self, parent=None, root_path=None):
        super(VideoBrowser, self).__init__(parent)
        self._parent = parent
        
        # 设置默认根目录
        self._root_path = root_path or os.path.expanduser("~")
        
        # 视频文件扩展名
        self._video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
        
        # 当前选中的视频路径
        self._current_video_path = None
        
        self._initUI()
        self._connectSignals()
        
        # 加载根目录
        self.setRootPath(self._root_path)
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建分割器
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # === 左侧：文件夹树 ===
        self._createLeftPanel()
        self.splitter.addWidget(self.left_panel)
        
        # === 右侧：视频预览 ===
        self._createRightPanel()
        self.splitter.addWidget(self.right_panel)
        
        # 设置初始比例 (左:右 = 1:2)
        self.splitter.setSizes([300, 600])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(self.splitter)
    
    def _createLeftPanel(self):
        """创建左侧面板"""
        self.left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("文件夹")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 刷新按钮
        # 🔥 响应式按钮尺寸
        btn_size = scale_w(30)
        
        self.btn_refresh = QtWidgets.QPushButton()
        self.btn_refresh.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.btn_refresh.setToolTip("刷新")
        self.btn_refresh.setFixedSize(btn_size, btn_size)
        title_layout.addWidget(self.btn_refresh)
        
        # 选择根目录按钮
        self.btn_select_root = QtWidgets.QPushButton()
        self.btn_select_root.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        self.btn_select_root.setToolTip("选择根目录")
        self.btn_select_root.setFixedSize(btn_size, btn_size)
        title_layout.addWidget(self.btn_select_root)
        
        left_layout.addLayout(title_layout)
        
        # 根路径显示
        self.root_path_label = QtWidgets.QLabel(self._root_path)
        self.root_path_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                font-size: 9pt;
            }
        """)
        self.root_path_label.setWordWrap(True)
        left_layout.addWidget(self.root_path_label)
        
        # 文件系统模型和树视图
        self.file_model = QtWidgets.QFileSystemModel()
        self.file_model.setRootPath("")
        
        # 只显示文件夹
        self.file_model.setFilter(QtCore.QDir.Dirs | QtCore.QDir.NoDotAndDotDot)
        
        # 树视图
        self.tree_view = QtWidgets.QTreeView()
        self.tree_view.setModel(self.file_model)
        
        # 隐藏不需要的列（只保留名称列）
        self.tree_view.setColumnHidden(1, True)  # Size
        self.tree_view.setColumnHidden(2, True)  # Type
        self.tree_view.setColumnHidden(3, True)  # Date Modified
        
        # 设置样式
        self.tree_view.setStyleSheet("""
            QTreeView {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTreeView::item {
                padding: 5px;
            }
            QTreeView::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QTreeView::item:hover {
                background-color: #e0e0e0;
            }
        """)
        
        left_layout.addWidget(self.tree_view)
        
        # 统计信息
        self.stats_label = QtWidgets.QLabel("文件夹: 0 | 视频: 0")
        self.stats_label.setStyleSheet("font-size: 9pt; color: #666;")
        left_layout.addWidget(self.stats_label)
    
    def _createRightPanel(self):
        """创建右侧预览面板"""
        self.right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(10)
        
        # 预览容器（占据大部分空间）- 响应式布局
        self.preview_container = QtWidgets.QWidget()
        self.preview_container.setMinimumHeight(scale_h(400))  # 🔥 响应式高度
        self.preview_container.setStyleSheet("""
            QWidget {
                background-color: black;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
            }
        """)
        
        preview_layout = QtWidgets.QVBoxLayout(self.preview_container)
        
        # 预览标签（显示缩略图或提示）
        self.preview_label = QtWidgets.QLabel("点击左侧文件夹选择视频")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14pt;
                background-color: transparent;
                border: none;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        
        right_layout.addWidget(self.preview_container, stretch=2)
        
        # 视频信息
        info_group = QtWidgets.QGroupBox("视频信息")
        info_layout = QtWidgets.QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignRight)
        
        self.lbl_file_name = QtWidgets.QLabel("--")
        info_layout.addRow("文件名:", self.lbl_file_name)
        
        self.lbl_file_size = QtWidgets.QLabel("--")
        info_layout.addRow("文件大小:", self.lbl_file_size)
        
        self.lbl_file_path = QtWidgets.QLabel("--")
        self.lbl_file_path.setWordWrap(True)
        info_layout.addRow("路径:", self.lbl_file_path)
        
        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)
        
        # 操作按钮
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_play = QtWidgets.QPushButton("播放")
        self.btn_play.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self.btn_play.setEnabled(False)
        btn_layout.addWidget(self.btn_play)
        
        self.btn_open_folder = QtWidgets.QPushButton("打开文件夹")
        self.btn_open_folder.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        self.btn_open_folder.setEnabled(False)
        btn_layout.addWidget(self.btn_open_folder)
        
        btn_layout.addStretch()
        
        right_layout.addLayout(btn_layout)
    
    def _connectSignals(self):
        """连接信号槽"""
        # 左侧面板
        self.tree_view.clicked.connect(self._onFolderClicked)
        self.tree_view.doubleClicked.connect(self._onFolderDoubleClicked)
        self.btn_refresh.clicked.connect(self._onRefresh)
        self.btn_select_root.clicked.connect(self._onSelectRoot)
        
        # 右侧面板
        self.btn_play.clicked.connect(self._onPlayVideo)
        self.btn_open_folder.clicked.connect(self._onOpenFolder)
    
    # ========== 公共方法 ==========
    
    def setRootPath(self, path):
        """
        设置根目录
        
        Args:
            path: 根目录路径
        """
        if not osp.exists(path):
            return False
        
        self._root_path = path
        self.root_path_label.setText(path)
        
        # 设置树视图的根路径
        root_index = self.file_model.setRootPath(path)
        self.tree_view.setRootIndex(root_index)
        
        # 展开根节点
        self.tree_view.expand(root_index)
        
        return True
    
    def getRootPath(self):
        """获取当前根目录"""
        return self._root_path
    
    def getCurrentFolder(self):
        """获取当前选中的文件夹路径"""
        index = self.tree_view.currentIndex()
        if index.isValid():
            return self.file_model.filePath(index)
        return None
    
    def getCurrentVideo(self):
        """获取当前选中的视频文件路径"""
        return self._current_video_path
    
    def getVideoList(self):
        """获取当前文件夹中的视频列表"""
        folder = self.getCurrentFolder()
        if not folder or not osp.exists(folder):
            return []
        
        videos = []
        try:
            for file_name in sorted(os.listdir(folder)):
                file_path = osp.join(folder, file_name)
                if osp.isfile(file_path):
                    ext = osp.splitext(file_name)[1].lower()
                    if ext in self._video_extensions:
                        videos.append(file_path)
        except Exception as e:
            return []
        
        return videos
    
    # ========== 私有方法 ==========
    
    def _loadVideosFromFolder(self, folder_path):
        """
        加载文件夹中的视频文件，并自动显示第一个视频
        
        Args:
            folder_path: 文件夹路径
        """
        self._current_video_path = None
        self._clearVideoInfo()
        
        if not osp.exists(folder_path):
            return
        
        # 扫描视频文件
        video_files = []
        video_count = 0
        try:
            for file_name in sorted(os.listdir(folder_path)):
                file_path = osp.join(folder_path, file_name)
                
                # 检查是否是视频文件
                if osp.isfile(file_path):
                    ext = osp.splitext(file_name)[1].lower()
                    if ext in self._video_extensions:
                        video_files.append(file_path)
                        video_count += 1
            
            # 更新统计信息
            folder_count = len([f for f in os.listdir(folder_path) 
                               if osp.isdir(osp.join(folder_path, f))])
            self.stats_label.setText(f"文件夹: {folder_count} | 视频: {video_count}")
            
            # 如果有视频，自动加载第一个
            if video_files:
                self._current_video_path = video_files[0]
                self._updateVideoInfo(video_files[0])
                
                # 发送信号
                self.videoSelected.emit(video_files[0])
                
            else:
                self.preview_label.setText("该文件夹中没有视频文件")
            
        except Exception as e:
            self.stats_label.setText("加载失败")
    
    def _clearVideoInfo(self):
        """清空视频信息显示"""
        self.lbl_file_name.setText("--")
        self.lbl_file_size.setText("--")
        self.lbl_file_path.setText("--")
        self.preview_label.setText("点击左侧文件夹选择视频")
        self.btn_play.setEnabled(False)
        self.btn_open_folder.setEnabled(False)
    
    def _updateVideoInfo(self, video_path):
        """
        更新视频信息显示
        
        Args:
            video_path: 视频文件路径
        """
        if not osp.exists(video_path):
            return
        
        # 文件名
        file_name = osp.basename(video_path)
        self.lbl_file_name.setText(file_name)
        
        # 文件大小
        file_size = os.path.getsize(video_path)
        size_mb = file_size / (1024 * 1024)
        if size_mb < 1024:
            self.lbl_file_size.setText(f"{size_mb:.2f} MB")
        else:
            size_gb = size_mb / 1024
            self.lbl_file_size.setText(f"{size_gb:.2f} GB")
        
        # 文件路径
        self.lbl_file_path.setText(video_path)
        
        # 更新预览
        self.preview_label.setText(f"视频: {file_name}\n\n(预览功能需要视频解码库支持)")
        
        # 启用按钮
        self.btn_play.setEnabled(True)
        self.btn_open_folder.setEnabled(True)
    
    # ========== 槽函数 ==========
    
    def _onFolderClicked(self, index):
        """文件夹被点击"""
        if not index.isValid():
            return
        
        folder_path = self.file_model.filePath(index)
        
        # 加载该文件夹中的视频
        self._loadVideosFromFolder(folder_path)
        
        # 发送信号
        self.folderSelected.emit(folder_path)
    
    def _onFolderDoubleClicked(self, index):
        """文件夹被双击"""
        if not index.isValid():
            return
        
        # 双击时展开/折叠
        if self.tree_view.isExpanded(index):
            self.tree_view.collapse(index)
        else:
            self.tree_view.expand(index)
    
    def _onRefresh(self):
        """刷新"""
        current_folder = self.getCurrentFolder()
        if current_folder:
            self._loadVideosFromFolder(current_folder)
    
    def _onSelectRoot(self):
        """选择根目录"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择根目录",
            self._root_path
        )
        
        if folder:
            self.setRootPath(folder)
    
    def _onPlayVideo(self):
        """播放视频"""
        if not self._current_video_path:
            return
        
        # 发送信号
        self.videoPlayed.emit(self._current_video_path)
        
        # 使用系统默认程序打开视频
        try:
            if os.name == 'nt':  # Windows
                os.startfile(self._current_video_path)
            elif os.name == 'posix':  # macOS 或 Linux
                import subprocess
                subprocess.Popen(['xdg-open', self._current_video_path])
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "播放失败",
                f"无法播放视频:\n{str(e)}"
            )
    
    def _onOpenFolder(self):
        """打开文件夹"""
        if not self._current_video_path:
            return
        
        # 打开视频所在的文件夹
        folder_path = osp.dirname(self._current_video_path)
        
        try:
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # macOS 或 Linux
                import subprocess
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            pass


if __name__ == "__main__":
    """独立调试入口 - 测试代码"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("VideoBrowser 视频浏览器测试")
    window.resize(1200, 800)
    
    # 创建视频浏览器
    video_browser = VideoBrowser()
    window.setCentralWidget(video_browser)
    
    def on_folder_selected(folder_path):
        pass
    
    def on_video_selected(video_path):
        pass
    
    def on_video_played(video_path):
        pass
    
    video_browser.folderSelected.connect(on_folder_selected)
    video_browser.videoSelected.connect(on_video_selected)
    video_browser.videoPlayed.connect(on_video_played)
    
    window.show()
    sys.exit(app.exec_())

