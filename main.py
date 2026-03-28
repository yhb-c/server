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
        print(f"[端口检测] 检测端口 {port} 监听状态失败: {e}")
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


def start_local_services():
    """
    启动本地服务（使用start_services.sh脚本）

    Returns:
        bool: 启动成功返回 True，否则返回 False
    """
    print(f"\n[服务启动] 正在启动服务...")

    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        start_script = os.path.join(project_root, 'start_services.sh')

        # 检查启动脚本是否存在
        if not os.path.exists(start_script):
            print(f"[服务启动] 启动脚本不存在: {start_script}")
            return False

        # 执行启动脚本
        result = subprocess.run(
            ['bash', start_script],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            text=True
        )

        if result.returncode != 0:
            print(f"[服务启动] 启动脚本执行失败")
            print(f"[错误信息] {result.stderr}")
            return False

        print(f"[服务启动] 服务启动完成")
        return True

    except subprocess.TimeoutExpired:
        print(f"[服务启动] 启动超时")
        return False
    except Exception as e:
        print(f"[服务启动] 启动失败: {e}")
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

    # 2. 检测 WebSocket 服务器
    print(f"\n[2/2] 检测 WebSocket 服务器: {ws_host}:{ws_port}")
    status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

    # 检查本地端口监听状态，避免重复启动
    api_listening = check_port_listening(api_port)
    ws_listening = check_port_listening(ws_port)

    print(f"\n[端口监听] API端口 {api_port}: {'已监听' if api_listening else '未监听'}")
    print(f"[端口监听] WebSocket端口 {ws_port}: {'已监听' if ws_listening else '未监听'}")

    # 如果任一服务端口未监听，尝试启动所有服务
    if not api_listening or not ws_listening:
        print(f"\n      状态: 检测到服务未启动，尝试启动所有服务...")

        # 启动服务
        if start_local_services():
            # 等待服务完全启动
            print(f"\n[服务检测] 等待服务完全启动...")
            time.sleep(3)

            # 重新检测服务状态
            status['api_server'] = check_port(api_host, api_port)
            status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

            if status['api_server']:
                print(f"[API服务] 状态: 启动成功")
            else:
                print(f"[API服务] 状态: 启动失败")

            if status['ws_server']:
                print(f"[推理服务] 状态: 启动成功")
            else:
                print(f"[推理服务] 状态: 启动失败")
        else:
            print(f"[服务启动] 服务启动失败")
    else:
        print(f"\n      状态: 所有服务已在运行")

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
