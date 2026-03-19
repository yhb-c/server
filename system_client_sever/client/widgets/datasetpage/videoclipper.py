# -*- coding: utf-8 -*-

"""
视频裁剪器组件

三栏布局：
- 左侧：照片目录列表
- 中间：裁剪图片展示区
- 右侧：视频预览区
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
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


class VideoClipper(QtWidgets.QWidget):
    """
    视频裁剪器组件
    
    三栏布局界面：左侧目录、中间图片、右侧视频
    """
    
    # 自定义信号
    photoSelected = QtCore.Signal(str)      # 照片被选中
    clipImageSelected = QtCore.Signal(str)  # 裁剪图片被选中
    
    def __init__(self, parent=None):
        super(VideoClipper, self).__init__(parent)
        self._parent = parent
        
        self._initUI()
    
    def _initUI(self):
        """初始化UI - 三栏布局"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建可调整大小的分割器
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # === 左侧：照片目录 ===
        self.left_panel = self._createLeftPanel()
        self.splitter.addWidget(self.left_panel)
        
        # === 中间：裁剪图片展示区 ===
        self.middle_panel = self._createMiddlePanel()
        self.splitter.addWidget(self.middle_panel)
        
        # === 右侧：视频预览区 ===
        self.right_panel = self._createRightPanel()
        self.splitter.addWidget(self.right_panel)
        
        # 设置分割器比例 (左:中:右 = 1:2:2)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(self.splitter)
    
    def _createLeftPanel(self):
        """创建左侧照片目录面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("照片目录")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 刷新按钮
        self.btn_refresh_photos = QtWidgets.QPushButton("刷新")
        self.btn_refresh_photos.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_refresh_photos)
        
        layout.addLayout(title_layout)
        
        # 照片目录树
        self.photo_tree = QtWidgets.QTreeWidget()
        self.photo_tree.setHeaderLabels(["文件夹", "数量"])
        self.photo_tree.setAlternatingRowColors(True)
        self.photo_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #c0c0c0;
                background-color: white;
                alternate-background-color: #f5f5f5;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(self.photo_tree)
        
        # 底部统计信息
        self.lbl_photo_stats = QtWidgets.QLabel("照片: 0 | 文件夹: 0")
        self.lbl_photo_stats.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.lbl_photo_stats)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _createMiddlePanel(self):
        """创建中间裁剪图片展示面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("裁剪图片")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 工具按钮
        self.btn_clear_clips = QtWidgets.QPushButton("清空")
        self.btn_clear_clips.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_clear_clips)
        
        self.btn_save_clips = QtWidgets.QPushButton("保存")
        self.btn_save_clips.setFixedWidth(scale_w(60))  # 🔥 响应式宽度
        title_layout.addWidget(self.btn_save_clips)
        
        layout.addLayout(title_layout)
        
        # 裁剪图片滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
        """)
        
        # 滚动区域的内容容器
        self.clip_container = QtWidgets.QWidget()
        self.clip_layout = QtWidgets.QVBoxLayout(self.clip_container)
        self.clip_layout.setContentsMargins(10, 10, 10, 10)
        self.clip_layout.setSpacing(10)
        self.clip_layout.setAlignment(Qt.AlignTop)
        
        # 添加占位提示
        placeholder = QtWidgets.QLabel("暂无裁剪图片\n\n从右侧视频中裁剪图片将显示在这里")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #999; font-size: 11pt; padding: 50px;")
        self.clip_layout.addWidget(placeholder)
        
        scroll_area.setWidget(self.clip_container)
        layout.addWidget(scroll_area)
        
        # 底部统计信息
        self.lbl_clip_stats = QtWidgets.QLabel("裁剪数量: 0")
        self.lbl_clip_stats.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.lbl_clip_stats)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel
    
    def _createRightPanel(self):
        """创建右侧视频预览面板"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("视频预览")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 视频预览区域 - 响应式布局
        self.video_preview = QtWidgets.QLabel()
        self.video_preview.setAlignment(Qt.AlignCenter)
        self.video_preview.setMinimumSize(scale_w(400), scale_h(300))  # 🔥 响应式尺寸
        self.video_preview.setStyleSheet("""
            QLabel {
                background-color: black;
                border: 2px solid #c0c0c0;
                color: white;
                font-size: 11pt;
            }
        """)
        self.video_preview.setText("视频预览区\n\n选择视频文件后将在此显示")
        layout.addWidget(self.video_preview, stretch=1)
        
        # 视频信息组
        info_group = QtWidgets.QGroupBox("视频信息")
        info_layout = QtWidgets.QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignRight)
        
        self.lbl_video_name = QtWidgets.QLabel("--")
        info_layout.addRow("文件名:", self.lbl_video_name)
        
        self.lbl_video_size = QtWidgets.QLabel("--")
        info_layout.addRow("文件大小:", self.lbl_video_size)
        
        self.lbl_video_duration = QtWidgets.QLabel("--")
        info_layout.addRow("时长:", self.lbl_video_duration)
        
        self.lbl_video_resolution = QtWidgets.QLabel("--")
        info_layout.addRow("分辨率:", self.lbl_video_resolution)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 控制按钮组
        control_layout = QtWidgets.QHBoxLayout()
        
        self.btn_select_video = QtWidgets.QPushButton("选择视频")
        self.btn_select_video.setFixedHeight(scale_h(35))  # 🔥 响应式高度
        control_layout.addWidget(self.btn_select_video)
        
        self.btn_play_pause = QtWidgets.QPushButton("播放")
        self.btn_play_pause.setFixedHeight(scale_h(35))  # 🔥 响应式高度
        self.btn_play_pause.setEnabled(False)
        control_layout.addWidget(self.btn_play_pause)
        
        self.btn_clip_frame = QtWidgets.QPushButton("裁剪当前帧")
        self.btn_clip_frame.setFixedHeight(scale_h(35))  # 🔥 响应式高度
        self.btn_clip_frame.setEnabled(False)
        control_layout.addWidget(self.btn_clip_frame)
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.video_progress = QtWidgets.QSlider(Qt.Horizontal)
        self.video_progress.setEnabled(False)
        self.video_progress.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #c0c0c0;
                height: 8px;
                background: #e0e0e0;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d7;
                border: 1px solid #005a9e;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #005a9e;
            }
        """)
        layout.addWidget(self.video_progress)
        
        # 时间标签
        time_layout = QtWidgets.QHBoxLayout()
        self.lbl_current_time = QtWidgets.QLabel("00:00:00")
        self.lbl_current_time.setStyleSheet("color: #666;")
        time_layout.addWidget(self.lbl_current_time)
        
        time_layout.addStretch()
        
        self.lbl_total_time = QtWidgets.QLabel("00:00:00")
        self.lbl_total_time.setStyleSheet("color: #666;")
        time_layout.addWidget(self.lbl_total_time)
        
        layout.addLayout(time_layout)
        
        # 设置面板样式
        panel.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
        
        return panel


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("VideoClipper 视频裁剪器组件测试")
    window.resize(1400, 800)
    
    # 创建视频裁剪器组件
    video_clipper = VideoClipper()
    window.setCentralWidget(video_clipper)
    
    test_folders = [
        ("项目A", 25),
        ("项目B", 18),
        ("项目C", 32),
    ]
    
    for folder_name, photo_count in test_folders:
        item = QtWidgets.QTreeWidgetItem(video_clipper.photo_tree)
        item.setText(0, folder_name)
        item.setText(1, str(photo_count))
        
        # 添加子文件夹示例
        sub_item1 = QtWidgets.QTreeWidgetItem(item)
        sub_item1.setText(0, "子文件夹1")
        sub_item1.setText(1, str(photo_count // 2))
        
        sub_item2 = QtWidgets.QTreeWidgetItem(item)
        sub_item2.setText(0, "子文件夹2")
        sub_item2.setText(1, str(photo_count // 3))
    
    # 展开第一个项目
    video_clipper.photo_tree.expandItem(
        video_clipper.photo_tree.topLevelItem(0)
    )
    
    # 调整列宽
    video_clipper.photo_tree.setColumnWidth(0, 150)
    video_clipper.photo_tree.setColumnWidth(1, 60)
    
    video_clipper.lbl_photo_stats.setText(f"照片: {sum(c for _, c in test_folders)} | 文件夹: {len(test_folders)}")
    
    window.show()
    sys.exit(app.exec_())

