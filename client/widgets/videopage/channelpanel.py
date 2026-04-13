# -*- coding: utf-8 -*-
"""
通道面板组件 - 使用 PlayCtrl SDK 直接渲染 + InfoOverlay 叠加层

渲染方式：PlayCtrl SDK 直接渲染到 videoWidget.winId() 返回的 HWND
叠加层：InfoOverlay 是独立的透明顶层窗口，叠加在视频上方显示信息
"""

import logging
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt

# 导入图标工具和响应式布局
try:
    from ..style_manager import newIcon, FontManager
    from ..responsive_layout import scale_w, scale_h
except (ImportError, ValueError):
    import sys
    import os.path as osp
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    try:
        from style_manager import newIcon, FontManager
        from responsive_layout import scale_w, scale_h
    except ImportError:
        def newIcon(icon_name):
            return QtGui.QIcon()
        class FontManager:
            @staticmethod
            def applyToWidget(widget, **kwargs):
                pass
        scale_w = lambda x: x
        scale_h = lambda x: x


class ButtonOverlay(QtWidgets.QWidget):
    """
    按钮叠加层 - 固定在视频控件底部的按钮栏
    """

    # 定义信号
    toggleConnectClicked = QtCore.Signal()
    editClicked = QtCore.Signal()
    curveClicked = QtCore.Signal()
    amplifyClicked = QtCore.Signal()

    def __init__(self, parent=None):
        super(ButtonOverlay, self).__init__(parent)
        self._initUI()

    def _initUI(self):
        """初始化按钮UI"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 背景样式
        self.setStyleSheet("background-color: rgba(50, 50, 50, 200);")

        button_style = """
            QPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 3px; padding: 5px; }
            QPushButton:hover { background-color: rgba(100, 100, 100, 150); border: 1px solid rgba(150, 150, 150, 200); }
            QPushButton:pressed { background-color: rgba(80, 80, 80, 150); }
            QPushButton:disabled { opacity: 0.5; }
        """

        icon_size = scale_w(24)
        btn_size = scale_w(35)

        self.btnToggleConnect = QtWidgets.QPushButton()
        self.btnToggleConnect.setIcon(newIcon("开始"))
        self.btnToggleConnect.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnToggleConnect.setToolTip("打开通道")
        self.btnToggleConnect.setStyleSheet(button_style)
        self.btnToggleConnect.setFixedSize(btn_size, btn_size)
        self.btnToggleConnect.clicked.connect(self.toggleConnectClicked.emit)

        self.btnEdit = QtWidgets.QPushButton()
        self.btnEdit.setIcon(newIcon('设置'))
        self.btnEdit.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnEdit.setToolTip("通道设置")
        self.btnEdit.setStyleSheet(button_style)
        self.btnEdit.setFixedSize(btn_size, btn_size)
        self.btnEdit.clicked.connect(self.editClicked.emit)

        self.btnCurve = QtWidgets.QPushButton()
        self.btnCurve.setIcon(newIcon('动态曲线'))
        self.btnCurve.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnCurve.setToolTip("查看曲线")
        self.btnCurve.setStyleSheet(button_style)
        self.btnCurve.setFixedSize(btn_size, btn_size)
        self.btnCurve.clicked.connect(self.curveClicked.emit)

        self.btnAmplify = QtWidgets.QPushButton()
        self.btnAmplify.setIcon(newIcon('amplify'))
        self.btnAmplify.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnAmplify.setToolTip("放大显示")
        self.btnAmplify.setStyleSheet(button_style)
        self.btnAmplify.setFixedSize(btn_size, btn_size)
        self.btnAmplify.clicked.connect(self.amplifyClicked.emit)

        layout.addWidget(self.btnToggleConnect)
        layout.addWidget(self.btnEdit)
        layout.addWidget(self.btnCurve)
        layout.addWidget(self.btnAmplify)
        layout.addStretch()

        self.setFixedHeight(45)

    def resizeEvent(self, event):
        """窗口大小改变时自动调整位置"""
        super(ButtonOverlay, self).resizeEvent(event)
        if self.parent():
            parent_height = self.parent().height()
            parent_width = self.parent().width()
            y_pos = parent_height - 45
            self.setGeometry(0, y_pos, parent_width, 45)


class InfoOverlay(QtWidgets.QWidget):
    """
    信息叠加层 - 独立顶层窗口，叠加在视频上方显示信息

    特点：
    - 无边框顶层窗口
    - 透明背景
    - 不获取焦点
    - 跟随目标视频控件位置
    - 绘制液位线和检测结果
    """

    def __init__(self, channel_id="", parent=None):
        super(InfoOverlay, self).__init__(parent)
        self.channel_id = channel_id

        # 不设置为顶层窗口，作为普通子控件
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # 信息数据
        self.channel_name = channel_id
        self.task_name = "未分配任务"
        self.fps = 0.0
        self.resolution = "0x0"
        self.target_widget = None

        # 液位线数据
        self.liquid_positions = {}
        self.is_new_data = True
        self.video_width = 0
        self.video_height = 0

        # 创建UI
        self._initUI()

        # 初始隐藏
        self.hide()

    def _initUI(self):
        """初始化UI - 使用QLabel"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # 顶部信息栏背景
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180);")

        # 通道名称标签
        self.channelLabel = QtWidgets.QLabel(self.channel_name)
        self.channelLabel.setStyleSheet("color: white; font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.channelLabel)

        # 分隔符
        sep1 = QtWidgets.QLabel("|")
        sep1.setStyleSheet("color: rgb(100, 100, 100);")
        layout.addWidget(sep1)

        # 分辨率标签
        self.resolutionLabel = QtWidgets.QLabel(self.resolution)
        self.resolutionLabel.setStyleSheet("color: rgb(255, 255, 0); font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.resolutionLabel)

        # 分隔符
        sep2 = QtWidgets.QLabel("|")
        sep2.setStyleSheet("color: rgb(100, 100, 100);")
        layout.addWidget(sep2)

        # FPS标签
        self.fpsLabel = QtWidgets.QLabel(f"FPS: {self.fps:.1f}")
        self.fpsLabel.setStyleSheet("color: rgb(0, 255, 0); font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.fpsLabel)

        # 弹簧，将任务名称推到右侧
        layout.addStretch()

        # 任务名称标签
        self.taskLabel = QtWidgets.QLabel(self.task_name)
        self.taskLabel.setStyleSheet("color: rgb(0, 255, 255); font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.taskLabel)

        # 设置固定高度
        self.setFixedHeight(28)
    
    def set_target(self, widget):
        """设置要跟随的视频控件"""
        self.target_widget = widget
    
    def update_position(self):
        """更新位置 - 固定在父控件顶部"""
        if self.parent():
            parent_width = self.parent().width()
            self.setGeometry(0, 0, parent_width, 28)
            self.raise_()

    def resizeEvent(self, event):
        """窗口大小改变时自动调整位置"""
        super(InfoOverlay, self).resizeEvent(event)
        if self.parent():
            parent_width = self.parent().width()
            self.setGeometry(0, 0, parent_width, 28)

    def _is_widget_in_viewport(self, widget):
        """检查控件是否在滚动区域的可视范围内 - 已废弃"""
        return True
    
    def update_info(self, channel_name=None, task_name=None, fps=None, resolution=None):
        """更新显示信息"""
        if channel_name is not None:
            self.channel_name = channel_name
            self.channelLabel.setText(channel_name)
        if task_name is not None:
            self.task_name = task_name
            self.taskLabel.setText(task_name)
        if fps is not None:
            self.fps = fps
            self.fpsLabel.setText(f"FPS: {self.fps:.1f}")
        if resolution is not None:
            self.resolution = resolution
            self.resolutionLabel.setText(resolution)
            # 解析分辨率
            try:
                parts = resolution.split('x')
                if len(parts) == 2:
                    self.video_width = int(parts[0])
                    self.video_height = int(parts[1])
            except:
                pass
        self.update_position()
    
    def update_liquid_lines(self, liquid_positions, is_new_data=True, video_width=0, video_height=0):
        """更新液位线数据

        Args:
            liquid_positions: 液位线位置数据 {area_idx: {left, right, y, height_mm, valid, ...}}
            is_new_data: 是否为新数据（True=红色，False=黄色）
            video_width: 原始视频宽度
            video_height: 原始视频高度
        """
        self.liquid_positions = liquid_positions or {}
        self.is_new_data = is_new_data
        if video_width > 0:
            self.video_width = video_width
        if video_height > 0:
            self.video_height = video_height

    def clear_liquid_lines(self):
        """清空液位线数据"""
        self.liquid_positions = {}
    

class VideoRenderWidget(QtWidgets.QWidget):
    """视频渲染专用Widget - 支持HWND直接渲染和QPixmap渲染"""
    
    def __init__(self, parent=None):
        super(VideoRenderWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background-color: black;")
        
        self._pixmap = None
    
    def setPixmap(self, pixmap):
        """设置要显示的pixmap"""
        self._pixmap = pixmap
        self.update()
    
    def paintEvent(self, event):
        """绘制事件"""
        if self._pixmap and not self._pixmap.isNull():
            from qtpy import QtGui
            painter = QtGui.QPainter(self)
            
            # 计算居中位置
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            
            # 绘制pixmap
            painter.drawPixmap(x, y, self._pixmap)
        else:
            # 没有pixmap时，PlayCtrl完全控制渲染
            pass



class ChannelPanel(QtWidgets.QWidget):
    """
    通道面板组件

    用于显示通道视频流和控制按钮
    使用 PlayCtrl SDK 直接渲染 + InfoOverlay 叠加层
    """

    # 自定义信号
    channelSelected = QtCore.Signal(dict)
    channelConnected = QtCore.Signal(str)
    channelDisconnected = QtCore.Signal(str)
    channelAdded = QtCore.Signal(dict)
    channelRemoved = QtCore.Signal(str)
    channelEdited = QtCore.Signal(str, dict)
    curveClicked = QtCore.Signal(str)
    amplifyClicked = QtCore.Signal(str)
    channelNameChanged = QtCore.Signal(str, str)
    panelClicked = QtCore.Signal(str)  # 新增：面板点击信号，传递channel_id
    
    def __init__(self, title="通道", parent=None, debug_mode=False, width=None, height=None):
        super(ChannelPanel, self).__init__(parent)
        self._parent = parent
        self._title = title
        self._channels = {}
        self._current_channel_id = None
        self._debug_mode = debug_mode
        self._is_disabled = False
        self._channel_number = title.replace("通道", "")
        self._hwnd_render_mode = False
        self._is_connected = False
        self._custom_width = width  # 自定义宽度
        self._custom_height = height  # 自定义高度

        # 初始化 logger
        self.logger = logging.getLogger(f"ChannelPanel.{title}")

        self.setObjectName("ChannelPanel")

        # 按钮叠加层引用（在_initUI之前声明）
        self._buttonOverlay = None

        self._initUI()
        self._ensureButtonOverlay()  # 创建按钮叠加层
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI布局"""
        # 使用自定义尺寸或默认尺寸
        if self._custom_width and self._custom_height:
            self.setFixedSize(self._custom_width, self._custom_height)
        else:
            self.setFixedSize(scale_w(620), scale_h(465))
        
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(0, 0, 0))
        self.setPalette(palette)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 视频渲染区域
        self.videoWidget = VideoRenderWidget()
        self.videoWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.videoLabel = self.videoWidget  # 兼容性
        
        # InfoOverlay 叠加层（延迟创建，避免影响主窗口显示）
        self._infoOverlay = None
        
        # 🔥 兼容性：创建 taskLabel 属性（实际显示由 InfoOverlay 处理）
        self.taskLabel = QtWidgets.QLabel()
        self.taskLabel.hide()  # 隐藏，仅用于兼容旧代码
        
        # 🔥 兼容性：创建 nameLabel 属性
        self.nameLabel = QtWidgets.QLabel()
        self.nameLabel.hide()
        
        # 🔥 兼容性：创建 debugLabel 属性
        self.debugLabel = QtWidgets.QLabel()
        self.debugLabel.hide()
        
        # 未连接提示
        self._overlayLabel = QtWidgets.QLabel(self.videoWidget)
        self._overlayLabel.setStyleSheet("QLabel { background-color: black; color: white; }")
        self._overlayLabel.setAlignment(Qt.AlignCenter)
        self._overlayLabel.setText("未打开通道")
        if FontManager:
            FontManager.applyToWidget(self._overlayLabel)
        
        layout.addWidget(self.videoWidget, 1)

        # 按钮叠加层将在_initUI后创建
        # 兼容性：预先声明按钮引用
        self.btnToggleConnect = None
        self.btnEdit = None
        self.btnCurve = None
        self.btnAmplify = None
    
    def _connectSignals(self):
        """连接信号槽"""
        if self._buttonOverlay:
            self._buttonOverlay.toggleConnectClicked.connect(self._onToggleConnectClicked)
            self._buttonOverlay.editClicked.connect(self._onEditClicked)
            self._buttonOverlay.curveClicked.connect(self._onCurveClicked)
            self._buttonOverlay.amplifyClicked.connect(self._onAmplifyClicked)

        # 视频区域点击事件
        self.videoWidget.mousePressEvent = self._onVideoWidgetClicked
    
    # ==================== HWND渲染模式API ====================

    def _ensureButtonOverlay(self):
        """确保 ButtonOverlay 已创建"""
        if self._buttonOverlay is None:
            self._buttonOverlay = ButtonOverlay(self.videoWidget)
            # 兼容性：保留按钮引用
            self.btnToggleConnect = self._buttonOverlay.btnToggleConnect
            self.btnEdit = self._buttonOverlay.btnEdit
            self.btnCurve = self._buttonOverlay.btnCurve
            self.btnAmplify = self._buttonOverlay.btnAmplify
            # 初始化位置
            self._buttonOverlay.setGeometry(0, self.videoWidget.height() - 45, self.videoWidget.width(), 45)
            self._buttonOverlay.show()

    def _ensureInfoOverlay(self):
        """确保 InfoOverlay 已创建"""
        if self._infoOverlay is None:
            # 修改：将 InfoOverlay 的父控件设置为 videoWidget，而不是 self
            self._infoOverlay = InfoOverlay(self._title, self.videoWidget)
            self._infoOverlay.set_target(self.videoWidget)
            # 初始化位置
            self._infoOverlay.setGeometry(0, 0, self.videoWidget.width(), 28)
            self._infoOverlay.show()
    
    def getVideoHwnd(self):
        """获取视频显示区域的窗口句柄"""
        if hasattr(self.videoWidget, 'winId'):
            return int(self.videoWidget.winId())
        return 0
    
    def setHwndRenderMode(self, enabled=True):
        """设置HWND直接渲染模式"""
        self._hwnd_render_mode = enabled
        if enabled:
            self._overlayLabel.hide()
            # 启用 InfoOverlay 叠加层
            self._ensureInfoOverlay()
            self._infoOverlay.show()
            # 启用 ButtonOverlay 叠加层
            self._ensureButtonOverlay()
            self._buttonOverlay.show()
            self.logger.debug(f"[ChannelPanel] HWND渲染模式已启用，InfoOverlay和ButtonOverlay已显示")
        else:
            self._overlayLabel.show()
            if self._infoOverlay:
                self._infoOverlay.hide()
            if self._buttonOverlay:
                self._buttonOverlay.hide()
            self.logger.debug(f"[ChannelPanel] Qt渲染模式已启用")
    
    def showOverlay(self):
        """显示叠加层"""
        if self._hwnd_render_mode:
            self._ensureInfoOverlay()
            self._infoOverlay.show()
    
    def hideOverlay(self):
        """隐藏叠加层"""
        if self._infoOverlay:
            self._infoOverlay.hide()
    
    def updateOverlayInfo(self, channel_name=None, task_name=None, fps=None, resolution=None):
        """更新叠加层信息"""
        self._ensureInfoOverlay()
        self._infoOverlay.update_info(channel_name, task_name, fps, resolution)
    
    def updateLiquidLines(self, liquid_positions, is_new_data=True, video_width=0, video_height=0):
        """更新液位线数据
        
        Args:
            liquid_positions: 液位线位置数据 {area_idx: {left, right, y, height_mm, valid, ...}}
            is_new_data: 是否为新数据（True=红色，False=黄色）
            video_width: 原始视频宽度
            video_height: 原始视频高度
        """
        self._ensureInfoOverlay()
        self._infoOverlay.update_liquid_lines(liquid_positions, is_new_data, video_width, video_height)
    
    def clearLiquidLines(self):
        """清空液位线数据"""
        if self._infoOverlay:
            self._infoOverlay.clear_liquid_lines()

    
    # ==================== 通道管理API ====================
    
    def addChannel(self, channel_id, channel_data):
        """添加通道"""
        if channel_id in self._channels:
            return False
        self._channels[channel_id] = channel_data
        if self._current_channel_id is None:
            self._current_channel_id = channel_id
        self.channelAdded.emit(channel_data)
        return True
    
    def removeChannel(self, channel_id):
        """删除通道"""
        if channel_id not in self._channels:
            return False
        del self._channels[channel_id]
        if self._current_channel_id == channel_id:
            self._current_channel_id = None
            if self._channels:
                self._current_channel_id = next(iter(self._channels))
        self.channelRemoved.emit(channel_id)
        return True
    
    def updateChannel(self, channel_id, channel_data):
        """更新通道信息"""
        if channel_id not in self._channels:
            return False
        self._channels[channel_id].update(channel_data)
        return True
    
    def getChannel(self, channel_id):
        """获取通道信息"""
        return self._channels.get(channel_id)
    
    def getCurrentChannel(self):
        """获取当前选中的通道"""
        if self._current_channel_id and self._current_channel_id in self._channels:
            return self._current_channel_id, self._channels[self._current_channel_id]
        return None, None
    
    def setCurrentChannel(self, channel_id):
        """设置当前选中的通道"""
        if channel_id in self._channels:
            self._current_channel_id = channel_id
            return True
        return False
    
    def clearChannels(self):
        """清空所有通道"""
        self._channels.clear()
        self._current_channel_id = None
    
    # ==================== 显示控制API ====================
    
    def displayFrame(self, frame):
        """显示视频帧
        
        Args:
            frame: QPixmap或numpy数组
        """
        try:
            from qtpy import QtGui
            
            # 如果是QPixmap，直接显示
            if isinstance(frame, QtGui.QPixmap):
                # 缩放到videoWidget大小
                scaled_pixmap = frame.scaled(
                    self.videoWidget.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                # 设置到videoWidget
                self.videoWidget.setPixmap(scaled_pixmap)
                
                # 隐藏未连接提示
                if self._overlayLabel.isVisible():
                    self._overlayLabel.hide()

                # 显示InfoOverlay
                if self._infoOverlay:
                    self._infoOverlay.show()

                # 显示ButtonOverlay
                if self._buttonOverlay:
                    self._buttonOverlay.show()

                return
            
            # 如果是numpy数组，转换为QPixmap
            if hasattr(frame, 'shape'):
                import cv2
                import numpy as np

                height, width, channel = frame.shape
                bytes_per_line = 3 * width

                # BGR转RGB（HKcapture输出BGR格式）
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame = np.ascontiguousarray(rgb_frame)

                # 转换为QImage并交换R和B通道
                q_image = QtGui.QImage(
                    rgb_frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format_RGB888
                ).rgbSwapped()

                # 转换为QPixmap
                pixmap = QtGui.QPixmap.fromImage(q_image)

                # 递归调用显示
                self.displayFrame(pixmap)
                
        except Exception as e:
            self.logger.debug(f"[ChannelPanel] displayFrame异常: {e}")
    
    def clearDisplay(self):
        """清空显示区域"""
        self._hwnd_render_mode = False
        self._overlayLabel.clear()
        self._overlayLabel.setText("未打开通道")
        self._overlayLabel.setGeometry(0, 0, self.videoWidget.width(), self.videoWidget.height())
        self._overlayLabel.show()
        if self._infoOverlay:
            self._infoOverlay.hide()
        if self._buttonOverlay:
            self._buttonOverlay.hide()
    
    def setChannelName(self, name):
        """设置通道名称"""
        self._ensureInfoOverlay()
        self._infoOverlay.update_info(channel_name=name)
    
    def getChannelName(self):
        """获取通道名称"""
        if self._infoOverlay:
            return self._infoOverlay.channel_name
        return self._title
    
    def setTaskInfo(self, task_folder_name):
        """设置任务信息"""
        self._ensureInfoOverlay()
        if task_folder_name and task_folder_name.strip() and task_folder_name.lower() != "none":
            self._infoOverlay.update_info(task_name=task_folder_name.strip())
            self._setDisabled(False)
        else:
            self._infoOverlay.update_info(task_name="未分配任务")
            self._setDisabled(True)
    
    def clearTaskInfo(self):
        """清空任务信息"""
        self._ensureInfoOverlay()
        self._infoOverlay.update_info(task_name="未分配任务")
        self._setDisabled(True)
    
    def getTaskInfo(self):
        """获取任务信息"""
        if not self._infoOverlay:
            return None
        task = self._infoOverlay.task_name
        if not task or task == "未分配任务":
            return None
        return task
    
    def setConnected(self, is_connected):
        """设置连接状态"""
        self._is_connected = is_connected
        if is_connected:
            self.btnToggleConnect.setIcon(newIcon("停止1"))
            self.btnToggleConnect.setToolTip("断开连接")
        else:
            self.btnToggleConnect.setIcon(newIcon("开始"))
            self.btnToggleConnect.setToolTip("打开通道")
    
    def _setDisabled(self, disabled):
        """设置面板禁用状态"""
        self._is_disabled = disabled
        self.btnToggleConnect.setEnabled(not disabled)
        self.btnCurve.setEnabled(not disabled)
        self.btnAmplify.setEnabled(not disabled)
        self.btnEdit.setEnabled(not disabled)
    
    # ==================== 事件处理 ====================
    
    def _onToggleConnectClicked(self):
        """连接/断开按钮点击"""
        channel_id, _ = self.getCurrentChannel()
        if not channel_id:
            return
        if self._is_connected:
            # 立即切换到断开状态
            self.setConnected(False)
            self.channelDisconnected.emit(channel_id)
        else:
            # 立即切换到连接状态
            self.setConnected(True)
            self.channelConnected.emit(channel_id)
    
    def _onEditClicked(self):
        """编辑按钮点击"""
        channel_id, channel_data = self.getCurrentChannel()
        if not channel_id:
            channel_id = self._title or "未命名通道"
            channel_data = {}
        self.channelEdited.emit(channel_id, channel_data or {})
    
    def _onCurveClicked(self):
        """曲线按钮点击"""
        task_name = self.getTaskInfo()
        self.curveClicked.emit(task_name if task_name else "")
    
    def _onAmplifyClicked(self):
        """放大按钮点击"""
        channel_id, _ = self.getCurrentChannel()
        if not channel_id:
            channel_id = self._title or "未命名通道"
        self.amplifyClicked.emit(channel_id)

    def _onVideoWidgetClicked(self, event):
        """视频区域点击事件"""
        # 只有在连接状态下才响应点击
        if self._is_connected:
            channel_id, _ = self.getCurrentChannel()
            if channel_id:
                self.panelClicked.emit(channel_id)

    def resizeEvent(self, event):
        """窗口大小改变"""
        super(ChannelPanel, self).resizeEvent(event)
        if hasattr(self, '_overlayLabel'):
            self._overlayLabel.setGeometry(0, 0, self.videoWidget.width(), self.videoWidget.height())
        # 不再在resizeEvent中调用update_position，让叠加层自己的resizeEvent处理
    
    def moveEvent(self, event):
        """窗口移动"""
        super(ChannelPanel, self).moveEvent(event)
        # 不需要在moveEvent中更新叠加层位置
    
    def showEvent(self, event):
        """窗口显示"""
        super(ChannelPanel, self).showEvent(event)
        if self._hwnd_render_mode and self._infoOverlay:
            self._infoOverlay.show()
        if self._buttonOverlay:
            self._buttonOverlay.show()
    
    def hideEvent(self, event):
        """窗口隐藏"""
        super(ChannelPanel, self).hideEvent(event)
        if self._infoOverlay:
            self._infoOverlay.hide()
        if self._buttonOverlay:
            self._buttonOverlay.hide()
    
    def closeEvent(self, event):
        """窗口关闭"""
        if self._infoOverlay:
            self._infoOverlay.close()
        if self._buttonOverlay:
            self._buttonOverlay.close()
        super(ChannelPanel, self).closeEvent(event)
