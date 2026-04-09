# -*- coding: utf-8 -*-
"""
液位检测系统客户端 - 主程序入口
"""

import sys
import subprocess
import platform
import os
import time
import socket
from pathlib import Path

from qtpy import QtWidgets
from qtpy.QtCore import Qt

# 全局日志开关
# True: 启用日志输出到文件
# False: 禁用日志输出
ENABLE_LOGGING = True

# 添加 client 目录到路径
client_path = Path(__file__).parent / 'client'
sys.path.insert(0, str(client_path))

from client.widgets.login import LoginWindow
from client.utils.config import load_config
from client.utils.logger import setup_logging
from client.network.start_api_service import start_api_service
from client.network.start_websocket_service import start_websocket_service


def check_port_listening(port):
    """
    检查本地端口是否处于监听状态（使用ss命令）

    Args:
        port: 端口号

    Returns:
        bool: 端口正在监听返回 True，否则返回 False
    """
    try:
        # 使用 ss 命令检测端口监听状态
        result = subprocess.run(
            ['ss', '-ltn', f'sport = :{port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )

        # 检查输出中是否包含 LISTEN 状态
        output = result.stdout
        return 'LISTEN' in output and str(port) in output
    except Exception as e:
        # print(f"[端口检测] 检测端口 {port} 监听状态失败: {e}")
        return False


def check_port(host, port, timeout=2, is_websocket=False):
    """
    检查指定主机端口是否开放

    Args:
        host: 主机地址
        port: 端口号
        timeout: 超时时间（秒）
        is_websocket: 是否为WebSocket端口（需要发送HTTP升级请求）

    Returns:
        bool: 端口开放返回 True，否则返回 False
    """
    try:
        if is_websocket:
            # WebSocket端口检测：发送完整的WebSocket握手请求
            import http.client
            try:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)
                headers = {
                    'Upgrade': 'websocket',
                    'Connection': 'Upgrade',
                    'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
                    'Sec-WebSocket-Version': '13'
                }
                conn.request("GET", "/", headers=headers)
                response = conn.getresponse()
                conn.close()
                # 101 Switching Protocols 或任何响应都说明端口开放
                return True
            except Exception:
                return False
        else:
            # 普通TCP端口检测
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
    except Exception as e:
        # print(f"[端口检测] 检测 {host}:{port} 失败: {e}")
        return False


def ping_host(host, timeout=2):
    """
    Ping 指定主机检测网络连接

    Args:
        host: 主机地址（IP或域名）
        timeout: 超时时间（秒）

    Returns:
        bool: 连接成功返回 True，否则返回 False
    """
    try:
        # 根据操作系统选择 ping 命令参数
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'

        # 构造 ping 命令
        command = ['ping', param, '1', timeout_param, str(timeout * 1000 if platform.system().lower() == 'windows' else timeout), host]

        # 执行 ping 命令
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )

        return result.returncode == 0

    except Exception as e:
        # print(f"[网络检测] Ping {host} 失败: {e}")
        return False



def check_network_connectivity(config):
    """
    检测网络连接状态并自动启动服务

    Args:
        config: 配置字典

    Returns:
        dict: 连接状态信息
            {
                'api_server': bool,  # API服务器连接状态
                'ws_server': bool    # WebSocket服务器连接状态
            }
    """
    status = {
        'api_server': False,
        'ws_server': False
    }

    # 获取服务器配置
    api_url = config.get('server', {}).get('api_url', 'http://192.168.0.121:8084')
    api_host = api_url.split('://')[1].split(':')[0] if '://' in api_url else '192.168.0.121'
    api_port = int(api_url.split(':')[-1]) if ':' in api_url else 8084

    ws_url = config.get('server', {}).get('ws_url', 'ws://192.168.0.121:8085')
    ws_host = ws_url.split('://')[1].split(':')[0] if '://' in ws_url else '192.168.0.121'
    ws_port = int(ws_url.split(':')[-1]) if ':' in ws_url else 8085

    # 1. 检测 API 服务器
    status['api_server'] = check_port(api_host, api_port)

    # 2. 检测 WebSocket 服务器
    status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

    # 检查本地端口监听状态，避免重复启动
    api_listening = check_port_listening(api_port)
    ws_listening = check_port_listening(ws_port)

    # 自动启动未运行的服务
    if not api_listening or not ws_listening:
        # 启动API服务
        if not api_listening:
            if start_api_service(api_host):
                time.sleep(1)
                status['api_server'] = check_port(api_host, api_port)

        # 启动WebSocket服务
        if not ws_listening:
            if start_websocket_service(ws_host):
                time.sleep(2)
                status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

    return status


def main():
    """主函数"""
    # print("="*60)
    # print("液位检测系统客户端启动")
    # print("="*60)

    # 设置高DPI支持(必须在QApplication创建之前)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 创建Qt应用
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('液位检测系统')
    app.setOrganizationName('Liquid Detection')

    # 加载配置
    config = load_config()

    # 配置日志
    setup_logging(config.get('log_level', 'INFO'))

    # 网络连接检测
    network_status = check_network_connectivity(config)

    # 检查关键服务是否可用

    login_window = LoginWindow(config)
    login_window.show()

    # 启动事件循环
    exit_code = app.exec_()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
