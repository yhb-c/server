# -*- coding: utf-8 -*-
"""
服务启动统一管理模块
整合网络连接检测和服务启动功能
"""

import subprocess
import socket
import time
import platform
from pathlib import Path


def is_local_host(host):
    """
    判断主机地址是否为本地地址

    Args:
        host: 主机地址

    Returns:
        bool: 是本地地址返回 True，否则返回 False
    """
    import netifaces

    local_addresses = ['localhost', '127.0.0.1', '0.0.0.0']

    # 检查是否为常见的本地地址
    if host in local_addresses:
        return True

    # 获取本机所有网络接口的IP地址
    try:
        local_ips = []

        # 方法1: 使用netifaces获取所有网络接口的IP
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            # 获取IPv4地址
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    if 'addr' in addr_info:
                        local_ips.append(addr_info['addr'])

        return host in local_ips
    except Exception as e:
        # 备用方法：使用socket
        try:
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            return host in local_ips
        except Exception:
            return False


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
    except Exception:
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
    except Exception:
        return False


def start_api_local():
    """
    单机模式：通过subprocess启动API服务

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        api_dir = project_root / 'server' / 'network' / 'api'
        api_executable = api_dir / 'liquid-api'
        log_dir = project_root / 'logs'

        # 创建日志目录
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'api.log'

        # 检查可执行文件是否存在
        if not api_executable.exists():
            return False

        # 启动API服务（后台运行）
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                [str(api_executable)],
                cwd=str(api_dir),
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        # 等待服务启动
        time.sleep(2)

        # 检查进程是否还在运行
        poll_result = process.poll()
        if poll_result is not None:
            return False

        return True

    except Exception as e:
        return False


def start_websocket_local():
    """
    单机模式：通过subprocess启动WebSocket服务

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        server_dir = project_root / 'server' / 'network'
        start_script = server_dir / 'start_websocket_server.py'
        log_dir = project_root / 'logs'

        # 创建日志目录
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'websocket.log'

        # 检查启动脚本是否存在
        if not start_script.exists():
            return False

        # 激活conda环境并启动服务
        conda_activate = 'source ~/anaconda3/bin/activate liquid'
        export_env = 'export PYTHONPATH="/home/lqj/liquid/server:$PYTHONPATH" && export LD_LIBRARY_PATH="/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH"'
        start_cmd = f'cd {server_dir} && python start_websocket_server.py'

        full_cmd = f'{conda_activate} && {export_env} && {start_cmd}'

        # 启动WebSocket服务（后台运行）
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                full_cmd,
                shell=True,
                executable='/bin/bash',
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        # 等待服务启动
        time.sleep(3)

        # 检查进程是否还在运行
        poll_result = process.poll()
        if poll_result is not None:
            return False

        return True

    except Exception as e:
        return False


def check_and_start_services(config):
    """
    检测网络连接状态并自动启动服务
    自动判断本地模式或远程模式：
    - 本地模式：服务器地址是本机IP，尝试启动本地服务
    - 远程模式：服务器地址是远程IP，只检测连接状态

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

    # 判断是否为本地模式
    is_local = is_local_host(api_host)

    # 1. 检测 API 服务器
    status['api_server'] = check_port(api_host, api_port)

    # 2. 检测 WebSocket 服务器
    status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

    # 只有在本地模式下才尝试启动服务
    if is_local:
        # 检查本地端口监听状态，避免重复启动
        api_listening = check_port_listening(api_port)
        ws_listening = check_port_listening(ws_port)

        # 自动启动未运行的服务
        if not api_listening or not ws_listening:
            # 启动API服务
            if not api_listening:
                if start_api_local():
                    time.sleep(1)
                    status['api_server'] = check_port(api_host, api_port)

            # 启动WebSocket服务
            if not ws_listening:
                if start_websocket_local():
                    time.sleep(2)
                    status['ws_server'] = check_port(ws_host, ws_port, is_websocket=True)

    return status
