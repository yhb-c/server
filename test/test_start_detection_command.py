#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：模拟客户端发送start_detection指令
用于测试WebSocket服务器对start_detection命令的响应
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtWidgets, QtCore
from client.network.websocket_client import WebSocketClient


class StartDetectionTest(QtWidgets.QWidget):
    """start_detection命令测试工具"""

    def __init__(self):
        super().__init__()
        self.ws_client = None
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Start Detection 命令测试")
        self.setGeometry(100, 100, 700, 500)

        layout = QtWidgets.QVBoxLayout()

        # 标题
        title = QtWidgets.QLabel("WebSocket Start Detection 测试工具")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # 连接状态
        self.status_label = QtWidgets.QLabel("状态: 未连接")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        layout.addWidget(self.status_label)

        # 配置区域
        config_group = QtWidgets.QGroupBox("连接配置")
        config_layout = QtWidgets.QFormLayout()

        self.server_input = QtWidgets.QLineEdit("ws://192.168.0.121:8085")
        self.server_input.setPlaceholderText("WebSocket服务器地址")
        config_layout.addRow("服务器地址:", self.server_input)

        self.channel_input = QtWidgets.QLineEdit("channel1")
        self.channel_input.setPlaceholderText("通道ID")
        config_layout.addRow("通道ID:", self.channel_input)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 操作按钮
        button_layout = QtWidgets.QHBoxLayout()

        self.connect_btn = QtWidgets.QPushButton("连接服务器")
        self.connect_btn.clicked.connect(self.connect_to_server)
        self.connect_btn.setStyleSheet("padding: 8px; font-size: 12px;")
        button_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QtWidgets.QPushButton("断开连接")
        self.disconnect_btn.clicked.connect(self.disconnect_from_server)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setStyleSheet("padding: 8px; font-size: 12px;")
        button_layout.addWidget(self.disconnect_btn)

        self.start_detection_btn = QtWidgets.QPushButton("发送 start_detection")
        self.start_detection_btn.clicked.connect(self.send_start_detection)
        self.start_detection_btn.setEnabled(False)
        self.start_detection_btn.setStyleSheet("padding: 8px; font-size: 12px; background-color: #4CAF50; color: white;")
        button_layout.addWidget(self.start_detection_btn)

        layout.addLayout(button_layout)

        # 日志区域
        log_group = QtWidgets.QGroupBox("日志输出")
        log_layout = QtWidgets.QVBoxLayout()

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)

        clear_btn = QtWidgets.QPushButton("清空日志")
        clear_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_btn)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        self.setLayout(layout)

    def connect_to_server(self):
        """连接到WebSocket服务器"""
        try:
            server_url = self.server_input.text().strip()
            if not server_url:
                self.log("错误: 请输入服务器地址")
                return

            self.log(f"正在连接到: {server_url}")

            # 停止现有连接
            if self.ws_client:
                self.ws_client.stop()

            # 创建新的WebSocket客户端
            self.ws_client = WebSocketClient(server_url, self)

            # 连接信号
            self.ws_client.connection_status.connect(self.on_connection_status)
            self.ws_client.detection_result.connect(self.on_detection_result)

            # 启动连接
            self.ws_client.start()

            # 更新UI状态
            self.connect_btn.setEnabled(False)
            self.server_input.setEnabled(False)

        except Exception as e:
            self.log(f"连接失败: {e}")
            import traceback
            self.log(traceback.format_exc())

    def disconnect_from_server(self):
        """断开WebSocket连接"""
        try:
            if self.ws_client:
                self.ws_client.stop()
                self.log("已断开连接")

            # 更新UI状态
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.start_detection_btn.setEnabled(False)
            self.server_input.setEnabled(True)
            self.status_label.setText("状态: 未连接")

        except Exception as e:
            self.log(f"断开连接失败: {e}")

    def send_start_detection(self):
        """发送start_detection命令"""
        try:
            if not self.ws_client:
                self.log("错误: WebSocket客户端未初始化")
                return

            if not self.ws_client.is_connected():
                self.log("错误: WebSocket未连接")
                return

            channel_id = self.channel_input.text().strip()
            if not channel_id:
                self.log("错误: 请输入通道ID")
                return

            self.log(f">>> 发送命令: start_detection")
            self.log(f"    通道ID: {channel_id}")

            # 发送命令
            success = self.ws_client.send_command('start_detection', channel_id=channel_id)

            if success:
                self.log("✓ 命令发送成功，等待服务器响应...")
            else:
                self.log("✗ 命令发送失败")

        except Exception as e:
            self.log(f"发送命令异常: {e}")
            import traceback
            self.log(traceback.format_exc())

    def on_connection_status(self, is_connected, message):
        """连接状态变化回调"""
        if is_connected:
            self.status_label.setText("状态: 已连接 ✓")
            self.status_label.setStyleSheet("padding: 5px; background-color: #c8e6c9;")
            self.disconnect_btn.setEnabled(True)
            self.start_detection_btn.setEnabled(True)
            self.log(f"✓ 连接成功: {message}")
        else:
            self.status_label.setText("状态: 未连接 ✗")
            self.status_label.setStyleSheet("padding: 5px; background-color: #ffcdd2;")
            self.disconnect_btn.setEnabled(False)
            self.start_detection_btn.setEnabled(False)
            self.log(f"✗ 连接断开: {message}")

    def on_detection_result(self, data):
        """检测结果回调"""
        self.log(f"<<< 收到服务器响应:")
        self.log(f"    类型: {data.get('type', 'unknown')}")

        # 格式化显示数据
        import json
        formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
        self.log(f"    数据:\n{formatted_data}")

    def log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        print(log_message)


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)

    # 创建测试窗口
    test_window = StartDetectionTest()
    test_window.show()

    print("=" * 60)
    print("Start Detection 命令测试工具已启动")
    print("=" * 60)
    print("使用说明:")
    print("1. 输入WebSocket服务器地址（默认: ws://192.168.0.121:8085）")
    print("2. 输入通道ID（默认: channel1）")
    print("3. 点击'连接服务器'按钮")
    print("4. 连接成功后，点击'发送 start_detection'按钮")
    print("5. 查看日志输出，观察服务器响应")
    print("=" * 60)

    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
