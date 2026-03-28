# -*- coding: utf-8 -*-
"""
API服务启动模块
支持单机和分离部署两种模式
"""

import subprocess
import time
import socket
from pathlib import Path


def is_local_server(server_host):
    """
    检测服务器是否为本机

    Args:
        server_host: 服务器地址

    Returns:
        bool: 是本机返回True，否则返回False
    """
    try:
        import netifaces

        # 获取本机所有IP地址
        local_ips = set()

        # 添加localhost和127.0.0.1
        local_ips.add('localhost')
        local_ips.add('127.0.0.1')

        # 获取所有网络接口的IP地址
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            # 获取IPv4地址
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    local_ips.add(addr['addr'])

        # 检查服务器地址是否在本机IP列表中
        return server_host in local_ips

    except ImportError:
        # 如果没有netifaces，使用备用方法
        try:
            hostname = socket.gethostname()
            local_ips = set(['localhost', '127.0.0.1'])

            # 尝试获取本机IP
            try:
                # 通过连接外部地址获取本机IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ips.add(s.getsockname()[0])
                s.close()
            except:
                pass

            return server_host in local_ips
        except Exception as e:
            print(f"[检测] 无法判断服务器位置: {e}")
            return False
    except Exception as e:
        print(f"[检测] 无法判断服务器位置: {e}")
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
        log_file = log_dir / 'api_service.log'

        # 检查可执行文件是否存在
        if not api_executable.exists():
            print(f"[错误] API可执行文件不存在: {api_executable}")
            return False

        print(f"[单机模式] 通过subprocess启动API服务...")

        # 启动API服务（后台运行）
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                [str(api_executable)],
                cwd=str(api_dir),
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        print(f"[单机模式] API服务已启动，PID: {process.pid}")
        print(f"[日志] {log_file}")

        # 等待服务启动
        time.sleep(2)

        return True

    except Exception as e:
        print(f"[错误] 单机模式启动失败: {e}")
        return False


def start_api_remote(server_host, server_user='lqj', server_password='admin'):
    """
    分离模式：通过SSH远程启动API服务

    Args:
        server_host: 服务器地址
        server_user: 服务器用户名
        server_password: 服务器密码

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    try:
        print(f"[分离模式] 通过SSH远程启动API服务...")
        print(f"[分离模式] 服务器: {server_user}@{server_host}")

        # 构建SSH命令
        remote_cmd = (
            f"cd /home/lqj/liquid/server/network/api && "
            f"nohup ./liquid-api > logs/api_service.log 2>&1 &"
        )

        # 使用sshpass执行SSH命令
        ssh_cmd = f"sshpass -p '{server_password}' ssh -o StrictHostKeyChecking=no {server_user}@{server_host} '{remote_cmd}'"

        result = subprocess.run(
            ssh_cmd,
            shell=True,
            executable='/bin/bash',
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print(f"[分离模式] API服务启动命令已发送")
            time.sleep(2)
            return True
        else:
            print(f"[错误] SSH命令执行失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[错误] SSH连接超时")
        return False
    except FileNotFoundError:
        print(f"[错误] 未安装sshpass，无法使用SSH自动启动")
        print(f"[提示] 请在服务器上手动启动API服务")
        return False
    except Exception as e:
        print(f"[错误] 分离模式启动失败: {e}")
        return False


def start_api_service(server_host='192.168.0.121'):
    """
    智能启动API服务
    自动检测单机或分离模式，选择合适的启动方式

    Args:
        server_host: 服务器地址

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    print(f"\n[启动] 正在启动API服务...")
    print(f"[检测] 服务器地址: {server_host}")

    # 检测是否为单机模式
    if is_local_server(server_host):
        print(f"[检测] 检测到单机模式（客户端和服务端在同一台机器）")
        return start_api_local()
    else:
        print(f"[检测] 检测到分离模式（客户端和服务端在不同机器）")
        return start_api_remote(server_host)
