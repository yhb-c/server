# -*- coding: utf-8 -*-
"""
数据库客户端使用示例
演示如何在客户端中使用数据库连接
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit, QLabel
from qtpy.QtCore import Qt
from database import DatabaseManager


class DatabaseTestWindow(QMainWindow):
    """数据库测试窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据库客户端测试")
        self.setGeometry(100, 100, 800, 600)

        # 初始化数据库管理器
        self.db_manager = DatabaseManager(
            http_url="http://localhost:8080",
            ws_url="ws://localhost:8080/ws"
        )

        # 连接信号
        self.db_manager.connection_status_changed.connect(self.on_connection_status)
        self.db_manager.mission_updated.connect(self.on_mission_updated)
        self.db_manager.result_received.connect(self.on_result_received)

        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # 状态标签
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.status_label)

        # 按钮区域
        btn_connect = QPushButton("连接数据库")
        btn_connect.clicked.connect(self.connect_db)
        layout.addWidget(btn_connect)

        btn_create_mission = QPushButton("创建测试任务")
        btn_create_mission.clicked.connect(self.create_test_mission)
        layout.addWidget(btn_create_mission)

        btn_get_missions = QPushButton("获取任务列表")
        btn_get_missions.clicked.connect(self.get_missions)
        layout.addWidget(btn_get_missions)

        btn_add_result = QPushButton("添加测试结果")
        btn_add_result.clicked.connect(self.add_test_result)
        layout.addWidget(btn_add_result)

        btn_get_results = QPushButton("获取结果数据")
        btn_get_results.clicked.connect(self.get_results)
        layout.addWidget(btn_get_results)

        btn_subscribe = QPushButton("订阅任务更新")
        btn_subscribe.clicked.connect(self.subscribe_mission)
        layout.addWidget(btn_subscribe)

        # 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def log(self, message: str):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def connect_db(self):
        """连接数据库"""
        self.log("正在连接数据库...")
        self.db_manager.connect()

    def on_connection_status(self, connected: bool, message: str):
        """连接状态变化"""
        if connected:
            self.status_label.setText(f"✓ 已连接 - {message}")
            self.status_label.setStyleSheet("color: green; font-size: 14px; padding: 10px;")
        else:
            self.status_label.setText(f"✗ 未连接 - {message}")
            self.status_label.setStyleSheet("color: red; font-size: 14px; padding: 10px;")

        self.log(message)

    def create_test_mission(self):
        """创建测试任务"""
        task_id = f"test_{int(datetime.now().timestamp())}"
        result = self.db_manager.create_mission(
            task_id=task_id,
            task_name="测试任务",
            selected_channels=["通道1", "通道2", "通道3"],
            status="未启动"
        )

        if "error" in result:
            self.log(f"❌ 创建任务失败: {result['error']}")
        else:
            self.log(f"✓ 创建任务成功: {task_id}")

    def get_missions(self):
        """获取任务列表"""
        missions = self.db_manager.get_missions(limit=10)

        if not missions:
            self.log("没有找到任务")
            return

        self.log(f"找到 {len(missions)} 个任务:")
        for mission in missions:
            self.log(f"  - {mission['task_id']}: {mission['task_name']} ({mission['status']})")

    def add_test_result(self):
        """添加测试结果"""
        # 获取第一个任务
        missions = self.db_manager.get_missions(limit=1)
        if not missions:
            self.log("❌ 没有可用的任务")
            return

        task_id = missions[0]['task_id']

        # 添加结果
        result = self.db_manager.add_result(
            task_id=task_id,
            channel_name="通道1",
            region_name="区域1",
            value=1.5
        )

        if "error" in result:
            self.log(f"❌ 添加结果失败: {result['error']}")
        else:
            self.log(f"✓ 添加结果成功: 任务 {task_id}")

    def get_results(self):
        """获取结果数据"""
        # 获取第一个任务
        missions = self.db_manager.get_missions(limit=1)
        if not missions:
            self.log("❌ 没有可用的任务")
            return

        task_id = missions[0]['task_id']

        # 获取最近1小时的结果
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        results = self.db_manager.get_mission_results(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time
        )

        if not results:
            self.log(f"任务 {task_id} 没有结果数据")
            return

        self.log(f"任务 {task_id} 找到 {len(results)} 条结果:")
        for result in results[:5]:  # 只显示前5条
            self.log(f"  - {result['channel_name']}/{result['region_name']}: {result['value']} @ {result['timestamp']}")

    def subscribe_mission(self):
        """订阅任务更新"""
        # 获取第一个任务
        missions = self.db_manager.get_missions(limit=1)
        if not missions:
            self.log("❌ 没有可用的任务")
            return

        task_id = missions[0]['task_id']
        self.db_manager.subscribe_mission(task_id)
        self.log(f"✓ 已订阅任务: {task_id}")

    def on_mission_updated(self, mission_data: dict):
        """任务更新回调"""
        self.log(f"📢 任务更新: {mission_data.get('task_id')} - {mission_data.get('status')}")

    def on_result_received(self, result_data: dict):
        """结果接收回调"""
        self.log(f"📊 新结果: {result_data.get('channel_name')}/{result_data.get('region_name')} = {result_data.get('value')}")

    def closeEvent(self, event):
        """关闭事件"""
        self.db_manager.disconnect()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = DatabaseTestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
