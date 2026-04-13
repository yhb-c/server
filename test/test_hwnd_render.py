# -*- coding: utf-8 -*-
"""
HWND渲染测试代码 - 4路视频
使用海康SDK的PlayCtrl直接渲染到窗口
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton
from PyQt5.QtCore import Qt

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
hk_sdk_path = os.path.join(project_root, 'client', 'handlers', 'videopage', 'HK_SDK')
sys.path.insert(0, hk_sdk_path)

print(f"HK_SDK路径: {hk_sdk_path}")
print(f"路径是否存在: {os.path.exists(hk_sdk_path)}")

try:
    from HKcapture import HKcapture
    print("HKcapture导入成功")
except Exception as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.captures = []  # 存储4个capture对象
        self.video_labels = []  # 存储4个视频显示区域
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('HWND渲染测试 - 4路摄像头预览')
        self.setGeometry(100, 100, 1280, 800)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 视频网格布局（2x2）
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        # 创建4个视频显示区域
        for i in range(4):
            video_label = QLabel()
            video_label.setFixedSize(640, 360)  # 每个窗口640x360
            video_label.setStyleSheet("background-color: black; border: 2px solid gray;")
            video_label.setAlignment(Qt.AlignCenter)
            video_label.setText(f"通道{i+1}\n等待视频流...")

            # 添加到网格（2行2列）
            row = i // 2
            col = i % 2
            grid_layout.addWidget(video_label, row, col)

            self.video_labels.append(video_label)

        # 按钮布局
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)

        # 开始按钮
        self.start_btn = QPushButton('开始预览（4路）')
        self.start_btn.clicked.connect(self.start_preview)
        button_layout.addWidget(self.start_btn)

        # 停止按钮
        self.stop_btn = QPushButton('停止预览')
        self.stop_btn.clicked.connect(self.stop_preview)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

    def start_preview(self):
        """开始预览4路视频"""
        try:
            # 摄像头配置（这里用同一个摄像头的4个通道，你可以改成4个不同的摄像头）
            camera_configs = [
                {"ip": "192.168.0.27", "channel": 1, "label_index": 0},
                {"ip": "192.168.0.27", "channel": 1, "label_index": 1},
                {"ip": "192.168.0.27", "channel": 1, "label_index": 2},
                {"ip": "192.168.0.27", "channel": 1, "label_index": 3},
            ]

            username = "admin"
            password = "cei345678"
            port = 8000

            print(f"\n========== 开始启动4路视频预览 ==========")

            # 确保窗口已显示
            QApplication.processEvents()

            # 创建4个HKcapture对象
            for i, config in enumerate(camera_configs):
                print(f"\n--- 启动通道{i+1} ---")
                print(f"摄像头: {config['ip']}, 通道: {config['channel']}")

                # 创建HKcapture对象
                capture = HKcapture(
                    source=config['ip'],
                    username=username,
                    password=password,
                    port=port,
                    channel=config['channel'],
                    fps=25,
                    debug=False,
                    decode_device='cpu'  # CPU软件解码
                )

                # 获取对应的视频标签窗口句柄
                label_index = config['label_index']
                hwnd = int(self.video_labels[label_index].winId())
                print(f"窗口句柄: {hwnd}")

                # 设置HWND
                capture.set_hwnd(hwnd)

                # 打开视频流
                if capture.open():
                    print(f"通道{i+1} 视频流打开成功")

                    # 启动HWND渲染
                    capture.start_render()
                    print(f"通道{i+1} HWND渲染已启动")

                    self.video_labels[label_index].setText("")
                    self.captures.append(capture)
                else:
                    print(f"通道{i+1} 视频流打开失败")
                    self.video_labels[label_index].setText(f"通道{i+1}\n连接失败")

            if len(self.captures) > 0:
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                print(f"\n========== 成功启动 {len(self.captures)} 路视频 ==========")
            else:
                print("\n========== 所有通道启动失败 ==========")

        except Exception as e:
            print(f"启动预览失败: {e}")
            import traceback
            traceback.print_exc()

    def stop_preview(self):
        """停止预览"""
        try:
            print("\n========== 停止所有视频预览 ==========")

            for i, capture in enumerate(self.captures):
                print(f"正在停止通道{i+1}...")
                capture.release()
                self.video_labels[i].setText(f"通道{i+1}\n已停止")

            self.captures.clear()
            print("所有通道已停止")

            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

        except Exception as e:
            print(f"停止预览失败: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.stop_preview()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = VideoWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
