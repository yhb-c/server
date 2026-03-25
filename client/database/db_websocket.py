# -*- coding: utf-8 -*-
"""
数据库 WebSocket 客户端
用于实时接收数据库更新通知
"""

from qtpy import QtCore, QtWebSockets, QtNetwork
import json
from typing import Optional, Callable


class DatabaseWebSocketClient(QtCore.QObject):
    """数据库 WebSocket 客户端 - 实时接收数据更新"""

    # 信号定义
    connected = QtCore.Signal()  # 连接成功
    disconnected = QtCore.Signal()  # 断开连接
    error_occurred = QtCore.Signal(str)  # 错误发生

    # 数据更新信号
    mission_created = QtCore.Signal(dict)  # 任务创建
    mission_updated = QtCore.Signal(dict)  # 任务更新
    mission_deleted = QtCore.Signal(str)  # 任务删除
    result_added = QtCore.Signal(dict)  # 结果添加
    config_updated = QtCore.Signal(dict)  # 配置更新

    def __init__(self, url: str = "ws://localhost:8080/ws", parent=None):
        """
        初始化 WebSocket 客户端

        Args:
            url: WebSocket 服务器地址
            parent: 父对象
        """
        super().__init__(parent)

        self.url = url
        self.websocket = None
        self.is_connected = False
        self.reconnect_timer = QtCore.QTimer()
        self.reconnect_timer.timeout.connect(self._reconnect)
        self.reconnect_interval = 5000  # 5秒重连

        print(f"[DatabaseWS] 初始化: {url}")

    def connect_to_server(self):
        """连接到服务器"""
        if self.is_connected:
            print("[DatabaseWS] 已连接")
            return

        try:
            self.websocket = QtWebSockets.QWebSocket()

            # 连接信号
            self.websocket.connected.connect(self._on_connected)
            self.websocket.disconnected.connect(self._on_disconnected)
            self.websocket.textMessageReceived.connect(self._on_message)
            self.websocket.error.connect(self._on_error)

            print(f"[DatabaseWS] 连接到: {self.url}")
            self.websocket.open(QtCore.QUrl(self.url))

        except Exception as e:
            print(f"[DatabaseWS] 连接失败: {e}")
            self.error_occurred.emit(str(e))
            self._start_reconnect()

    def disconnect_from_server(self):
        """断开连接"""
        if self.websocket:
            self.websocket.close()
        self.reconnect_timer.stop()

    def send_message(self, message: dict):
        """
        发送消息

        Args:
            message: 消息字典
        """
        if not self.is_connected or not self.websocket:
            print("[DatabaseWS] 未连接，无法发送消息")
            return

        try:
            json_str = json.dumps(message, ensure_ascii=False)
            self.websocket.sendTextMessage(json_str)
        except Exception as e:
            print(f"[DatabaseWS] 发送消息失败: {e}")

    def subscribe_mission(self, task_id: str):
        """
        订阅任务更新

        Args:
            task_id: 任务ID
        """
        self.send_message({
            "type": "subscribe",
            "resource": "mission",
            "id": task_id
        })

    def unsubscribe_mission(self, task_id: str):
        """
        取消订阅任务

        Args:
            task_id: 任务ID
        """
        self.send_message({
            "type": "unsubscribe",
            "resource": "mission",
            "id": task_id
        })

    def subscribe_results(self, task_id: str, channel: Optional[str] = None):
        """
        订阅结果更新

        Args:
            task_id: 任务ID
            channel: 通道名称（可选）
        """
        message = {
            "type": "subscribe",
            "resource": "results",
            "task_id": task_id
        }
        if channel:
            message["channel"] = channel

        self.send_message(message)

    # ==================== 内部方法 ====================

    def _on_connected(self):
        """连接成功回调"""
        self.is_connected = True
        self.reconnect_timer.stop()
        print("[DatabaseWS] 连接成功")
        self.connected.emit()

    def _on_disconnected(self):
        """断开连接回调"""
        self.is_connected = False
        print("[DatabaseWS] 连接断开")
        self.disconnected.emit()
        self._start_reconnect()

    def _on_message(self, message: str):
        """
        接收消息回调

        Args:
            message: 消息字符串
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "mission_created":
                self.mission_created.emit(data.get("data", {}))
            elif msg_type == "mission_updated":
                self.mission_updated.emit(data.get("data", {}))
            elif msg_type == "mission_deleted":
                self.mission_deleted.emit(data.get("task_id", ""))
            elif msg_type == "result_added":
                self.result_added.emit(data.get("data", {}))
            elif msg_type == "config_updated":
                self.config_updated.emit(data.get("data", {}))
            else:
                print(f"[DatabaseWS] 未知消息类型: {msg_type}")

        except json.JSONDecodeError as e:
            print(f"[DatabaseWS] JSON 解析失败: {e}")
        except Exception as e:
            print(f"[DatabaseWS] 处理消息失败: {e}")

    def _on_error(self, error_code):
        """
        错误回调

        Args:
            error_code: 错误代码
        """
        if self.websocket:
            error_string = self.websocket.errorString()
            print(f"[DatabaseWS] 错误: {error_string}")
            self.error_occurred.emit(error_string)

    def _start_reconnect(self):
        """开始重连"""
        if not self.reconnect_timer.isActive():
            print(f"[DatabaseWS] {self.reconnect_interval/1000}秒后重连")
            self.reconnect_timer.start(self.reconnect_interval)

    def _reconnect(self):
        """重连"""
        print("[DatabaseWS] 尝试重连...")
        self.connect_to_server()
