#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'client'))

from qtpy import QtWidgets, QtCore
from network.websocket_client import WebSocketClient


def test_keepalive():
    """测试WebSocket连接保持"""
    app = QtWidgets.QApplication(sys.argv)

    # 创建WebSocket客户端
    ws_client = WebSocketClient('ws://192.168.0.121:8085')

    # 连接状态记录
    connection_log = []

    def on_connection_status(is_connected, message):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        status = '已连接' if is_connected else '未连接'
        log_msg = f"[{timestamp}] 连接状态: {status} - {message}"
        print(log_msg)
        connection_log.append(log_msg)

    def on_detection_result(data):
        channel_id = data.get('channel_id', 'unknown')
        print(f"[检测结果] 通道: {channel_id}")

    ws_client.connection_status.connect(on_connection_status)
    ws_client.detection_result.connect(on_detection_result)

    # 启动客户端
    ws_client.start()

    print("="*60)
    print("WebSocket连接保持测试")
    print("="*60)
    print("测试目标: 验证连接能否保持超过2分钟")
    print("预期结果: 连接应该保持稳定，不会因为超时而断开")
    print("="*60)

    # 等待连接建立
    QtCore.QTimer.singleShot(2000, lambda: print("\n[测试] 连接已建立，开始订阅通道..."))

    # 2秒后订阅所有通道
    def subscribe_channels():
        print("[测试] 订阅所有通道...")
        for i in range(1, 17):
            channel_id = f'channel{i}'
            ws_client.send_command('subscribe', channel_id=channel_id)
            print(f"[测试] 已订阅: {channel_id}")
        print("[测试] 所有通道订阅完成")
        print("[测试] 等待2分钟，观察连接是否保持...")

    QtCore.QTimer.singleShot(2000, subscribe_channels)

    # 120秒后检查连接状态
    def check_connection():
        print("\n" + "="*60)
        print("[测试结果]")
        print("="*60)
        if ws_client.is_connected():
            print("✓ 测试通过: 连接保持超过2分钟")
            print(f"✓ 连接状态: 正常")
        else:
            print("✗ 测试失败: 连接已断开")
            print(f"✗ 连接状态: 断开")

        print("\n连接日志:")
        for log in connection_log:
            print(log)

        print("="*60)

        # 停止客户端并退出
        ws_client.stop()
        QtCore.QTimer.singleShot(1000, app.quit)

    QtCore.QTimer.singleShot(120000, check_connection)  # 120秒后检查

    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    test_keepalive()
