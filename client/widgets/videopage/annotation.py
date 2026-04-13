# -*- coding: utf-8 -*-

"""
标注界面组件

只负责UI控件设计和发送信号，业务逻辑由annotation_handler处理
提供标注界面的控件和用户交互
"""

import cv2
import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

# 导入响应式布局
try:
    from ..responsive_layout import scale_w, scale_h
except (ImportError, ValueError):
    import sys
    import os.path as osp
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from responsive_layout import scale_w, scale_h


class AnnotationWidget(QtWidgets.QWidget):
    """
    标注界面组件 - PyQt5版本
    
    只负责UI控件设计和发送信号，业务逻辑由handler处理
    提供标注界面的控件和用户交互
    """
    
    # 信号定义
    annotationCompleted = QtCore.Signal(list, list, list, list)  # 标注完成信号 (boxes, bottoms, tops, init_levels)
    annotationCancelled = QtCore.Signal()  # 标注取消信号
    
    # 新增信号 - 用于与handler交互
    annotationEngineRequested = QtCore.Signal()  # 请求标注引擎
    frameLoadRequested = QtCore.Signal()  # 请求加载帧
    annotationDataRequested = QtCore.Signal()  # 请求标注数据
    
    # ROI拖动完成信号 - 用于触发自动标注
    roiDragCompleted = QtCore.Signal(int, tuple)  # (roi_index, (cx, cy, size)) ROI拖动完成后发送
    
    def __init__(self, parent=None, annotation_engine=None):
        super(AnnotationWidget, self).__init__(parent)
        
        self.annotation_engine = annotation_engine
        self.current_frame = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drawing_box = False
        self.box_start = (0, 0)
        
        # 🔥 拖动点相关属性
        self.dragging_point = False  # 是否正在拖动点
        self.dragging_point_type = None  # 'bottom' 或 'top'
        self.dragging_point_index = -1  # 正在拖动的点的索引

        # 🔥 ROI框拖动和缩放相关属性
        self.dragging_box = False  # 是否正在拖动ROI框
        self.dragging_box_index = -1  # 正在拖动的ROI框索引
        self.drag_box_start_pos = None  # 拖动起始鼠标位置
        self.drag_box_start_center = None  # 拖动起始时ROI框中心位置
        self.selected_box_index = -1  # 当前选中的ROI框索引（用于滚轮缩放）
        self.roi_scale_step = 32  # ROI缩放步长（像素），与32像素对齐一致
        
        # 🔥 原地编辑相关属性
        self.edit_widget = None  # 当前编辑控件
        self.editing_area_index = -1  # 正在编辑的区域索引
        self.editing_type = None  # 'name' 或 'height'
        
        # 区域名称和高度配置（支持双击编辑）
        self.area_names = []  # 存储区域名称列表
        self.area_heights = []  # 存储区域高度列表（默认20mm）
        self.area_states = []  # 存储区域状态列表（默认、空、满）
        self.channel_name = ""  # 通道名称
        
        # 物理变焦相关
        self.physical_zoom_controller = None  # 物理变焦控制器
        self.physical_zoom_enabled = False  # 是否启用物理变焦
        self.zoom_factor = 1.0  # 当前变焦倍数
        self.min_zoom = 1.0  # 最小变焦倍数
        self.max_zoom = 30.0  # 最大变焦倍数
        self.zoom_step = 0.5  # 变焦步长
        self.zoom_center_x = 0  # 变焦中心X坐标
        self.zoom_center_y = 0  # 变焦中心Y坐标
        
        # 🔥 调试开关
        self.debug = False
        
        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI"""
        self.setWindowTitle("ROI预览窗口")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 使用QGraphicsView实现高性能绘制
        self.graphics_view = QtWidgets.QGraphicsView()
        self.graphics_scene = QtWidgets.QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setStyleSheet("background-color: #000000; border: none;")
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphics_view.setRenderHint(QtGui.QPainter.Antialiasing, False)  # 关闭抗锯齿提升性能
        self.graphics_view.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)  # 最小更新模式

        # 背景图像项（只设置一次）
        self.background_pixmap_item = None

        # 图形项列表（框、线条）
        self.graphics_items = []

        # 鼠标事件
        self.graphics_view.mousePressEvent = self._onMousePress
        self.graphics_view.mouseMoveEvent = self._onMouseMove
        self.graphics_view.mouseReleaseEvent = self._onMouseRelease
        self.graphics_view.mouseDoubleClickEvent = self._onMouseDoubleClick

        main_layout.addWidget(self.graphics_view)

        # 使用QTimer延迟调用showFullScreen，让窗口和控件先完成初始化
        QtCore.QTimer.singleShot(100, self._applyFullScreen)
    
    def _connectSignals(self):
        """连接信号"""
        pass  # 保留方法结构，暂无额外信号需要连接
    
    def _applyFullScreen(self):
        """应用全屏模式（延迟调用，确保控件已初始化）"""
        self.showFullScreen()
        self.setFocus()
        self.activateWindow()
        if self.current_frame is not None:
            self._updateDisplay()

    def resizeEvent(self, event):
        """窗口大小变化时重新调整视图"""
        super(AnnotationWidget, self).resizeEvent(event)
        if self.background_pixmap_item is not None:
            self.graphics_view.fitInView(self.graphics_scene.sceneRect(), Qt.KeepAspectRatio)

    def setAnnotationEngine(self, engine):
        """设置标注引擎"""
        self.annotation_engine = engine
    
    def setChannelName(self, channel_name):
        """设置通道名称（用于生成区域默认名称）"""
        self.channel_name = channel_name
    
    def setPhysicalZoomController(self, controller):
        """设置物理变焦控制器"""
        self.physical_zoom_controller = controller
        if controller:
            self.physical_zoom_enabled = True
            capabilities = controller.get_zoom_capabilities()
            if capabilities:
                self.min_zoom = capabilities.get('min_zoom', 1.0)
                self.max_zoom = capabilities.get('max_zoom', 30.0)
        else:
            self.physical_zoom_enabled = False
    
    def _generateAreaName(self, area_index):
        """生成区域默认名称：通道name_区域1234"""
        if self.channel_name:
            return f"{self.channel_name}_区域{area_index+1}"
        else:
            return f"区域{area_index+1}"
    
    def _ensureAreaConfig(self, area_index):
        """确保区域配置存在（名称、状态和高度）"""
        while len(self.area_names) <= area_index:
            self.area_names.append(self._generateAreaName(len(self.area_names)))
        while len(self.area_heights) <= area_index:
            self.area_heights.append("20mm")
        while len(self.area_states) <= area_index:
            self.area_states.append("默认")
    
    def _toggleAreaState(self, area_index):
        """切换区域状态：默认 → 空 → 满 → 默认"""
        if area_index < 0 or area_index >= len(self.area_states):
            return
        current_state = self.area_states[area_index]
        if current_state == "默认":
            self.area_states[area_index] = "空"
        elif current_state == "空":
            self.area_states[area_index] = "满"
        elif current_state == "满":
            self.area_states[area_index] = "默认"
        self._updateDisplay()
    
    def loadFrame(self, frame):
        """加载图像帧"""
        if frame is None:
            return False
        self.current_frame = frame.copy()
        self.frameLoadRequested.emit()
        self._updateDisplay()
        return True
    
    def _updateDisplay(self):
        """更新显示（完整渲染，包含文字）"""
        if self.current_frame is None:
            return

        self._displayImage(self.current_frame)

        if self.annotation_engine is not None:
            self._drawAnnotationsAsGraphicsItems()

        self._updateStatus()
    
    def _updateDisplayLightweight(self):
        """轻量级更新显示（拖动时使用，只更新图形项，不重绘背景）"""
        if self.current_frame is None:
            return

        # 只更新标注图形项，不重绘背景图像
        if self.annotation_engine is not None:
            self._drawAnnotationsAsGraphicsItems()
    
    def _drawAnnotationsLightweight(self, img):
        """轻量级绘制标注（只画框和线条，不画文字）"""
        if self.annotation_engine is None:
            return
        
        # 绘制已完成的框（黄色）
        for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
            half = size // 2
            top = cy - half
            bottom = cy + half
            left = cx - half
            right = cx + half
            cv2.rectangle(img, (left, top), (right, bottom), (0, 255, 255), 3)
        
        # 绘制底部线条（绿色）
        for i, pt in enumerate(self.annotation_engine.bottom_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            cv2.line(img, (x - half_length, y), (x + half_length, y), (0, 255, 0), 2)
        
        # 绘制顶部线条（红色）
        for i, pt in enumerate(self.annotation_engine.top_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            cv2.line(img, (x - half_length, y), (x + half_length, y), (0, 0, 255), 2)
        
        # 绘制初始液位线（蓝色）
        if hasattr(self.annotation_engine, 'init_level_points'):
            for i, pt in enumerate(self.annotation_engine.init_level_points):
                if i < len(self.annotation_engine.boxes):
                    _, _, size = self.annotation_engine.boxes[i]
                    line_length = int(size * 1.1)
                else:
                    line_length = 30
                half_length = line_length // 2
                x, y = pt
                cv2.line(img, (x - half_length, y), (x + half_length, y), (255, 165, 0), 2)  # 橙色
        
        # 如果正在画框，显示临时框
        if self.drawing_box:
            dx = self.current_mouse_pos[0] - self.box_start[0]
            dy = self.current_mouse_pos[1] - self.box_start[1]
            length = max(abs(dx), abs(dy))
            length = ((length + 31) // 32) * 32
            x2 = self.box_start[0] + (length if dx >= 0 else -length)
            y2 = self.box_start[1] + (length if dy >= 0 else -length)
            cv2.rectangle(img, self.box_start, (x2, y2), (0, 255, 255), 3)
    
    def _calculateDisplayParams(self):
        """计算显示参数"""
        if self.current_frame is None:
            return
        frame_height, frame_width = self.current_frame.shape[:2]
        label_width = self.image_label.width()
        label_height = self.image_label.height()
        scale_x = label_width / frame_width
        scale_y = label_height / frame_height
        self.scale_factor = min(scale_x, scale_y)
        scaled_width = int(frame_width * self.scale_factor)
        scaled_height = int(frame_height * self.scale_factor)
        self.offset_x = (label_width - scaled_width) // 2
        self.offset_y = (label_height - scaled_height) // 2

    def _drawAnnotationsAsGraphicsItems(self):
        """使用QGraphicsItem绘制标注（高性能，只更新图形项）"""
        if self.annotation_engine is None:
            return

        # 清除旧的图形项
        for item in self.graphics_items:
            self.graphics_scene.removeItem(item)
        self.graphics_items.clear()

        # 绘制已完成的框（黄色）
        for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
            half = size // 2
            rect = QtCore.QRectF(cx - half, cy - half, size, size)
            rect_item = self.graphics_scene.addRect(rect, QtGui.QPen(QtGui.QColor(255, 255, 0), 3))
            self.graphics_items.append(rect_item)

        # 绘制底部线条（绿色）
        for i, pt in enumerate(self.annotation_engine.bottom_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            line_item = self.graphics_scene.addLine(x - half_length, y, x + half_length, y,
                                                     QtGui.QPen(QtGui.QColor(0, 255, 0), 2))
            self.graphics_items.append(line_item)

        # 绘制顶部线条（红色）
        for i, pt in enumerate(self.annotation_engine.top_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            line_item = self.graphics_scene.addLine(x - half_length, y, x + half_length, y,
                                                     QtGui.QPen(QtGui.QColor(0, 0, 255), 2))
            self.graphics_items.append(line_item)

        # 绘制初始液位线（橙色）
        if hasattr(self.annotation_engine, 'init_level_points'):
            for i, pt in enumerate(self.annotation_engine.init_level_points):
                if i < len(self.annotation_engine.boxes):
                    _, _, size = self.annotation_engine.boxes[i]
                    line_length = int(size * 1.1)
                else:
                    line_length = 30
                half_length = line_length // 2
                x, y = pt
                line_item = self.graphics_scene.addLine(x - half_length, y, x + half_length, y,
                                                         QtGui.QPen(QtGui.QColor(255, 165, 0), 2))
                self.graphics_items.append(line_item)

        # 如果正在画框，显示临时框
        if self.drawing_box:
            dx = self.current_mouse_pos[0] - self.box_start[0]
            dy = self.current_mouse_pos[1] - self.box_start[1]
            length = max(abs(dx), abs(dy))
            length = ((length + 31) // 32) * 32
            x2 = self.box_start[0] + (length if dx >= 0 else -length)
            y2 = self.box_start[1] + (length if dy >= 0 else -length)
            temp_rect = QtCore.QRectF(min(self.box_start[0], x2), min(self.box_start[1], y2),
                                       abs(x2 - self.box_start[0]), abs(y2 - self.box_start[1]))
            temp_rect_item = self.graphics_scene.addRect(temp_rect, QtGui.QPen(QtGui.QColor(255, 255, 0), 3))
            self.graphics_items.append(temp_rect_item)

    def _drawAnnotations(self, img):
        """绘制标注内容"""
        if self.annotation_engine is None:
            return
        
        # 绘制已完成的框
        for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
            self._ensureAreaConfig(i)
            half = size // 2
            top = cy - half
            bottom = cy + half
            left = cx - half
            right = cx + half
            cv2.rectangle(img, (left, top), (right, bottom), (0, 255, 255), 3)
        
        # 绘制底部线条（绿色）
        for i, pt in enumerate(self.annotation_engine.bottom_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            cv2.line(img, (x - half_length, y), (x + half_length, y), (0, 255, 0), 1)
        
        # 绘制顶部线条（红色）
        for i, pt in enumerate(self.annotation_engine.top_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x, y = pt
            cv2.line(img, (x - half_length, y), (x + half_length, y), (0, 0, 255), 1)
        
        # 绘制初始液位线（橙色）
        if hasattr(self.annotation_engine, 'init_level_points'):
            for i, pt in enumerate(self.annotation_engine.init_level_points):
                if i < len(self.annotation_engine.boxes):
                    _, _, size = self.annotation_engine.boxes[i]
                    line_length = int(size * 1.1)
                else:
                    line_length = 30
                half_length = line_length // 2
                x, y = pt
                cv2.line(img, (x - half_length, y), (x + half_length, y), (0, 165, 255), 2)  # BGR格式橙色
        
        # 如果正在画框，显示临时框
        if self.drawing_box:
            dx = self.current_mouse_pos[0] - self.box_start[0]
            dy = self.current_mouse_pos[1] - self.box_start[1]
            length = max(abs(dx), abs(dy))
            length = ((length + 31) // 32) * 32
            x2 = self.box_start[0] + (length if dx >= 0 else -length)
            y2 = self.box_start[1] + (length if dy >= 0 else -length)
            cv2.rectangle(img, self.box_start, (x2, y2), (0, 255, 255), 3)
        
        # 使用PIL绘制中文文本
        try:
            from PIL import Image, ImageDraw, ImageFont
            img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)
            
            try:
                font_name = ImageFont.truetype("simhei.ttf", 24)
                font_height = ImageFont.truetype("msyh.ttc", 20)
                font_label = ImageFont.truetype("msyh.ttc", 18)
            except:
                try:
                    font_name = ImageFont.truetype("msyh.ttc", 24)
                    font_height = ImageFont.truetype("msyh.ttc", 20)
                    font_label = ImageFont.truetype("msyh.ttc", 18)
                except:
                    font_name = ImageFont.load_default()
                    font_height = ImageFont.load_default()
                    font_label = ImageFont.load_default()
            
            # 绘制底部线条标签
            for i, pt in enumerate(self.annotation_engine.bottom_points):
                draw.text((pt[0] + 15, pt[1] - 5), f"容器底部{i+1}", fill=(0, 255, 0), font=font_label)
            
            # 绘制顶部线条标签
            for i, pt in enumerate(self.annotation_engine.top_points):
                draw.text((pt[0] + 15, pt[1] - 5), f"容器顶部{i+1}", fill=(255, 0, 0), font=font_label)
            
            # 绘制初始液位线标签
            if hasattr(self.annotation_engine, 'init_level_points'):
                for i, pt in enumerate(self.annotation_engine.init_level_points):
                    draw.text((pt[0] + 15, pt[1] - 5), f"初始液位{i+1}", fill=(255, 165, 0), font=font_label)
            
            # 绘制区域名称和高度
            for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
                half = size // 2
                top = cy - half
                left = cx - half
                area_name = self.area_names[i]
                area_height = self.area_heights[i]
                area_state = self.area_states[i]
                
                text_y = top + 5
                draw.text((left + 5, text_y), area_name, fill=(0, 255, 0), font=font_name)
                
                try:
                    name_bbox = draw.textbbox((left + 5, text_y), area_name, font=font_name)
                    name_width = name_bbox[2] - name_bbox[0]
                except:
                    name_width = len(area_name) * 20
                
                draw.text((left + 5 + name_width + 15, text_y), area_height, fill=(255, 255, 0), font=font_height)
                draw.text((cx - len(area_state) * 10, cy), area_state, fill=(255, 255, 255), font=font_name)
            
            img[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        except (ImportError, Exception):
            pass  # 如果PIL不可用，跳过中文绘制
    
    def _drawInstructionText(self, img):
        """在图像右上角绘制说明文字"""
        if img is None:
            return
        
        if not hasattr(self, '_help_visible'):
            self._help_visible = True
        
        if not self._help_visible:
            return
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            height, width = img.shape[:2]
            
            instructions = [
                "标注操作指南",
                "1. 左键拖动放置ROI框",
                "2. 拖动线条调整位置",
                "3. 双击编辑名称/高度",
                "4. 双击状态标签切换状态",
                "5. 双击空白区域完成标注",
                "",
                "ROI操作",
                "滚轮=缩放ROI  中键拖动=移动ROI",
                "",
                "快捷键",
                "C/S=完成  D/U=删除  H=帮助  ESC=关闭"
            ]
            
            text_width = 320
            line_height = 24
            text_height = len(instructions) * line_height + 15
            start_x = width - text_width - 5
            start_y = 0
            
            overlay = img.copy()
            cv2.rectangle(overlay, (start_x - 10, start_y), 
                          (start_x + text_width + 10, start_y + text_height + 10), 
                          (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            draw = ImageDraw.Draw(pil_img)
            
            try:
                font = ImageFont.truetype("simhei.ttf", 16)
            except:
                try:
                    font = ImageFont.truetype("msyh.ttc", 16)
                except:
                    font = ImageFont.load_default()
            
            for i, instruction in enumerate(instructions):
                y_pos = start_y + 5 + i * line_height
                draw.text((start_x, y_pos), instruction, fill=(255, 255, 255), font=font)
            
            img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            cv2.rectangle(img, (start_x - 10, start_y), 
                         (start_x + text_width + 10, start_y + text_height + 10), 
                         (255, 255, 255), 2)
        except ImportError:
            pass
    
    def _displayImage(self, img):
        """显示图像（只设置背景，不绘制标注）"""
        if img is None:
            return

        # 转换为QPixmap
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qt_image)

        # 只在第一次或图像尺寸变化时重新设置背景
        if self.background_pixmap_item is None:
            self.background_pixmap_item = self.graphics_scene.addPixmap(pixmap)
            self.graphics_scene.setSceneRect(0, 0, w, h)
            # 只在第一次设置时调用fitInView
            self.graphics_view.fitInView(self.graphics_scene.sceneRect(), Qt.KeepAspectRatio)
        else:
            # 直接更新pixmap，不重建整个场景，不调用fitInView
            self.background_pixmap_item.setPixmap(pixmap)
    
    def _updateStatus(self):
        """更新状态显示"""
        pass

    def _onMousePress(self, event):
        """鼠标按下事件"""
        if self.annotation_engine is None or self.current_frame is None:
            return

        image_x, image_y = self._labelToImageCoords(event.x(), event.y())
        
        if event.button() == Qt.RightButton:
            self._showContextMenu(event.globalPos(), image_x, image_y)
            return
        
        if event.button() == Qt.MiddleButton:
            box_index = self._findBoxAtPosition(image_x, image_y)
            if box_index >= 0:
                self.dragging_box = True
                self.dragging_box_index = box_index
                self.drag_box_start_pos = (image_x, image_y)
                cx, cy, size = self.annotation_engine.boxes[box_index]
                self.drag_box_start_center = (cx, cy)
                self.setCursor(Qt.ClosedHandCursor)
            return
        
        if event.button() == Qt.LeftButton:
            # 首先检查是否点击了线条（用于拖动线条）
            point_type, point_index = self._findNearestPoint(image_x, image_y)
            if point_type is not None:
                self.dragging_point = True
                self.dragging_point_type = point_type
                self.dragging_point_index = point_index
                return
            
            # 检查是否点击了ROI框（左键拖动ROI框）
            box_index = self._findBoxAtPosition(image_x, image_y)
            if box_index >= 0:
                # 左键点击ROI框：选中并启动拖动
                self.selected_box_index = box_index
                self.dragging_box = True
                self.dragging_box_index = box_index
                self.drag_box_start_pos = (image_x, image_y)
                cx, cy, size = self.annotation_engine.boxes[box_index]
                self.drag_box_start_center = (cx, cy)
                self.setCursor(Qt.ClosedHandCursor)
                self._updateDisplay()
                return
            else:
                self.selected_box_index = -1
            
            # 点击空白区域：开始绘制新的ROI框
            if self.annotation_engine.step == 0:
                self.drawing_box = True
                self.box_start = (image_x, image_y)
                self.current_mouse_pos = (image_x, image_y)
    
    def _onMouseMove(self, event):
        """鼠标移动事件"""
        image_x, image_y = self._labelToImageCoords(event.x(), event.y())
        
        if self.dragging_box and self.dragging_box_index >= 0:
            if self.annotation_engine is not None and self.dragging_box_index < len(self.annotation_engine.boxes):
                dx = image_x - self.drag_box_start_pos[0]
                dy = image_y - self.drag_box_start_pos[1]
                new_cx = self.drag_box_start_center[0] + dx
                new_cy = self.drag_box_start_center[1] + dy
                _, _, size = self.annotation_engine.boxes[self.dragging_box_index]
                self.annotation_engine.boxes[self.dragging_box_index] = (new_cx, new_cy, size)
                
                if self.dragging_box_index < len(self.annotation_engine.bottom_points):
                    old_bx, old_by = self.annotation_engine.bottom_points[self.dragging_box_index]
                    self.annotation_engine.bottom_points[self.dragging_box_index] = (new_cx, old_by + dy)
                
                if self.dragging_box_index < len(self.annotation_engine.top_points):
                    old_tx, old_ty = self.annotation_engine.top_points[self.dragging_box_index]
                    self.annotation_engine.top_points[self.dragging_box_index] = (new_cx, old_ty + dy)
                
                # 同步移动初始液位线
                if hasattr(self.annotation_engine, 'init_level_points') and self.dragging_box_index < len(self.annotation_engine.init_level_points):
                    old_ix, old_iy = self.annotation_engine.init_level_points[self.dragging_box_index]
                    self.annotation_engine.init_level_points[self.dragging_box_index] = (new_cx, old_iy + dy)
                
                self.drag_box_start_pos = (image_x, image_y)
                self.drag_box_start_center = (new_cx, new_cy)
                # 拖动时使用轻量级绘制，只画框不画文字
                self._updateDisplayLightweight()
            return
        
        if self.dragging_point and self.annotation_engine is not None:
            if self.dragging_point_type == 'bottom':
                if 0 <= self.dragging_point_index < len(self.annotation_engine.bottom_points):
                    self.annotation_engine.bottom_points[self.dragging_point_index] = (image_x, image_y)
            elif self.dragging_point_type == 'top':
                if 0 <= self.dragging_point_index < len(self.annotation_engine.top_points):
                    self.annotation_engine.top_points[self.dragging_point_index] = (image_x, image_y)
            elif self.dragging_point_type == 'init_level':
                if hasattr(self.annotation_engine, 'init_level_points'):
                    if 0 <= self.dragging_point_index < len(self.annotation_engine.init_level_points):
                        self.annotation_engine.init_level_points[self.dragging_point_index] = (image_x, image_y)
            # 拖动时使用轻量级绘制
            self._updateDisplayLightweight()
            return
        
        if self.drawing_box and self.annotation_engine is not None:
            self.current_mouse_pos = (image_x, image_y)
            # 绘制新框时使用轻量级绘制
            self._updateDisplayLightweight()
    
    def _onMouseRelease(self, event):
        """鼠标释放事件"""
        if self.dragging_box:
            # 保存拖动的ROI索引，用于发送信号
            completed_box_index = self.dragging_box_index
            self.dragging_box = False
            self.dragging_box_index = -1
            self.drag_box_start_pos = None
            self.drag_box_start_center = None
            self.setCursor(Qt.ArrowCursor)
            # 释放后恢复完整渲染（显示文字）
            self._updateDisplay()
            
            # 发送ROI拖动完成信号，触发自动标注
            if completed_box_index >= 0 and completed_box_index < len(self.annotation_engine.boxes):
                box_data = self.annotation_engine.boxes[completed_box_index]
                self.roiDragCompleted.emit(completed_box_index, box_data)
            return
        
        if self.dragging_point:
            self.dragging_point = False
            self.dragging_point_type = None
            self.dragging_point_index = -1
            # 释放后恢复完整渲染
            self._updateDisplay()
            return
        
        if self.drawing_box and self.annotation_engine is not None:
            self.drawing_box = False
            image_x, image_y = self._labelToImageCoords(event.x(), event.y())
            
            dx = image_x - self.box_start[0]
            dy = image_y - self.box_start[1]
            length = max(abs(dx), abs(dy))
            length = ((length + 31) // 32) * 32
            
            if length > 0:
                x2 = self.box_start[0] + (length if dx >= 0 else -length)
                y2 = self.box_start[1] + (length if dy >= 0 else -length)
                cx = (self.box_start[0] + x2) // 2
                cy = (self.box_start[1] + y2) // 2
                size = length
                
                self.annotation_engine.add_box(cx, cy, size)
                self.annotation_engine.step = 0
                box_index = len(self.annotation_engine.boxes) - 1
                
                # 确保init_level_points存在并同步添加初始液位线（默认在中间位置）
                if not hasattr(self.annotation_engine, 'init_level_points'):
                    self.annotation_engine.init_level_points = []
                # 如果add_box没有自动添加init_level_point，手动添加
                if len(self.annotation_engine.init_level_points) < len(self.annotation_engine.boxes):
                    # 获取该box对应的top和bottom
                    if box_index < len(self.annotation_engine.top_points) and box_index < len(self.annotation_engine.bottom_points):
                        top_y = self.annotation_engine.top_points[box_index][1]
                        bottom_y = self.annotation_engine.bottom_points[box_index][1]
                        init_level_y = int((top_y + bottom_y) / 2)
                        self.annotation_engine.init_level_points.append((cx, init_level_y))
                
                self._ensureAreaConfig(box_index)
                self._updateDisplay()
                
                # 发送ROI拖动完成信号，触发自动标注（新建ROI框也触发）
                box_data = self.annotation_engine.boxes[box_index]
                self.roiDragCompleted.emit(box_index, box_data)
    
    def _onMouseDoubleClick(self, event):
        """鼠标双击事件"""
        if self.annotation_engine is None or self.current_frame is None:
            return
        
        image_x, image_y = self._labelToImageCoords(event.x(), event.y())
        
        # 检查是否双击了状态标签
        for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
            self._ensureAreaConfig(i)
            area_state = self.area_states[i]
            state_width = len(area_state) * 20
            state_height = 30
            state_left = cx - state_width // 2
            state_right = cx + state_width // 2
            state_top = cy - state_height // 2
            state_bottom = cy + state_height // 2
            
            if state_left <= image_x <= state_right and state_top <= image_y <= state_bottom:
                self._toggleAreaState(i)
                return
        
        # 检查是否双击了名称或高度
        for i, (cx, cy, size) in enumerate(self.annotation_engine.boxes):
            self._ensureAreaConfig(i)
            half = size // 2
            top = cy - half
            left = cx - half
            area_name = self.area_names[i]
            name_width = len(area_name) * 20
            
            text_rect_left = left + 5
            text_rect_right = left + 5 + name_width + 200
            text_rect_top = top + 5
            text_rect_bottom = top + 40
            
            if text_rect_left <= image_x <= text_rect_right and text_rect_top <= image_y <= text_rect_bottom:
                if image_x < left + 5 + name_width + 10:
                    self._editAreaName(i)
                else:
                    self._editAreaHeight(i)
                return
        
        self._onComplete()

    def _editAreaName(self, area_index):
        """原地编辑区域名称"""
        if self.edit_widget is not None:
            self._finishEdit()
        current_name = self.area_names[area_index]
        if area_index < len(self.annotation_engine.boxes):
            cx, cy, size = self.annotation_engine.boxes[area_index]
            half = size // 2
            top = cy - half
            left = cx - half
            screen_pos = self._imageToScreenCoords(left + 5, top + 5)
            self._createEditWidget(screen_pos[0], screen_pos[1], current_name, area_index, 'name')
    
    def _editAreaHeight(self, area_index):
        """原地编辑区域高度"""
        if self.edit_widget is not None:
            self._finishEdit()
        current_height = self.area_heights[area_index]
        if area_index < len(self.annotation_engine.boxes):
            cx, cy, size = self.annotation_engine.boxes[area_index]
            half = size // 2
            top = cy - half
            left = cx - half
            area_name = self.area_names[area_index]
            name_width = len(area_name) * 20
            screen_pos = self._imageToScreenCoords(left + 5 + name_width + 15, top + 5)
            self._createEditWidget(screen_pos[0], screen_pos[1], current_height, area_index, 'height')
    
    def _createEditWidget(self, x, y, text, area_index, edit_type):
        """创建原地编辑控件"""
        self.edit_widget = QtWidgets.QLineEdit(self)
        self.edit_widget.setText(text)
        self.edit_widget.selectAll()
        self.edit_widget.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 2px solid #4CAF50;
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        if edit_type == 'name':
            self.edit_widget.setFixedSize(scale_w(150), scale_h(30))
        else:
            self.edit_widget.setFixedSize(scale_w(80), scale_h(30))
        self.edit_widget.move(x, y)
        self.edit_widget.show()
        self.edit_widget.setFocus()
        self.editing_area_index = area_index
        self.editing_type = edit_type
        self.edit_widget.returnPressed.connect(self._finishEdit)
        self.edit_widget.editingFinished.connect(self._finishEdit)
    
    def _finishEdit(self):
        """完成编辑"""
        if self.edit_widget is None:
            return
        new_text = self.edit_widget.text().strip()
        if new_text and self.editing_area_index >= 0:
            if self.editing_type == 'name':
                self.area_names[self.editing_area_index] = new_text
            elif self.editing_type == 'height':
                self.area_heights[self.editing_area_index] = new_text
            self._updateDisplay()
        self.edit_widget.deleteLater()
        self.edit_widget = None
        self.editing_area_index = -1
        self.editing_type = None
    
    def _imageToScreenCoords(self, image_x, image_y):
        """将图像坐标转换为屏幕坐标"""
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        if self.current_frame is None:
            return (0, 0)
        img_height, img_width = self.current_frame.shape[:2]
        scale_x = screen_width / img_width
        scale_y = screen_height / img_height
        scale_factor = min(scale_x, scale_y)
        scaled_width = int(img_width * scale_factor)
        scaled_height = int(img_height * scale_factor)
        offset_x = (screen_width - scaled_width) // 2
        offset_y = (screen_height - scaled_height) // 2
        screen_x = int(image_x * scale_factor + offset_x)
        screen_y = int(image_y * scale_factor + offset_y)
        return (screen_x, screen_y)
    
    def _labelToImageCoords(self, view_x, view_y):
        """将视图坐标转换为图像坐标（scene坐标）"""
        if self.current_frame is None:
            return 0, 0

        # 将view坐标转换为scene坐标
        scene_pos = self.graphics_view.mapToScene(int(view_x), int(view_y))
        image_x = int(scene_pos.x())
        image_y = int(scene_pos.y())

        # 限制在图像范围内
        img_height, img_width = self.current_frame.shape[:2]
        image_x = max(0, min(image_x, img_width - 1))
        image_y = max(0, min(image_y, img_height - 1))
        return image_x, image_y
    
    def _findNearestPoint(self, x, y, threshold=15):
        """查找距离(x, y)最近的线条（包括底部、顶部、初始液位线）"""
        if self.annotation_engine is None:
            return None, -1
        min_distance = threshold
        nearest_type = None
        nearest_index = -1
        
        for i, (px, py) in enumerate(self.annotation_engine.bottom_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x_margin = 10
            if px - half_length - x_margin <= x <= px + half_length + x_margin:
                distance = abs(y - py)
            else:
                if x < px - half_length:
                    distance = ((x - (px - half_length)) ** 2 + (y - py) ** 2) ** 0.5
                else:
                    distance = ((x - (px + half_length)) ** 2 + (y - py) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_type = 'bottom'
                nearest_index = i
        
        for i, (px, py) in enumerate(self.annotation_engine.top_points):
            if i < len(self.annotation_engine.boxes):
                _, _, size = self.annotation_engine.boxes[i]
                line_length = int(size * 1.1)
            else:
                line_length = 30
            half_length = line_length // 2
            x_margin = 10
            if px - half_length - x_margin <= x <= px + half_length + x_margin:
                distance = abs(y - py)
            else:
                if x < px - half_length:
                    distance = ((x - (px - half_length)) ** 2 + (y - py) ** 2) ** 0.5
                else:
                    distance = ((x - (px + half_length)) ** 2 + (y - py) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_type = 'top'
                nearest_index = i
        
        # 检查初始液位线
        if hasattr(self.annotation_engine, 'init_level_points'):
            for i, (px, py) in enumerate(self.annotation_engine.init_level_points):
                if i < len(self.annotation_engine.boxes):
                    _, _, size = self.annotation_engine.boxes[i]
                    line_length = int(size * 1.1)
                else:
                    line_length = 30
                half_length = line_length // 2
                x_margin = 10
                if px - half_length - x_margin <= x <= px + half_length + x_margin:
                    distance = abs(y - py)
                else:
                    if x < px - half_length:
                        distance = ((x - (px - half_length)) ** 2 + (y - py) ** 2) ** 0.5
                    else:
                        distance = ((x - (px + half_length)) ** 2 + (y - py) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    nearest_type = 'init_level'
                    nearest_index = i
        
        return nearest_type, nearest_index
    
    def _isPointInLastBox(self, x, y):
        """检查点是否在最后一个检测框内"""
        if self.annotation_engine is None or len(self.annotation_engine.boxes) == 0:
            return False
        cx, cy, size = self.annotation_engine.boxes[-1]
        half = size // 2
        return (cx - half) <= x <= (cx + half) and (cy - half) <= y <= (cy + half)
    
    def _findBoxAtPosition(self, x, y, margin=20):
        """
        查找点击位置对应的标注框索引
        
        Args:
            x, y: 点击位置坐标
            margin: 选中容差范围（像素），扩大点击区域
        """
        if self.annotation_engine is None:
            return -1
        for i in range(len(self.annotation_engine.boxes) - 1, -1, -1):
            cx, cy, size = self.annotation_engine.boxes[i]
            half = size // 2
            # 扩大选中范围，增加margin像素的容差
            if (cx - half - margin) <= x <= (cx + half + margin) and (cy - half - margin) <= y <= (cy + half + margin):
                return i
        return -1
    
    def _deleteBoxAtIndex(self, index):
        """删除指定索引的标注框"""
        if self.annotation_engine is None or index < 0 or index >= len(self.annotation_engine.boxes):
            return
        self.annotation_engine.boxes.pop(index)
        if index < len(self.annotation_engine.bottom_points):
            self.annotation_engine.bottom_points.pop(index)
        if index < len(self.annotation_engine.top_points):
            self.annotation_engine.top_points.pop(index)
        if hasattr(self.annotation_engine, 'init_level_points') and index < len(self.annotation_engine.init_level_points):
            self.annotation_engine.init_level_points.pop(index)
        if index < len(self.area_names):
            self.area_names.pop(index)
        if index < len(self.area_heights):
            self.area_heights.pop(index)
        if index < len(self.area_states):
            self.area_states.pop(index)
        self._updateDisplay()
    
    def _showContextMenu(self, global_pos, image_x, image_y):
        """显示右键上下文菜单"""
        if self.annotation_engine is None:
            return
        clicked_box_index = self._findBoxAtPosition(image_x, image_y)
        context_menu = QtWidgets.QMenu(self)
        if clicked_box_index >= 0:
            area_name = self.area_names[clicked_box_index] if clicked_box_index < len(self.area_names) else f"区域{clicked_box_index + 1}"
            delete_action = context_menu.addAction(f"删除区域: {area_name}")
            delete_action.setEnabled(True)
        else:
            delete_action = context_menu.addAction("删除区域")
            delete_action.setEnabled(False)
        action = context_menu.exec_(global_pos)
        if action == delete_action and clicked_box_index >= 0:
            self._deleteBoxAtIndex(clicked_box_index)
    
    def _onRightClick(self):
        """删除最后一个标注框"""
        if self.annotation_engine is None:
            return
        if self.annotation_engine.step == 0 and len(self.annotation_engine.boxes) > 0:
            self.annotation_engine.boxes.pop()
            if len(self.annotation_engine.bottom_points) > 0:
                self.annotation_engine.bottom_points.pop()
            if len(self.annotation_engine.top_points) > 0:
                self.annotation_engine.top_points.pop()
            if hasattr(self.annotation_engine, 'init_level_points') and len(self.annotation_engine.init_level_points) > 0:
                self.annotation_engine.init_level_points.pop()
            if len(self.area_names) > 0:
                self.area_names.pop()
            if len(self.area_heights) > 0:
                self.area_heights.pop()
            if len(self.area_states) > 0:
                self.area_states.pop()
            self._updateDisplay()
    
    def _onReset(self):
        """重置标注"""
        if self.annotation_engine is not None:
            self.annotation_engine.reset_annotation()
            self.drawing_box = False
            self._updateDisplay()
    
    def _onComplete(self):
        """完成标注"""
        if self.annotation_engine is not None:
            boxes = self.annotation_engine.boxes
            bottoms = self.annotation_engine.bottom_points
            tops = self.annotation_engine.top_points
            init_levels = getattr(self.annotation_engine, 'init_level_points', [])
            # 直接发射annotationCompleted信号，包含init_levels
            self.annotationCompleted.emit(boxes, bottoms, tops, init_levels)
            self.close()

    def wheelEvent(self, event):
        """鼠标滚轮事件 - ROI框缩放"""
        if self.annotation_engine is None:
            return
        delta = event.angleDelta().y()
        mouse_pos = event.pos()
        image_x, image_y = self._labelToImageCoords(mouse_pos.x(), mouse_pos.y())
        
        box_index = self._findBoxAtPosition(image_x, image_y)
        if box_index < 0:
            box_index = self.selected_box_index
        
        if box_index >= 0 and box_index < len(self.annotation_engine.boxes):
            cx, cy, size = self.annotation_engine.boxes[box_index]
            if delta > 0:
                new_size = size + self.roi_scale_step
            else:
                new_size = max(32, size - self.roi_scale_step)
            new_size = ((new_size + 31) // 32) * 32
            
            if new_size != size:
                self.annotation_engine.boxes[box_index] = (cx, cy, new_size)
                half_new = new_size // 2
                if box_index < len(self.annotation_engine.bottom_points):
                    new_by = cy + half_new - (new_size * 0.1)
                    self.annotation_engine.bottom_points[box_index] = (cx, int(new_by))
                if box_index < len(self.annotation_engine.top_points):
                    new_ty = cy - half_new + (new_size * 0.1)
                    self.annotation_engine.top_points[box_index] = (cx, int(new_ty))
                # 更新初始液位线位置（保持相对位置比例）
                if hasattr(self.annotation_engine, 'init_level_points') and box_index < len(self.annotation_engine.init_level_points):
                    new_by = cy + half_new - (new_size * 0.1)
                    new_ty = cy - half_new + (new_size * 0.1)
                    # 初始液位线保持在中间位置
                    new_init_y = (new_ty + new_by) / 2
                    self.annotation_engine.init_level_points[box_index] = (cx, int(new_init_y))
                self._updateDisplay()
        event.accept()
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Escape and self.edit_widget is not None:
            self._cancelEdit()
            return
        
        if event.key() == Qt.Key_R:
            self._onReset()
        elif event.key() == Qt.Key_C:
            self._onComplete()
        elif event.key() == Qt.Key_D:
            self._onRightClick()
        elif event.key() == Qt.Key_U:
            self._onRightClick()
        elif event.key() == Qt.Key_S:
            self._onComplete()
        elif event.key() == Qt.Key_H:
            self._toggleHelpDisplay()
        elif event.key() == Qt.Key_F:
            if self.physical_zoom_controller and self.physical_zoom_enabled:
                self.physical_zoom_controller.auto_focus()
        elif event.key() == Qt.Key_1:
            self._quickSetHeight(0, "20mm")
        elif event.key() == Qt.Key_2:
            self._quickSetHeight(1, "20mm")
        elif event.key() == Qt.Key_3:
            self._quickSetHeight(2, "20mm")
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
    
    def _toggleHelpDisplay(self):
        """切换帮助信息显示状态"""
        if not hasattr(self, '_help_visible'):
            self._help_visible = True
        self._help_visible = not self._help_visible
        self._updateDisplay()
    
    def _quickSetHeight(self, area_index, height_value):
        """快速设置指定区域的高度"""
        if self.annotation_engine is None or area_index < 0 or area_index >= len(self.annotation_engine.boxes):
            return
        self._ensureAreaConfig(area_index)
        self.area_heights[area_index] = height_value
        self._updateDisplay()
    
    def _cancelEdit(self):
        """取消编辑"""
        if self.edit_widget is not None:
            self.edit_widget.deleteLater()
            self.edit_widget = None
            self.editing_area_index = -1
            self.editing_type = None
    
    def closeEvent(self, event):
        """关闭事件"""
        self.annotationCancelled.emit()
        event.accept()
    
    def showAnnotationCompleted(self, boxes, bottoms, tops, init_levels=None):
        """显示标注完成"""
        if init_levels is None:
            init_levels = []
        self.annotationCompleted.emit(boxes, bottoms, tops, init_levels)
        self.close()
    
    def showAnnotationError(self, message):
        """显示标注错误"""
        pass
