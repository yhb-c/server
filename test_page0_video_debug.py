"""
调试版本 - 测试page0_video.ui界面文件
"""
import sys
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))

def main():
    app = QApplication(sys.argv)
    
    # 加载UI文件
    window = uic.loadUi('client/ui/page0_video.ui')
    
    print("=== 调试信息 ===")
    
    # 查找所有控件
    preview_widget = window.findChild(QWidget, "videoWidget_preview")
    print(f"预览控件: {preview_widget}")
    if preview_widget:
        print(f"  尺寸: {preview_widget.size()}")
        print(f"  最小尺寸: {preview_widget.minimumSize()}")
        print(f"  最大尺寸: {preview_widget.maximumSize()}")
    
    small_container = window.findChild(QWidget, "smallVideosContainer")
    print(f"小视频容器: {small_container}")
    if small_container:
        print(f"  尺寸: {small_container.size()}")
        print(f"  最小尺寸: {small_container.minimumSize()}")
    
    for i in range(8):
        video_widget = window.findChild(QWidget, f"videoWidget_{i}")
        if video_widget:
            print(f"找到 videoWidget_{i}: 尺寸={video_widget.size()}")
        else:
            print(f"未找到 videoWidget_{i}")
    
    # 在大预览区域添加占位文本
    if preview_widget:
        layout = QVBoxLayout(preview_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("预览区域 1200x900")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(label)
        print("已添加预览区域标签")
    
    # 在8个小视频区域添加占位文本
    for i in range(8):
        video_widget = window.findChild(QWidget, f"videoWidget_{i}")
        if video_widget:
            layout = QVBoxLayout(video_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(f"CH{i+1}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: white; font-size: 12px;")
            layout.addWidget(label)
            print(f"已添加通道{i+1}标签")
    
    print("=== 显示窗口 ===")
    # 显示窗口
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
