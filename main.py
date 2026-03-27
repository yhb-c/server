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

# 添加 client 目录到路径
client_path = Path(__file__).parent / 'client'
sys.path.insert(0, str(client_path))

from client.widgets.login import LoginWindow
from client.utils.config import load_config
from client.utils.logger import setup_logging


def check_port(host, port, timeout=2):
    """
    检查指定主机端口是否开放

    Args:
        host: 主机地址
        port: 端口号
        timeout: 超时时间（秒）

    Returns:
        bool: 端口开放返回 True，否则返回 False
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"[端口检测] 检测 {host}:{port} 失败: {e}")
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
        print(f"[网络检测] Ping {host} 失败: {e}")
        return False


def start_remote_service(service_name, host, port, start_command):
    """
    启动远程服务

    Args:
        service_name: 服务名称
        host: 服务器地址
        port: 服务端口
        start_command: 启动命令

    Returns:
        bool: 启动成功返回 True，否则返回 False
    """
    print(f"\n[服务启动] 正在启动 {service_name}...")

    try:
        # 使用SSH启动远程服务（后台运行）
        ssh_command = f"ssh lqj@{host} 'nohup bash -c \"{start_command}\" > /dev/null 2>&1 &'"

        result = subprocess.run(
            ssh_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )

        if result.returncode != 0:
            print(f"[服务启动] {service_name} 启动命令执行失败")
            return False

        # 等待服务启动
        print(f"[服务启动] 等待 {service_name} 启动...")
        for i in range(10):
            time.sleep(1)
            if check_port(host, port):
                print(f"[服务启动] {service_name} 启动成功")
                return True
            print(f"[服务启动] 等待中... ({i+1}/10)")

        print(f"[服务启动] {service_name} 启动超时")
        return False

    except Exception as e:
        print(f"[服务启动] {service_name} 启动失败: {e}")
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
    print("\n" + "="*50)
    print("网络连接检测")
    print("="*50)

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
    print(f"\n[1/2] 检测 API 服务器: {api_host}:{api_port}")
    status['api_server'] = check_port(api_host, api_port)

    if not status['api_server']:
        print(f"      状态: 连接失败，尝试启动服务...")
        # 启动 Go API 服务
        api_start_cmd = f"cd /home/lqj/liquid/api && source ~/anaconda3/bin/activate liquid && go run main.go"
        status['api_server'] = start_remote_service("API服务", api_host, api_port, api_start_cmd)
    else:
        print(f"      状态: 连接成功")

    # 2. 检测 WebSocket 服务器
    print(f"\n[2/2] 检测 WebSocket 服务器: {ws_host}:{ws_port}")
    status['ws_server'] = check_port(ws_host, ws_port)

    if not status['ws_server']:
        print(f"      状态: 连接失败，尝试启动服务...")
        # 启动 Python 推理服务
        ws_start_cmd = f"cd /home/lqj/liquid/server && source ~/anaconda3/bin/activate liquid && python api_server.py"
        status['ws_server'] = start_remote_service("推理服务", ws_host, ws_port, ws_start_cmd)
    else:
        print(f"      状态: 连接成功")

    print("\n" + "="*50)
    print("网络检测完成")
    print("="*50 + "\n")

    return status


def main():
    """主函数"""
    print("="*60)
    print("液位检测系统客户端启动")
    print("="*60)

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
    print("\n[系统启动] 检测服务连接状态...")
    network_status = check_network_connectivity(config)

    # 检查关键服务是否可用
    print("\n[系统启动] 服务状态总结:")

    # API服务状态
    if network_status['api_server']:
        print("[API服务] 状态: 服务器连接正常")
    else:
        print("[API服务] 状态: 服务器连接异常")
        print("[警告] API 服务器连接失败，部分功能可能不可用")

    # 推理服务状态
    if network_status['ws_server']:
        print("[推理服务] 状态: 服务器连接正常")
    else:
        print("[推理服务] 状态: 服务器连接异常")
        print("[警告] WebSocket 服务器连接失败，实时数据推送功能可能不可用")

    print("\n[系统启动] 启动客户端界面...")

    # 显示登录窗口
    login_window = LoginWindow(config)
    login_window.show()

    print("[系统启动] 客户端界面已启动")
    print("="*60)

    # 启动事件循环
    exit_code = app.exec_()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
