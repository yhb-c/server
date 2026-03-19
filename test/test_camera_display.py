# 测试相机画面显示功能

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtWidgets, QtCore, QtGui
from client.function.channelpanel_handler import ChannelPanelHandler


class TestChannelPanel(QtWidgets.QLabel):
    """测试用的通道面板"""
    
    # 信号定义
    channelConnected = QtCore.Signal(str)
    channelDisconnected = QtCore.Signal(str)
    
    def __init__(self, channel_id, parent=None):
        super().__init__(parent)
        self.channel_id = channel_id
        self.is_connected = False
        
        # 设置基本属性
        self.setMinimumSize(320, 240)
        self.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setText("未打开通道")
        self.setScaledContents(True)
        
        # 创建控制按钮
        self.connect_btn = QtWidgets.QPushButton("连接", self)
        self.connect_btn.setGeometry(10, 10, 60, 30)
        self.connect_btn.clicked.connect(self._onConnectClicked)
        
        self.disconnect_btn = QtWidgets.QPushButton("断开", self)
        self.disconnect_btn.setGeometry(80, 10, 60, 30)
        self.disconnect_btn.clicked.connect(self._onDisconnectClicked)
        self.disconnect_btn.setEnabled(False)
        
        print(f"[测试面板] {channel_id} 初始化完成")
    
    def _onConnectClicked(self):
        """连接按钮点击"""
        if not self.is_connected:
            print(f"[测试面板] {self.channel_id} 发送连接信号")
            self.channelConnected.emit(self.channel_id)
    
    def _onDisconnectClicked(self):
        """断开按钮点击"""
        if self.is_connected:
            print(f"[测试面板] {self.channel_id} 发送断开信号")
            self.channelDisconnected.emit(self.channel_id)
    
    def displayFrame(self, pixmap):
        """显示视频帧
        
        Args:
            pixmap: QPixmap对象
        """
        if pixmap and not pixmap.isNull():
            # 缩放到面板大小
            scaled_pixmap = pixmap.scaled(
                self.size(), 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
    
    def setConnected(self, connected):
        """设置连接状态
        
        Args:
            connected: 是否已连接
        """
        self.is_connected = connected
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        
        if connected:
            self.setText("")  # 清空文本，准备显示视频
        else:
            self.clear()  # 清空图像
            self.setText("未打开通道")
    
    def clearDisplay(self):
        """清空显示"""
        self.clear()
        self.setText("未打开通道")
    
    def addChannel(self, channel_id, channel_data):
        """添加通道数据（兼容接口）"""
        print(f"[测试面板] 添加通道数据: {channel_id} -> {channel_data}")
    
    def updateChannelStatus(self, channel_id, status):
        """更新通道状态（兼容接口）"""
        print(f"[测试面板] 更新通道状态: {channel_id} -> {status}")


class TestMainWindow(QtWidgets.QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("相机画面显示测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央窗口
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QtWidgets.QGridLayout(central_widget)
        
        # 创建通道面板
        self.channel_panels = []
        for i in range(4):
            channel_id = f"channel{i+1}"
            panel = TestChannelPanel(channel_id)
            self.channel_panels.append(panel)
            
            # 添加到网格布局
            row = i // 2
            col = i % 2
            layout.addWidget(panel, row, col)
        
        # 创建通道处理器
        self.channel_handler = ChannelPanelHandler()
        
        # 初始化通道面板
        self.channel_handler.initializeChannelPanels(self.channel_panels)
        
        # 连接信号
        for panel in self.channel_panels:
            self.channel_handler.connectChannelPanelSignals(panel)
        
        # 创建状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
        
        print("[测试窗口] 初始化完成")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        print("[测试窗口] 正在关闭...")
        
        # 清理资源
        if hasattr(self, 'channel_handler'):
            self.channel_handler.cleanup()
        
        event.accept()


def main():
    """主函数"""
    print("=== 相机画面显示功能测试 ===")
    print("测试相机地址: rtsp://admin:cei345678@192.168.0.27:8000/stream1")
    print("点击面板上的'连接'按钮开始播放相机画面")
    print("按Ctrl+C或关闭窗口退出测试")
    print()
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建测试窗口
    window = TestMainWindow()
    window.show()
    
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("\n正在退出测试...")
        app.quit()


if __name__ == "__main__":
    main()