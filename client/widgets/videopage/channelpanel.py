# -*- coding: utf-8 -*-
"""
通道面板组件 - 使用Qt渲染模式

渲染方式：Qt直接渲染视频帧和液位线到VideoRenderWidget
"""

import logging
import numpy as np
import os
import yaml
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


class VideoRenderWidget(QtWidgets.QWidget):
    """视频渲染专用Widget - Qt渲染模式，支持液位线绘制"""

    def __init__(self, parent=None):
        super(VideoRenderWidget, self).__init__(parent)
        self.setStyleSheet("background-color: black;")

        # 视频帧
        self._pixmap = None

        # 液位线数据
        self.liquid_positions = {}
        self.is_new_data = True
        self.video_width = 0
        self.video_height = 0

        # ROI数据
        self.roi_boxes = []
        self.show_roi = True

        # 信息显示数据
        self.channel_name = ""
        self.task_name = "未分配任务"
        self.fps = 0.0
        self.resolution = "0x0"

        # ROI配置文件路径
        self.roi_config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'server', 'config', 'annotation_result.yaml'
        )

    def setPixmap(self, pixmap):
        """设置要显示的pixmap"""
        self._pixmap = pixmap
        self.update()

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

        # 触发重绘
        self.update()

    def clear_liquid_lines(self):
        """清空液位线数据"""
        self.liquid_positions = {}
        self.update()

    def load_roi_config(self, channel_id):
        """加载ROI配置

        Args:
            channel_id: 通道ID，如 "channel1"
        """
        try:
            if not os.path.exists(self.roi_config_path):
                return

            with open(self.roi_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not config or channel_id not in config:
                self.roi_boxes = []
                return

            channel_config = config[channel_id]
            boxes = channel_config.get('boxes', [])
            fixed_tops = channel_config.get('fixed_tops', [])
            fixed_bottoms = channel_config.get('fixed_bottoms', [])

            # 获取配置文件中保存的标注分辨率（默认1920x1080）
            annotation_width = channel_config.get('annotation_width', 1920)
            annotation_height = channel_config.get('annotation_height', 1080)

            # 计算分辨率缩放比例
            if self.video_width > 0 and self.video_height > 0:
                scale_x = self.video_width / annotation_width
                scale_y = self.video_height / annotation_height
                print(f"[ROI加载] 标注分辨率: {annotation_width}x{annotation_height}")
                print(f"[ROI加载] 当前视频分辨率: {self.video_width}x{self.video_height}")
                print(f"[ROI加载] 缩放比例: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
            else:
                # 如果还没有获取到视频分辨率，暂不缩放
                scale_x = 1.0
                scale_y = 1.0
                print(f"[ROI加载] 视频分辨率未知，暂不缩放ROI")

            # 构建ROI框列表 [left, top, right, bottom]
            # boxes格式: [center_x, center_y, crop_size]
            self.roi_boxes = []
            for i, box in enumerate(boxes):
                if len(box) >= 3:
                    center_x = box[0]
                    center_y = box[1]
                    crop_size = box[2]
                    half_size = crop_size // 2

                    # 应用分辨率缩放
                    left = int((center_x - half_size) * scale_x)
                    right = int((center_x + half_size) * scale_x)
                    top_orig = fixed_tops[i] if i < len(fixed_tops) else 0
                    bottom_orig = fixed_bottoms[i] if i < len(fixed_bottoms) else 0
                    top = int(top_orig * scale_y)
                    bottom = int(bottom_orig * scale_y)

                    self.roi_boxes.append([left, top, right, bottom])
                    print(f"[ROI加载] ROI[{i}] 原始: left={center_x - half_size}, right={center_x + half_size}, top={top_orig}, bottom={bottom_orig}")
                    print(f"[ROI加载] ROI[{i}] 缩放后: left={left}, right={right}, top={top}, bottom={bottom}")

            self.update()

        except Exception as e:
            print(f"加载ROI配置失败: {e}")
            self.roi_boxes = []

    def set_show_roi(self, show):
        """设置是否显示ROI"""
        self.show_roi = show
        self.update()

    def update_info(self, channel_name=None, task_name=None, fps=None, resolution=None):
        """更新显示信息"""
        resolution_changed = False

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
                    new_width = int(parts[0])
                    new_height = int(parts[1])
                    # 检查分辨率是否变化
                    if new_width != self.video_width or new_height != self.video_height:
                        self.video_width = new_width
                        self.video_height = new_height
                        resolution_changed = True
                        print(f"[VideoRenderWidget] 视频分辨率更新: {self.video_width}x{self.video_height}")
            except:
                pass

        # 如果分辨率变化且有通道名称，重新加载ROI配置
        if resolution_changed and self.channel_name:
            channel_id = self.channel_name.lower().replace('通道', 'channel')
            print(f"[VideoRenderWidget] 分辨率变化，重新加载ROI配置: {channel_id}")
            self.load_roi_config(channel_id)

        self.update()

    def paintEvent(self, event):
        """绘制事件 - 绘制视频帧、ROI、液位线和信息栏"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 1. 绘制视频帧
        if self._pixmap and not self._pixmap.isNull():
            # 计算居中位置
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2

            # 绘制pixmap
            painter.drawPixmap(x, y, self._pixmap)

            # 2. 绘制ROI区域（在视频帧上方）
            if self.show_roi and self.roi_boxes:
                self._draw_roi_boxes(painter, x, y)

            # 3. 绘制液位线（在ROI上方）
            if self.liquid_positions:
                self._draw_liquid_lines(painter, x, y)

            # 4. 绘制信息栏（在最上方）
            self._draw_info_bar(painter)

    def _draw_roi_boxes(self, painter, offset_x, offset_y):
        """绘制ROI区域框

        Args:
            painter: QPainter对象
            offset_x: 视频帧X偏移
            offset_y: 视频帧Y偏移
        """
        if not self.roi_boxes or not self._pixmap:
            return

        # 计算缩放比例
        if self.video_width > 0 and self.video_height > 0:
            scale_x = self._pixmap.width() / self.video_width
            scale_y = self._pixmap.height() / self.video_height
        else:
            scale_x = 1.0
            scale_y = 1.0

        print(f"\n[ROI绘制] 视频原始尺寸: {self.video_width}x{self.video_height}")
        print(f"[ROI绘制] Pixmap显示尺寸: {self._pixmap.width()}x{self._pixmap.height()}")
        print(f"[ROI绘制] 绘制缩放比例: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
        print(f"[ROI绘制] 偏移量: offset_x={offset_x}, offset_y={offset_y}")

        # 设置ROI框样式：蓝色半透明矩形
        roi_color = QtGui.QColor(0, 255, 255, 100)  # 青色半透明
        roi_border_color = QtGui.QColor(0, 255, 255)  # 青色边框

        # 绘制每个ROI框
        for i, box in enumerate(self.roi_boxes):
            try:
                left, top, right, bottom = box

                print(f"[ROI绘制] ROI[{i}] 原始坐标: left={left}, top={top}, right={right}, bottom={bottom}")

                # 应用缩放和偏移
                scaled_left = int(left * scale_x) + offset_x
                scaled_top = int(top * scale_y) + offset_y
                scaled_right = int(right * scale_x) + offset_x
                scaled_bottom = int(bottom * scale_y) + offset_y

                width = scaled_right - scaled_left
                height = scaled_bottom - scaled_top

                print(f"[ROI绘制] ROI[{i}] 缩放后坐标: left={scaled_left}, top={scaled_top}, right={scaled_right}, bottom={scaled_bottom}")
                print(f"[ROI绘制] ROI[{i}] 宽高: width={width}, height={height}")

                # 绘制半透明填充
                painter.fillRect(scaled_left, scaled_top, width, height, roi_color)

                # 绘制边框
                painter.setPen(QtGui.QPen(roi_border_color, 2))
                painter.drawRect(scaled_left, scaled_top, width, height)

                # 绘制ROI标签
                label = f"ROI {i+1}"
                painter.setPen(roi_border_color)
                font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
                painter.setFont(font)
                painter.drawText(scaled_left + 5, scaled_top + 15, label)

            except Exception as e:
                print(f"[ROI绘制] 绘制ROI[{i}]失败: {e}")
                continue

    def _draw_liquid_lines(self, painter, offset_x, offset_y):
        """绘制液位线

        Args:
            painter: QPainter对象
            offset_x: 视频帧X偏移
            offset_y: 视频帧Y偏移
        """
        if not self.liquid_positions or not self._pixmap:
            return

        # 计算缩放比例
        if self.video_width > 0 and self.video_height > 0:
            scale_x = self._pixmap.width() / self.video_width
            scale_y = self._pixmap.height() / self.video_height
        else:
            scale_x = 1.0
            scale_y = 1.0

        # 设置液位线颜色（红色=新数据，黄色=旧数据）
        line_color = QtGui.QColor(255, 0, 0) if self.is_new_data else QtGui.QColor(255, 255, 0)
        text_color = QtGui.QColor(0, 255, 0)

        # 设置画笔
        pen = QtGui.QPen(line_color, 2)
        painter.setPen(pen)

        # 设置字体
        font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        painter.setFont(font)

        # 输出绘制液位线的配置信息
        print("\n========== 绘制液位线配置信息 ==========")
        print(f"视频尺寸: {self.video_width}x{self.video_height}")
        print(f"显示尺寸: {self._pixmap.width()}x{self._pixmap.height()}")
        print(f"缩放比例: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
        print(f"偏移量: offset_x={offset_x}, offset_y={offset_y}")
        print(f"液位线数据数量: {len(self.liquid_positions)}")

        # 加载配置文件进行对比
        try:
            if os.path.exists(self.roi_config_path):
                with open(self.roi_config_path, 'r', encoding='utf-8') as f:
                    roi_config = yaml.safe_load(f)
                print(f"\n配置文件路径: {self.roi_config_path}")
                print(f"配置文件中的通道: {list(roi_config.keys()) if roi_config else []}")
            else:
                roi_config = None
                print(f"\n配置文件不存在: {self.roi_config_path}")
        except Exception as e:
            roi_config = None
            print(f"\n读取配置文件失败: {e}")

        # 遍历每个ROI的液位线数据
        for area_idx, position_data in self.liquid_positions.items():
            try:
                left = position_data.get('left', 0)
                right = position_data.get('right', 0)
                y_absolute = position_data.get('y', position_data.get('y_absolute', 0))
                height_mm = position_data.get('height_mm', 0)

                print(f"\n--- 区域 {area_idx} ---")
                print(f"液位线数据: left={left}, right={right}, y={y_absolute}, height_mm={height_mm}")
                # 不打印完整数据，避免输出大量mask数组
                filtered_data = {k: v for k, v in position_data.items() if k != 'observation_mask'}
                print(f"过滤后数据: {filtered_data}")

                # 对比配置文件中的ROI信息
                if roi_config and hasattr(self, 'channel_name'):
                    channel_id = self.channel_name.lower().replace('通道', 'channel')
                    if channel_id in roi_config:
                        channel_config = roi_config[channel_id]
                        boxes = channel_config.get('boxes', [])
                        fixed_tops = channel_config.get('fixed_tops', [])
                        fixed_bottoms = channel_config.get('fixed_bottoms', [])

                        print(f"\n配置文件中 {channel_id} 的ROI信息:")
                        if area_idx < len(boxes):
                            box = boxes[area_idx]
                            top = fixed_tops[area_idx] if area_idx < len(fixed_tops) else None
                            bottom = fixed_bottoms[area_idx] if area_idx < len(fixed_bottoms) else None
                            print(f"  boxes[{area_idx}]: {box} (格式: [center_x, center_y, crop_size])")
                            print(f"  fixed_tops[{area_idx}]: {top}")
                            print(f"  fixed_bottoms[{area_idx}]: {bottom}")

                            # 对比数据
                            if len(box) >= 3:
                                config_center_x = box[0]
                                config_center_y = box[1]
                                config_crop_size = box[2]
                                config_half_size = config_crop_size // 2
                                config_left = config_center_x - config_half_size
                                config_right = config_center_x + config_half_size

                                print(f"\n配置文件ROI计算:")
                                print(f"  center_x={config_center_x}, center_y={config_center_y}, crop_size={config_crop_size}")
                                print(f"  计算得到: left={config_left}, right={config_right}")

                                print(f"\n数据对比:")
                                print(f"  left: 液位线={left}, 配置计算={config_left}, 匹配={left==config_left}")
                                print(f"  right: 液位线={right}, 配置计算={config_right}, 匹配={right==config_right}")
                                if top is not None and bottom is not None:
                                    print(f"  Y坐标范围: 液位线y={y_absolute}, 配置top={top}, 配置bottom={bottom}")
                                    print(f"  Y坐标是否在范围内: {top <= y_absolute <= bottom}")

                                # 检查ROI框加载
                                if area_idx < len(self.roi_boxes):
                                    roi_box = self.roi_boxes[area_idx]
                                    print(f"\n加载的ROI框[{area_idx}]: {roi_box} (格式: [left, top, right, bottom])")
                                    print(f"  ROI框与配置对比: left匹配={roi_box[0]==config_left}, right匹配={roi_box[2]==config_right}")

                # 应用缩放和偏移
                scaled_left = int(left * scale_x) + offset_x
                scaled_right = int(right * scale_x) + offset_x
                scaled_y = int(y_absolute * scale_y) + offset_y

                print(f"缩放后坐标: scaled_left={scaled_left}, scaled_right={scaled_right}, scaled_y={scaled_y}")

                # 绘制红色液位线
                painter.setPen(QtGui.QPen(line_color, 2))
                painter.drawLine(scaled_left, scaled_y, scaled_right, scaled_y)

                # 绘制绿色高度文字
                height_mm_rounded = int(round(height_mm, 0))
                text = f"{height_mm_rounded}mm"
                painter.setPen(text_color)
                painter.drawText(scaled_left + 5, scaled_y - 10, text)

            except Exception as e:
                print(f"绘制区域 {area_idx} 失败: {e}")
                continue

        print("========================================\n")

    def _draw_info_bar(self, painter):
        """绘制信息栏（顶部）"""
        # 绘制半透明背景
        painter.fillRect(0, 0, self.width(), 28, QtGui.QColor(0, 0, 0, 180))

        # 设置字体
        font = QtGui.QFont("Arial", 9, QtGui.QFont.Bold)
        painter.setFont(font)

        # 绘制通道名称
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(8, 18, self.channel_name)

        # 绘制分隔符
        x_offset = 8 + painter.fontMetrics().horizontalAdvance(self.channel_name) + 10
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawText(x_offset, 18, "|")
        x_offset += 15

        # 绘制分辨率
        painter.setPen(QtGui.QColor(255, 255, 0))
        painter.drawText(x_offset, 18, self.resolution)
        x_offset += painter.fontMetrics().horizontalAdvance(self.resolution) + 10

        # 绘制分隔符
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawText(x_offset, 18, "|")
        x_offset += 15

        # 绘制FPS
        fps_text = f"FPS: {self.fps:.1f}"
        painter.setPen(QtGui.QColor(0, 255, 0))
        painter.drawText(x_offset, 18, fps_text)

        # 绘制任务名称（右对齐）
        painter.setPen(QtGui.QColor(0, 255, 255))
        task_width = painter.fontMetrics().horizontalAdvance(self.task_name)
        painter.drawText(self.width() - task_width - 8, 18, self.task_name)


class ChannelPanel(QtWidgets.QWidget):
    """
    通道面板组件

    用于显示通道视频流和控制按钮
    使用Qt渲染模式
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
    panelClicked = QtCore.Signal(str)

    def __init__(self, title="通道", parent=None, debug_mode=False, width=None, height=None):
        super(ChannelPanel, self).__init__(parent)
        self._parent = parent
        self._title = title
        self._channels = {}
        self._current_channel_id = None
        self._debug_mode = debug_mode
        self._is_disabled = False
        self._channel_number = title.replace("通道", "")
        self._is_connected = False
        self._custom_width = width
        self._custom_height = height

        # 初始化 logger
        self.logger = logging.getLogger(f"ChannelPanel.{title}")

        self.setObjectName("ChannelPanel")

        # 按钮叠加层引用
        self._buttonOverlay = None

        self._initUI()
        self._ensureButtonOverlay()
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

        # 兼容性：创建隐藏的标签属性
        self.taskLabel = QtWidgets.QLabel()
        self.taskLabel.hide()
        self.nameLabel = QtWidgets.QLabel()
        self.nameLabel.hide()
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

        # 按钮引用（将在_ensureButtonOverlay中设置）
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

    def _ensureButtonOverlay(self):
        """确保 ButtonOverlay 已创建"""
        if self._buttonOverlay is None:
            self._buttonOverlay = ButtonOverlay(self.videoWidget)
            # 保留按钮引用
            self.btnToggleConnect = self._buttonOverlay.btnToggleConnect
            self.btnEdit = self._buttonOverlay.btnEdit
            self.btnCurve = self._buttonOverlay.btnCurve
            self.btnAmplify = self._buttonOverlay.btnAmplify
            # 初始化位置
            self._buttonOverlay.setGeometry(0, self.videoWidget.height() - 45, self.videoWidget.width(), 45)
            self._buttonOverlay.show()

    # ==================== 显示控制API ====================

    def updateOverlayInfo(self, channel_name=None, task_name=None, fps=None, resolution=None):
        """更新信息显示"""
        self.videoWidget.update_info(channel_name, task_name, fps, resolution)

    def updateLiquidLines(self, liquid_positions, is_new_data=True, video_width=0, video_height=0):
        """更新液位线数据"""
        self.videoWidget.update_liquid_lines(liquid_positions, is_new_data, video_width, video_height)

    def clearLiquidLines(self):
        """清空液位线数据"""
        self.videoWidget.clear_liquid_lines()

    def loadROIConfig(self, channel_id):
        """加载ROI配置

        Args:
            channel_id: 通道ID，如 "channel1"
        """
        self.videoWidget.load_roi_config(channel_id)

    def setShowROI(self, show):
        """设置是否显示ROI

        Args:
            show: True显示，False隐藏
        """
        self.videoWidget.set_show_roi(show)

    def showOverlay(self):
        """显示叠加层（兼容性方法）"""
        pass

    def hideOverlay(self):
        """隐藏叠加层（兼容性方法）"""
        pass

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

    def displayFrame(self, frame):
        """显示视频帧

        Args:
            frame: QPixmap或numpy数组
        """
        try:
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

                return

            # 如果是numpy数组，转换为QPixmap
            if hasattr(frame, 'shape'):
                import cv2

                height, width, channel = frame.shape
                bytes_per_line = 3 * width

                # BGR转RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame = np.ascontiguousarray(rgb_frame)

                # 转换为QImage
                q_image = QtGui.QImage(
                    rgb_frame.data,
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
        self._overlayLabel.clear()
        self._overlayLabel.setText("未打开通道")
        self._overlayLabel.setGeometry(0, 0, self.videoWidget.width(), self.videoWidget.height())
        self._overlayLabel.show()

    def setChannelName(self, name):
        """设置通道名称"""
        self.videoWidget.update_info(channel_name=name)

    def getChannelName(self):
        """获取通道名称"""
        return self.videoWidget.channel_name or self._title

    def setTaskInfo(self, task_folder_name):
        """设置任务信息"""
        if task_folder_name and task_folder_name.strip() and task_folder_name.lower() != "none":
            self.videoWidget.update_info(task_name=task_folder_name.strip())
            self._setDisabled(False)
        else:
            self.videoWidget.update_info(task_name="未分配任务")
            self._setDisabled(True)

    def clearTaskInfo(self):
        """清空任务信息"""
        self.videoWidget.update_info(task_name="未分配任务")
        self._setDisabled(True)

    def getTaskInfo(self):
        """获取任务信息"""
        task = self.videoWidget.task_name
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
            self.setConnected(False)
            self.channelDisconnected.emit(channel_id)
        else:
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
        if self._is_connected:
            channel_id, _ = self.getCurrentChannel()
            if channel_id:
                self.panelClicked.emit(channel_id)

    def resizeEvent(self, event):
        """窗口大小改变"""
        super(ChannelPanel, self).resizeEvent(event)
        if hasattr(self, '_overlayLabel'):
            self._overlayLabel.setGeometry(0, 0, self.videoWidget.width(), self.videoWidget.height())

    def showEvent(self, event):
        """窗口显示"""
        super(ChannelPanel, self).showEvent(event)
        if self._buttonOverlay:
            self._buttonOverlay.show()

    def hideEvent(self, event):
        """窗口隐藏"""
        super(ChannelPanel, self).hideEvent(event)
        if self._buttonOverlay:
            self._buttonOverlay.hide()

    def closeEvent(self, event):
        """窗口关闭"""
        if self._buttonOverlay:
            self._buttonOverlay.close()
        super(ChannelPanel, self).closeEvent(event)
