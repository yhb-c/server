# -*- coding: utf-8 -*-
"""
通道面板组件 - 使用 PlayCtrl SDK 直接渲染 + InfoOverlay 叠加层

渲染方式：PlayCtrl SDK 直接渲染到 videoWidget.winId() 返回的 HWND
叠加层：InfoOverlay 是独立的透明顶层窗口，叠加在视频上方显示信息
"""

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
        
        # 设置为无边框顶层窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.Tool |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 信息数据
        self.channel_name = channel_id
        self.task_name = "未分配任务"
        self.fps = 0.0
        self.resolution = "0x0"
        self.target_widget = None
        
        # 🔥 液位线数据
        self.liquid_positions = {}  # {area_idx: {left, right, y, height_mm, valid, ...}}
        self.is_new_data = True  # 是否为新数据（影响颜色）
        self.video_width = 0  # 原始视频宽度
        self.video_height = 0  # 原始视频高度
        
        # 初始隐藏
        self.hide()
    
    def set_target(self, widget):
        """设置要跟随的视频控件"""
        self.target_widget = widget
        self.update_position()
    
    def update_position(self):
        """更新位置跟随目标控件"""
        if self.target_widget and self.target_widget.isVisible():
            pos = self.target_widget.mapToGlobal(QtCore.QPoint(0, 0))
            self.setGeometry(pos.x(), pos.y(),
                           self.target_widget.width(), self.target_widget.height())
    
    def update_info(self, channel_name=None, task_name=None, fps=None, resolution=None):
        """更新显示信息"""
        if channel_name is not None:
            self.channel_name = channel_name
        if task_name is not None:
            self.task_name = task_name
        if fps is not None:
            self.fps = fps
        if resolution is not None:
            self.resolution = resolution
            # 解析分辨率
            try:
                parts = resolution.split('x')
                if len(parts) == 2:
                    self.video_width = int(parts[0])
                    self.video_height = int(parts[1])
            except:
                pass
        self.update_position()
        self.repaint()
    
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
        self.repaint()
    
    def clear_liquid_lines(self):
        """清空液位线数据"""
        self.liquid_positions = {}
        self.repaint()
    
    def paintEvent(self, event):
        """绑制叠加信息"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 顶部信息栏背景
        painter.fillRect(0, 0, self.width(), 28, QtGui.QColor(0, 0, 0, 180))
        
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        x_pos = 8
        
        # 通道名称
        painter.setPen(Qt.white)
        painter.drawText(x_pos, 19, self.channel_name)
        x_pos += 80
        
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawText(x_pos, 19, "|")
        x_pos += 15
        
        # 分辨率
        painter.setPen(QtGui.QColor(255, 255, 0))
        painter.drawText(x_pos, 19, self.resolution)
        x_pos += 90
        
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawText(x_pos, 19, "|")
        x_pos += 15
        
        # FPS
        painter.setPen(QtGui.QColor(0, 255, 0))
        painter.drawText(x_pos, 19, f"FPS: {self.fps:.1f}")
        
        # 任务名称（右侧）
        painter.setPen(QtGui.QColor(0, 255, 255))
        task_text = self.task_name if self.task_name else "未分配任务"
        font_metrics = painter.fontMetrics()
        task_width = font_metrics.horizontalAdvance(task_text)
        painter.drawText(self.width() - task_width - 10, 19, task_text)
        
        # 🔥 绘制液位线
        self._draw_liquid_lines(painter)
    
    def _draw_liquid_lines(self, painter):
        """绘制液位线
        
        Args:
            painter: QPainter 对象
        """
        if not self.liquid_positions:
            return
        
        # 计算缩放比例（视频坐标 -> 控件坐标）
        if self.video_width <= 0 or self.video_height <= 0:
            return
        
        scale_x = self.width() / self.video_width
        scale_y = self.height() / self.video_height
        
        # 选择颜色
        if self.is_new_data:
            line_color = QtGui.QColor(255, 0, 0)  # 红色 - 新数据
            text_color = QtGui.QColor(0, 255, 0)  # 绿色文字
        else:
            line_color = QtGui.QColor(255, 255, 0)  # 黄色 - 历史数据
            text_color = QtGui.QColor(255, 255, 0)
        
        pen = QtGui.QPen(line_color, 2)
        painter.setPen(pen)
        
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        for area_idx, position_data in self.liquid_positions.items():
            try:
                left = position_data.get('left', 0)
                right = position_data.get('right', 0)
                y_absolute = position_data.get('y', 0)
                height_mm = position_data.get('height_mm', 0)
                valid = position_data.get('valid', True)
                
                if not valid:
                    continue
                
                # 坐标转换
                x1 = int(left * scale_x)
                x2 = int(right * scale_x)
                y = int(y_absolute * scale_y)
                
                # 绘制液位线
                painter.setPen(pen)
                painter.drawLine(x1, y, x2, y)
                
                # 绘制高度文字
                height_mm_int = int(round(height_mm, 0))
                text = f"{height_mm_int}mm"
                painter.setPen(text_color)
                painter.drawText(x1 + 5, y - 10, text)
                
            except Exception as e:
                continue


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
    
    def __init__(self, title="通道", parent=None, debug_mode=False):
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
        
        self.setObjectName("ChannelPanel")
        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI布局"""
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
        
        # 按钮面板
        buttonPanel = QtWidgets.QWidget()
        buttonPanel.setStyleSheet("background-color: palette(button);")
        buttonPanel.setFixedHeight(scale_h(45))
        
        buttonLayout = QtWidgets.QHBoxLayout(buttonPanel)
        buttonLayout.setContentsMargins(5, 5, 5, 5)
        buttonLayout.setSpacing(5)
        
        button_style = """
            QPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 3px; padding: 5px; }
            QPushButton:hover { background-color: palette(light); border: 1px solid palette(mid); }
            QPushButton:pressed { background-color: palette(midlight); }
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
        
        self.btnEdit = QtWidgets.QPushButton()
        self.btnEdit.setIcon(newIcon('设置'))
        self.btnEdit.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnEdit.setToolTip("通道设置")
        self.btnEdit.setStyleSheet(button_style)
        self.btnEdit.setFixedSize(btn_size, btn_size)
        
        self.btnCurve = QtWidgets.QPushButton()
        self.btnCurve.setIcon(newIcon('动态曲线'))
        self.btnCurve.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnCurve.setToolTip("查看曲线")
        self.btnCurve.setStyleSheet(button_style)
        self.btnCurve.setFixedSize(btn_size, btn_size)
        
        self.btnAmplify = QtWidgets.QPushButton()
        self.btnAmplify.setIcon(newIcon('amplify'))
        self.btnAmplify.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btnAmplify.setToolTip("放大显示")
        self.btnAmplify.setStyleSheet(button_style)
        self.btnAmplify.setFixedSize(btn_size, btn_size)
        
        buttonLayout.addWidget(self.btnToggleConnect)
        buttonLayout.addWidget(self.btnEdit)
        buttonLayout.addWidget(self.btnCurve)
        buttonLayout.addWidget(self.btnAmplify)
        buttonLayout.addStretch()
        
        layout.addWidget(buttonPanel)
    
    def _connectSignals(self):
        """连接信号槽"""
        self.btnToggleConnect.clicked.connect(self._onToggleConnectClicked)
        self.btnEdit.clicked.connect(self._onEditClicked)
        self.btnCurve.clicked.connect(self._onCurveClicked)
        self.btnAmplify.clicked.connect(self._onAmplifyClicked)
    
    # ==================== HWND渲染模式API ====================
    
    def _ensureInfoOverlay(self):
        """确保 InfoOverlay 已创建"""
        if self._infoOverlay is None:
            self._infoOverlay = InfoOverlay(self._title, self)
            self._infoOverlay.set_target(self.videoWidget)
    
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
            # 🔥 启用 InfoOverlay 叠加层
            self._ensureInfoOverlay()
            self._infoOverlay.show()
            self._infoOverlay.update_position()
            self.logger.debug(f"[ChannelPanel] HWND渲染模式已启用，InfoOverlay已显示")
        else:
            self._overlayLabel.show()
            if self._infoOverlay:
                self._infoOverlay.hide()
            self.logger.debug(f"[ChannelPanel] Qt渲染模式已启用")
    
    def showOverlay(self):
        """显示叠加层"""
        if self._hwnd_render_mode:
            self._ensureInfoOverlay()
            self._infoOverlay.show()
            self._infoOverlay.update_position()
    
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
                    self._infoOverlay.update_position()
                
                return
            
            # 如果是numpy数组，转换为QPixmap
            if hasattr(frame, 'shape'):
                import cv2
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                
                # 转换为QImage
                q_image = QtGui.QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format_RGB888
                )
                
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
    
    def resizeEvent(self, event):
        """窗口大小改变"""
        super(ChannelPanel, self).resizeEvent(event)
        if hasattr(self, '_overlayLabel'):
            self._overlayLabel.setGeometry(0, 0, self.videoWidget.width(), self.videoWidget.height())
        if self._infoOverlay:
            QtCore.QTimer.singleShot(0, self._infoOverlay.update_position)
    
    def moveEvent(self, event):
        """窗口移动"""
        super(ChannelPanel, self).moveEvent(event)
        if self._infoOverlay:
            self._infoOverlay.update_position()
    
    def showEvent(self, event):
        """窗口显示"""
        super(ChannelPanel, self).showEvent(event)
        if self._hwnd_render_mode and self._infoOverlay:
            self._infoOverlay.show()
            self._infoOverlay.update_position()
    
    def hideEvent(self, event):
        """窗口隐藏"""
        super(ChannelPanel, self).hideEvent(event)
        if self._infoOverlay:
            self._infoOverlay.hide()
    
    def closeEvent(self, event):
        """窗口关闭"""
        if self._infoOverlay:
            self._infoOverlay.close()
        super(ChannelPanel, self).closeEvent(event)
