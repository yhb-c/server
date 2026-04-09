#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from qtpy import QtWidgets, QtCore, QtGui
from qtpy import uic

class TestVideoPage(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Page0 视频监控页面预览")

        # 加载UI文件
        ui_file = os.path.join(project_root, 'client', 'ui', 'page0_video.ui')
        print(f"UI文件路径: {ui_file}")
        print(f"UI文件是否存在: {os.path.exists(ui_file)}")

        try:
            self.central_widget = uic.loadUi(ui_file)
            self.setCentralWidget(self.central_widget)
        except Exception as e:
            print(f"加载UI文件失败: {e}")
            import traceback
            traceback.print_exc()
            raise

        # 设置窗口大小
        self.resize(1920, 1080)

        # 添加一些示例内容以便查看布局
        self._add_sample_content()

    def _add_sample_content(self):
        """添加示例内容"""
        try:
            # 在任务表格容器中添加示例标签
            mission_container = self.central_widget.findChild(QtWidgets.QWidget, "missionTable")
            if mission_container:
                layout = QtWidgets.QVBoxLayout(mission_container)
                label = QtWidgets.QLabel("任务表格区域\n(MissionPanel)")
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setStyleSheet("background-color: #2b2b2b; color: white; font-size: 16px; padding: 20px;")
                layout.addWidget(label)

            # 在通道容器中添加示例通道面板
            channel_container = self.central_widget.findChild(QtWidgets.QWidget, "defaultChannelContainer")
            if channel_container:
                # 创建16个示例通道面板 (2列 x 8行)
                for i in range(16):
                    row = i // 2
                    col = i % 2
                    x = 30 + col * (620 + 20)
                    y = 10 + row * (465 + 20)

                    panel = QtWidgets.QLabel(channel_container)
                    panel.setText(f"通道 {i+1}\n620x465")
                    panel.setAlignment(QtCore.Qt.AlignCenter)
                    panel.setStyleSheet("""
                        background-color: #1e1e1e;
                        color: #00ff00;
                        border: 2px solid #444;
                        font-size: 14px;
                    """)
                    panel.setGeometry(x, y, 620, 465)

            # 在曲线面板容器中添加示例标签
            curve_panel = self.central_widget.findChild(QtWidgets.QWidget, "curvePanel")
            if curve_panel:
                layout = QtWidgets.QVBoxLayout(curve_panel)
                label = QtWidgets.QLabel("曲线面板区域\n(CurvePanel)")
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setStyleSheet("background-color: #2b2b2b; color: white; font-size: 16px; padding: 20px;")
                layout.addWidget(label)

            # 在曲线通道容器中添加示例
            curve_container = self.central_widget.findChild(QtWidgets.QWidget, "curveChannelContainer")
            if curve_container:
                layout = QtWidgets.QVBoxLayout(curve_container)
                label = QtWidgets.QLabel("垂直通道列表区域")
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-size: 14px; padding: 20px;")
                layout.addWidget(label)

            # 添加模式切换按钮
            self._add_mode_switch_button()

        except Exception as e:
            print(f"添加示例内容时出错: {e}")

    def _add_mode_switch_button(self):
        """添加模式切换按钮"""
        try:
            # 创建浮动按钮
            self.mode_button = QtWidgets.QPushButton("切换到曲线模式", self.central_widget)
            self.mode_button.setGeometry(10, 10, 150, 40)
            self.mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
            """)
            self.mode_button.clicked.connect(self._toggle_mode)
            self.mode_button.raise_()

            self.current_mode = 0

        except Exception as e:
            print(f"添加切换按钮时出错: {e}")

    def _toggle_mode(self):
        """切换显示模式"""
        try:
            video_stack = self.central_widget.findChild(QtWidgets.QStackedWidget, "videoLayoutStack")
            if video_stack:
                self.current_mode = 1 - self.current_mode
                video_stack.setCurrentIndex(self.current_mode)

                if self.current_mode == 0:
                    self.mode_button.setText("切换到曲线模式")
                else:
                    self.mode_button.setText("切换到默认模式")
        except Exception as e:
            print(f"切换模式时出错: {e}")


def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
    except Exception as e:
        print(f"创建QApplication失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 设置应用样式
    try:
        app.setStyle('Fusion')
    except Exception as e:
        print(f"设置样式失败: {e}")

    # 设置深色主题
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)

    try:
        window = TestVideoPage()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"运行窗口失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
