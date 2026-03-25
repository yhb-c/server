# -*- coding: utf-8 -*-
"""
液位检测系统客户端 - 主程序入口（带网络检测和自动连接）
"""

import sys
import subprocess
import platform
import os
import time
import threading
from pathlib import Path

from qtpy import QtWidgets
from qtpy.QtCore import Qt

# ============================================================
# 运行模式配置
# ============================================================
# True: 离线模式 - 跳过所有远程服务检测和启动
# False: 在线模式 - 连接服务器并启动远程服务
OFFLINE_MODE = True
# ============================================================

# 添加 client 目录到路径
client_path = Path(__file__).parent / 'client'
sys.path.insert(0, str(client_path))

from client.widgets.login import LoginWindow
from client.utils.config import load_config
from client.utils.logger import setup_logging
from ssh_connect.ssh_manager import SSHManager


def check_and_setup_ssh_connection():
    """
    检查并设置SSH免密连接
    
    Returns:
        SSHManager: SSH管理器实例
    """
    print("\n[SSH连接] 检查SSH免密连接配置...")
    
    ssh_manager = SSHManager()
    
    # 检查SSH是否已配置
    if ssh_manager.is_ssh_configured():
        print("[SSH连接] SSH配置文件已存在")
        
        # 测试连接
        if ssh_manager.test_ssh_connection():
            print("[SSH连接] SSH免密连接正常")
            return ssh_manager
        else:
            print("[SSH连接] SSH连接测试失败，尝试重新配置...")
    else:
        print("[SSH连接] SSH未配置，开始自动配置...")
    
    # 尝试设置SSH连接
    try:
        if ssh_manager.setup_ssh_connection():
            print("[SSH连接] SSH免密连接配置成功")
            return ssh_manager
        else:
            print("[SSH连接] SSH免密连接配置失败")
            print("[SSH连接] 将使用网络检测方式连接远程服务")
            return ssh_manager
    except Exception as e:
        print(f"[SSH连接] SSH配置异常: {e}")
        print("[SSH连接] 将使用网络检测方式连接远程服务")
        return ssh_manager


def check_remote_services_via_ssh(ssh_manager):
    """
    通过SSH检查远程服务状态
    
    Args:
        ssh_manager: SSH管理器实例
        
    Returns:
        dict: 远程服务状态
    """
    print("\n[远程服务] 通过SSH检查远程服务状态...")
    
    try:
        # 检查SSH连接是否可用
        if not ssh_manager.test_ssh_connection():
            print("[远程服务] SSH连接不可用，跳过远程服务检查")
            return {}
        
        # 检查远程服务
        remote_status = ssh_manager.check_remote_services()
        
        print("\n[远程服务] 远程服务状态:")
        if remote_status.get('go_api'):
            print("[远程服务] Go API服务: 正在运行")
        else:
            print("[远程服务] Go API服务: 未运行")
            
        if remote_status.get('python_inference'):
            print("[远程服务] Python推理服务: 正在运行")
        else:
            print("[远程服务] Python推理服务: 未运行")
        
        return remote_status
        
    except Exception as e:
        print(f"[远程服务] 检查远程服务异常: {e}")
        return {}


def start_remote_services_if_needed(ssh_manager, remote_status):
    """
    如果需要，启动远程服务
    
    Args:
        ssh_manager: SSH管理器实例
        remote_status: 远程服务状态
    """
    print("\n[远程服务] 检查是否需要启动远程服务...")
    
    try:
        # 检查SSH连接
        if not ssh_manager.test_ssh_connection():
            print("[远程服务] SSH连接不可用，无法启动远程服务")
            return
        
        # 启动Go API服务
        if not remote_status.get('go_api'):
            print("[远程服务] 尝试启动Go API服务...")
            
            # 切换到项目目录并启动API服务
            start_api_cmd = (
                "cd /home/lqj/liquid && "
                "source /home/lqj/anaconda3/etc/profile.d/conda.sh && "
                "conda activate liquid && "
                "cd api && "
                "nohup ./liquid-api > ../logs/api.log 2>&1 & "
                "echo $! > ../logs/api.pid"
            )
            
            result = ssh_manager.execute_remote_command(start_api_cmd, timeout=10)
            if result['success']:
                print("[远程服务] Go API服务启动命令执行成功")
                time.sleep(2)  # 等待服务启动
            else:
                print(f"[远程服务] Go API服务启动失败: {result['stderr']}")
        
        # 启动Python推理服务
        if not remote_status.get('python_inference'):
            print("[远程服务] 尝试启动Python推理服务...")
            
            # 设置环境变量并启动推理服务
            start_inference_cmd = (
                "cd /home/lqj/liquid && "
                "source /home/lqj/anaconda3/etc/profile.d/conda.sh && "
                "conda activate liquid && "
                "export LD_LIBRARY_PATH=/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH && "
                "cd server && "
                "nohup python -m websocket.ws_server > ../logs/inference.log 2>&1 & "
                "echo $! > ../logs/inference.pid"
            )
            
            result = ssh_manager.execute_remote_command(start_inference_cmd, timeout=10)
            if result['success']:
                print("[远程服务] Python推理服务启动命令执行成功")
                time.sleep(2)  # 等待服务启动
            else:
                print(f"[远程服务] Python推理服务启动失败: {result['stderr']}")
        
        # 再次检查服务状态
        print("[远程服务] 验证服务启动状态...")
        time.sleep(3)  # 等待服务完全启动
        updated_status = ssh_manager.check_remote_services()
        
        if updated_status.get('go_api'):
            print("[远程服务] Go API服务启动成功")
        if updated_status.get('python_inference'):
            print("[远程服务] Python推理服务启动成功")
            
    except Exception as e:
        print(f"[远程服务] 启动远程服务异常: {e}")


