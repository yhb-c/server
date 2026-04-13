# -*- coding: utf-8 -*-
"""
GPU使用情况检测测试
通过监控GPU和CPU占用来判断HWND渲染是否使用GPU
"""
import sys
import os
import time
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PyQt5.QtCore import Qt, QTimer

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
hk_sdk_path = os.path.join(project_root, 'client', 'handlers', 'videopage', 'HK_SDK')
sys.path.insert(0, hk_sdk_path)

try:
    from HKcapture import HKcapture
    print("HKcapture导入成功")
except Exception as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    import psutil
    print("psutil导入成功")
except:
    print("psutil未安装，无法监控CPU")
    psutil = None

GPUtil = None  # 不使用GPUtil


class MonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.capture = None
        self.monitoring = False
        self.init_ui()

        # 定时器：每秒更新资源占用
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

    def init_ui(self):
        self.setWindowTitle('GPU使用检测 - HWND渲染测试')
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # 视频显示区域
        self.video_label = QLabel()
        self.video_label.setFixedSize(960, 540)
        self.video_label.setStyleSheet("background-color: black; border: 2px solid gray;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("等待视频流...")
        layout.addWidget(self.video_label)

        # 资源监控显示
        self.stats_text = QTextEdit()
        self.stats_text.setFixedHeight(100)
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)

        # 开始按钮
        self.start_btn = QPushButton('开始预览（CPU解码）')
        self.start_btn.clicked.connect(lambda: self.start_preview('cpu'))
        layout.addWidget(self.start_btn)

        # 硬件解码按钮
        self.hw_btn = QPushButton('开始预览（硬件解码）')
        self.hw_btn.clicked.connect(lambda: self.start_preview('hardware'))
        layout.addWidget(self.hw_btn)

        # 停止按钮
        self.stop_btn = QPushButton('停止预览')
        self.stop_btn.clicked.connect(self.stop_preview)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

    def start_preview(self, decode_mode):
        """开始预览"""
        try:
            camera_ip = "192.168.0.27"
            username = "admin"
            password = "cei345678"

            print(f"\n========== 开始预览（{decode_mode}解码）==========")

            self.capture = HKcapture(
                source=camera_ip,
                username=username,
                password=password,
                port=8000,
                channel=1,
                fps=25,
                debug=False,
                decode_device=decode_mode
            )

            QApplication.processEvents()
            hwnd = int(self.video_label.winId())
            self.capture.set_hwnd(hwnd)

            if self.capture.open():
                self.capture.start_render()
                self.video_label.setText("")
                self.start_btn.setEnabled(False)
                self.hw_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self.monitoring = True
                print(f"预览已启动（{decode_mode}解码）")
            else:
                print("连接失败")
                self.video_label.setText("连接失败")

        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()

    def stop_preview(self):
        """停止预览"""
        try:
            self.monitoring = False
            if self.capture:
                self.capture.release()
                self.capture = None

            self.video_label.setText("已停止")
            self.start_btn.setEnabled(True)
            self.hw_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            print("预览已停止")

        except Exception as e:
            print(f"停止失败: {e}")

    def update_stats(self):
        """更新资源占用统计"""
        if not self.monitoring:
            self.stats_text.setText("未运行")
            return

        stats = []

        # CPU占用
        if psutil:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            stats.append(f"CPU总占用: {cpu_percent:.1f}%")

            # 当前进程CPU占用
            process = psutil.Process()
            process_cpu = process.cpu_percent(interval=0.1)
            stats.append(f"本进程CPU: {process_cpu:.1f}%")
        else:
            stats.append("CPU: psutil未安装")

        # GPU占用（通过nvidia-smi检测）
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,name', '--format=csv,noheader,nounits'],
                                  capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for i, line in enumerate(lines):
                    parts = line.split(',')
                    if len(parts) >= 4:
                        gpu_util = parts[0].strip()
                        mem_used = parts[1].strip()
                        mem_total = parts[2].strip()
                        gpu_name = parts[3].strip()
                        stats.append(f"GPU{i} ({gpu_name}): {gpu_util}% | 显存: {mem_used}MB/{mem_total}MB")
            else:
                stats.append("GPU: 未检测到NVIDIA GPU")
        except FileNotFoundError:
            stats.append("GPU: nvidia-smi未找到（可能是Intel/AMD显卡或无独显）")
        except Exception as e:
            stats.append(f"GPU: 检测失败")

        self.stats_text.setText(" | ".join(stats))

    def closeEvent(self, event):
        self.stop_preview()
        event.accept()


def main():
    print("\n========== GPU使用检测工具 ==========")
    print("说明：")
    print("1. 点击'开始预览（CPU解码）'测试纯CPU模式")
    print("2. 点击'开始预览（硬件解码）'测试GPU解码模式")
    print("3. 观察资源占用变化判断GPU是否参与")
    print("\n如果需要完整监控，请安装：")
    print("  pip install psutil GPUtil")
    print("=====================================\n")

    app = QApplication(sys.argv)
    window = MonitorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
