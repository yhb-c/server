"""
检查UI控件的实际显示尺寸
"""
import sys
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))

def check_sizes():
    app = QApplication(sys.argv)
    
    # 加载UI文件
    window = uic.loadUi('client/ui/page0_video.ui')
    window.show()
    
    # 等待窗口完全显示后再检查尺寸
    def print_sizes():
        print("=" * 60)
        print("实际显示尺寸检查")
        print("=" * 60)
        
        # 主窗口
        print(f"\n主窗口:")
        print(f"  尺寸: {window.width()} x {window.height()}")
        
        # 任务表格
        mission_table = window.findChild(QWidget, "missionTable")
        if mission_table:
            print(f"\n任务表格 (missionTable):")
            print(f"  尺寸: {mission_table.width()} x {mission_table.height()}")
        
        # 大预览区域
        preview = window.findChild(QWidget, "videoWidget_preview")
        if preview:
            print(f"\n大预览区域 (videoWidget_preview):")
            print(f"  尺寸: {preview.width()} x {preview.height()}")
            print(f"  比例: {preview.width() / preview.height():.2f}:1")
            if abs(preview.width() / preview.height() - 16/9) < 0.01:
                print(f"  ✓ 这是 16:9 比例")
            elif abs(preview.width() / preview.height() - 4/3) < 0.01:
                print(f"  ✓ 这是 4:3 比例")
        
        # 小视频容器
        small_container = window.findChild(QWidget, "smallVideosContainer")
        if small_container:
            print(f"\n小视频容器 (smallVideosContainer):")
            print(f"  尺寸: {small_container.width()} x {small_container.height()}")
        
        # 8个小视频
        print(f"\n8个小视频区域:")
        for i in range(8):
            video_widget = window.findChild(QWidget, f"videoWidget_{i}")
            if video_widget:
                print(f"  videoWidget_{i}: {video_widget.width()} x {video_widget.height()}")
        
        print("\n" + "=" * 60)
        
        # 退出应用
        QTimer.singleShot(1000, app.quit)
    
    # 延迟500ms后检查尺寸，确保窗口已完全渲染
    QTimer.singleShot(500, print_sizes)
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    check_sizes()