def start_api_service():
    """
    启动API服务 (端口8084)
    """
    print("\n[服务启动] 正在启动API服务...")
    
    # 项目根目录
    project_root = Path(__file__).parent
    
    # API服务路径
    api_path = project_root / "api"
    
    # 检查是否存在API服务可执行文件
    if platform.system().lower() == 'windows':
        api_executable = api_path / "liquid-api.exe"
    else:
        api_executable = api_path / "liquid-api"
    
    try:
        if api_executable.exists():
            # 启动API服务
            print(f"[API服务] 启动可执行文件: {api_executable}")
            process = subprocess.Popen(
                [str(api_executable)],
                cwd=str(api_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"[API服务] 进程ID: {process.pid}")
            print(f"[API服务] 服务地址: http://localhost:8084")
            return process
        else:
            print(f"[API服务] API可执行文件不存在: {api_executable}")
            print(f"[API服务] 请先构建API服务:")
            if platform.system().lower() == 'windows':
                print(f"[API服务] 运行: cd api ; .\\build.bat")
            else:
                print(f"[API服务] 运行: cd api && ./build.sh")
            print(f"[API服务] 跳过本地启动，将检测远程服务连接")
            return None
            
    except Exception as e:
        print(f"[API服务] 启动失败: {e}")
        return None




def monitor_service(service_name, process):
    """
    监控服务进程输出
    
    Args:
        service_name: 服务名称
        process: 进程对象
    """
    if not process:
        return
        
    def read_output(pipe, prefix):
        try:
            for line in iter(pipe.readline, ''):
                if line.strip():
                    print(f"[{service_name}] {prefix}: {line.strip()}")
        except Exception as e:
            print(f"[{service_name}] 输出监控异常: {e}")
    
    # 启动输出监控线程
    stdout_thread = threading.Thread(
        target=read_output, 
        args=(process.stdout, "输出"),
        daemon=True
    )
    stderr_thread = threading.Thread(
        target=read_output, 
        args=(process.stderr, "错误"),
        daemon=True
    )
    
    stdout_thread.start()
    stderr_thread.start()


def check_service_status(port, service_name, max_retries=10):
    """
    检查服务是否启动成功
    
    Args:
        port: 服务端口
        service_name: 服务名称
        max_retries: 最大重试次数
    
    Returns:
        bool: 服务是否启动成功
    """
    import socket
    
    for i in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result == 0:
                print(f"[{service_name}] 服务启动成功，端口{port}已开放")
                return True
        except Exception:
            pass
        
        print(f"[{service_name}] 等待服务启动... ({i+1}/{max_retries})")
        time.sleep(2)
    
    print(f"[{service_name}] 服务启动超时，端口{port}未响应")
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


def check_network_connectivity(config):
    """
    检测网络连接状态

    Args:
        config: 配置字典

    Returns:
        dict: 连接状态信息
            {
                'api_server': bool,  # API服务器连接状态
                'ws_server': bool,   # WebSocket服务器连接状态
                'camera': bool       # 摄像头连接状态
            }
    """
    print("\n" + "="*50)
    print("网络连接检测")
    print("="*50)

    status = {
        'api_server': False,
        'ws_server': False,
        'camera': False
    }

    # 1. 检测 API 服务器
    api_url = config.get('server', {}).get('api_url', 'http://localhost:8084')
    api_host = api_url.split('://')[1].split(':')[0] if '://' in api_url else 'localhost'

    print(f"\n[1/3] 检测 API 服务器: {api_host}")
    status['api_server'] = ping_host(api_host)
    print(f"      状态: {'连接成功' if status['api_server'] else '连接失败'}")

    # 2. 检测 WebSocket 服务器
    ws_url = config.get('server', {}).get('ws_url', 'ws://localhost:8085')
    ws_host = ws_url.split('://')[1].split(':')[0] if '://' in ws_url else 'localhost'

    print(f"\n[2/3] 检测 WebSocket 服务器: {ws_host}")
    status['ws_server'] = ping_host(ws_host)
    print(f"      状态: {'连接成功' if status['ws_server'] else '连接失败'}")

    # 3. 检测摄像头（从配置中读取）
    # 这里假设摄像头地址在 channels 配置中
    camera_host = None
    channels = config.get('channels', {})
    if channels:
        # 获取第一个通道的地址
        first_channel = next(iter(channels.values()), {})
        rtsp_url = first_channel.get('address', '')
        if rtsp_url and '@' in rtsp_url:
            # 从 rtsp://admin:password@192.168.0.27:8000/stream1 提取 IP
            camera_host = rtsp_url.split('@')[1].split(':')[0]

    if camera_host:
        print(f"\n[3/3] 检测摄像头: {camera_host}")
        status['camera'] = ping_host(camera_host)
        print(f"      状态: {'连接成功' if status['camera'] else '连接失败'}")
    else:
        print(f"\n[3/3] 检测摄像头: 未配置")
        print(f"      状态: - 跳过")

    print("\n" + "="*50)
    print("网络检测完成")
    print("="*50 + "\n")

    return status


def main():
    """主函数"""
    print("="*60)
    print("液位检测系统客户端启动")
    print(f"运行模式: {'离线模式' if OFFLINE_MODE else '在线模式'}")
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

    # 初始化变量
    ssh_manager = None
    remote_status = {}

    # 根据模式决定是否执行远程服务相关操作
    if not OFFLINE_MODE:
        # 在线模式：检查并连接远程服务
        # 1. 检查并设置SSH免密连接
        ssh_manager = check_and_setup_ssh_connection()

        # 2. 检查远程服务状态
        remote_status = check_remote_services_via_ssh(ssh_manager)

        # 3. 如果需要，启动远程服务
        start_remote_services_if_needed(ssh_manager, remote_status)
    else:
        # 离线模式：跳过所有远程服务检测
        print("\n[离线模式] 跳过SSH连接和远程服务检测")

    # 4. 启动本地服务
    print("\n[系统启动] 正在检查本地后端服务...")
    
    # 检查API服务 (端口8084) - 通常部署在服务器上
    api_process = start_api_service()
    if api_process:
        monitor_service("API服务", api_process)
        # 检查API服务是否启动成功
        api_started = check_service_status(8084, "API服务")
    else:
        api_started = False
        print("[API服务] 本地未启动，将检测远程服务器连接")
    
    # 推理服务只在远程服务器运行，不启动本地服务
    print("[推理服务] 推理服务部署在远程服务器，跳过本地启动")
    inference_started = False
    inference_process = None

    # 5. 网络连接检测
    print("\n[系统启动] 检测服务连接状态...")
    network_status = check_network_connectivity(config)

    # 6. 检查关键服务是否可用
    print("\n[系统启动] 服务状态总结:")
    
    # API服务状态
    if api_started:
        print("[API服务] 状态: 本地正常运行")
    elif network_status['api_server'] or remote_status.get('go_api'):
        if remote_status.get('go_api'):
            print("[API服务] 状态: 远程服务器正常运行")
        else:
            print("[API服务] 状态: 远程服务器连接正常")
    else:
        print("[API服务] 状态: 本地未启动且远程连接异常")
        print("[警告] API 服务器连接失败，部分功能可能不可用")

    # 推理服务状态
    if remote_status.get('python_inference'):
        print("[推理服务] 状态: 远程服务器正常运行")
    else:
        print("[推理服务] 状态: 远程服务器连接异常")
        print("[警告] WebSocket 服务器连接失败，实时数据推送功能可能不可用")

    # 摄像头状态
    if network_status['camera']:
        print("[摄像头] 状态: 连接正常")
    else:
        print("[摄像头] 状态: 连接异常或未配置")

    # SSH连接状态
    if not OFFLINE_MODE:
        if ssh_manager and ssh_manager.is_ssh_configured() and ssh_manager.test_ssh_connection():
            print("[SSH连接] 状态: 免密连接正常")
        else:
            print("[SSH连接] 状态: 未配置或连接异常")
    else:
        print("[SSH连接] 状态: 离线模式")

    print("\n[系统启动] 启动客户端界面...")
    
    # 显示登录窗口
    login_window = LoginWindow(config)
    login_window.show()

    print("[系统启动] 客户端界面已启动")
    print("="*60)

    # 启动事件循环
    try:
        exit_code = app.exec_()
    finally:
        # 清理服务进程
        print("\n[系统关闭] 正在关闭后端服务...")
        
        if api_process and api_process.poll() is None:
            print("[API服务] 正在关闭本地服务...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
                print("[API服务] 本地服务已关闭")
            except subprocess.TimeoutExpired:
                print("[API服务] 强制关闭本地服务...")
                api_process.kill()
        
        if inference_process and inference_process.poll() is None:
            print("[推理服务] 正在关闭...")
            inference_process.terminate()
            try:
                inference_process.wait(timeout=5)
                print("[推理服务] 已关闭")
            except subprocess.TimeoutExpired:
                print("[推理服务] 强制关闭...")
                inference_process.kill()
        
        print("[系统关闭] 所有本地服务已关闭")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()