# -*- coding: utf-8 -*-
"""
WebSocket自动连接模块
"""

import time
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtCore
from client.network.websocket_client import WebSocketClient


class WebSocketAutoConnector(QtCore.QObject):
    """WebSocket自动连接管理器"""

    # 信号定义
    connection_ready = QtCore.Signal(bool)  # 连接就绪信号

    def __init__(self, ws_url, max_retry=5, retry_interval=3, parent=None):
        """
        初始化WebSocket自动连接器

        Args:
            ws_url: WebSocket服务器地址
            max_retry: 最大重试次数
            retry_interval: 重试间隔（秒）
            parent: 父对象
        """
        super().__init__(parent)

        self.ws_url = ws_url
        self.max_retry = max_retry
        self.retry_interval = retry_interval
        self.retry_count = 0
        self.is_connected = False

        # WebSocket客户端
        self.ws_client = None

        # 重试定时器
        self.retry_timer = QtCore.QTimer()
        self.retry_timer.timeout.connect(self._retry_connect)

        print(f"[自动连接] WebSocket自动连接器初始化")
        print(f"[自动连接] 服务器地址: {ws_url}")
        print(f"[自动连接] 最大重试次数: {max_retry}")
        print(f"[自动连接] 重试间隔: {retry_interval}秒")

    def start(self):
        """开始自动连接"""
        print(f"\n[自动连接] 开始自动连接WebSocket服务...")
        self._connect()

    def _connect(self):
        """执行连接"""
        try:
            print(f"[自动连接] 尝试连接 ({self.retry_count + 1}/{self.max_retry})...")

            # 创建WebSocket客户端
            if self.ws_client is None:
                self.ws_client = WebSocketClient(self.ws_url)
                self.ws_client.connection_status.connect(self._on_connection_status)

            # 启动连接
            self.ws_client.start()

        except Exception as e:
            print(f"[自动连接] 连接失败: {e}")
            self._schedule_retry()

    def _on_connection_status(self, connected, message):
        """
        连接状态变化回调

        Args:
            connected: 是否连接成功
            message: 状态消息
        """
        if connected:
            print(f"[自动连接] 连接成功: {message}")
            self.is_connected = True
            self.retry_count = 0
            self.retry_timer.stop()
            self.connection_ready.emit(True)
        else:
            print(f"[自动连接] 连接失败: {message}")
            self.is_connected = False

            # 如果是连接被拒绝，安排重试
            if "ConnectionRefusedError" in message or "连接被拒绝" in message:
                self._schedule_retry()

    def _schedule_retry(self):
        """安排重试"""
        self.retry_count += 1

        if self.retry_count >= self.max_retry:
            print(f"[自动连接] 已达到最大重试次数 ({self.max_retry})，停止重试")
            self.connection_ready.emit(False)
            return

        print(f"[自动连接] {self.retry_interval}秒后重试...")
        self.retry_timer.start(self.retry_interval * 1000)

    def _retry_connect(self):
        """重试连接"""
        self.retry_timer.stop()
        self._connect()

    def get_client(self):
        """
        获取WebSocket客户端实例

        Returns:
            WebSocketClient: WebSocket客户端实例
        """
        return self.ws_client

    def stop(self):
        """停止自动连接"""
        print(f"[自动连接] 停止自动连接")
        self.retry_timer.stop()
        if self.ws_client:
            self.ws_client.stop()


def create_websocket_connector(ws_url, max_retry=5, retry_interval=3):
    """
    创建WebSocket自动连接器

    Args:
        ws_url: WebSocket服务器地址
        max_retry: 最大重试次数
        retry_interval: 重试间隔（秒）

    Returns:
        WebSocketAutoConnector: 自动连接器实例
    """
    connector = WebSocketAutoConnector(ws_url, max_retry, retry_interval)
    return connector
