# -*- coding: utf-8 -*-
"""
数据库管理器
统一管理 HTTP API 和 WebSocket 连接
"""

from qtpy import QtCore
from typing import Optional, List, Dict
from datetime import datetime

from .db_client import DatabaseClient
from .db_websocket import DatabaseWebSocketClient


class DatabaseManager(QtCore.QObject):
    """数据库管理器 - 统一管理数据库连接"""

    # 信号定义
    connection_status_changed = QtCore.Signal(bool, str)  # 连接状态变化
    mission_updated = QtCore.Signal(dict)  # 任务更新
    result_received = QtCore.Signal(dict)  # 结果接收

    def __init__(
        self,
        http_url: str = "http://localhost:8080",
        ws_url: str = "ws://localhost:8080/ws",
        parent=None
    ):
        """
        初始化数据库管理器

        Args:
            http_url: HTTP API 地址
            ws_url: WebSocket 地址
            parent: 父对象
        """
        super().__init__(parent)

        # HTTP 客户端
        self.http_client = DatabaseClient(http_url)

        # WebSocket 客户端
        self.ws_client = DatabaseWebSocketClient(ws_url)
        self._connect_ws_signals()

        # 连接状态
        self.is_connected = False

        print(f"[DatabaseManager] 初始化完成")
        print(f"  HTTP: {http_url}")
        print(f"  WebSocket: {ws_url}")

    def connect(self):
        """连接到数据库服务器"""
        # 测试 HTTP 连接
        if self.http_client.test_connection():
            self.is_connected = True
            self.connection_status_changed.emit(True, "HTTP 连接成功")
            print("[DatabaseManager] HTTP 连接成功")

            # 启动 WebSocket 连接
            self.ws_client.connect_to_server()
        else:
            self.is_connected = False
            self.connection_status_changed.emit(False, "HTTP 连接失败")
            print("[DatabaseManager] HTTP 连接失败")

    def disconnect(self):
        """断开连接"""
        self.ws_client.disconnect_from_server()
        self.http_client.close()
        self.is_connected = False
        self.connection_status_changed.emit(False, "已断开连接")

    # ==================== 任务操作 ====================

    def create_mission(
        self,
        task_id: str,
        task_name: str,
        selected_channels: List[str],
        status: str = "未启动",
        result_folder: str = ""
    ) -> Dict:
        """
        创建任务

        Args:
            task_id: 任务ID
            task_name: 任务名称
            selected_channels: 选中的通道列表
            status: 状态
            result_folder: 结果文件夹路径

        Returns:
            dict: 响应数据
        """
        mission_data = {
            "task_id": task_id,
            "task_name": task_name,
            "status": status,
            "selected_channels": selected_channels,
            "created_time": datetime.now().isoformat(),
            "mission_result_folder_path": result_folder
        }

        return self.http_client.create_mission(mission_data)

    def get_missions(self, limit: int = 10, offset: int = 0) -> List[Dict]:
        """获取任务列表"""
        return self.http_client.get_missions(limit, offset)

    def get_mission(self, task_id: str) -> Optional[Dict]:
        """获取单个任务"""
        return self.http_client.get_mission(task_id)

    def update_mission_status(self, task_id: str, status: str) -> Dict:
        """更新任务状态"""
        return self.http_client.update_mission_status(task_id, status)

    def delete_mission(self, task_id: str) -> Dict:
        """删除任务"""
        return self.http_client.delete_mission(task_id)

    # ==================== 结果操作 ====================

    def get_mission_results(
        self,
        task_id: str,
        channel: Optional[str] = None,
        region: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """获取任务结果"""
        return self.http_client.get_mission_results(
            task_id, channel, region, start_time, end_time
        )

    def add_result(
        self,
        task_id: str,
        channel_name: str,
        region_name: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        添加结果记录

        Args:
            task_id: 任务ID
            channel_name: 通道名称
            region_name: 区域名称
            value: 数值
            timestamp: 时间戳（可选，默认当前时间）

        Returns:
            dict: 响应数据
        """
        if timestamp is None:
            timestamp = datetime.now()

        return self.http_client.create_mission_result(
            task_id, channel_name, region_name, timestamp, value
        )

    def batch_add_results(self, task_id: str, results: List[Dict]) -> Dict:
        """批量添加结果"""
        return self.http_client.batch_create_results(task_id, results)

    # ==================== 配置操作 ====================

    def save_config(
        self,
        config_type: str,
        config_name: str,
        config_data: Dict
    ) -> Dict:
        """保存配置"""
        return self.http_client.save_config(config_type, config_name, config_data)

    def get_config(self, config_type: str, config_name: str) -> Optional[Dict]:
        """获取配置"""
        return self.http_client.get_config(config_type, config_name)

    def list_configs(self, config_type: Optional[str] = None) -> List[Dict]:
        """列出配置"""
        return self.http_client.list_configs(config_type)

    def delete_config(self, config_type: str, config_name: str) -> Dict:
        """删除配置"""
        return self.http_client.delete_config(config_type, config_name)

    # ==================== WebSocket 订阅 ====================

    def subscribe_mission(self, task_id: str):
        """订阅任务更新"""
        self.ws_client.subscribe_mission(task_id)

    def unsubscribe_mission(self, task_id: str):
        """取消订阅任务"""
        self.ws_client.unsubscribe_mission(task_id)

    def subscribe_results(self, task_id: str, channel: Optional[str] = None):
        """订阅结果更新"""
        self.ws_client.subscribe_results(task_id, channel)

    # ==================== 内部方法 ====================

    def _connect_ws_signals(self):
        """连接 WebSocket 信号"""
        self.ws_client.connected.connect(self._on_ws_connected)
        self.ws_client.disconnected.connect(self._on_ws_disconnected)
        self.ws_client.mission_updated.connect(self.mission_updated.emit)
        self.ws_client.result_added.connect(self.result_received.emit)

    def _on_ws_connected(self):
        """WebSocket 连接成功"""
        print("[DatabaseManager] WebSocket 连接成功")
        self.connection_status_changed.emit(True, "WebSocket 连接成功")

    def _on_ws_disconnected(self):
        """WebSocket 断开连接"""
        print("[DatabaseManager] WebSocket 断开")
        self.connection_status_changed.emit(False, "WebSocket 断开")
