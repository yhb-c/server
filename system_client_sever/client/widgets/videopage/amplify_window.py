# -*- coding: utf-8 -*-

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import cv2
import numpy as np


class AmplifyWindow(QtWidgets.QWidget):
    """
    全屏放大显示窗口（与标注界面样式一致）
    
    只负责UI控件设计和发送信号，业务逻辑由handler处理
    """
    
    # 自定义信号
    windowClosed = QtCore.Signal(str)  # 窗口关闭信号，传递channel_id
    mouseClicked = QtCore.Signal(int, int)  # 鼠标点击信号，传递x, y坐标
    wheelScrolled = QtCore.Signal(int)  # 鼠标滚轮信号，传递滚动方向(1或-1)
    keyPressed = QtCore.Signal(int)  # 键盘按键信号，传递按键码
    
    def __init__(self, channel_id, channel_name="通道", parent=None):
        super(AmplifyWindow, self).__init__(parent)
        
        self._channel_id = channel_id
        self._channel_name = channel_name
        self._parent = parent
        
        # 设置窗口属性（与标注界面一致）
        self.setWindowTitle(f"放大显示 - {channel_name}")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
        #  设置为全屏模式（与标注界面一致）
        self.showFullScreen()
        
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建视频显示区域
        self.videoLabel = QtWidgets.QLabel()
        self.videoLabel.setAlignment(Qt.AlignCenter)
        self.videoLabel.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: none;
            }
        """)
        
        # 启用鼠标跟踪以接收鼠标事件
        self.videoLabel.setMouseTracking(True)
        self.videoLabel.setFocusPolicy(Qt.StrongFocus)
        
        main_layout.addWidget(self.videoLabel)
        
        # 🔥 改为在图像上绘制说明文字（与标注界面一致）
        # 不再创建QWidget容器
        
        # 连接信号
        self._connectSignals()
    
    def _drawInstructionText(self, img):
        """在图像右上角绘制操作说明文字（与标注界面一致）"""
        if img is None:
            return
        
        # 检查是否显示帮助信息
        if not hasattr(self, '_help_visible'):
            self._help_visible = True  # 默认显示
        
        if not self._help_visible:
            # 如果隐藏帮助，只显示一个简单的提示
            try:
                from PIL import Image, ImageDraw, ImageFont
                import numpy as np
                
                height, width = img.shape[:2]
                
                # 简单提示
                simple_text = "按 H 键显示帮助"
                
                # 计算位置（右上角）
                text_width = 120
                text_height = 30
                start_x = width - text_width - 10
                start_y = 10
                
                # 绘制半透明背景
                overlay = img.copy()
                cv2.rectangle(overlay, (start_x - 5, start_y - 5), 
                              (start_x + text_width + 5, start_y + text_height + 5), 
                              (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
                
                # 转换为PIL图像
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                draw = ImageDraw.Draw(pil_img)
                
                # 加载字体
                try:
                    font = ImageFont.truetype("msyh.ttc", 14)
                except:
                    font = ImageFont.load_default()
                
                # 绘制文字
                draw.text((start_x, start_y + 8), simple_text, fill=(255, 255, 255), font=font)
                
                # 转换回 OpenCV 图像
                img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                img[:] = img_bgr[:]
                
                # 绘制边框
                cv2.rectangle(img, (start_x - 5, start_y - 5), 
                             (start_x + text_width + 5, start_y + text_height + 5), 
                             (128, 128, 128), 1)
                
            except ImportError:
                # 如果没有PIL，使用OpenCV绘制
                height, width = img.shape[:2]
                cv2.putText(img, "Press H for Help", (width - 150, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            return
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np
            
            # 获取图像尺寸
            height, width = img.shape[:2]
            
            # 放大界面操作说明（右上角）
            instructions = [
                "放大显示操作指南",
                "滚轮 - 调整变焦倍数",
                "左键 - 设置变焦中心点",
                "R - 重置变焦中心",
                "H - 切换帮助显示",
                "ESC - 关闭窗口"
            ]
            
            # 计算文字区域位置（右上角，紧贴顶部）
            text_width = 280
            line_height = 24
            text_height = len(instructions) * line_height + 15
            start_x = width - text_width - 5
            start_y = 0
            
            # 绘制半透明背景（紧贴顶部）
            overlay = img.copy()
            cv2.rectangle(overlay, (start_x - 10, start_y), 
                          (start_x + text_width + 10, start_y + text_height + 10), 
                          (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
            
            # 将OpenCV图像转换为PIL图像
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            draw = ImageDraw.Draw(pil_img)
            
            # 尝试加载中文字体
            try:
                font = ImageFont.truetype("simhei.ttf", 16)
            except:
                try:
                    font = ImageFont.truetype("msyh.ttc", 16)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
            
            # 绘制文字（从顶部开始）
            for i, instruction in enumerate(instructions):
                y_pos = start_y + 5 + i * line_height
                draw.text((start_x, y_pos), instruction, fill=(255, 255, 255), font=font)
            
            # 将PIL图像转换回OpenCV图像
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            img[:] = img_bgr[:]
            
            # 绘制边框
            cv2.rectangle(img, (start_x - 10, start_y), 
                         (start_x + text_width + 10, start_y + text_height + 10), 
                         (255, 255, 255), 2)
            
        except ImportError:
            # 如果没有PIL，使用英文替代
            height, width = img.shape[:2]
            cv2.putText(img, "Zoom Control", (width - 200, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(img, "Scroll=Zoom, Click=Center, R=Reset, H=Help, ESC=Close", 
                       (width - 500, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    def _drawStatusText(self, img):
        """在图像左上角绘制状态文字（与标注界面一致）"""
        if img is None:
            return
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np
            
            height, width = img.shape[:2]
            
            # 状态文字（左上角）
            status_lines = [
                f"变焦倍数: {self._zoom_factor:.1f}x" if hasattr(self, '_zoom_factor') else "变焦倍数: 1.0x",
                f"焦点: ({self._center_x}, {self._center_y})" if hasattr(self, '_center_x') else "焦点: (960, 540)"
            ]
            
            # 计算文字区域位置（左上角，紧贴顶部）
            text_width = 220
            line_height = 24
            text_height = len(status_lines) * line_height + 15
            start_x = 5
            start_y = 0
            
            # 绘制半透明背景
            overlay = img.copy()
            cv2.rectangle(overlay, (start_x - 5, start_y), 
                          (start_x + text_width + 5, start_y + text_height + 10), 
                          (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
            
            # 将OpenCV图像转换为PIL图像
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            draw = ImageDraw.Draw(pil_img)
            
            # 尝试加载字体
            try:
                font = ImageFont.truetype("msyh.ttc", 16)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except:
                    font = ImageFont.load_default()
            
            # 绘制文字（黄色，与标注界面一致）
            for i, status_line in enumerate(status_lines):
                y_pos = start_y + 5 + i * line_height
                draw.text((start_x, y_pos), status_line, fill=(0, 255, 255), font=font)
            
            # 将PIL图像转换回OpenCV图像
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            img[:] = img_bgr[:]
            
            # 绘制边框
            cv2.rectangle(img, (start_x - 5, start_y), 
                         (start_x + text_width + 5, start_y + text_height + 10), 
                         (0, 255, 255), 2)
            
        except ImportError:
            # 如果没有PIL，使用OpenCV绘制
            height, width = img.shape[:2]
            zoom_text = f"Zoom: {self._zoom_factor:.1f}x" if hasattr(self, '_zoom_factor') else "Zoom: 1.0x"
            center_text = f"Center: ({self._center_x}, {self._center_y})" if hasattr(self, '_center_x') else "Center: (960, 540)"
            cv2.putText(img, zoom_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(img, center_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    def _connectSignals(self):
        """连接信号槽"""
        # 注意：事件处理需要在主窗口级别，而不是在videoLabel上
        # 因为videoLabel是QLabel，默认不接收某些事件
        pass
    
    def displayFrame(self, frame):
        """
        显示视频帧（纯UI操作，与全屏标注界面一致）
        
        缩放图像到适合显示区域的尺寸，保持宽高比并居中显示
        
        Args:
            frame: numpy.ndarray, BGR格式的图像帧
        """
        if frame is None:
            return
        
        try:
            # 🔥 在显示前绘制说明文字和状态信息
            display_frame = frame.copy()
            self._drawStatusText(display_frame)  # 左上角：状态信息
            self._drawInstructionText(display_frame)  # 右上角：操作说明
            
            # 获取图像和显示区域尺寸
            img_height, img_width = display_frame.shape[:2]
            label_width = self.videoLabel.width()
            label_height = self.videoLabel.height()
            
            # 🔥 关键修复：计算缩放比例，保持宽高比（与全屏标注界面一致）
            if label_width > 0 and label_height > 0:
                scale_x = label_width / img_width
                scale_y = label_height / img_height
                scale_factor = min(scale_x, scale_y)
                
                # 缩放图像
                scaled_width = int(img_width * scale_factor)
                scaled_height = int(img_height * scale_factor)
                display_frame = cv2.resize(display_frame, (scaled_width, scaled_height))
            
            # 转换BGR到RGB
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # 获取图像尺寸
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # 转换为QImage
            q_image = QtGui.QImage(
                rgb_frame.data, 
                w, h, 
                bytes_per_line, 
                QtGui.QImage.Format_RGB888
            )
            
            # 显示到Label（居中对齐已在初始化时设置）
            pixmap = QtGui.QPixmap.fromImage(q_image)
            self.videoLabel.setPixmap(pixmap)
            
        except Exception as e:
            pass  # 静默处理显示错误
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        pass
        # 发送窗口关闭信号
        self.windowClosed.emit(self._channel_id)
        event.accept()
    
    def onMousePress(self, event):
        """鼠标左键点击事件 - 发送信号"""
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()
            click_x, click_y = click_pos.x(), click_pos.y()
            self.mouseClicked.emit(click_x, click_y)
    
    def onWheelEvent(self, event):
        """鼠标滚轮事件 - 发送信号"""
        delta = event.angleDelta().y()
        direction = 1 if delta > 0 else -1
        self.wheelScrolled.emit(direction)
    
    def onKeyPress(self, event):
        """键盘事件处理 - 发送信号"""
        key = event.key()
        self.keyPressed.emit(key)
        
        # ESC键直接关闭窗口
        if key == Qt.Key_Escape:
            self.close()
    
    def wheelEvent(self, event):
        """鼠标滚轮事件处理（窗口级别）"""
        self.onWheelEvent(event)
        event.accept()
    
    def mousePressEvent(self, event):
        """鼠标点击事件处理（窗口级别）"""
        self.onMousePress(event)
        event.accept()
    
    def keyPressEvent(self, event):
        """键盘事件处理（窗口级别）"""
        self.onKeyPress(event)
        super(AmplifyWindow, self).keyPressEvent(event)
    
    def updateStatusHint(self, zoom_factor=None, center_x=None, center_y=None):
        """更新状态信息（用于绘制在左上角）"""
        # 🔥 改为存储状态变量，在displayFrame时绘制
        if zoom_factor is not None:
            self._zoom_factor = zoom_factor
        if center_x is not None and center_y is not None:
            self._center_x = center_x
            self._center_y = center_y
    
    def toggleHelpVisibility(self):
        """切换帮助信息显示/隐藏"""
        if not hasattr(self, '_help_visible'):
            self._help_visible = True
        self._help_visible = not self._help_visible
    
    def showHint(self):
        """显示交互说明"""
        self._help_visible = True
    
    def hideHint(self):
        """隐藏交互说明"""
        self._help_visible = False


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建全屏窗口
    window = AmplifyWindow("test_channel", "测试通道")
    window.show()
    
    sys.exit(app.exec_())