# -*- coding: utf-8 -*-
"""
动态液位线绘制模块
支持根据检测结果动态更新液位线位置
"""

import os
import sys
import time
import threading
from typing import Optional, Tuple

# 添加HK_SDK路径
current_dir = os.path.dirname(os.path.abspath(__file__))
hk_sdk_path = os.path.join(os.path.dirname(current_dir), 'videopage', 'HK_SDK')
sys.path.insert(0, hk_sdk_path)

from level_line_overlay import LevelLineOverlay


class DynamicLevelLine:
    """动态液位线管理类"""

    def __init__(self, ip: str, port: int, username: str, password: str, channel: int = 1):
        """
        初始化动态液位线

        Args:
            ip: 相机IP地址
            port: 相机端口
            username: 用户名
            password: 密码
            channel: 通道号
        """
        self.overlay = LevelLineOverlay()
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.channel = channel

        self.current_y = 0
        self.is_running = False
        self.update_thread = None
        self.lock = threading.Lock()

    def start(self) -> bool:
        """
        启动液位线服务

        Returns:
            bool: 是否启动成功
        """
        # 初始化SDK
        if not self.overlay.initialize_sdk():
            print("SDK初始化失败")
            return False

        # 登录设备
        if not self.overlay.login_device(self.ip, self.port, self.username, self.password):
            print("设备登录失败")
            return False

        self.is_running = True
        print(f"动态液位线服务已启动 - 通道:{self.channel}")
        return True

    def stop(self):
        """停止液位线服务"""
        self.is_running = False

        # 清除液位线
        self.overlay.clear_level_line(self.channel)

        # 清理资源
        self.overlay.cleanup()
        print("动态液位线服务已停止")

    def update_level_line(self, y_position: int, level_value: Optional[float] = None) -> bool:
        """
        更新液位线位置

        Args:
            y_position: Y坐标位置(0-576)
            level_value: 液位值(可选,用于显示在液位线上)

        Returns:
            bool: 是否更新成功
        """
        if not self.is_running:
            print("服务未启动")
            return False

        with self.lock:
            # 构建液位线文本
            if level_value is not None:
                line_text = f"━━━━ 液位: {level_value:.2f}m ━━━━━━━━━━━━━━━━━━━━"
            else:
                line_text = "━" * 40

            # 绘制液位线
            success = self.overlay.draw_level_line(self.channel, y_position, line_text)

            if success:
                self.current_y = y_position

            return success

    def get_current_position(self) -> int:
        """获取当前液位线Y坐标"""
        with self.lock:
            return self.current_y


class LevelLineController:
    """液位线控制器 - 与检测系统集成"""

    def __init__(self, camera_config: dict):
        """
        初始化控制器

        Args:
            camera_config: 相机配置字典,包含address等信息
        """
        self.camera_config = camera_config
        self.dynamic_line = None
        self.is_active = False

        # 解析RTSP地址
        self.ip, self.port, self.username, self.password = self._parse_rtsp_url(
            camera_config.get('address', '')
        )

    def _parse_rtsp_url(self, rtsp_url: str) -> Tuple[str, int, str, str]:
        """
        解析RTSP URL

        Args:
            rtsp_url: RTSP地址,格式: rtsp://username:password@ip:port/stream

        Returns:
            tuple: (ip, port, username, password)
        """
        try:
            # rtsp://admin:cei345678@192.168.0.27:8000/stream2
            if not rtsp_url.startswith('rtsp://'):
                raise ValueError("无效的RTSP URL")

            # 移除协议前缀
            url = rtsp_url[7:]

            # 分离认证信息和地址
            if '@' in url:
                auth, addr = url.split('@', 1)
                username, password = auth.split(':', 1)
            else:
                username = 'admin'
                password = ''
                addr = url

            # 分离IP和端口
            if '/' in addr:
                addr = addr.split('/')[0]

            if ':' in addr:
                ip, port_str = addr.rsplit(':', 1)
                port = int(port_str)
            else:
                ip = addr
                port = 554

            return ip, port, username, password

        except Exception as e:
            print(f"解析RTSP URL失败: {e}")
            return "192.168.0.27", 8000, "admin", "cei345678"

    def start(self, channel: int = 1) -> bool:
        """
        启动液位线控制器

        Args:
            channel: 通道号

        Returns:
            bool: 是否启动成功
        """
        if self.is_active:
            print("控制器已在运行")
            return True

        # 创建动态液位线对象
        self.dynamic_line = DynamicLevelLine(
            self.ip, self.port, self.username, self.password, channel
        )

        # 启动服务
        if self.dynamic_line.start():
            self.is_active = True
            print("液位线控制器已启动")
            return True
        else:
            print("液位线控制器启动失败")
            return False

    def stop(self):
        """停止液位线控制器"""
        if self.dynamic_line:
            self.dynamic_line.stop()
            self.dynamic_line = None

        self.is_active = False
        print("液位线控制器已停止")

    def update_from_detection(self, detection_result: dict) -> bool:
        """
        根据检测结果更新液位线

        Args:
            detection_result: 检测结果字典,包含液位信息
                {
                    'level_y': int,  # 液位线Y坐标
                    'level_value': float,  # 液位值(米)
                }

        Returns:
            bool: 是否更新成功
        """
        if not self.is_active or not self.dynamic_line:
            return False

        level_y = detection_result.get('level_y', 0)
        level_value = detection_result.get('level_value', None)

        return self.dynamic_line.update_level_line(level_y, level_value)


def test_dynamic_level_line():
    """测试动态液位线"""
    # 相机配置
    camera_config = {
        'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream2',
        'name': '通道1'
    }

    # 创建控制器
    controller = LevelLineController(camera_config)

    # 启动控制器
    if not controller.start(channel=1):
        print("启动失败")
        return

    try:
        # 模拟液位变化
        print("模拟液位变化...")
        for i in range(5):
            y_position = 200 + i * 50  # 从200到400
            level_value = 10.0 + i * 2.0  # 从10m到18m

            detection_result = {
                'level_y': y_position,
                'level_value': level_value
            }

            controller.update_from_detection(detection_result)
            print(f"更新液位线: Y={y_position}, 液位={level_value}m")

            time.sleep(2)

    finally:
        # 停止控制器
        controller.stop()


if __name__ == "__main__":
    test_dynamic_level_line()
