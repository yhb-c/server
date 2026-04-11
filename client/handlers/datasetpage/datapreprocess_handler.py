# -*- coding: utf-8 -*-

"""
数据预处理处理器

功能：
1. 在视频预览区域画框选择裁剪区域
2. 弹出裁剪配置对话框
3. 根据配置执行视频帧裁剪和保存
"""

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt, Signal, QTimer
import os
import os.path as osp
import sys
import cv2
import numpy as np

try:
    from widgets.style_manager import DialogManager
except ImportError as e:
    DialogManager = None

try:
    from client.config import get_project_root
except Exception:
    def get_project_root():
        return osp.abspath(osp.join(osp.dirname(__file__), '..', '..'))


DEFAULT_CROP_SAVE_DIR = osp.join(get_project_root(), 'database', 'Corp_picture')
os.makedirs(DEFAULT_CROP_SAVE_DIR, exist_ok=True)




class DrawableLabel(QtWidgets.QLabel):
    """
    可绘制矩形框的Label组件
    
    用于在视频预览区域绘制裁剪区域
    支持最多3个裁剪区域
    """
    
    # 信号：矩形绘制完成 (矩形索引, x, y, width, height)
    rectangleDrawn = Signal(int, int, int, int, int)
    # 信号：按下C键确认裁剪
    cropConfirmed = Signal()
    # 信号：按下R键重置
    resetRequested = Signal()
    # 信号：矩形被删除 (矩形索引)
    rectangleDeleted = Signal(int)
    
    MAX_RECTANGLES = 3  # 最多3个矩形
    
    def __init__(self, parent=None):
        super(DrawableLabel, self).__init__(parent)
        
        # 绘制状态
        self._drawing = False
        self._draw_enabled = False
        
        # 矩形坐标（支持多个矩形）
        self._start_point = None
        self._end_point = None
        self._rectangles = []  # 存储多个矩形 [(x, y, w, h), ...]
        
        # 原始图像和显示的pixmap
        self._original_pixmap = None
        
        # 设置鼠标追踪
        self.setMouseTracking(True)
        
        # 设置焦点策略，以便接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 启用右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._showContextMenu)
    
    def _mapToPixmap(self, pos):
        """
        将Label坐标转换为Pixmap坐标
        
        Args:
            pos: QPoint，Label上的坐标
            
        Returns:
            QPoint: Pixmap上的坐标，如果不在pixmap范围内则返回None
        """
        if not self._original_pixmap:
            return None
        
        # 获取pixmap尺寸
        pixmap_size = self._original_pixmap.size()
        
        # 获取label尺寸
        label_size = self.size()
        
        # 计算pixmap在label中的实际位置（考虑对齐方式）
        # 如果pixmap小于label，且设置了居中对齐，pixmap会在label中心
        alignment = self.alignment()
        
        # 计算偏移量
        offset_x = 0
        offset_y = 0
        
        if pixmap_size.width() < label_size.width():
            if alignment & Qt.AlignHCenter:
                offset_x = (label_size.width() - pixmap_size.width()) // 2
            elif alignment & Qt.AlignRight:
                offset_x = label_size.width() - pixmap_size.width()
        
        if pixmap_size.height() < label_size.height():
            if alignment & Qt.AlignVCenter:
                offset_y = (label_size.height() - pixmap_size.height()) // 2
            elif alignment & Qt.AlignBottom:
                offset_y = label_size.height() - pixmap_size.height()
        
        # 转换坐标
        pixmap_x = pos.x() - offset_x
        pixmap_y = pos.y() - offset_y
        
        # 检查是否在pixmap范围内
        if pixmap_x < 0 or pixmap_x >= pixmap_size.width() or \
           pixmap_y < 0 or pixmap_y >= pixmap_size.height():
            return None
        
        return QtCore.QPoint(pixmap_x, pixmap_y)
    
    def setDrawEnabled(self, enabled):
        """设置是否启用绘制"""
        if enabled:
            # 启用绘制时，如果没有 pixmap，尝试从当前显示中获取
            if not self._original_pixmap:
                current_pixmap = self.pixmap()
                if current_pixmap:
                    self._original_pixmap = current_pixmap
        
        self._draw_enabled = enabled
        if not enabled:
            self._drawing = False
            self._start_point = None
            self._end_point = None
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
    
    def isDrawEnabled(self):
        """是否启用绘制"""
        return self._draw_enabled
    
    def setPixmap(self, pixmap):
        """重写setPixmap，保存原始pixmap"""
        self._original_pixmap = pixmap
        super(DrawableLabel, self).setPixmap(pixmap)
    
    def getRectangles(self):
        """获取所有绘制的矩形"""
        return self._rectangles.copy()
    
    def getRectangleCount(self):
        """获取已绘制的矩形数量"""
        return len(self._rectangles)
    
    def clearRectangles(self):
        """清除所有矩形"""
        self._rectangles.clear()
        self._start_point = None
        self._end_point = None
        if self._original_pixmap:
            super(DrawableLabel, self).setPixmap(self._original_pixmap)
        self.update()
    
    def deleteRectangle(self, index):
        """删除指定索引的矩形"""
        if 0 <= index < len(self._rectangles):
            self._rectangles.pop(index)
            self._redrawAllRectangles()
            self.rectangleDeleted.emit(index)
    
    def _getRectangleAtPosition(self, pos):
        """
        获取鼠标位置所在的矩形索引
        
        Args:
            pos: QPoint，Label上的坐标
            
        Returns:
            int: 矩形索引，如果不在任何矩形内则返回-1
        """
        # 将Label坐标转换为Pixmap坐标
        pixmap_pos = self._mapToPixmap(pos)
        if pixmap_pos is None:
            return -1
        
        # 从后向前遍历（优先选择最后绘制的矩形）
        for i in range(len(self._rectangles) - 1, -1, -1):
            x, y, w, h = self._rectangles[i]
            if (x <= pixmap_pos.x() <= x + w and 
                y <= pixmap_pos.y() <= y + h):
                return i
        
        return -1
    
    def _showContextMenu(self, pos):
        """显示右键菜单"""
        if not self._draw_enabled:
            return
        
        # 检查点击位置是否在某个矩形内
        rect_index = self._getRectangleAtPosition(pos)
        
        if rect_index >= 0:
            # 创建右键菜单
            menu = QtWidgets.QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #dcdcdc;
                    padding: 4px;
                }
                QMenu::item {
                    background-color: transparent;
                    color: #000000;
                    padding: 6px 12px;
                }
                QMenu::item:selected {
                    background-color: #f0f0f0;
                }
            """)
            
            # 添加删除动作
            delete_action = menu.addAction(f"删除区域 {rect_index + 1}")
            delete_action.triggered.connect(lambda: self.deleteRectangle(rect_index))
            
            # 显示菜单
            menu.exec_(self.mapToGlobal(pos))
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if self._draw_enabled and event.button() == Qt.LeftButton:
            # 将鼠标坐标转换为pixmap坐标
            pixmap_pos = self._mapToPixmap(event.pos())
            if pixmap_pos is not None:
                self._drawing = True
                self._start_point = pixmap_pos
                self._end_point = pixmap_pos
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._drawing and self._draw_enabled:
            # 将鼠标坐标转换为pixmap坐标
            pixmap_pos = self._mapToPixmap(event.pos())
            if pixmap_pos is not None:
                self._end_point = pixmap_pos
                self._updateDrawing()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self._drawing and self._draw_enabled and event.button() == Qt.LeftButton:
            self._drawing = False
            # 将鼠标坐标转换为pixmap坐标
            pixmap_pos = self._mapToPixmap(event.pos())
            if pixmap_pos is not None:
                self._end_point = pixmap_pos
            
            # 计算最终矩形
            if self._start_point and self._end_point:
                x1 = min(self._start_point.x(), self._end_point.x())
                y1 = min(self._start_point.y(), self._end_point.y())
                x2 = max(self._start_point.x(), self._end_point.x())
                y2 = max(self._start_point.y(), self._end_point.y())
                
                w = x2 - x1
                h = y2 - y1
                
                # 只有矩形足够大才认为有效
                if w > 10 and h > 10:
                    # 检查是否达到最大数量
                    if len(self._rectangles) < self.MAX_RECTANGLES:
                        rect = (x1, y1, w, h)
                        self._rectangles.append(rect)
                        rect_index = len(self._rectangles) - 1
                        self.rectangleDrawn.emit(rect_index, x1, y1, w, h)
                        
                        # 清除临时绘制点，准备下一个矩形
                        self._start_point = None
                        self._end_point = None
                        
                        # 重新绘制所有矩形
                        self._redrawAllRectangles()
                    else:
                        # 已达到最大数量，清除临时点
                        self._start_point = None
                        self._end_point = None
                        self._redrawAllRectangles()
                else:
                    # 矩形太小，清除临时点
                    self._start_point = None
                    self._end_point = None
                    self._redrawAllRectangles()
            else:
                # 没有有效的起点或终点，清除
                self._start_point = None
                self._end_point = None
                self._redrawAllRectangles()
    
    def _updateDrawing(self):
        """更新绘制（绘制已有矩形和正在绘制的矩形）"""
        if not self._original_pixmap:
            return
        
        # 复制原始pixmap
        pixmap = self._original_pixmap.copy()
        
        # 在pixmap上绘制矩形
        painter = QtGui.QPainter(pixmap)
        
        # 定义不同颜色用于区分不同的矩形
        colors = [
            QtGui.QColor(0, 255, 0),      # 绿色 - 第一个矩形
            QtGui.QColor(255, 165, 0),    # 橙色 - 第二个矩形
            QtGui.QColor(255, 0, 255),    # 紫色 - 第三个矩形
        ]
        
        # 绘制已保存的矩形
        for i, (x, y, w, h) in enumerate(self._rectangles):
            color = colors[i % len(colors)]
            pen = QtGui.QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)
            brush = QtGui.QBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 30))
            painter.setBrush(brush)
            
            rect = QtCore.QRect(x, y, w, h)
            painter.drawRect(rect)
            
            # 绘制矩形编号
            painter.setPen(QtGui.QPen(color, 1, Qt.SolidLine))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x + 5, y + 20, f"区域 {i + 1}")
        
        # 绘制正在绘制的临时矩形
        if self._start_point and self._end_point:
            # 使用下一个颜色
            next_index = len(self._rectangles)
            if next_index < self.MAX_RECTANGLES:
                color = colors[next_index % len(colors)]
                pen = QtGui.QPen(color, 2, Qt.DashLine)  # 虚线表示临时矩形
                painter.setPen(pen)
                brush = QtGui.QBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 20))
                painter.setBrush(brush)
                
                x1 = min(self._start_point.x(), self._end_point.x())
                y1 = min(self._start_point.y(), self._end_point.y())
                x2 = max(self._start_point.x(), self._end_point.x())
                y2 = max(self._start_point.y(), self._end_point.y())
                
                rect = QtCore.QRect(x1, y1, x2 - x1, y2 - y1)
                painter.drawRect(rect)
        
        painter.end()
        
        # 显示
        super(DrawableLabel, self).setPixmap(pixmap)
    
    def _redrawAllRectangles(self):
        """重新绘制所有已保存的矩形"""
        if not self._original_pixmap:
            return
        
        # 复制原始pixmap
        pixmap = self._original_pixmap.copy()
        
        if len(self._rectangles) == 0:
            # 没有矩形，直接显示原图
            super(DrawableLabel, self).setPixmap(pixmap)
            return
        
        # 在pixmap上绘制矩形
        painter = QtGui.QPainter(pixmap)
        
        # 定义不同颜色用于区分不同的矩形
        colors = [
            QtGui.QColor(0, 255, 0),      # 绿色 - 第一个矩形
            QtGui.QColor(255, 165, 0),    # 橙色 - 第二个矩形
            QtGui.QColor(255, 0, 255),    # 紫色 - 第三个矩形
        ]
        
        # 绘制所有已保存的矩形
        for i, (x, y, w, h) in enumerate(self._rectangles):
            color = colors[i % len(colors)]
            pen = QtGui.QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)
            brush = QtGui.QBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 30))
            painter.setBrush(brush)
            
            rect = QtCore.QRect(x, y, w, h)
            painter.drawRect(rect)
            
            # 绘制矩形编号
            painter.setPen(QtGui.QPen(color, 1, Qt.SolidLine))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x + 5, y + 20, f"区域 {i + 1}")
        
        painter.end()
        
        # 显示
        super(DrawableLabel, self).setPixmap(pixmap)
    
    def enterEvent(self, event):
        """鼠标进入事件 - 自动启用绘制模式"""
        # 只有在有pixmap的情况下才自动启用绘制
        if self._original_pixmap or self.pixmap():
            if not self._draw_enabled:
                self.setDrawEnabled(True)
                # 设置焦点以便接收键盘事件
                self.setFocus()
        super(DrawableLabel, self).enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件 - 可选择性禁用绘制模式"""
        # 注释掉自动禁用，让用户可以继续操作
        # if self._draw_enabled and not self._drawing:
        #     self.setDrawEnabled(False)
        super(DrawableLabel, self).leaveEvent(event)
    
    def keyPressEvent(self, event):
        """键盘按下事件"""
        if self._draw_enabled:
            # 按下C键确认裁剪 - 已禁用
            # if event.key() == Qt.Key_C:
            #     if len(self._rectangles) > 0:
            #         self.cropConfirmed.emit()
            # 按下R键重置所有矩形
            if event.key() == Qt.Key_R:
                self.clearRectangles()
                self.resetRequested.emit()
        
        super(DrawableLabel, self).keyPressEvent(event)


