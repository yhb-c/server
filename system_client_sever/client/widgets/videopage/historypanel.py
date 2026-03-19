"""


"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl, Qt
import os

# 导入图标工具和响应式布局
try:
    from widgets.style_manager import newIcon
    from widgets.responsive_layout import ResponsiveLayout, scale_w, scale_h
except ImportError:
    try:
        from style_manager import newIcon
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        def newIcon(icon):
            from PyQt5 import QtGui
            return QtGui.QIcon()
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x


class HistoryPanel(QtWidgets.QWidget):
    """"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._media_player = None
        self._video_widget = None
        self._is_seeking = False  # 
        self._initUI()
        
    def _initUI(self):
        """UI - 使用固定大小和绝对位置布局"""
        # 🔥 设置面板固定大小 - 响应式布局
        self.setFixedSize(scale_w(660), scale_h(380))
        
        # 不使用布局管理器，直接使用绝对位置
        self._createVideoArea()
        self._createControlsArea()
        self._createInfoArea()
        
    def _createVideoArea(self):
        """创建视频显示区域 - 固定位置和大小"""
        self._video_widget = QVideoWidget(self)
        # 固定位置和大小：左上角(5, 5)，宽度650，高度300
        self._video_widget.setGeometry(5, 5, 650, 300)
        self._video_widget.setStyleSheet(
            "background: black; "
            "border: 2px solid #dee2e6; "
            "border-radius: 4px;"
        )
        
        # 
        self._media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self._media_player.setVideoOutput(self._video_widget)
        
        # 
        self._media_player.positionChanged.connect(self._onPositionChanged)
        self._media_player.durationChanged.connect(self._onDurationChanged)
        self._media_player.stateChanged.connect(self._onStateChanged)
        self._media_player.error.connect(self._onError)
        
    def _createControlsArea(self):
        """创建控制区域 - 固定位置和大小"""
        button_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: palette(light);
                border: 1px solid palette(mid);
            }
            QPushButton:pressed {
                background-color: palette(midlight);
            }
            QPushButton:disabled {
                opacity: 0.5;
            }
        """
        
        # 播放/暂停按钮 - 固定位置(5, 310)，大小35x35
        self.play_pause_button = QtWidgets.QPushButton(self)
        self.play_pause_button.setGeometry(5, 310, 35, 35)
        self.play_pause_button.setIcon(newIcon('开始'))
        self.play_pause_button.setIconSize(QtCore.QSize(24, 24))
        self.play_pause_button.setToolTip('播放')
        self.play_pause_button.setStyleSheet(button_style)
        
        # 进度条 - 固定位置(45, 318)，宽度380
        self.position_slider = QtWidgets.QSlider(Qt.Horizontal, self)
        self.position_slider.setGeometry(45, 318, 380, 20)
        self.position_slider.setRange(0, 0)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999;
                height: 8px;
                background: #f0f0f0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2196F3;
                border: 1px solid #1976D2;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: #2196F3;
                border-radius: 4px;
            }
        """)
        self.position_slider.sliderPressed.connect(self._onSliderPressed)
        self.position_slider.sliderReleased.connect(self._onSliderReleased)
        self.position_slider.sliderMoved.connect(self._onSliderMoved)
        
        # 时间标签 - 固定位置(430, 315)，宽度85
        self.time_label = QtWidgets.QLabel("00:00 / 00:00", self)
        self.time_label.setGeometry(430, 315, 85, 25)
        self.time_label.setStyleSheet("color: #666; font-size: 8pt;")
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # 音量控制器已删除，不再需要
        # 设置默认音量
        self._media_player.setVolume(50)
        
    def _createInfoArea(self):
        """创建信息区域（已隐藏）"""
        self.info_label = QtWidgets.QLabel("", self)
        self.info_label.setGeometry(5, 350, 650, 25)
        self.info_label.setStyleSheet(
            "color: #666; "
            "font-size: 7pt; "
            "padding: 3px;"
        )
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(False)  # 隐藏文件路径标签
        
    def loadVideo(self, video_path, title=None, info_text=None):
        """
        
        
        Args:
            video_path: 
            title: 
            info_text: 
        """
        print(f"[HistoryPanel] ========== loadVideo  ==========")
        print(f"[HistoryPanel] : {video_path}")
        print(f"[HistoryPanel] : {os.path.exists(video_path)}")
        
        if not os.path.exists(video_path):
            print(f"[HistoryPanel]  : ")
            QtWidgets.QMessageBox.warning(self, "", f":\n{video_path}")
            return False
            
        try:
            # 
            if info_text:
                self.info_label.setText(info_text)
                print(f"[HistoryPanel] : {info_text}")
            else:
                self.info_label.setText(f": {video_path}")
                print(f"[HistoryPanel] ")
                
            # 
            abs_path = os.path.abspath(video_path)
            print(f"[HistoryPanel] : {abs_path}")
            
            video_url = QUrl.fromLocalFile(abs_path)
            print(f"[HistoryPanel] URL: {video_url.toString()}")
            print(f"[HistoryPanel] URL: {video_url.isValid()}")
            
            media_content = QMediaContent(video_url)
            print(f"[HistoryPanel] : {media_content}")
            print(f"[HistoryPanel] : {media_content.isNull()}")
            
            print(f"[HistoryPanel] ...")
            self._media_player.setMedia(media_content)
            
            print(f"[HistoryPanel] : {self._media_player.state()}")
            print(f"[HistoryPanel] : {self._media_player.mediaStatus()}")
            print(f"[HistoryPanel] : {self._media_player.error()}")
            if self._media_player.error() != QMediaPlayer.NoError:
                print(f"[HistoryPanel] : {self._media_player.errorString()}")
            
            print(f"[HistoryPanel]  ")
            return True
            
        except Exception as e:
            print(f"[HistoryPanel]  : {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(self, "", f":\n{str(e)}")
            return False
            
    def play(self):
        """"""
        self._media_player.play()
        
    def pause(self):
        """"""
        self._media_player.pause()
        
    def stop(self):
        """"""
        self._media_player.stop()
        
    def _onPositionChanged(self, position):
        """"""
        if not self._is_seeking:
            self.position_slider.setValue(position)
            
        # 
        current_time = position // 1000
        total_time = self._media_player.duration() // 1000
        self.time_label.setText(
            f"{current_time//60:02d}:{current_time%60:02d} / "
            f"{total_time//60:02d}:{total_time%60:02d}"
        )
        
    def _onDurationChanged(self, duration):
        """"""
        self.position_slider.setRange(0, duration)
        
    def _onStateChanged(self, state):
        """handler"""
        # 
        pass
            
    def _onError(self, error):
        """"""
        error_string = self._media_player.errorString()
        print(f"[HistoryPanel] : {error_string}")
        QtWidgets.QMessageBox.warning(self, "", f":\n{error_string}")
        
    def _onSliderPressed(self):
        """"""
        self._is_seeking = True
        
    def _onSliderReleased(self):
        """"""
        self._is_seeking = False
        self._media_player.setPosition(self.position_slider.value())
        
    def _onSliderMoved(self, position):
        """"""
        # 
        current_time = position // 1000
        total_time = self._media_player.duration() // 1000
        self.time_label.setText(
            f"{current_time//60:02d}:{current_time%60:02d} / "
            f"{total_time//60:02d}:{total_time%60:02d}"
        )
        
    def _onVolumeChanged(self, value):
        """"""
        self._media_player.setVolume(value)
        
    def setStatistics(self, stats_dict):
        """
        
        
        Args:
            stats_dict:  {
                'total_frames': 100,
                'detection_count': 33,
                'success_count': 30,
                'fail_count': 3,
                'success_rate': 90.9
            }
        """
        # 
        stats_text = (
            f": {stats_dict.get('total_frames', 0)} | "
            f": {stats_dict.get('detection_count', 0)} | "
            f": {stats_dict.get('success_count', 0)} | "
            f": {stats_dict.get('fail_count', 0)} | "
            f": {stats_dict.get('success_rate', 0):.1f}%"
        )
        
        # 
        if not hasattr(self, 'stats_label'):
            # 
            stats_widget = QtWidgets.QWidget()
            stats_widget.setStyleSheet(
                "background: #f8f9fa; "
                "border: 1px solid #dee2e6; "
                "border-radius: 5px; "
                "padding: 12px;"
            )
            stats_layout = QtWidgets.QVBoxLayout(stats_widget)
            stats_layout.setContentsMargins(0, 0, 0, 0)
            
            stats_title = QtWidgets.QLabel("")
            stats_title.setStyleSheet(
                "color: #333; "
                "font-size: 10pt; "
                "font-weight: bold; "
                "background: transparent; "
                "border: none; "
                "padding: 0;"
            )
            stats_layout.addWidget(stats_title)
            
            self.stats_label = QtWidgets.QLabel(stats_text)
            self.stats_label.setStyleSheet(
                "color: #666; "
                "font-size: 8pt; "
                "background: transparent; "
                "border: none; "
                "padding: 3px 0;"
            )
            stats_layout.addWidget(self.stats_label)
            
            # 
            main_layout = self.layout()
            main_layout.insertWidget(1, stats_widget)
        else:
            self.stats_label.setText(stats_text)
