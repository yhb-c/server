"""
测试page0_video.ui界面文件
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
    
    # 尝试导入并添加MissionPanel
    try:
        from widgets.videopage import MissionPanel
        
        # 找到missionTable容器
        mission_container = window.findChild(QWidget, "missionTable")
        if mission_container:
            # 创建布局
            layout = QVBoxLayout(mission_container)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # 创建并添加MissionPanel
            mission_panel = MissionPanel()
            layout.addWidget(mission_panel)
            
            print("成功加载MissionPanel组件")
    except Exception as e:
        print(f"无法加载MissionPanel: {e}")
        print("显示占位文本")
        
        # 如果无法加载，显示占位文本
        mission_container = window.findChild(QWidget, "missionTable")
        if mission_container:
            layout = QVBoxLayout(mission_container)
            label = QLabel("任务表格区域\n(需要MissionPanel组件)")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #666; font-size: 14px;")
            layout.addWidget(label)
    
    # 在大预览区域添加占位文本
    preview_widget = window.findChild(QWidget, "videoWidget_preview")
    if preview_widget:
        layout = QVBoxLayout(preview_widget)
        label = QLabel("预览区域\n点击小视频切换显示")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #999; font-size: 18px;")
        layout.addWidget(label)
    
    # 在8个小视频区域添加占位文本
    for i in range(8):
        video_widget = window.findChild(QWidget, f"videoWidget_{i}")
        if video_widget:
            layout = QVBoxLayout(video_widget)
            label = QLabel(f"通道{i+1}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #999; font-size: 10px;")
            layout.addWidget(label)
    
    # 显示窗口
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
