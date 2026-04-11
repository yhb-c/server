"""
二维码检测脚本 - 使用海康SDK和PyQt5显示预览窗口
支持从海康威视摄像头RTSP流读取视频，使用pyzbar检测二维码并用红框标注
"""
import sys
import os
import cv2
import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

# 设置Java环境变量
java_home = 'C:/Users/admin/anaconda3/envs/yeweienv/Library'
java_bin = 'C:/Users/admin/anaconda3/envs/yeweienv/Library/bin'
os.environ['JAVA_HOME'] = java_home
os.environ['PATH'] = java_bin + ';' + os.environ.get('PATH', '')

# 验证Java环境
import subprocess
try:
    result = subprocess.run([os.path.join(java_bin, 'java.exe'), '-version'],
                          capture_output=True, text=True, timeout=5)
    print(f"Java环境已配置: {result.stderr.split()[2] if result.stderr else 'OK'}")
except Exception as e:
    print(f"警告: Java环境配置可能有问题: {e}")

from pyzxing import BarCodeReader

# 添加HK_SDK路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'handlers', 'videopage', 'HK_SDK'))
from HKcapture import HKcapture


class QRCodeDetector(QtWidgets.QMainWindow):
    """二维码检测主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("二维码检测器 (海康SDK + ZXing高精度)")
        self.setGeometry(100, 100, 1280, 720)

        # 视频捕获对象
        self.cap = None
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)

        # 创建OpenCV QRCodeDetector（高精度）
        self.qr_detector = cv2.QRCodeDetector()

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        # 主容器
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QVBoxLayout(main_widget)

        # 控制面板
        control_panel = QtWidgets.QWidget()
        control_layout = QtWidgets.QHBoxLayout(control_panel)

        # RTSP地址输入
        control_layout.addWidget(QtWidgets.QLabel("RTSP地址:"))
        self.address_input = QtWidgets.QLineEdit()
        self.address_input.setText("rtsp://admin:cei345678@192.168.0.27:8000/stream1")
        control_layout.addWidget(self.address_input)

        # 开始按钮
        self.start_btn = QtWidgets.QPushButton("开始检测")
        self.start_btn.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_btn)

        # 停止按钮
        self.stop_btn = QtWidgets.QPushButton("停止检测")
        self.stop_btn.clicked.connect(self.stop_detection)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_layout.addStretch()
        main_layout.addWidget(control_panel)

        # 视频显示区域
        self.video_label = QtWidgets.QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; border: 2px solid #555;")
        self.video_label.setMinimumSize(1200, 600)
        main_layout.addWidget(self.video_label)

        # 状态栏
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        main_layout.addWidget(self.status_label)

    def start_detection(self):
        """开始检测"""
        # 释放之前的捕获对象
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        try:
            rtsp_url = self.address_input.text().strip()
            if not rtsp_url:
                self.status_label.setText("错误: 请输入RTSP地址")
                return

            self.status_label.setText(f"正在连接: {rtsp_url}")

            # 解析RTSP地址
            username, password, ip, port = self._parse_rtsp(rtsp_url)

            if not ip or not username or not password:
                self.status_label.setText("错误: RTSP地址格式不正确")
                return

            # 创建HKcapture对象
            self.cap = HKcapture(
                source=rtsp_url,
                username=username,
                password=password,
                port=port,
                channel=1,
                fps=25,
                debug=True
            )

            # 打开连接
            if not self.cap.open():
                self.status_label.setText("错误: 无法连接到摄像头")
                self.cap = None
                return

            # 开始捕获
            if not self.cap.start_capture():
                self.status_label.setText("错误: 无法开始视频捕获")
                self.cap.release()
                self.cap = None
                return

            # 启动定时器更新画面
            self.timer.start(40)  # 25fps
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("检测中...")

        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def stop_detection(self):
        """停止检测"""
        self.timer.stop()
        if self.cap is not None:
            self.cap.stop_capture()
            self.cap.release()
            self.cap = None

        self.video_label.clear()
        self.video_label.setText("已停止")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("已停止")

    def update_frame(self):
        """更新视频帧"""
        if self.cap is None:
            self.stop_detection()
            return

        # 读取最新帧
        ret, frame = self.cap.read_latest()

        if not ret or frame is None:
            # 显示等待信息
            if not hasattr(self, '_frame_count'):
                self._frame_count = 0
            self._frame_count += 1
            if self._frame_count % 25 == 0:  # 每秒显示一次
                print(f"等待帧数据... ({self._frame_count // 25}秒)")
            return

        # 成功读取到帧
        if not hasattr(self, '_first_frame_received'):
            self._first_frame_received = True
            print(f"[调试] 成功接收到第一帧!")
            print(f"[调试] 帧形状: {frame.shape}")
            print(f"[调试] 帧数据类型: {frame.dtype}")
            print(f"[调试] 帧通道数: {frame.shape[2] if len(frame.shape) == 3 else 1}")
            # 检查颜色：取中心像素
            if len(frame.shape) == 3:
                h, w = frame.shape[:2]
                center_pixel = frame[h//2, w//2]
                print(f"[调试] 中心像素值 (应该是BGR顺序): {center_pixel}")
            self.status_label.setText("已接收到视频流，开始检测...")

        # 检测二维码
        frame_with_qr = self.detect_qrcode(frame)

        # 转换为Qt可显示的格式
        self.display_frame(frame_with_qr)

    def detect_qrcode(self, frame):
        """
        使用OpenCV QRCodeDetector检测二维码并标注（高精度）

        Args:
            frame: 输入图像帧 (BGR格式)

        Returns:
            标注后的图像帧
        """
        # 复制帧以避免修改原始数据
        output_frame = frame.copy()

        try:
            # 使用OpenCV QRCodeDetector检测二维码（直接使用BGR格式）
            data, points, straight_qrcode = self.qr_detector.detectAndDecode(frame)

            if data:
                print(f"[成功] 检测到二维码! 内容: {data}")
                # 绘制红色边框
                if points is not None and len(points) > 0:
                    points = points[0].astype(int)
                    cv2.polylines(output_frame, [points], True, (0, 0, 255), 3)

                    # 在二维码上方显示解码内容
                    x, y = points[0]
                    text_pos = (x, max(y - 10, 20))

                    # 使用PIL绘制中文文本
                    from PIL import Image, ImageFont, ImageDraw
                    pil_img = Image.fromarray(cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB))
                    draw = ImageDraw.Draw(pil_img)
                    try:
                        font = ImageFont.truetype("msyh.ttc", 20)
                    except:
                        font = ImageFont.load_default()
                    draw.text(text_pos, f"QR: {data}", font=font, fill=(0, 255, 0))
                    output_frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                    # 更新状态栏
                    self.status_label.setText(f"检测到二维码: {data}")
            else:
                self.status_label.setText("检测中... (未检测到二维码)")

        except Exception as e:
            print(f"二维码检测错误: {e}")
            import traceback
            traceback.print_exc()

        return output_frame
        """
        使用ZXing检测二维码并标注（高精度）

        Args:
            frame: 输入图像帧 (BGR格式)

        Returns:
            标注后的图像帧
        """
        # 复制帧以避免修改原始数据
        output_frame = frame.copy()

        try:
            # 转换BGR到RGB (ZXing需要RGB格式)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 保存临时图像文件供ZXing读取（使用原始RGB图像，不做增强）
            from PIL import Image
            import time
            import tempfile
            # 使用临时目录避免文件堆积
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f'temp_qr_frame_{int(time.time() * 1000)}.png')
            img = Image.fromarray(rgb_frame)
            img.save(temp_file, format='PNG', compress_level=0)  # PNG无损格式

            # 调试：打印临时文件信息
            if not hasattr(self, '_debug_count'):
                self._debug_count = 0
            self._debug_count += 1
            if self._debug_count % 25 == 0:  # 每秒打印一次
                print(f"[调试] 已保存临时文件: {temp_file}, 大小: {os.path.getsize(temp_file)} bytes")

            # 使用ZXing检测二维码
            print(f"[调试] 开始调用ZXing检测，文件: {temp_file}")
            try:
                results = self.qr_reader.decode(temp_file)
                print(f"[调试] ZXing调用成功，返回结果类型: {type(results)}")
                print(f"[调试] ZXing返回结果: {results}")
            except Exception as e:
                print(f"[错误] ZXing调用失败: {e}")
                import traceback
                traceback.print_exc()
                results = None

            # 调试：打印检测结果
            if self._debug_count % 25 == 0:
                print(f"[调试-每秒] ZXing检测结果: {results}")
                if results:
                    for r in results:
                        print(f"[调试-每秒] 结果详情 - format: {r.get('format')}, parsed: {r.get('parsed')}, points: {r.get('points')}")
                # 保存一张测试图片供检查
                test_file = 'test_qr_debug.png'
                img.save(test_file, format='PNG')
                print(f"[调试-每秒] 已保存测试图片: {test_file}")

            # 立即删除临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"[警告] 无法删除临时文件 {temp_file}: {e}")

            # 过滤有效结果（必须包含parsed字段且不为空，并且格式为QR_CODE）
            valid_results = []
            if results:
                for result in results:
                    parsed_data = result.get('parsed', b'')
                    format_type = result.get('format', b'')
                    print(f"[调试-过滤] format={format_type}, parsed={parsed_data}, 是否QR_CODE={format_type == b'QR_CODE'}")
                    # 只处理QR_CODE格式
                    if parsed_data and parsed_data != b'' and format_type == b'QR_CODE':
                        valid_results.append(result)
                        print(f"[成功] 检测到二维码! 结果: {result}")

            if valid_results:
                for result in valid_results:
                    # 获取二维码数据
                    parsed_data = result.get('parsed', b'')
                    # 解码bytes为字符串
                    if isinstance(parsed_data, bytes):
                        try:
                            data = parsed_data.decode('gbk')  # 尝试GBK解码中文
                        except:
                            try:
                                data = parsed_data.decode('utf-8')  # 尝试UTF-8
                            except:
                                data = str(parsed_data)  # 最后转为字符串
                    else:
                        data = str(parsed_data)

                    # 获取边界框坐标 (ZXing返回的是元组列表)
                    points = result.get('points', [])

                    if len(points) >= 4:
                        # 绘制红色边框 (points是元组列表，格式为 [(x, y), ...])
                        pts = np.array([[int(p[0]), int(p[1])] for p in points], dtype=np.int32)
                        cv2.polylines(output_frame, [pts], True, (0, 0, 255), 3)

                        # 在二维码上方显示解码内容
                        x = int(points[0][0])
                        y = int(points[0][1])
                        text_pos = (x, max(y - 10, 20))

                        # 使用PIL绘制中文文本
                        from PIL import ImageFont, ImageDraw
                        pil_img = Image.fromarray(cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB))
                        draw = ImageDraw.Draw(pil_img)
                        # 使用系统字体显示中文
                        try:
                            font = ImageFont.truetype("msyh.ttc", 20)  # 微软雅黑
                        except:
                            font = ImageFont.load_default()
                        draw.text(text_pos, f"QR: {data}", font=font, fill=(0, 255, 0))
                        output_frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                        # 更新状态栏
                        self.status_label.setText(f"检测到二维码: {data}")
            else:
                self.status_label.setText("检测中... (未检测到二维码)")

        except Exception as e:
            print(f"二维码检测错误: {e}")
            import traceback
            traceback.print_exc()

        return output_frame

    def display_frame(self, frame):
        """
        在QLabel中显示图像帧

        Args:
            frame: OpenCV格式的图像帧 (BGR)
        """
        # 调试信息：显示转换前的帧信息
        if not hasattr(self, '_display_debug_printed'):
            self._display_debug_printed = True
            print(f"[调试-display_frame] 输入帧形状: {frame.shape}")
            print(f"[调试-display_frame] 输入帧数据类型: {frame.dtype}")
            if len(frame.shape) == 3:
                h, w = frame.shape[:2]
                center_pixel_before = frame[h//2, w//2]
                print(f"[调试-display_frame] 转换前中心像素 (BGR): {center_pixel_before}")

        # 检查帧的通道数
        if len(frame.shape) == 2:
            # 灰度图，转换为RGB
            print(f"[调试-display_frame] 检测到灰度图，转换为RGB")
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 3:
            # BGR图像，转换为RGB
            print(f"[调试-display_frame] 检测到BGR图像，转换为RGB")
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 调试信息：显示转换后的像素值
            if not hasattr(self, '_display_debug_printed2'):
                self._display_debug_printed2 = True
                h, w = rgb_frame.shape[:2]
                center_pixel_after = rgb_frame[h//2, w//2]
                print(f"[调试-display_frame] 转换后中心像素 (RGB): {center_pixel_after}")
                print(f"[调试-display_frame] 颜色通道是否交换: B={center_pixel_before[0]}->R={center_pixel_after[0]}, G={center_pixel_before[1]}->G={center_pixel_after[1]}, R={center_pixel_before[2]}->B={center_pixel_after[2]}")
        elif frame.shape[2] == 4:
            # BGRA图像，转换为RGB
            print(f"[调试-display_frame] 检测到BGRA图像，转换为RGB")
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        else:
            # 未知格式，直接使用
            print(f"[调试-display_frame] 未知格式，直接使用")
            rgb_frame = frame

        # 获取图像尺寸
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w

        # 确保数据是连续的
        rgb_frame = np.ascontiguousarray(rgb_frame)

        # 转换为QImage
        qt_image = QtGui.QImage(rgb_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)

        # 缩放到label大小（保持宽高比）
        scaled_pixmap = QtGui.QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 显示
        self.video_label.setPixmap(scaled_pixmap)

    def _parse_rtsp(self, rtsp_url):
        """
        解析RTSP URL

        Returns:
            tuple: (username, password, ip, port)
        """
        try:
            import re

            # RTSP格式: rtsp://username:password@ip:port/path
            if rtsp_url.startswith('rtsp://'):
                url_part = rtsp_url[7:]

                # 找到最后一个@符号
                last_at_index = url_part.rfind('@')

                if last_at_index != -1:
                    # 有认证信息
                    credentials_part = url_part[:last_at_index]
                    host_part = url_part[last_at_index + 1:]

                    # 分离用户名和密码
                    first_colon = credentials_part.find(':')

                    if first_colon != -1:
                        username = credentials_part[:first_colon]
                        password = credentials_part[first_colon + 1:]
                    else:
                        username = credentials_part
                        password = None
                else:
                    username = None
                    password = None
                    host_part = url_part

                # 提取IP和端口
                colon_idx = host_part.find(':')
                slash_idx = host_part.find('/')

                if colon_idx != -1:
                    ip = host_part[:colon_idx]
                    if slash_idx != -1:
                        port_str = host_part[colon_idx + 1:slash_idx]
                    else:
                        port_str = host_part[colon_idx + 1:]
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 8000
                else:
                    if slash_idx != -1:
                        ip = host_part[:slash_idx]
                    else:
                        ip = host_part
                    port = 8000

                return username, password, ip, port

            return None, None, None, 8000

        except Exception as e:
            print(f"解析RTSP地址错误: {e}")
            return None, None, None, 8000

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.stop_detection()
        event.accept()


def main():
    """主函数"""
    try:
        # 设置高DPI支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        app = QtWidgets.QApplication(sys.argv)

        # 设置应用样式
        app.setStyle('Fusion')

        # 创建主窗口
        window = QRCodeDetector()
        window.show()
        window.raise_()
        window.activateWindow()

        print("二维码检测器已启动 (使用海康SDK + ZXing高精度识别)")

        # 运行应用
        sys.exit(app.exec_())
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("正在启动二维码检测器 (海康SDK + ZXing高精度版本)...")
    main()
