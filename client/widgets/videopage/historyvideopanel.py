# -*- coding: utf-8 -*-

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt

# 导入视频播放相关组件
try:
    from qtpy.QtMultimedia import QMediaPlayer, QMediaContent
    from qtpy.QtMultimediaWidgets import QVideoWidget
    from qtpy.QtCore import QUrl
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False
    QMediaPlayer = None
    QMediaContent = None
    QVideoWidget = None
    QUrl = None

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    # 从父目录（widgets）导入
    from ..style_manager import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    # 独立运行时的处理
    import sys
    import os.path as osp
    # 添加父目录到路径
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from style_manager import newIcon
    from responsive_layout import ResponsiveLayout, scale_w, scale_h


class HistoryVideoPanel(QtWidgets.QWidget):
    """
    历史视频面板组件（专用）
    
    基于ChannelPanel设计，但不包含底部按钮
    用于显示历史数据的视频流
    尺寸固定为 620x465px（4:3比例）
    """
    
    # 自定义信号（保留必要的信号）
    channelSelected = QtCore.Signal(dict)   # 通道选中信号
    amplifyClicked = QtCore.Signal(str)    # 放大按钮点击信号，传递channel_id
    channelNameChanged = QtCore.Signal(str, str)  # 通道名称改变信号(channel_id, new_name)
    
    def __init__(self, title="历史视频", parent=None, debug_mode=False, main_window=None):
        super(HistoryVideoPanel, self).__init__(parent)
        self._parent = parent
        self._main_window = main_window  # 存储主窗口引用以访问 curvemission
        self._title = title  # 保存标题但不显示
        self._channels = {}  # 存储通道信息 {channel_id: channel_data}
        self._current_channel_id = None  # 当前选中的通道ID
        self._debug_mode = debug_mode  # debug模式标志
        self._is_disabled = False  # 面板禁用状态
        self._channel_number = title.replace("历史视频", "").replace("通道", "")  # 提取通道编号
        
        self.setObjectName("HistoryVideoPanel")
        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI布局 - 简洁设计，无底部按钮"""
        # 🔥 设置固定大小 - 不使用响应式布局，直接使用固定尺寸
        self.setFixedSize(620, 465)
        
        # 设置黑色背景（QWidget需要autoFillBackground）
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(0, 0, 0))
        self.setPalette(palette)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 🔥 导入字体管理器（在if-else之前导入，避免作用域问题）
        try:
            from ..style_manager import FontManager
        except ImportError:
            from widgets.style_manager import FontManager
        
        # 🔥 视频显示区域（使用 QVideoWidget 或 QLabel）
        if MULTIMEDIA_AVAILABLE:
            # 使用 QVideoWidget 显示视频
            self.videoWidget = QVideoWidget()
            self.videoWidget.setStyleSheet("background-color: black;")
            self.videoWidget.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding
            )
            
            # 创建媒体播放器
            self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
            self.mediaPlayer.setVideoOutput(self.videoWidget)
            
            # 连接媒体播放器信号
            self.mediaPlayer.stateChanged.connect(self._onMediaStateChanged)
            self.mediaPlayer.positionChanged.connect(self._onMediaPositionChanged)
            self.mediaPlayer.durationChanged.connect(self._onMediaDurationChanged)
            self.mediaPlayer.error.connect(self._onMediaError)
            
            # 使用 videoWidget 作为视频显示区域
            self.videoLabel = self.videoWidget
        else:
            # 后备方案：使用 QLabel
            self.videoLabel = QtWidgets.QLabel()
            self.videoLabel.setStyleSheet("background-color: black;")
            self.videoLabel.setAlignment(Qt.AlignCenter)
            self.videoLabel.setScaledContents(False)
            self.videoLabel.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding
            )
            
            self.videoLabel.setText("历史回放视频")
            self.videoLabel.setFont(FontManager.getLargeFont())
            self.videoLabel.setStyleSheet("""
                QLabel {
                    background-color: black;
                    color: white;
                }
            """)
            
            self.mediaPlayer = None
        
        # 🔥 历史视频面板不显示通道名称标签
        # 创建名称显示标签（隐藏，保留用于兼容性）
        self.nameLabel = QtWidgets.QLabel(self.videoLabel)
        self.nameLabel.setText("")
        self.nameLabel.hide()  # 隐藏标签
        
        # 创建调试模式静态文本控件（叠加在视频区域顶部中间，仅在调试模式下显示）
        self.debugLabel = QtWidgets.QLabel(self.videoLabel)
        self.debugLabel.setText("")  # 初始为空，等待设置current_mission
        self.debugLabel.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: white;
                font-size: 10pt;
                font-weight: bold;
                padding: 3px 8px;
            }
        """)
        self.debugLabel.setAlignment(Qt.AlignCenter)
        self.debugLabel.adjustSize()
        # 定位到顶部中间
        self._positionDebugLabel()
        # 根据调试模式控制显示/隐藏
        self.debugLabel.setVisible(self._debug_mode)
        
        # 🔥 历史视频面板不显示任务信息标签
        # 创建任务信息显示标签（隐藏，保留用于兼容性）
        self.taskLabel = QtWidgets.QLabel(self.videoLabel)
        self.taskLabel.setText("")
        self.taskLabel.hide()  # 隐藏标签
        
        # 创建名称编辑框（初始隐藏）
        self.nameEdit = QtWidgets.QLineEdit(self.videoLabel)
        self.nameEdit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 230);
                color: black;
                font-size: 12pt;
                font-weight: bold;
                padding: 5px 10px;
                border: 2px solid #4682B4;
                border-radius: 3px;
            }
        """)
        self.nameEdit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nameEdit.hide()
        self.nameEdit.setMaxLength(50)  # 限制最大长度
        
        # 🔥 视频区域
        layout.addWidget(self.videoLabel, 1)
        
        # 🔥 底部控件区域
        bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(5)
        
        # NVR地址输入框
        nvr_layout = QtWidgets.QHBoxLayout()
        nvr_layout.setSpacing(5)
        
        nvr_label = QtWidgets.QLabel("NVR地址:")
        nvr_label.setFont(FontManager.getMediumFont())
        nvr_label.setStyleSheet("color: white;")
        nvr_layout.addWidget(nvr_label)
        
        self.nvrAddressEdit = QtWidgets.QLineEdit()
        self.nvrAddressEdit.setPlaceholderText("NVR历史回放功能开发中，敬请期待。")
        self.nvrAddressEdit.setFont(FontManager.getMediumFont())
        self.nvrAddressEdit.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4682B4;
            }
        """)
        nvr_layout.addWidget(self.nvrAddressEdit, 1)
        
        bottom_layout.addLayout(nvr_layout)
        
        # 进度条
        progress_layout = QtWidgets.QHBoxLayout()
        progress_layout.setSpacing(5)
        
        # 播放/暂停按钮（使用图标）
        self.btnPlayPause = QtWidgets.QPushButton()
        self.btnPlayPause.setIcon(newIcon("开始"))  # 初始为播放图标
        self.btnPlayPause.setIconSize(QtCore.QSize(24, 24))
        self.btnPlayPause.setFixedSize(32, 32)
        self.btnPlayPause.setToolTip("播放")
        self.btnPlayPause.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(70, 130, 180, 0.3);
                border: 1px solid #4682B4;
            }
            QPushButton:pressed {
                background-color: rgba(70, 130, 180, 0.5);
            }
        """)
        self._is_playing = False  # 播放状态标志
        progress_layout.addWidget(self.btnPlayPause)
        
        self.progressSlider = QtWidgets.QSlider(Qt.Horizontal)
        self.progressSlider.setMinimum(0)
        self.progressSlider.setMaximum(100)
        self.progressSlider.setValue(0)
        self.progressSlider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #2b2b2b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4682B4;
                border: 1px solid #4682B4;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #5a9fd4;
            }
            QSlider::sub-page:horizontal {
                background: #4682B4;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progressSlider, 1)
        
        self.progressLabel = QtWidgets.QLabel("00:00 / 00:00")
        self.progressLabel.setFont(FontManager.getMediumFont())
        self.progressLabel.setStyleSheet("color: white;")
        self.progressLabel.setMinimumWidth(100)
        progress_layout.addWidget(self.progressLabel)
        
        bottom_layout.addLayout(progress_layout)
        
        # 设置底部控件区域的背景色
        bottom_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        bottom_widget.setFixedHeight(80)
        
        layout.addWidget(bottom_widget)
    
    def _connectSignals(self):
        """连接信号槽"""
        # 连接名称编辑框的信号
        self.nameEdit.returnPressed.connect(self._onNameEditFinished)
        self.nameEdit.editingFinished.connect(self._onNameEditFinished)
        
        # 连接播放/暂停按钮信号
        if hasattr(self, 'btnPlayPause'):
            self.btnPlayPause.clicked.connect(self._onPlayPauseClicked)
        
        # 连接进度条信号
        if hasattr(self, 'progressSlider'):
            self.progressSlider.sliderPressed.connect(self._onProgressSliderPressed)
            self.progressSlider.sliderReleased.connect(self._onProgressSliderReleased)
            self.progressSlider.valueChanged.connect(self._onProgressValueChanged)
    
    def addChannel(self, channel_id, channel_data):
        """
        添加通道
        
        Args:
            channel_id: 通道ID
            channel_data: 通道数据字典
                {
                    'name': str,
                    'type': str ('rtsp', 'usb', 'file'),
                    'url': str,
                    'status': str ('disconnected', 'connected', 'error'),
                    'resolution': str,
                    ...
                }
        """
        if channel_id in self._channels:
            return False
        
        self._channels[channel_id] = channel_data
        
        # 如果是第一个通道，自动设为当前通道
        if self._current_channel_id is None:
            self._current_channel_id = channel_id
        
        return True
    
    def removeChannel(self, channel_id):
        """删除通道"""
        if channel_id not in self._channels:
            return False
        
        del self._channels[channel_id]
        
        # 如果删除的是当前选中的通道，重置当前通道ID
        if self._current_channel_id == channel_id:
            self._current_channel_id = None
            # 如果有其他通道，选择第一个
            if self._channels:
                self._current_channel_id = next(iter(self._channels))
        
        return True
    
    def updateChannel(self, channel_id, channel_data):
        """更新通道信息"""
        if channel_id not in self._channels:
            return False
        
        self._channels[channel_id].update(channel_data)
        
        # 如果更新的是当前通道，更新显示
        if channel_id == self._current_channel_id:
            self._updateDisplay()
        
        return True
    
    def getCurrentChannel(self):
        """获取当前选中的通道"""
        if self._current_channel_id and self._current_channel_id in self._channels:
            return self._current_channel_id, self._channels[self._current_channel_id]
        return None, None
    
    def setCurrentChannel(self, channel_id):
        """设置当前选中的通道"""
        if channel_id in self._channels:
            self._current_channel_id = channel_id
            self._updateDisplay()
            return True
        return False
    
    def _updateDisplay(self):
        """更新显示内容"""
        channel_id, channel_data = self.getCurrentChannel()
        if channel_data:
            # 更新名称标签
            self.nameLabel.setText(channel_data.get('name', self._title))
            self.nameLabel.adjustSize()
        else:
            self.nameLabel.setText(self._title)
            self.nameLabel.adjustSize()
    
    def _positionDebugLabel(self):
        """定位debug标签到顶部中间"""
        if hasattr(self, 'debugLabel') and hasattr(self, 'videoLabel'):
            video_width = self.videoLabel.width()
            label_width = self.debugLabel.width()
            x = (video_width - label_width) // 2
            self.debugLabel.move(x, 0)
    
    def _positionTaskLabel(self):
        """定位任务标签到右上角"""
        if hasattr(self, 'taskLabel') and hasattr(self, 'videoLabel'):
            video_width = self.videoLabel.width()
            label_width = self.taskLabel.width()
            x = video_width - label_width
            self.taskLabel.move(x, 0)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 重新定位标签
        self._positionDebugLabel()
        self._positionTaskLabel()
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理名称标签的双击事件"""
        if obj == self.nameLabel and event.type() == QtCore.QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                self._startNameEdit()
                return True
        return super().eventFilter(obj, event)
    
    def _startNameEdit(self):
        """开始编辑名称"""
        # 获取当前名称
        current_name = self.nameLabel.text()
        
        # 设置编辑框的位置和大小
        self.nameEdit.setGeometry(self.nameLabel.geometry())
        self.nameEdit.setText(current_name)
        self.nameEdit.selectAll()
        
        # 显示编辑框，隐藏标签
        self.nameLabel.hide()
        self.nameEdit.show()
        self.nameEdit.setFocus()
    
    def _onNameEditFinished(self):
        """名称编辑完成"""
        new_name = self.nameEdit.text().strip()
        old_name = self.nameLabel.text()
        
        # 如果名称为空，恢复原名称
        if not new_name:
            new_name = old_name
        
        # 更新标签文本
        self.nameLabel.setText(new_name)
        self.nameLabel.adjustSize()
        
        # 隐藏编辑框，显示标签
        self.nameEdit.hide()
        self.nameLabel.show()
        
        # 如果名称确实改变了，发出信号
        if new_name != old_name:
            channel_id, _ = self.getCurrentChannel()
            if channel_id:
                self.channelNameChanged.emit(channel_id, new_name)
    
    def setVideoFrame(self, frame):
        """设置视频帧显示"""
        if frame is not None:
            # 将OpenCV帧转换为QPixmap并显示
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QtGui.QImage(frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).rgbSwapped()
            pixmap = QtGui.QPixmap.fromImage(q_image)
            
            # 缩放以适应标签大小，保持宽高比
            scaled_pixmap = pixmap.scaled(
                self.videoLabel.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.videoLabel.setPixmap(scaled_pixmap)
        else:
            self.videoLabel.clear()
            self.videoLabel.setText("无视频数据")
    
    def clearVideo(self):
        """清空视频显示"""
        self.videoLabel.clear()
        self.videoLabel.setText("历史数据加载中...")
    
    def setCurrentMission(self, mission_path):
        """设置当前任务路径（用于debug显示）"""
        if self._debug_mode and hasattr(self, 'debugLabel'):
            if mission_path:
                # 统一路径分隔符为 /
                normalized_path = mission_path.replace('\\', '/')
                self.debugLabel.setText(normalized_path)
            else:
                self.debugLabel.setText("无任务")
            
            self.debugLabel.adjustSize()
            self._positionDebugLabel()
    
    def _onPlayPauseClicked(self):
        """播放/暂停按钮点击"""
        if not self.mediaPlayer:
            return
        
        # 🔥 检查是否已加载视频
        if self.mediaPlayer.media().isNull():
            # 没有加载视频，尝试从 curvemission 加载
            task_name = self._getCurrentMissionFromParent()
            if task_name:
                success = self.loadVideoFromTask(task_name)
                if not success:
                    return
            else:
                return
        
        # 根据当前播放状态切换
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            # 当前正在播放，暂停
            self.mediaPlayer.pause()
        else:
            # 当前暂停或停止，开始播放
            self.mediaPlayer.play()
    
    def _onMediaStateChanged(self, state):
        """媒体播放器状态改变"""
        if state == QMediaPlayer.PlayingState:
            # 播放中，显示暂停图标
            self.btnPlayPause.setIcon(newIcon("停止1"))
            self.btnPlayPause.setToolTip("暂停")
            self._is_playing = True
        else:
            # 暂停或停止，显示播放图标
            self.btnPlayPause.setIcon(newIcon("开始"))
            self.btnPlayPause.setToolTip("播放")
            self._is_playing = False
    
    def _onMediaPositionChanged(self, position):
        """媒体播放位置改变"""
        if not self.mediaPlayer:
            return
        
        duration = self.mediaPlayer.duration()
        if duration > 0:
            # 更新进度条（避免用户拖动时的冲突）
            if not self.progressSlider.isSliderDown():
                progress = int(position * 100 / duration)
                self.progressSlider.setValue(progress)
            
            # 更新时间显示
            current_seconds = position // 1000
            total_seconds = duration // 1000
            
            current_time = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
            total_time = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
            
            if hasattr(self, 'progressLabel'):
                self.progressLabel.setText(f"{current_time} / {total_time}")
    
    def _onMediaDurationChanged(self, duration):
        """媒体总时长改变"""
        if duration > 0:
            total_seconds = duration // 1000
            total_time = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
    
    def _onMediaError(self, error):
        """媒体播放错误"""
        if self.mediaPlayer:
            error_string = self.mediaPlayer.errorString()
    
    def _onProgressSliderPressed(self):
        """进度条按下"""
        pass
    
    def _onProgressSliderReleased(self):
        """进度条释放"""
        if not self.mediaPlayer:
            return
        
        value = self.progressSlider.value()
        duration = self.mediaPlayer.duration()
        
        if duration > 0:
            # 计算目标位置（毫秒）
            position = int(duration * value / 100)
            self.mediaPlayer.setPosition(position)
    
    def _onProgressValueChanged(self, value):
        """进度条值改变（用户拖动时）"""
        # 只在用户拖动时更新显示，播放时由 _onMediaPositionChanged 更新
        if self.progressSlider.isSliderDown() and self.mediaPlayer:
            duration = self.mediaPlayer.duration()
            if duration > 0:
                current_seconds = int(duration * value / 100) // 1000
                total_seconds = duration // 1000
                
                current_time = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
                total_time = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
                
                if hasattr(self, 'progressLabel'):
                    self.progressLabel.setText(f"{current_time} / {total_time}")
    
    def setProgress(self, value):
        """设置进度条值（0-100）"""
        if hasattr(self, 'progressSlider'):
            self.progressSlider.setValue(value)
    
    def setPlaying(self, is_playing):
        """
        设置播放状态（外部调用）
        
        Args:
            is_playing: True表示播放中，False表示暂停
        """
        self._is_playing = is_playing
        if hasattr(self, 'btnPlayPause'):
            if is_playing:
                self.btnPlayPause.setIcon(newIcon("停止1"))
                self.btnPlayPause.setToolTip("暂停")
            else:
                self.btnPlayPause.setIcon(newIcon("开始"))
                self.btnPlayPause.setToolTip("播放")
    
    def isPlaying(self):
        """
        获取当前播放状态
        
        Returns:
            bool: True表示播放中，False表示暂停
        """
        return self._is_playing
    
    def loadVideo(self, video_path):
        """
        加载视频文件
        
        Args:
            video_path: 视频文件路径
        """
        if not self.mediaPlayer:
            return False
        
        import os
        if not os.path.exists(video_path):
            return False
        
        # 设置媒体内容
        media_url = QUrl.fromLocalFile(video_path)
        media_content = QMediaContent(media_url)
        self.mediaPlayer.setMedia(media_content)
        
        return True
    
    def loadVideoFromTask(self, task_folder_name):
        """
        从任务文件夹加载视频
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_2"）
        """
        if not task_folder_name or task_folder_name == "None":
            return False
        
        import os
        import sys
        
        # 获取项目根目录
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            try:
                from client.config import get_project_root
                project_root = get_project_root()
            except ImportError:
                project_root = os.getcwd()
        
        # 构建任务文件夹路径
        task_folder = os.path.join(project_root, 'database', 'mission_result', task_folder_name)
        
        if not os.path.exists(task_folder):
            return False
        
        # 查找视频文件（支持常见格式）
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv']
        video_files = []
        
        for file in os.listdir(task_folder):
            file_lower = file.lower()
            if any(file_lower.endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(task_folder, file))
        
        if not video_files:
            return False
        
        # 加载第一个视频文件
        video_path = video_files[0]
        return self.loadVideo(video_path)
    
    def setNvrAddress(self, address):
        """设置NVR地址"""
        if hasattr(self, 'nvrAddressEdit'):
            self.nvrAddressEdit.setText(address)
    
    def getNvrAddress(self):
        """获取NVR地址"""
        if hasattr(self, 'nvrAddressEdit'):
            return self.nvrAddressEdit.text()
        return ""
    
    def setTaskInfo(self, task_folder_name):
        """
        设置任务信息显示（仅用于显示，不存储任务名称）
        
        Args:
            task_folder_name: 任务文件夹名称
        """
        if task_folder_name and task_folder_name != "None":
            self.taskLabel.setText(task_folder_name)
            # 任务分配后启用面板
            self._setDisabled(False)
        else:
            self.taskLabel.setText("历史数据")
            # 清空任务时禁用面板
            self._setDisabled(True)
        
        self.taskLabel.adjustSize()
        # 定位到右上角
        self._positionTaskLabel()
    
    def clearTaskInfo(self):
        """清空任务信息显示"""
        self.taskLabel.setText("历史数据")
        # 清空任务时禁用面板
        self._setDisabled(True)
        self.taskLabel.adjustSize()
        self._positionTaskLabel()
    
    def _getCurrentMissionFromParent(self):
        """
        从主窗口的 curvemission 获取当前任务名称
        
        Returns:
            str: 任务文件夹名称，如果不存在或为"请选择任务"则返回None
        """
        try:
            # 🔥 优先使用主窗口引用
            if self._main_window and hasattr(self._main_window, 'curvemission'):
                mission_name = self._main_window.curvemission.currentText()
                if mission_name and mission_name != "请选择任务":
                    return mission_name
                else:
                    return None
            
            return None
        except Exception as e:
            return None
    
    def _setDisabled(self, disabled):
        """设置面板禁用状态"""
        self._is_disabled = disabled
        
        # 历史视频面板没有按钮，只需要更新视觉状态
        if disabled:
            self.setStyleSheet("HistoryVideoPanel { opacity: 0.6; }")
        else:
            self.setStyleSheet("HistoryVideoPanel { opacity: 1.0; }")
    
    def isDisabled(self):
        """获取面板禁用状态"""
        return self._is_disabled


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    import uuid
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("HistoryVideoPanel 组件测试")
    main_window.resize(640, 480)
    
    # 创建历史视频面板
    history_panel = HistoryVideoPanel("历史通道1", main_window, debug_mode=True)
    
    # 连接信号用于测试
    def on_channel_name_changed(channel_id, new_name):
        pass
    
    history_panel.channelNameChanged.connect(on_channel_name_changed)
    
    # 添加测试数据
    test_channels = [
        {
            'id': str(uuid.uuid4()),
            'data': {
                'name': '历史数据通道1',
                'type': 'file',
                'url': '/path/to/history/video1.mp4',
                'status': 'ready',
                'resolution': '1920x1080'
            }
        },
        {
            'id': str(uuid.uuid4()),
            'data': {
                'name': '历史数据通道2',
                'type': 'file',
                'url': '/path/to/history/video2.mp4',
                'status': 'ready',
                'resolution': '1920x1080'
            }
        }
    ]
    
    for channel in test_channels:
        history_panel.addChannel(channel['id'], channel['data'])
    
    # 设置任务信息
    history_panel.setTaskInfo("123_历史任务测试")
    history_panel.setCurrentMission("d:/restructure/liquid_level_line_detection_system/database/mission_result/123_历史任务测试")
    
    # 设置为中央部件
    main_window.setCentralWidget(history_panel)
    
    main_window.show()
    sys.exit(app.exec_())
