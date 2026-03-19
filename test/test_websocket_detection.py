# WebSocket检测命令测试脚本
# 用于测试客户端WebSocket连接和检测命令发送功能

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtWidgets, QtCore
from client.network.websocket_client import WebSocketClient

class WebSocketDetectionTest(QtWidgets.QWidget):
    """WebSocket检测命令测试界面"""
    
    def __init__(self):
        super().__init__()
        self.ws_client = None
        self.init_ui()
        self.init_websocket()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("WebSocket检测命令测试")
        self.setGeometry(100, 100, 600, 400)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 连接状态显示
        self.status_label = QtWidgets.QLabel("连接状态: 未连接")
        layout.addWidget(self.status_label)
        
        # 服务器地址输入
        server_layout = QtWidgets.QHBoxLayout()
        server_layout.addWidget(QtWidgets.QLabel("服务器地址:"))
        self.server_input = QtWidgets.QLineEdit("ws://192.168.0.121:8085")
        server_layout.addWidget(self.server_input)
        layout.addLayout(server_layout)
        
        # 通道ID输入
        channel_layout = QtWidgets.QHBoxLayout()
        channel_layout.addWidget(QtWidgets.QLabel("通道ID:"))
        self.channel_input = QtWidgets.QLineEdit("channel1")
        channel_layout.addWidget(self.channel_input)
        layout.addLayout(channel_layout)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        self.connect_btn = QtWidgets.QPushButton("连接WebSocket")
        self.connect_btn.clicked.connect(self.connect_websocket)
        button_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QtWidgets.QPushButton("断开连接")
        self.disconnect_btn.clicked.connect(self.disconnect_websocket)
        button_layout.addWidget(self.disconnect_btn)
        
        self.test_detection_btn = QtWidgets.QPushButton("测试检测命令")
        self.test_detection_btn.clicked.connect(self.test_detection_command)
        button_layout.addWidget(self.test_detection_btn)
        
        layout.addLayout(button_layout)
        
        # 日志显示区域
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 清空日志按钮
        self.clear_log_btn = QtWidgets.QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        layout.addWidget(self.clear_log_btn)
        
        self.setLayout(layout)
    
    def init_websocket(self):
        """初始化WebSocket客户端"""
        try:
            server_url = self.server_input.text()
            self.ws_client = WebSocketClient(server_url, self)
            
            # 连接信号
            self.ws_client.connection_status.connect(self.on_connection_status_changed)
            self.ws_client.detection_result.connect(self.on_detection_result)
            
            self.log("WebSocket客户端初始化完成")
            
        except Exception as e:
            self.log(f"WebSocket客户端初始化失败: {e}")
    
    def connect_websocket(self):
        """连接WebSocket"""
        try:
            if self.ws_client:
                self.ws_client.stop()  # 先停止现有连接
            
            server_url = self.server_input.text()
            self.ws_client = WebSocketClient(server_url, self)
            
            # 重新连接信号
            self.ws_client.connection_status.connect(self.on_connection_status_changed)
            self.ws_client.detection_result.connect(self.on_detection_result)
            
            self.ws_client.start()
            self.log(f"正在连接到服务器: {server_url}")
            
        except Exception as e:
            self.log(f"连接WebSocket失败: {e}")
    
    def disconnect_websocket(self):
        """断开WebSocket连接"""
        try:
            if self.ws_client:
                self.ws_client.stop()
                self.log("已断开WebSocket连接")
            
        except Exception as e:
            self.log(f"断开连接失败: {e}")
    
    def test_detection_command(self):
        """测试检测命令发送"""
        try:
            if not self.ws_client:
                self.log("错误: WebSocket客户端未初始化")
                return
            
            # 检查连接状态
            is_connected = self.ws_client.is_connected()
            self.log(f"当前连接状态: {is_connected}")
            
            if not is_connected:
                self.log("错误: WebSocket未连接，尝试重新连接...")
                self.ws_client.force_reconnect()
                
                # 等待连接建立
                for i in range(20):  # 最多等待2秒
                    time.sleep(0.1)
                    QtWidgets.QApplication.processEvents()  # 处理Qt事件
                    if self.ws_client.is_connected():
                        self.log("重连成功")
                        break
                else:
                    self.log("重连失败，无法发送检测命令")
                    return
            
            # 发送检测命令
            channel_id = self.channel_input.text()
            self.log(f"发送检测命令到通道: {channel_id}")
            
            success = self.ws_client.send_command('start_detection', channel_id=channel_id)
            
            if success:
                self.log("检测命令发送成功")
            else:
                self.log("检测命令发送失败")
                
        except Exception as e:
            self.log(f"测试检测命令异常: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def on_connection_status_changed(self, is_connected, message):
        """WebSocket连接状态变化回调"""
        status_text = "已连接" if is_connected else "未连接"
        self.status_label.setText(f"连接状态: {status_text}")
        self.log(f"连接状态变化: {status_text} - {message}")
    
    def on_detection_result(self, data):
        """检测结果回调"""
        self.log(f"收到检测结果: {data}")
    
    def log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        print(log_message)  # 同时输出到控制台
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()

def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建测试窗口
    test_window = WebSocketDetectionTest()
    test_window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()