class VideoControlBar(QtWidgets.QWidget):
    """
    视频控制栏组件
    
    覆盖在视频预览区域底部，包含进度条和播放控制按钮
    """
    
    # 信号
    playPauseClicked = Signal(bool)  # 播放/暂停状态切换
    sliderMoved = Signal(int)        # 进度条拖动
    timeRangeChanged = Signal(int, int)  # 时间段选择变化 (起始帧, 结束帧)
    timeRangeEnabled = Signal(bool)  # 时间段选择模式启用/禁用
    
    def __init__(self, parent=None):
        super(VideoControlBar, self).__init__(parent)
        
        self._is_playing = False
        self._total_frames = 0
        self._current_frame = 0
        self._fps = 25.0
        
        # 时间段选择相关
        self._time_range_mode = False  # 是否启用时间段选择模式
        self._start_frame = 0  # 选择的起始帧
        self._end_frame = 0    # 选择的结束帧
        
        self._initUI()
    
    def _initUI(self):
        """初始化UI"""
        # 设置半透明背景
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # 设置控制栏样式 - 移除边框
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        
        # 主布局 - 左右边距为0，使视频帧宽度与容器一致
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 3, 0, 5)
        main_layout.setSpacing(5)
        
        # 进度条容器（完全透明背景）
        progress_container = QtWidgets.QWidget()
        progress_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
        """)
        progress_layout = QtWidgets.QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(10, 6, 10, 6)
        progress_layout.setSpacing(6)
        
        # 进度条组合容器（用于叠加多个滑块）
        slider_container = QtWidgets.QWidget()
        slider_container.setFixedHeight(20)
        slider_container.setStyleSheet("background: transparent;")
        
        # 时间段高亮显示（覆盖在进度条上）
        self.time_range_highlight = QtWidgets.QLabel(slider_container)
        self.time_range_highlight.setVisible(False)
        self.time_range_highlight.setStyleSheet("""
            QLabel {
                background: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(76, 175, 80, 0.5);
                border-radius: 2px;
            }
        """)
        # 重要：让高亮标签不接受鼠标事件，使鼠标事件可以穿透到下层的滑块
        self.time_range_highlight.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        # 主进度条 - 白色样式，更细
        self.slider = QtWidgets.QSlider(Qt.Horizontal, slider_container)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid rgba(255, 255, 255, 0.8);
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(255, 255, 255, 0.9);
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
        """)
        self.slider.sliderMoved.connect(self._onSliderMoved)
        
        # 起始帧标记滑块 - 绿色
        self.start_marker = QtWidgets.QSlider(Qt.Horizontal, slider_container)
        self.start_marker.setMinimum(0)
        self.start_marker.setMaximum(0)
        self.start_marker.setValue(0)
        self.start_marker.setVisible(False)  # 初始隐藏
        self.start_marker.setMouseTracking(True)  # 启用鼠标追踪
        self.start_marker.setEnabled(True)  # 确保启用
        self.start_marker.setFocusPolicy(Qt.StrongFocus)  # 可获取焦点
        self.start_marker.setStyleSheet("""
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: transparent;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                border: 2px solid white;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #66BB6A;
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border-radius: 9px;
            }
        """)
        self.start_marker.valueChanged.connect(self._onStartMarkerChanged)
        self.start_marker.sliderMoved.connect(lambda: self._onMarkerPressed('start'))
        
        # 安装事件过滤器，用于智能处理鼠标事件
        self.start_marker.installEventFilter(self)
        
        # 结束帧标记滑块 - 红色
        self.end_marker = QtWidgets.QSlider(Qt.Horizontal, slider_container)
        self.end_marker.setMinimum(0)
        self.end_marker.setMaximum(0)
        self.end_marker.setValue(0)
        self.end_marker.setVisible(False)  # 初始隐藏
        self.end_marker.setMouseTracking(True)  # 启用鼠标追踪
        self.end_marker.setEnabled(True)  # 确保启用
        self.end_marker.setFocusPolicy(Qt.StrongFocus)  # 可获取焦点
        self.end_marker.setStyleSheet("""
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: transparent;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #F44336;
                border: 2px solid white;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #EF5350;
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border-radius: 9px;
            }
        """)
        self.end_marker.valueChanged.connect(self._onEndMarkerChanged)
        self.end_marker.sliderMoved.connect(lambda: self._onMarkerPressed('end'))
        
        # 安装事件过滤器，用于智能处理鼠标事件
        self.end_marker.installEventFilter(self)
        
        # 设置初始的控件层级顺序（z-order）
        # 从下到上：高亮标签 -> 主进度条 -> 标记滑块
        self.time_range_highlight.lower()  # 最底层
        self.slider.raise_()  # 提升主进度条
        self.start_marker.raise_()  # 提升起始标记到最上层
        self.end_marker.raise_()  # 提升结束标记到最上层
        
        # 调整滑块容器大小
        def resize_sliders():
            width = slider_container.width()
            for slider in [self.slider, self.start_marker, self.end_marker]:
                slider.setGeometry(0, 0, width, 20)
            # 更新时间段高亮位置
            self._updateTimeRangeHighlight()
        
        slider_container.resizeEvent = lambda e: resize_sliders()
        
        # 保存slider_container引用，用于后续计算高亮位置
        self._slider_container = slider_container
        
        progress_layout.addWidget(slider_container)
        
        # 控制按钮和时间显示行
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(0)  # 设置为0，通过margin精确控制
        controls_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 左对齐，垂直居中
        
        # 播放/暂停按钮 - 使用图片图标
        self.btn_play_pause = QtWidgets.QPushButton()
        self.btn_play_pause.setFixedSize(36, 36)  # 调整为方形按钮
        self.btn_play_pause.setFlat(True)  # 设置为扁平按钮，移除所有默认边框
        self.btn_play_pause.setFocusPolicy(Qt.NoFocus)  # 禁用焦点，避免蓝色边框
        self.btn_play_pause.setAttribute(Qt.WA_TranslucentBackground, True)  # 设置透明背景属性
        self.btn_play_pause.setIconSize(QtCore.QSize(28, 28))  # 设置图标大小
        self._updatePlayPauseIcon()
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background: none;
                background-color: rgba(0, 0, 0, 0);
                border: none;
                border-radius: 0px;
                padding: 0px;
                margin-left: 10px;     /* 左侧间距 */
                margin-right: 5px;     /* 右侧间距 */
                margin-top: 0px;       /* 上方间距 */
                margin-bottom: 10px;   /* 下方间距 */
                outline: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """)
        self.btn_play_pause.clicked.connect(self._onPlayPauseClicked)
        controls_layout.addWidget(self.btn_play_pause, 0, Qt.AlignVCenter)
        
        # 时间显示 - 紧贴播放按钮
        self.lbl_time = QtWidgets.QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10pt;
                font-weight: normal;
                background: transparent;
                padding-left: 5px;
                line-height: 1.0;
            }
        """)
        controls_layout.addWidget(self.lbl_time, 0, Qt.AlignVCenter)
        
        controls_layout.addStretch()
        
        # 时间段选择按钮
        self.btn_time_range = QtWidgets.QPushButton("时间段")
        self.btn_time_range.setFixedSize(60, 28)
        self.btn_time_range.setCheckable(True)  # 可切换状态
        self.btn_time_range.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 4px;
                font-size: 9pt;
                padding: 2px;
                margin-right: 10px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
            QPushButton:checked {
                background: rgba(76, 175, 80, 0.6);
                border: 1px solid rgba(76, 175, 80, 0.8);
                font-weight: bold;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.35);
            }
        """)
        self.btn_time_range.clicked.connect(self._onTimeRangeButtonClicked)
        controls_layout.addWidget(self.btn_time_range, 0, Qt.AlignVCenter)
        
        # 时间段范围显示标签（初始隐藏）
        self.lbl_time_range = QtWidgets.QLabel("")
        self.lbl_time_range.setVisible(False)
        self.lbl_time_range.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 9pt;
                font-weight: bold;
                background: transparent;
                padding-left: 10px;
                padding-right: 5px;
            }
        """)
        controls_layout.addWidget(self.lbl_time_range, 0, Qt.AlignVCenter)
        
        # 帧数显示 - 隐藏不使用
        self.lbl_frame = QtWidgets.QLabel("")
        self.lbl_frame.setVisible(False)
        
        progress_layout.addLayout(controls_layout)
        
        main_layout.addStretch()
        main_layout.addWidget(progress_container)
    
    def _updatePlayPauseIcon(self):
        """更新播放/暂停按钮图标"""
        # 获取图标路径
        icons_dir = osp.join(osp.dirname(osp.dirname(osp.dirname(__file__))), 'resources', 'icons')
        
        if self._is_playing:
            # 暂停图标
            icon_path = osp.join(icons_dir, '停止.png')
        else:
            # 播放图标
            icon_path = osp.join(icons_dir, '开始 (1).png')
        
        # 设置图标
        if osp.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
            self.btn_play_pause.setIcon(icon)
        else:
            # 如果图标文件不存在，回退到文字显示
            self.btn_play_pause.setText("暂停" if self._is_playing else "播放")
    
    def _onPlayPauseClicked(self):
        """播放/暂停按钮点击"""
        self._is_playing = not self._is_playing
        self._updatePlayPauseIcon()
        self.playPauseClicked.emit(self._is_playing)
    
    def _onSliderMoved(self, value):
        """进度条拖动"""
        self._current_frame = value
        self._updateTimeDisplay()
        self.sliderMoved.emit(value)
    
    def _updateTimeDisplay(self):
        """更新时间显示"""
        if self._fps > 0:
            current_seconds = self._current_frame / self._fps
            total_seconds = self._total_frames / self._fps
            
            current_time = self._formatTime(current_seconds)
            total_time = self._formatTime(total_seconds)
            
            self.lbl_time.setText(f"{current_time} / {total_time}")
            # 帧数显示已隐藏
            # self.lbl_frame.setText(f"帧: {self._current_frame}/{self._total_frames}")
    
    def _formatTime(self, seconds):
        """格式化时间显示"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def setTotalFrames(self, total_frames):
        """设置总帧数"""
        self._total_frames = total_frames
        max_value = max(0, total_frames - 1)
        self.slider.setMaximum(max_value)
        
        # 同时设置标记滑块的最大值
        self.start_marker.setMaximum(max_value)
        self.end_marker.setMaximum(max_value)
        
        # 如果处于时间段模式，更新结束帧
        if self._time_range_mode:
            self._end_frame = max_value
            self.end_marker.blockSignals(True)
            self.end_marker.setValue(self._end_frame)
            self.end_marker.blockSignals(False)
            self._updateTimeRangeDisplay()
        
        self._updateTimeDisplay()
    
    def setCurrentFrame(self, frame):
        """设置当前帧"""
        self._current_frame = frame
        self.slider.blockSignals(True)
        self.slider.setValue(frame)
        self.slider.blockSignals(False)
        self._updateTimeDisplay()
    
    def setFPS(self, fps):
        """设置帧率"""
        self._fps = fps if fps > 0 else 25.0
        self._updateTimeDisplay()
    
    def setPlaying(self, is_playing):
        """设置播放状态"""
        self._is_playing = is_playing
        self._updatePlayPauseIcon()
    
    def isPlaying(self):
        """获取播放状态"""
        return self._is_playing
    
    def eventFilter(self, obj, event):
        """
        事件过滤器：智能处理标记滑块的鼠标事件
        
        当用户点击时，判断点击位置更接近哪个标记的handle，
        然后将该标记提升到最上层，使其可以被拖动，并阻止另一个标记响应该事件
        """
        # 只处理标记滑块的鼠标按下事件
        if (obj == self.start_marker or obj == self.end_marker) and \
           event.type() == QtCore.QEvent.MouseButtonPress and \
           self._time_range_mode:
            
            # 获取点击位置（相对于滑块的x坐标）
            click_x = event.pos().x()
            slider_width = obj.width()
            
            # 计算点击位置对应的帧值
            if slider_width > 0 and self._total_frames > 0:
                click_ratio = click_x / slider_width
                click_frame = int(click_ratio * (self._total_frames - 1))
                
                # 计算两个标记handle在屏幕上的像素位置
                start_ratio = self._start_frame / max(1, self._total_frames - 1)
                end_ratio = self._end_frame / max(1, self._total_frames - 1)
                
                start_pixel = start_ratio * slider_width
                end_pixel = end_ratio * slider_width
                
                # 计算点击位置到两个handle中心的像素距离
                dist_to_start_pixel = abs(click_x - start_pixel)
                dist_to_end_pixel = abs(click_x - end_pixel)
                
                # 根据像素距离决定应该由哪个标记处理事件
                if dist_to_start_pixel <= dist_to_end_pixel:
                    # 更接近起始标记的handle，应该由绿色标记处理
                    if obj == self.start_marker:
                        # 当前对象是绿色标记，提升它并允许它处理事件
                        self.start_marker.raise_()
                        return super(VideoControlBar, self).eventFilter(obj, event)
                    else:
                        # 当前对象是红色标记，但应该由绿色标记处理
                        # 阻止红色标记处理该事件
                        self.start_marker.raise_()
                        return True  # 阻止事件继续传播到红色标记
                else:
                    # 更接近结束标记的handle，应该由红色标记处理
                    if obj == self.end_marker:
                        # 当前对象是红色标记，提升它并允许它处理事件
                        self.end_marker.raise_()
                        return super(VideoControlBar, self).eventFilter(obj, event)
                    else:
                        # 当前对象是绿色标记，但应该由红色标记处理
                        # 阻止绿色标记处理该事件
                        self.end_marker.raise_()
                        return True  # 阻止事件继续传播到绿色标记
        
        # 继续正常的事件处理
        return super(VideoControlBar, self).eventFilter(obj, event)
    
    def _onTimeRangeButtonClicked(self):
        """时间段选择按钮点击"""
        self._time_range_mode = self.btn_time_range.isChecked()
        
        if self._time_range_mode:
            # 启用时间段选择模式
            # 初始化起始和结束帧：默认在时间轴两端
            total_frames = max(1, self._total_frames - 1)
            
            # 绿点在最左端（起始），红点在最右端（结束）
            self._start_frame = 0
            self._end_frame = total_frames
            
            # 设置标记滑块的值
            # 重要：先设置值，再显示控件
            self.start_marker.blockSignals(True)
            self.end_marker.blockSignals(True)
            self.start_marker.setValue(self._start_frame)
            self.end_marker.setValue(self._end_frame)
            self.start_marker.blockSignals(False)
            self.end_marker.blockSignals(False)
            
            # 显示所有相关控件
            self.time_range_highlight.setVisible(True)
            self.start_marker.setVisible(True)
            self.end_marker.setVisible(True)
            self.lbl_time_range.setVisible(True)
            
            # 关键修复：禁用主进度条的鼠标交互，让标记滑块可以接收事件
            self.slider.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            
            # 设置标记滑块的层级顺序
            # 因为绿点在左端、红点在右端，它们不会重叠
            # 但我们需要确保两个标记都在主进度条之上
            self.time_range_highlight.lower()  # 高亮在最底层
            self.slider.lower()  # 主进度条也在底层
            self.start_marker.raise_()  # 提升绿色标记
            self.end_marker.raise_()    # 提升红色标记
            
            self._updateTimeRangeDisplay()
            self._updateTimeRangeHighlight()
            
            # 发射信号
            self.timeRangeEnabled.emit(True)
            self.timeRangeChanged.emit(self._start_frame, self._end_frame)
        else:
            # 禁用时间段选择模式
            # 隐藏标记滑块
            self.start_marker.setVisible(False)
            self.end_marker.setVisible(False)
            
            # 隐藏时间范围标签和高亮
            self.lbl_time_range.setVisible(False)
            self.time_range_highlight.setVisible(False)
            
            # 重新启用主进度条的鼠标交互
            self.slider.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
            # 发射信号
            self.timeRangeEnabled.emit(False)
    
    def _onStartMarkerChanged(self, value):
        """起始标记变化"""
        
        # 确保起始帧不超过结束帧
        if value > self._end_frame:
            value = self._end_frame
            self.start_marker.blockSignals(True)
            self.start_marker.setValue(value)
            self.start_marker.blockSignals(False)
        
        self._start_frame = value
        self._updateTimeRangeDisplay()
        self._updateTimeRangeHighlight()
        
        # 发射信号
        self.timeRangeChanged.emit(self._start_frame, self._end_frame)
    
    def _onEndMarkerChanged(self, value):
        """结束标记变化"""
        
        # 确保结束帧不小于起始帧
        if value < self._start_frame:
            value = self._start_frame
            self.end_marker.blockSignals(True)
            self.end_marker.setValue(value)
            self.end_marker.blockSignals(False)
        
        self._end_frame = value
        self._updateTimeRangeDisplay()
        self._updateTimeRangeHighlight()
        
        # 发射信号
        self.timeRangeChanged.emit(self._start_frame, self._end_frame)
    
    def _updateTimeRangeDisplay(self):
        """更新时间范围显示"""
        if self._fps > 0:
            start_seconds = self._start_frame / self._fps
            end_seconds = self._end_frame / self._fps
            
            start_time = self._formatTime(start_seconds)
            end_time = self._formatTime(end_seconds)
            
            duration_seconds = end_seconds - start_seconds
            duration_time = self._formatTime(duration_seconds)
            
            self.lbl_time_range.setText(f"范围: {start_time} - {end_time} (时长: {duration_time})")
    
    def _updateTimeRangeHighlight(self):
        """更新时间段高亮显示"""
        if not self._time_range_mode or self._total_frames <= 0:
            return
        
        # 获取滑块容器的宽度
        container_width = self._slider_container.width()
        
        if container_width <= 0:
            return
        
        # 计算起始和结束位置（像素）
        # QSlider 的 handle 位置计算需要考虑 handle 的宽度
        start_ratio = self._start_frame / max(1, self._total_frames - 1)
        end_ratio = self._end_frame / max(1, self._total_frames - 1)
        
        # 计算实际的像素位置
        start_x = int(start_ratio * container_width)
        end_x = int(end_ratio * container_width)
        
        # 设置高亮区域的位置和大小
        width = max(1, end_x - start_x)
        
        # 高亮区域覆盖整个进度条高度
        self.time_range_highlight.setGeometry(start_x, 0, width, 20)
    
    def _onMarkerPressed(self, marker_type):
        """
        标记被按下/拖动时的处理
        
        Args:
            marker_type: 'start' 或 'end'
        """
        # 当用户拖动某个标记时，将该标记提升到最上层
        # 这样确保正在拖动的标记始终可见且可操作
        if marker_type == 'start':
            self.start_marker.raise_()
        else:
            self.end_marker.raise_()
        
        # 更新高亮显示
        self._updateTimeRangeHighlight()
    
    def _adjustMarkerZOrder(self):
        """
        动态调整标记的z-order（已废弃，保留用于兼容性）
        
        现在使用 _onMarkerPressed 来实现更智能的交互：
        哪个标记被点击，哪个就在最上层
        """
        pass  # 不再需要自动调整，由用户点击来决定
    
    def setTimeRangeMode(self, enabled):
        """设置时间段选择模式"""
        self.btn_time_range.setChecked(enabled)
        self._onTimeRangeButtonClicked()
    
    def isTimeRangeMode(self):
        """是否处于时间段选择模式"""
        return self._time_range_mode
    
    def getTimeRange(self):
        """获取选择的时间范围 (起始帧, 结束帧)"""
        return (self._start_frame, self._end_frame)
    
    def setTimeRange(self, start_frame, end_frame):
        """设置时间范围"""
        # 验证范围
        start_frame = max(0, min(start_frame, self._total_frames - 1))
        end_frame = max(start_frame, min(end_frame, self._total_frames - 1))
        
        self._start_frame = start_frame
        self._end_frame = end_frame
        
        # 更新滑块
        self.start_marker.blockSignals(True)
        self.end_marker.blockSignals(True)
        self.start_marker.setValue(start_frame)
        self.end_marker.setValue(end_frame)
        self.start_marker.blockSignals(False)
        self.end_marker.blockSignals(False)
        
        # 更新显示
        self._updateTimeRangeDisplay()
        self._updateTimeRangeHighlight()
        
        # 发射信号
        self.timeRangeChanged.emit(self._start_frame, self._end_frame)


class VideoPreviewWithControls(QtWidgets.QWidget):
    """
    带控制栏的视频预览组件
    
    将DrawableLabel和VideoControlBar组合在一起
    """
    
    # 信号
    playPauseClicked = Signal(bool)
    sliderMoved = Signal(int)
    
    def __init__(self, parent=None):
        super(VideoPreviewWithControls, self).__init__(parent)
        
        # 创建DrawableLabel
        self.video_label = DrawableLabel(self)
        
        # 创建控制栏
        self.control_bar = VideoControlBar(self)
        
        # 设置布局（使用StackedLayout让控制栏覆盖在视频上）
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加video_label
        layout.addWidget(self.video_label)
        
        # 将控制栏覆盖在底部
        self.control_bar.raise_()
        
        # 连接信号
        self.control_bar.playPauseClicked.connect(self.playPauseClicked)
        self.control_bar.sliderMoved.connect(self.sliderMoved)
    
    def resizeEvent(self, event):
        """窗口大小改变时，调整控制栏位置"""
        super(VideoPreviewWithControls, self).resizeEvent(event)
        
        # 让控制栏位于底部，占据宽度，高度约70像素（更紧凑）
        control_height = 70
        self.control_bar.setGeometry(
            0,
            self.height() - control_height,
            self.width(),
            control_height
        )


class VideoGridItemDelegate(QtWidgets.QStyledItemDelegate):
    """
    自定义委托，确保列表项在被选中时也能保持自身的前景颜色。
    """

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        foreground = index.data(Qt.ForegroundRole)

        if foreground:
            brush = foreground
            if isinstance(foreground, QtGui.QColor):
                brush = QtGui.QBrush(foreground)

            for group in (
                QtGui.QPalette.Active,
                QtGui.QPalette.Inactive,
                QtGui.QPalette.Disabled,
            ):
                opt.palette.setBrush(group, QtGui.QPalette.Text, brush)
                opt.palette.setBrush(group, QtGui.QPalette.HighlightedText, brush)

        super(VideoGridItemDelegate, self).paint(painter, opt, index)


class DataPreprocessHandler(QtCore.QObject):
    """
    数据预处理处理器
    
    负责处理数据预处理面板的业务逻辑
    """
    
    # 信号
    cropStarted = Signal(dict)      # 裁剪开始
    cropProgress = Signal(int)      # 裁剪进度 (0-100)
    cropFinished = Signal(str)      # 裁剪完成 (保存路径)
    cropError = Signal(str)         # 裁剪错误
    
    def __init__(self, panel=None):
        """
        Args:
            panel: DataPreprocessPanel 实例
        """
        super(DataPreprocessHandler, self).__init__()
        
        self._panel = panel
        
        # 当前视频信息
        self._current_video_path = None
        self._current_video_capture = None
        self._video_width = 0
        self._video_height = 0
        self._video_total_frames = 0
        self._video_fps = 0
        
        # 裁剪区域 (在原始视频尺寸下的坐标)
        self._crop_rects = []  # [(x, y, w, h), ...]，支持多个裁剪区域
        
        # 裁剪状态
        self._cropping = False
        
        # 视频播放相关
        self._play_timer = None
        self._current_frame_index = 0
        
        # 裁剪预览处理器
        self._crop_preview_handler = None
        
        # 视频与裁剪图片的映射关系 {video_path: {'save_path': str, 'region_paths': [str], 'timestamp': float}}
        self._video_crop_mapping = {}
        
        # 映射关系的持久化存储文件路径
        self._mapping_file = osp.join(get_project_root(), 'database', 'video_crop_mapping.json')
        
        # 加载已保存的映射关系
        self._loadMappingFromFile()
        
        if self._panel:
            self._initPanel()
    
    def _showWarning(self, title, message):
        """显示警告对话框"""
        if DialogManager:
            DialogManager.show_warning(self._panel, title, message)
        else:
            QtWidgets.QMessageBox.warning(self._panel, title, message)
    
    def _showInformation(self, title, message):
        """显示信息对话框"""
        if DialogManager:
            DialogManager.show_information(self._panel, title, message)
        else:
            QtWidgets.QMessageBox.information(self._panel, title, message)
    
    def _showCritical(self, title, message):
        """显示错误对话框"""
        if DialogManager:
            DialogManager.show_critical(self._panel, title, message)
        else:
            QtWidgets.QMessageBox.critical(self._panel, title, message)
    
    def _showQuestion(self, title, message):
        """显示询问对话框"""
        if DialogManager:
            return DialogManager.show_question(self._panel, title, message)
        else:
            reply = QtWidgets.QMessageBox.question(
                self._panel, title, message,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            return reply == QtWidgets.QMessageBox.Yes

    def _openFolder(self, folder_path):
        """打开文件夹（跨平台支持）"""
        try:
            # Windows系统打开文件夹
            if sys.platform == 'win32':
                os.startfile(folder_path)
            # macOS系统
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.call(['open', folder_path])
            # Linux系统
            else:
                import subprocess
                subprocess.call(['xdg-open', folder_path])
        except Exception as open_err:
            self._showWarning("提示", 
                f"无法自动打开文件夹，请手动打开：\n{folder_path}"
            )

    def _initPanel(self):
        """初始化面板"""
        # 设置面板的handler引用
        if hasattr(self._panel, '_handler'):
            self._panel._handler = self

        
        # 替换普通Label为可绘制Label
        self._replaceVideoPreviewWithDrawable()
        
        # 让视频网格在选中时保持自定义颜色
        if hasattr(self._panel, 'video_grid'):
            self._panel.video_grid.setItemDelegate(
                VideoGridItemDelegate(self._panel.video_grid)
            )

        # 初始化裁剪预览处理器
        self._initCropPreviewHandler()
        
        # 连接信号
        self._connectSignals()
    
    def _replaceVideoPreviewWithDrawable(self):
        """替换视频预览Label为带控制栏的视频预览组件"""
        try:
            # 获取原始Label的父容器和布局
            old_label = self._panel.video_preview
            
            # 检查old_label是否有效
            if old_label is None:
                return
            
            # 尝试获取父容器
            try:
                parent = old_label.parent()
                if parent is None:
                    return
            except RuntimeError:
                return
            
            # 获取布局
            layout = parent.layout()
            if layout is None:
                return
            
            # 保存原始属性
            try:
                old_size = old_label.size()
                old_alignment = old_label.alignment()
                old_stylesheet = old_label.styleSheet()
                old_text = old_label.text()
            except RuntimeError:
                old_size = QtCore.QSize(640, 480)
                old_alignment = Qt.AlignCenter
                old_stylesheet = ""
                old_text = "视频预览"
            
            # 创建新的带控制栏的视频预览组件
            new_widget = VideoPreviewWithControls(parent)
            new_widget.setFixedSize(old_size)
            
            # 配置内部的video_label
            new_widget.video_label.setAlignment(old_alignment)
            new_widget.video_label.setStyleSheet(old_stylesheet)
            new_widget.video_label.setText(old_text)
            
            # 替换布局中的控件
            index = layout.indexOf(old_label)
            if index >= 0:
                layout.removeWidget(old_label)
                layout.insertWidget(index, new_widget)
            else:
                # 如果找不到索引，直接添加
                layout.addWidget(new_widget)
            
            # 删除旧Label
            try:
                old_label.deleteLater()
            except RuntimeError:
                pass  # 已经被删除
            
            # 更新面板引用（保存整个组件）
            self._panel.video_preview_widget = new_widget
            self._panel.video_preview = new_widget.video_label  # 保持兼容性
            
            # 连接DrawableLabel的信号
            new_widget.video_label.rectangleDrawn.connect(self._onRectangleDrawn)
            new_widget.video_label.rectangleDeleted.connect(self._onRectangleDeleted)
            new_widget.video_label.cropConfirmed.connect(self._onCropConfirmed)
            new_widget.video_label.resetRequested.connect(self._onResetRequested)
            
            # 连接控制栏的信号
            new_widget.playPauseClicked.connect(self._onPlayPause)
            new_widget.sliderMoved.connect(self._onSliderMoved)
            
            # 连接时间段选择信号
            new_widget.control_bar.timeRangeEnabled.connect(self._onTimeRangeEnabled)
            new_widget.control_bar.timeRangeChanged.connect(self._onTimeRangeChanged)
            
        except Exception as e:
            pass
    
    def _initCropPreviewHandler(self):
        """初始化裁剪预览处理器（延迟初始化，避免首次卡顿）"""
        try:
            # 不在这里立即创建处理器，而是在第一次裁剪时创建
            # 这样可以避免启动时的卡顿
            
            # 连接信号：裁剪开始时启动监控（延迟创建处理器）
            self.cropStarted.connect(self._onCropStartedForPreview)
            
            # 连接信号：裁剪完成时刷新显示
            self.cropFinished.connect(self._onCropFinishedForPreview)
                
        except Exception as e:
            self._crop_preview_handler = None
    
    def _ensureCropPreviewHandler(self):
        """确保裁剪预览处理器已创建（延迟初始化）"""
        if self._crop_preview_handler is not None:
            return True
        
        try:
            # 导入裁剪预览处理器
            from .crop_preview_handler import CropPreviewHandler
            
            # 获取裁剪预览面板
            if hasattr(self._panel, 'getCropPreviewPanel'):
                crop_preview_panel = self._panel.getCropPreviewPanel()
                
                if crop_preview_panel is not None:
                    # 创建裁剪预览处理器
                    self._crop_preview_handler = CropPreviewHandler(crop_preview_panel)
                    return True
                else:
                    return False
            else:
                return False
                
        except Exception as e:
            self._crop_preview_handler = None
            return False
    
    def _loadMappingFromFile(self):
        """从文件加载视频与裁剪图片的映射关系"""
        try:
            if not osp.exists(self._mapping_file):
                return
            
            import json
            with open(self._mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证并加载映射关系
            loaded_count = 0
            for video_path, info in data.items():
                # 检查视频文件是否仍然存在
                if osp.exists(video_path):
                    self._video_crop_mapping[video_path] = info
                    loaded_count += 1
            
        except Exception as e:
            pass
    
    def _saveMappingToFile(self):
        """保存视频与裁剪图片的映射关系到文件"""
        try:
            import json
            
            # 确保目录存在
            mapping_dir = osp.dirname(self._mapping_file)
            os.makedirs(mapping_dir, exist_ok=True)
            
            # 保存映射关系
            with open(self._mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self._video_crop_mapping, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            pass
    
    def updateVideoGridStyles(self):
        """更新视频网格中所有视频的样式，标记已裁剪的视频"""
        if not hasattr(self._panel, 'video_grid'):
            return
        
        video_grid = self._panel.video_grid
        
        # 更新整体样式表，为已裁剪的视频添加绿色边框
        video_grid.setStyleSheet("""
            QListWidget {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QListWidget::item {
                border: 2px solid transparent;
                border-radius: 5px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 2px solid #0078d7;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                border: 2px solid #c0c0c0;
            }
        """)
        
        # 遍历所有视频项，为已裁剪的视频添加绿色边框
        cropped_count = 0
        removed_mappings = []  # 记录需要移除的映射
        
        for i in range(video_grid.count()):
            item = video_grid.item(i)
            if item:
                video_path = item.data(Qt.UserRole)
                
                # 检查是否有裁剪记录
                if video_path in self._video_crop_mapping:
                    # 验证裁剪图片是否实际存在
                    crop_info = self._video_crop_mapping[video_path]
                    has_images = self._checkCroppedImagesExist(crop_info)
                    
                    if has_images:
                        # 裁剪图片存在，添加绿色标识
                        item.setBackground(QtGui.QColor(230, 255, 230))  # 更淡的绿色背景
                        item.setForeground(QtGui.QColor(0, 128, 0))  # 深绿色文字
                        cropped_count += 1
                    else:
                        # 裁剪图片已被删除，移除绿色标识并记录需要删除的映射
                        item.setBackground(QtGui.QColor(255, 255, 255))  # 白色背景
                        item.setForeground(QtGui.QColor(0, 0, 0))  # 黑色文字
                        removed_mappings.append(video_path)
                else:
                    # 未裁剪，恢复默认样式
                    item.setBackground(QtGui.QColor(255, 255, 255))  # 白色背景
                    item.setForeground(QtGui.QColor(0, 0, 0))  # 黑色文字
        
        # 移除已删除图片的映射记录
        if removed_mappings:
            for video_path in removed_mappings:
                del self._video_crop_mapping[video_path]
            # 保存更新后的映射关系
            self._saveMappingToFile()
    
    def _checkCroppedImagesExist(self, crop_info):
        """
        检查裁剪图片是否实际存在
        
        Args:
            crop_info: 裁剪信息字典，包含 save_path 和 region_paths
            
        Returns:
            bool: 如果至少有一个区域文件夹存在且包含图片则返回True，否则返回False
        """
        try:
            save_path = crop_info.get('save_path')
            region_paths = crop_info.get('region_paths', [])
            
            if not save_path or not region_paths:
                return False
            
            # 支持的图片格式
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            
            # 检查每个区域文件夹
            for region_path in region_paths:
                if osp.exists(region_path) and osp.isdir(region_path):
                    # 检查文件夹中是否有图片
                    try:
                        files = os.listdir(region_path)
                        for f in files:
                            if osp.splitext(f)[1].lower() in image_extensions:
                                # 找到至少一张图片，说明裁剪图片存在
                                return True
                    except Exception as e:
                        continue
            
            # 所有区域文件夹都不存在或都没有图片
            return False
            
        except Exception as e:
            return False
    
    def _loadCroppedImagesForVideo(self, video_path):
        """加载并显示指定视频的裁剪图片"""
        try:
            # 检查该视频是否有裁剪记录
            if video_path not in self._video_crop_mapping:
                # 清空预览面板
                if self._ensureCropPreviewHandler():
                    self._crop_preview_handler.clearDisplay()
                return
            
            # 获取裁剪信息
            crop_info = self._video_crop_mapping[video_path]
            save_path = crop_info['save_path']
            region_paths = crop_info['region_paths']
            
            # 使用裁剪预览处理器加载并显示图片
            if self._ensureCropPreviewHandler():
                # 获取视频名称（不含扩展名）
                video_name = osp.splitext(osp.basename(video_path))[0]
                
                # 加载该视频的裁剪图片（不启动监控，只加载已有图片）
                self._crop_preview_handler.loadExistingImages(
                    save_path,
                    video_name=video_name
                )
                
        except Exception as e:
            pass
    
    def _onCropStartedForPreview(self, config):
        """裁剪任务开始 - 启动预览监控"""
        # 确保裁剪预览处理器已创建（延迟初始化）
        if not self._ensureCropPreviewHandler():
            return
        
        save_liquid_data_path = config.get('save_liquid_data_path')
        video_path = config.get('video_path')
        
        if save_liquid_data_path and video_path:
            # 从视频路径中提取视频名称（不含扩展名）
            video_name = osp.splitext(osp.basename(video_path))[0]
            
            # 启动新的监控（自动清空旧显示，只监控当前视频的区域文件夹）
            self._crop_preview_handler.startMonitoring(
                save_liquid_data_path, 
                clear_first=True, 
                video_name=video_name
            )
    
    def _onCropFinishedForPreview(self, save_liquid_data_path):
        """裁剪任务完成 - 刷新预览显示"""
        if self._crop_preview_handler is not None:
            # 注意：不需要手动刷新，实时监控已经在工作
            # 避免重新加载可能导致显示旧任务的图片
            pass
    
    def _connectSignals(self):
        """连接信号"""
        # 面板信号
        if hasattr(self._panel, 'videoSelected'):
            self._panel.videoSelected.connect(self._onVideoSelected)
        
        # 监听文件夹选中信号，当视频列表加载完成后更新样式
        if hasattr(self._panel, 'folderSelected'):
            self._panel.folderSelected.connect(self._onFolderSelected)
        
        # 监听视频重命名信号，更新映射关系
        if hasattr(self._panel, 'videoRenamed'):
            self._panel.videoRenamed.connect(self._onVideoRenamed)
        
        # 连接面板的cropStarted信号（从红色框区域的开始裁剪按钮触发）
        if hasattr(self._panel, 'cropStarted'):
            self._panel.cropStarted.connect(self._onPanelCropStarted)
        
        # 修改裁剪按钮的行为
        if hasattr(self._panel, 'btn_crop'):
            # 断开原有连接
            try:
                self._panel.btn_crop.clicked.disconnect()
            except:
                pass
            # 连接到新的处理函数
            self._panel.btn_crop.clicked.connect(self._onCropButtonClicked)
    
    def _onFolderSelected(self, folder_path):
        """文件夹被选中（视频列表加载完成）"""
        
        # 延迟更新样式，确保视频网格已经加载完成
        # 使用QTimer.singleShot延迟100ms执行
        QTimer.singleShot(100, self.updateVideoGridStyles)
    
    def _onVideoRenamed(self, old_path, new_path):
        """视频被重命名，更新映射关系"""
        
        # 检查旧路径是否在映射中
        if old_path in self._video_crop_mapping:
            # 获取旧的映射信息
            crop_info = self._video_crop_mapping[old_path]
            
            # 删除旧路径的映射
            del self._video_crop_mapping[old_path]
            
            # 添加新路径的映射
            self._video_crop_mapping[new_path] = crop_info
            
            # 保存到文件
            self._saveMappingToFile()
        
        # 无论是否更新了映射，都需要刷新视频网格样式
        # 因为重命名任何视频都会导致视频列表重新加载，需要重新应用样式
        # 延迟执行，等待视频列表刷新完成
        QTimer.singleShot(200, self.updateVideoGridStyles)
    
    def _onVideoSelected(self, video_path):
        """视频被选中"""
        self._current_video_path = video_path
        
        # 停止之前视频的播放
        if self._play_timer is not None and self._play_timer.isActive():
            self._play_timer.stop()
        
        # 重置播放状态
        if hasattr(self._panel, 'video_preview_widget'):
            control_bar = self._panel.video_preview_widget.control_bar
            control_bar.setPlaying(False)
        
        # 加载视频信息
        self._loadVideoInfo(video_path)
        
        # 清除之前的裁剪区域
        self._crop_rects.clear()
        if isinstance(self._panel.video_preview, DrawableLabel):
            self._panel.video_preview.clearRectangles()
            self._panel.video_preview.setDrawEnabled(False)
        
        # 禁用开始裁剪按钮
        if hasattr(self._panel, 'btn_start_crop'):
            self._panel.btn_start_crop.setEnabled(False)
        
        # 加载并显示该视频之前裁剪的图片
        self._loadCroppedImagesForVideo(video_path)
    
    def releaseVideoCapture(self):
        """释放视频文件句柄（用于重命名等操作）"""
        try:
            if self._current_video_capture is not None:
                self._current_video_capture.release()
                self._current_video_capture = None
        except Exception as e:
            pass
    
    def _loadVideoInfo(self, video_path):
        """加载视频信息"""
        try:
            # 关闭之前的视频
            if self._current_video_capture is not None:
                self._current_video_capture.release()
            
            # 打开新视频
            self._current_video_capture = cv2.VideoCapture(video_path)
            
            if self._current_video_capture.isOpened():
                self._video_width = int(self._current_video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                self._video_height = int(self._current_video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self._video_total_frames = int(self._current_video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                self._video_fps = self._current_video_capture.get(cv2.CAP_PROP_FPS)
                
                if self._video_fps <= 0:
                    self._video_fps = 25.0
                
                # 重置到第一帧
                self._current_frame_index = 0
                
                # 更新控制栏信息
                if hasattr(self._panel, 'video_preview_widget'):
                    control_bar = self._panel.video_preview_widget.control_bar
                    control_bar.setTotalFrames(self._video_total_frames)
                    control_bar.setFPS(self._video_fps)
                    control_bar.setCurrentFrame(0)
                
                # 显示第一帧
                self._showFrame(0)
            
        except Exception as e:
            self._video_width = 0
            self._video_height = 0
            self._video_total_frames = 0
            self._video_fps = 25.0
    
    def _showFrame(self, frame_index):
        """显示指定帧"""
        try:
            if self._current_video_capture is None or not self._current_video_capture.isOpened():
                return
            
            # 设置帧位置
            self._current_video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            
            # 读取帧
            ret, frame = self._current_video_capture.read()
            
            if ret:
                # 转换颜色空间 BGR -> RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 转换为QImage
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                
                # 转换为QPixmap并显示
                pixmap = QtGui.QPixmap.fromImage(q_image)
                
                # 缩放到合适大小
                if hasattr(self._panel, 'video_preview'):
                    label_size = self._panel.video_preview.size()
                    scaled_pixmap = pixmap.scaled(
                        label_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self._panel.video_preview.setPixmap(scaled_pixmap)
                
                # 更新当前帧索引
                self._current_frame_index = frame_index
                
                # 更新控制栏
                if hasattr(self._panel, 'video_preview_widget'):
                    control_bar = self._panel.video_preview_widget.control_bar
                    control_bar.setCurrentFrame(frame_index)
                    
        except Exception as e:
            pass
    
    def _onPlayPause(self, is_playing):
        """播放/暂停按钮点击"""
        if is_playing:
            # 获取播放范围
            start_frame = 0
            end_frame = self._video_total_frames - 1
            
            # 检查是否启用了时间段选择模式
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                if control_bar.isTimeRangeMode():
                    start_frame, end_frame = control_bar.getTimeRange()
            
            # 检查当前帧位置，决定从哪里开始播放
            if self._current_frame_index < start_frame or self._current_frame_index >= end_frame:
                # 当前帧不在播放范围内，从起始帧开始
                self._current_frame_index = start_frame
                self._showFrame(start_frame)
            
            # 开始播放
            if self._play_timer is None:
                self._play_timer = QTimer()
                self._play_timer.timeout.connect(self._playNextFrame)
            
            # 计算定时器间隔（毫秒）
            interval = int(1000 / self._video_fps) if self._video_fps > 0 else 40
            self._play_timer.start(interval)
        else:
            # 暂停播放
            if self._play_timer is not None:
                self._play_timer.stop()
    
    def _playNextFrame(self):
        """播放下一帧"""
        # 获取播放范围
        start_frame = 0
        end_frame = self._video_total_frames - 1
        
        # 检查是否启用了时间段选择模式
        if hasattr(self._panel, 'video_preview_widget'):
            control_bar = self._panel.video_preview_widget.control_bar
            if control_bar.isTimeRangeMode():
                start_frame, end_frame = control_bar.getTimeRange()
        
        # 检查是否到达结束帧
        if self._current_frame_index < end_frame:
            self._current_frame_index += 1
            self._showFrame(self._current_frame_index)
        else:
            # 到达结束帧
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                if control_bar.isTimeRangeMode():
                    # 时间段模式：循环播放选定的时间段
                    self._current_frame_index = start_frame
                    self._showFrame(start_frame)
                else:
                    # 普通模式：停止播放
                    if self._play_timer is not None:
                        self._play_timer.stop()
                    control_bar.setPlaying(False)
            else:
                # 没有控制栏，停止播放
                if self._play_timer is not None:
                    self._play_timer.stop()
    
    def _onSliderMoved(self, frame_index):
        """进度条拖动"""
        # 暂停播放
        if self._play_timer is not None and self._play_timer.isActive():
            self._play_timer.stop()
            
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                control_bar.setPlaying(False)
        
        # 跳转到指定帧
        self._showFrame(frame_index)
    
    def _onTimeRangeEnabled(self, enabled):
        """时间段选择模式启用/禁用"""
        if enabled:
            pass
            
            # 获取当前选择的时间范围
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                start_frame, end_frame = control_bar.getTimeRange()
                
                start_time = self._formatTimeFromFrame(start_frame)
                end_time = self._formatTimeFromFrame(end_frame)
                

                
                # 不自动跳转到起始帧，保持当前播放位置（白点不跟随绿点移动）
                # self._current_frame_index = start_frame
                # self._showFrame(start_frame)
        else:
            pass
            
            # 如果正在播放，停止播放
            if self._play_timer is not None and self._play_timer.isActive():
                self._play_timer.stop()
                if hasattr(self._panel, 'video_preview_widget'):
                    control_bar = self._panel.video_preview_widget.control_bar
                    control_bar.setPlaying(False)
    
    def _onTimeRangeChanged(self, start_frame, end_frame):
        """时间段选择变化"""
        start_time = self._formatTimeFromFrame(start_frame)
        end_time = self._formatTimeFromFrame(end_frame)
        
        duration_frames = end_frame - start_frame + 1
        duration_time = self._formatTimeFromFrame(duration_frames)
        
        # 不自动跳转，让用户自己控制播放位置（白点不跟随绿点移动）
        # if self._current_frame_index < start_frame or self._current_frame_index > end_frame:
        #     self._current_frame_index = start_frame
        #     self._showFrame(start_frame)

    
    def _formatTimeFromFrame(self, frame_count):
        """从帧数格式化时间"""
        if self._video_fps > 0:
            seconds = frame_count / self._video_fps
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        return "00:00"
    
    def _onCropButtonClicked(self):
        """裁剪按钮点击"""
        if not self._current_video_path:
            self._showWarning("警告", "请先选择要裁剪的视频")
            return
        
        # 启用绘制模式
        if isinstance(self._panel.video_preview, DrawableLabel):
            # 检查是否有视频画面
            if not self._panel.video_preview.pixmap():
                self._showWarning("警告", "视频预览尚未加载，请稍候片刻再试")
                return
            
            if self._panel.video_preview.isDrawEnabled():
                # 如果已经启用绘制模式，提示用户
                rect_count = self._panel.video_preview.getRectangleCount()
                self._showInformation("提示", 
                    f"当前已绘制 {rect_count} 个裁剪区域（最多3个）\n\n"
                    "操作说明：\n"
                    "• 继续拖拽绘制新的裁剪区域\n"
                    "• 按键盘 'C' 键确认裁剪\n"
                    "• 按键盘 'R' 键重置所有区域"
                )
            else:
                # 启用绘制模式
                self._panel.video_preview.setDrawEnabled(True)
                # 设置焦点到video_preview，以便接收键盘事件
                self._panel.video_preview.setFocus()
                
                self._showInformation("绘制裁剪区域", 
                    "请在视频预览区域用鼠标拖拽绘制裁剪区域\n\n"
                    "功能说明：\n"
                    "• 最多可绘制 3 个裁剪区域\n"
                    "• 按住鼠标左键拖拽绘制矩形\n"
                    "• 不同区域用不同颜色标识（绿色、橙色、紫色）\n"
                    "• 绘制完成后按键盘 'C' 键确认\n"
                    "• 按键盘 'R' 键可重置，重新绘制"
                )
    
    def _onRectangleDrawn(self, rect_index, x, y, w, h):
        """矩形绘制完成"""
        # 将屏幕坐标转换为视频坐标
        label = self._panel.video_preview
        
        # 获取显示的pixmap尺寸
        pixmap = label.pixmap()
        if not pixmap:
            return
        
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()
        
        # 计算缩放比例
        scale_x = self._video_width / pixmap_width
        scale_y = self._video_height / pixmap_height
        
        # 转换坐标到原始视频尺寸
        video_x = int(x * scale_x)
        video_y = int(y * scale_y)
        video_w = int(w * scale_x)
        video_h = int(h * scale_y)
        
        # 确保坐标在视频范围内
        video_x = max(0, min(video_x, self._video_width))
        video_y = max(0, min(video_y, self._video_height))
        video_w = min(video_w, self._video_width - video_x)
        video_h = min(video_h, self._video_height - video_y)
        
        # 添加到裁剪区域列表
        video_rect = (video_x, video_y, video_w, video_h)
        
        # 确保索引有效
        if rect_index == len(self._crop_rects):
            self._crop_rects.append(video_rect)
        elif rect_index < len(self._crop_rects):
            self._crop_rects[rect_index] = video_rect
        
        # 启用开始裁剪按钮
        if hasattr(self._panel, 'btn_start_crop') and len(self._crop_rects) > 0:
            self._panel.btn_start_crop.setEnabled(True)
    
    def _onCropConfirmed(self):
        """按下C键确认裁剪区域"""
        if len(self._crop_rects) > 0:
            self._showCropDialog()
        else:
            self._showWarning("警告", "请先在视频预览区域绘制裁剪区域")
    
    def _onRectangleDeleted(self, rect_index):
        """矩形被删除"""
        # 从裁剪区域列表中删除对应的区域
        if 0 <= rect_index < len(self._crop_rects):
            self._crop_rects.pop(rect_index)
        
        # 如果没有裁剪区域了，禁用开始裁剪按钮
        if len(self._crop_rects) == 0:
            if hasattr(self._panel, 'btn_start_crop'):
                self._panel.btn_start_crop.setEnabled(False)
    
    def _onResetRequested(self):
        """按下R键重置裁剪区域"""
        self._crop_rects.clear()
        
        # 禁用开始裁剪按钮
        if hasattr(self._panel, 'btn_start_crop'):
            self._panel.btn_start_crop.setEnabled(False)
        
        self._showInformation("提示", "已重置所有裁剪区域，请重新绘制")
    
    def _onPanelCropStarted(self, config):
        """面板的开始裁剪按钮被点击"""
        # 检查是否有裁剪区域
        if len(self._crop_rects) == 0:
            self._showWarning("警告", "请先在视频预览区域绘制裁剪区域")
            return
        
        # 检查是否有视频
        if not self._current_video_path:
            self._showWarning("警告", "请先选择视频")
            return
        
        # 将视频路径和裁剪区域添加到配置中
        config['video_path'] = self._current_video_path
        config['crop_rects'] = self._crop_rects.copy()
        
        # 执行裁剪
        self._executeCrop(config)
    
    def _showCropDialog(self):
        """显示裁剪配置对话框"""
        # 禁用绘制模式
        if isinstance(self._panel.video_preview, DrawableLabel):
            self._panel.video_preview.setDrawEnabled(False)
        
        # 导入对话框（使用多种导入方式确保兼容性）
        CropConfigDialog = None
        
        # 方式1: 相对导入（从 handlers.datasetpage 到 widgets.datasetpage）
        try:
            from ...widgets.datasetpage import CropConfigDialog as _CropConfigDialog
            CropConfigDialog = _CropConfigDialog
        except (ImportError, ValueError) as e:
            pass
        
        # 方式2: 绝对导入（从 detection 包导入）
        if CropConfigDialog is None:
            try:
                from widgets.datasetpage import CropConfigDialog as _CropConfigDialog
                CropConfigDialog = _CropConfigDialog
            except ImportError:
                pass
        
        # 方式3: 直接从 widgets 导入（如果 detection 在 sys.path 中）
        if CropConfigDialog is None:
            try:
                from widgets.datasetpage import CropConfigDialog as _CropConfigDialog
                CropConfigDialog = _CropConfigDialog
            except ImportError:
                pass
        
        # 如果所有方式都失败，显示错误
        if CropConfigDialog is None:
            self._showCritical("错误", 
                "无法导入 CropConfigDialog\n\n"
                "可能的原因：\n"
                "1. 缺少必要的依赖库\n"
                "2. 文件路径错误\n\n"
                "请检查项目结构和依赖"
            )
            return
        
        # 默认保存路径
        default_save_liquid_data_path = DEFAULT_CROP_SAVE_DIR
        
        # 创建并显示对话框
        dialog = CropConfigDialog(
            parent=self._panel,
            default_save_liquid_data_path=default_save_liquid_data_path,
            default_frequency=1
        )
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # 获取配置
            config = dialog.getConfig()
            
            # 添加裁剪区域信息（支持多个区域）
            config['crop_rects'] = self._crop_rects.copy()  # 使用列表
            config['video_path'] = self._current_video_path
            config['video_width'] = self._video_width
            config['video_height'] = self._video_height
            config['video_total_frames'] = self._video_total_frames
            config['video_fps'] = self._video_fps
            
            # 检查是否启用了时间段选择，显示确认对话框
            confirm_message = "即将开始裁剪视频帧。\n\n"
            
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                if control_bar.isTimeRangeMode():
                    start_frame, end_frame = control_bar.getTimeRange()
                    start_time = self._formatTimeFromFrame(start_frame)
                    end_time = self._formatTimeFromFrame(end_frame)
                    duration_frames = end_frame - start_frame + 1
                    
                    confirm_message += f"时间段裁剪模式已启用\n"
                    confirm_message += f"时间段: {start_time} - {end_time}\n"
                    confirm_message += f"帧范围: {start_frame} - {end_frame} (共{duration_frames}帧)\n\n"
                    confirm_message += "只会裁剪选定时间段的视频帧。\n\n"
                else:
                    confirm_message += "未启用时间段选择\n"
                    confirm_message += "将裁剪整个视频的所有帧。\n\n"
            
            confirm_message += "确认开始裁剪吗？"
            
            reply = self._showQuestion("确认裁剪", confirm_message)
            
            if not reply:
                # 执行裁剪
                self._executeCrop(config)
            else:
                # 用户取消
                pass
        else:
            # 用户取消配置对话框，清除裁剪区域
            self._crop_rects.clear()
            if isinstance(self._panel.video_preview, DrawableLabel):
                self._panel.video_preview.clearRectangles()
    
    def _executeCrop(self, config):
        """
        执行裁剪任务
        
        Args:
            config (dict): 裁剪配置
                - video_path: 视频路径
                - crop_rects: 裁剪区域列表 [(x, y, w, h), ...]
                - save_liquid_data_path: 保存路径
                - crop_frequency: 裁剪频率
                - file_prefix: 文件名前缀
                - image_format: 图片格式
        """
        if self._cropping:
            self._showWarning("警告", "正在执行裁剪任务，请稍候...")
            return
        
        self._cropping = True
        
        # 发射开始信号
        self.cropStarted.emit(config)
        
        # 检查是否使用时间段裁剪，并显示提示
        is_time_range_mode = False
        time_range_str = ""
        if hasattr(self._panel, 'video_preview_widget'):
            control_bar = self._panel.video_preview_widget.control_bar
            if control_bar.isTimeRangeMode():
                is_time_range_mode = True
                start_f, end_f = control_bar.getTimeRange()
                start_t = self._formatTimeFromFrame(start_f)
                end_t = self._formatTimeFromFrame(end_f)
                time_range_str = f" (时间段: {start_t} - {end_t})"
        
        # 🔥 使用全局DialogManager创建进度对话框
        progress_title = "裁剪进度" + time_range_str
        progress_label = "正在裁剪视频帧" + time_range_str + "..."
        progress_dialog = DialogManager.create_progress_dialog(
            parent=self._panel,
            title=progress_title,
            label_text=progress_label,
            icon_name="裁剪",  # 使用icons目录中的"裁剪"图标
            cancelable=True
        )
        
        try:
            # 提取配置
            video_path = config['video_path']
            crop_rects = config['crop_rects']  # 现在是列表
            save_liquid_data_path = config['save_liquid_data_path']
            crop_frequency = config['crop_frequency']
            file_prefix = config['file_prefix']
            image_format = config['image_format']
            
            # 验证裁剪区域
            if not crop_rects or len(crop_rects) == 0:
                raise Exception("没有裁剪区域，请先绘制裁剪区域")
            
            # 验证保存路径
            if not save_liquid_data_path or not save_liquid_data_path.strip():
                raise Exception("保存路径为空，请指定有效的保存路径")
            
            # 转换为绝对路径
            save_liquid_data_path = osp.abspath(save_liquid_data_path)
            
            # 输出保存路径信息（帮助用户定位图片位置）

            
            # 打开视频（设置参数以提高容错性）
            cap = cv2.VideoCapture(video_path)
            
            # 设置视频读取参数，提高对损坏帧的容错性
            # CAP_PROP_BUFFERSIZE: 减小缓冲区大小，加快错误恢复
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except:
                pass
            
            if not cap.isOpened():
                raise Exception("无法打开视频文件")
            

            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 检查是否启用了时间段选择
            start_frame_limit = 0
            end_frame_limit = total_frames - 1
            
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                if control_bar.isTimeRangeMode():
                    start_frame_limit, end_frame_limit = control_bar.getTimeRange()

                    
                    # 跳转到起始帧
                    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame_limit)
            
            # 获取视频文件名（不含扩展名）
            video_name = osp.splitext(osp.basename(video_path))[0]
            
            # 为每个裁剪区域创建子目录（使用"视频名_区域X"的中文形式）
            region_paths = []

            for i in range(len(crop_rects)):
                region_folder_name = f"{video_name}_区域{i+1}"
                region_path = osp.join(save_liquid_data_path, region_folder_name)
                region_paths.append(region_path)
                try:
                    os.makedirs(region_path, exist_ok=True)
                except Exception as mkdir_err:
                    raise Exception(f"无法创建区域{i+1}的保存目录: {mkdir_err}")
                
                # 验证目录是否可写
                if not os.access(region_path, os.W_OK):
                    raise Exception(f"区域{i+1}的保存目录没有写入权限: {region_path}")
            
            # 计数器
            frame_count = start_frame_limit  # 从起始帧开始计数
            saved_counts = [0] * len(crop_rects)  # 每个区域的保存计数
            
            # 计算实际需要处理的帧数（用于进度显示）
            frames_to_process = end_frame_limit - start_frame_limit + 1
            
            # 连续读取失败计数器
            consecutive_read_failures = 0
            max_consecutive_failures = 10  # 允许最多连续失败10次
            
            # 进度更新计数器（减少processEvents调用频率）
            progress_update_counter = 0
            progress_update_interval = 5  # 每处理5帧更新一次进度（平衡性能和响应性）
            
            while frame_count <= end_frame_limit:
                # 检查是否取消
                if progress_dialog.wasCanceled():
                    break
                
                # 检查连续失败次数
                if consecutive_read_failures >= max_consecutive_failures:
                    break
                
                # 读取帧
                try:
                    ret, frame = cap.read()
                    
                    if not ret:
                        consecutive_read_failures += 1
                        frame_count += 1
                        continue
                    
                    # 读取成功,重置失败计数器
                    consecutive_read_failures = 0
                    
                except Exception as read_err:
                    consecutive_read_failures += 1
                    frame_count += 1
                    continue
                
                # 根据频率决定是否裁剪
                if (frame_count - start_frame_limit) % crop_frequency == 0:
                    # 对每个裁剪区域进行处理
                    for i, (x, y, w, h) in enumerate(crop_rects):
                        # 裁剪区域
                        cropped = frame[y:y+h, x:x+w]
                        
                        # 生成文件名
                        filename = f"{file_prefix}_区域{i+1}_{saved_counts[i]+1:06d}.{image_format}"
                        filepath = osp.join(region_paths[i], filename)
                        
                        # 保存图片（使用cv2.imencode解决中文路径问题）
                        try:
                            # 使用imencode编码图片，然后用numpy写入文件
                            # 这样可以避免cv2.imwrite在Windows上处理中文路径的bug
                            ext = '.' + image_format
                            success, encoded_img = cv2.imencode(ext, cropped)
                            
                            if success:
                                # 使用numpy写入文件，支持中文路径
                                with open(filepath, 'wb') as f:
                                    f.write(encoded_img.tobytes())
                                
                                saved_counts[i] += 1
                            else:
                                pass
                                
                        except Exception as save_err:
                            # 继续处理下一个区域，不中断整个流程
                            pass
                
                frame_count += 1
                progress_update_counter += 1
                
                # 优化进度更新频率（减少processEvents调用）
                if progress_update_counter >= progress_update_interval:
                    progress_update_counter = 0
                    
                    # 更新进度（基于实际处理的帧数）
                    processed_frames = frame_count - start_frame_limit
                    progress = int((processed_frames / frames_to_process) * 100)
                    progress_dialog.setValue(progress)
                    self.cropProgress.emit(progress)
                    
                    # 强制刷新预览面板（确保实时更新）
                    if self._crop_preview_handler is not None:
                        self._crop_preview_handler.forceRefresh()
                    
                    # 处理事件，保持界面响应
                    QtWidgets.QApplication.processEvents()
            
            # 释放资源
            cap.release()
            
            # 完成
            progress_dialog.setValue(100)
            
            # 输出统计信息

            
            # 保存视频与裁剪图片的映射关系
            import time
            self._video_crop_mapping[video_path] = {
                'save_path': save_liquid_data_path,
                'region_paths': region_paths,
                'timestamp': time.time()
            }

            
            # 保存映射关系到文件（持久化存储）
            self._saveMappingToFile()
            
            # 更新视频网格样式，标记已裁剪的视频
            self.updateVideoGridStyles()
            
            # 发射完成信号
            self.cropFinished.emit(save_liquid_data_path)
            
            # 构建详细信息
            processed_frames = frame_count - start_frame_limit
            
            # 检查是否使用了时间段选择
            time_range_info = ""
            if hasattr(self._panel, 'video_preview_widget'):
                control_bar = self._panel.video_preview_widget.control_bar
                if control_bar.isTimeRangeMode():
                    start_time = self._formatTimeFromFrame(start_frame_limit)
                    end_time = self._formatTimeFromFrame(end_frame_limit)
                    time_range_info = f"时间段: {start_time} - {end_time} (帧 {start_frame_limit} - {end_frame_limit})\n"
            
            detail_info = f"{time_range_info}处理帧数: {processed_frames}\n\n"
            for i in range(len(crop_rects)):
                detail_info += f"区域{i+1}: 保存 {saved_counts[i]} 张图片\n"
            detail_info += f"\n文件格式: {file_prefix}_regionX_XXXXXX.{image_format}\n"
            detail_info += f"\n保存位置:\n{save_liquid_data_path}"
            
            # 显示完成消息
            if not progress_dialog.wasCanceled():
                # 构建主要消息
                main_text = f"视频帧裁剪完成！共处理 {len(crop_rects)} 个区域"
                if hasattr(self._panel, 'video_preview_widget'):
                    control_bar = self._panel.video_preview_widget.control_bar
                    if control_bar.isTimeRangeMode():
                        main_text += "\n\n已使用时间段裁剪模式"
                
                # 🔥 使用全局DialogManager显示带详细信息和自定义按钮的对话框
                if DialogManager:
                    custom_buttons = [("打开文件夹", QtWidgets.QMessageBox.ActionRole)]
                    clicked_button = DialogManager.show_information_with_details(
                        self._panel, "裁剪完成", main_text, detail_info, custom_buttons
                    )
                    
                    # 如果用户点击了"打开文件夹"按钮
                    if clicked_button == "打开文件夹":
                        self._openFolder(save_liquid_data_path)
                else:
                    # 备用方案：使用原生QMessageBox
                    msg_box = QtWidgets.QMessageBox(self._panel)
                    msg_box.setIcon(QtWidgets.QMessageBox.Information)
                    msg_box.setWindowTitle("裁剪完成")
                    msg_box.setText(main_text)
                    msg_box.setInformativeText(detail_info)
                    
                    # 添加打开文件夹按钮
                    open_folder_btn = msg_box.addButton("打开文件夹", QtWidgets.QMessageBox.ActionRole)
                    msg_box.addButton("确定", QtWidgets.QMessageBox.AcceptRole)
                    
                    msg_box.exec_()
                    
                    # 如果用户点击了"打开文件夹"按钮
                    if msg_box.clickedButton() == open_folder_btn:
                        self._openFolder(save_liquid_data_path)
            
        except Exception as e:
            error_msg = f"裁剪失败: {e}"
            
            # 发射错误信号
            self.cropError.emit(error_msg)
            
            # 显示错误消息
            self._showCritical("错误", error_msg)
         
        finally:
            self._cropping = False
            progress_dialog.close()
            
            # 清除裁剪区域
            self._crop_rects.clear()
            if isinstance(self._panel.video_preview, DrawableLabel):
                self._panel.video_preview.clearRectangles()
            
            # 禁用开始裁剪按钮
            if hasattr(self._panel, 'btn_start_crop'):
                self._panel.btn_start_crop.setEnabled(False)
    
    # ========== 公共方法 ==========
    
    def setPanel(self, panel):
        """设置面板"""
        self._panel = panel
        if self._panel:
            self._initPanel()
    
    def getPanel(self):
        """获取面板"""
        return self._panel
    
    def getCropRects(self):
        """获取所有裁剪区域"""
        return self._crop_rects.copy()
    
    def isCropping(self):
        """是否正在裁剪"""
        return self._cropping


# ==================== 测试代码 ====================

if __name__ == "__main__":
    """独立测试"""
    import sys
    
    # 导入面板
    try:
        from widgets.datasetpage import DataPreprocessPanel
    except ImportError:
        sys.exit(1)
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("数据预处理处理器测试")
    window.resize(1400, 800)
    
    # 创建面板
    test_root = osp.join(osp.expanduser("~"), "data_collection_test")
    panel = DataPreprocessPanel(root_path=test_root)
    
    # 创建处理器
    handler = DataPreprocessHandler(panel)
    
    # 连接处理器信号
    def on_crop_started(config):
        pass
    
    def on_crop_progress(progress):
        pass
    
    def on_crop_finished(save_liquid_data_path):
        pass
    
    def on_crop_error(error):
        pass
    
    handler.cropStarted.connect(on_crop_started)
    handler.cropProgress.connect(on_crop_progress)
    handler.cropFinished.connect(on_crop_finished)
    handler.cropError.connect(on_crop_error)
    
    window.setCentralWidget(panel)
    
    window.show()
    sys.exit(app.exec_())

