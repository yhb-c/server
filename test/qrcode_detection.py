"""
二维码识别脚本
从RTSP相机流中实时识别二维码并用红色框标注
使用PyQt5显示实时预览窗口
"""

import cv2
import numpy as np
import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

class QRCodeDetectorThread(QThread):
    """二维码检测线程"""
    frame_ready = pyqtSignal(np.ndarray)
    qrcode_detected = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.cap = None
        self.qr_detector = cv2.QRCodeDetector()
        self.running = False

    def connect_camera(self):
        """连接RTSP相机"""
        self.status_update.emit(f"正在连接相机: {self.rtsp_url}")
        self.cap = cv2.VideoCapture(self.rtsp_url)

        if not self.cap.isOpened():
            self.status_update.emit("无法连接到RTSP相机")
            return False

        self.status_update.emit("相机连接成功")
        return True

    def detect_qrcode(self, frame):
        """
        检测图像中的二维码

        Args:
            frame: 输入图像帧

        Returns:
            (data, points) 二维码数据和角点坐标
        """
        # 使用OpenCV的QRCodeDetector检测二维码
        data, points, _ = self.qr_detector.detectAndDecode(frame)
        return data, points

    def draw_qrcode_box(self, frame, data, points):
        """
        在图像上绘制二维码边框

        Args:
            frame: 输入图像帧
            data: 二维码数据
            points: 二维码角点坐标

        Returns:
            标注后的图像
        """
        if points is not None and data:
            # 将points转换为整数坐标
            points = points[0].astype(int)

            # 绘制红色边框
            cv2.polylines(frame, [points], True, (0, 0, 255), 3)

            # 在二维码上方显示内容
            x = points[0][0]
            y = points[0][1] - 10

            # 绘制文本背景
            text = f"QR: {data[:30]}"
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x, y - text_height - 5), (x + text_width, y + 5), (0, 0, 255), -1)

            # 绘制文本
            cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # 发送检测到的二维码信号
            self.qrcode_detected.emit(data)

        return frame

    def run(self):
        """运行二维码检测线程"""
        if not self.connect_camera():
            return

        self.running = True
        self.status_update.emit("开始检测二维码")

        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                self.status_update.emit("无法读取视频帧")
                break

            # 检测二维码
            data, points = self.detect_qrcode(frame)

            # 绘制边框
            result_frame = self.draw_qrcode_box(frame.copy(), data, points)

            # 发送帧信号
            self.frame_ready.emit(result_frame)

        if self.cap:
            self.cap.release()
        self.status_update.emit("检测已停止")

    def stop(self):
        """停止检测"""
        self.running = False
        self.wait()


class QRCodeDetectorWindow(QMainWindow):
    """二维码检测主窗口"""

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.detector_thread = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("二维码实时检测")
        self.setGeometry(100, 100, 1000, 700)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建布局
        layout = QVBoxLayout()

        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("border: 2px solid #333; background-color: #000;")
        self.video_label.setMinimumSize(800, 600)
        layout.addWidget(self.video_label)

        # 状态标签
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.status_label)

        # 二维码内容标签
        self.qrcode_label = QLabel("二维码内容: 无")
        self.qrcode_label.setStyleSheet("font-size: 14px; padding: 5px; color: #0066cc;")
        layout.addWidget(self.qrcode_label)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 开始按钮
        self.start_button = QPushButton("开始检测")
        self.start_button.setStyleSheet("font-size: 14px; padding: 10px;")
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)

        # 停止按钮
        self.stop_button = QPushButton("停止检测")
        self.stop_button.setStyleSheet("font-size: 14px; padding: 10px;")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def start_detection(self):
        """开始检测"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # 创建检测线程
        self.detector_thread = QRCodeDetectorThread(self.rtsp_url)
        self.detector_thread.frame_ready.connect(self.update_frame)
        self.detector_thread.qrcode_detected.connect(self.update_qrcode)
        self.detector_thread.status_update.connect(self.update_status)
        self.detector_thread.start()

    def stop_detection(self):
        """停止检测"""
        if self.detector_thread:
            self.detector_thread.stop()
            self.detector_thread = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_status("检测已停止")

    def update_frame(self, frame):
        """更新视频帧"""
        # 转换为RGB格式
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 转换为QImage
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # 缩放到标签大小
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.video_label.setPixmap(scaled_pixmap)

    def update_qrcode(self, data):
        """更新二维码内容"""
        self.qrcode_label.setText(f"二维码内容: {data}")

    def update_status(self, status):
        """更新状态"""
        self.status_label.setText(f"状态: {status}")

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.detector_thread:
            self.detector_thread.stop()
        event.accept()

def main():
    # RTSP相机地址
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"

    # 创建应用
    app = QApplication(sys.argv)

    # 创建主窗口
    window = QRCodeDetectorWindow(rtsp_url)
    window.show()

    # 运行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
