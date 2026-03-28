# -*- coding: utf-8 -*-
"""
WebSocket推理服务启动模块
"""

import subprocess
import time
from pathlib import Path


def start_websocket_service():
    """
    启动WebSocket推理服务

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        server_dir = project_root / 'server'
        start_script = server_dir / 'start_websocket_server.py'
        log_dir = project_root / 'logs'

        # 创建日志目录
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'websocket_service.log'

        # 检查启动脚本是否存在
        if not start_script.exists():
            print(f"[错误] WebSocket启动脚本不存在: {start_script}")
            return False

        print(f"[启动] 正在启动WebSocket推理服务...")

        # 激活conda环境并启动服务
        conda_activate = 'source ~/anaconda3/bin/activate liquid'
        export_env = 'export PYTHONPATH="/home/lqj/liquid/server:$PYTHONPATH" && export LD_LIBRARY_PATH="/home/lqj/liquid/sdk/hikvision/lib:$LD_LIBRARY_PATH"'
        start_cmd = f'cd {server_dir} && python start_websocket_server.py'

        full_cmd = f'{conda_activate} && {export_env} && {start_cmd}'

        # 启动WebSocket服务（后台运行）
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                full_cmd,
                shell=True,
                executable='/bin/bash',
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        print(f"[启动] WebSocket服务已启动，PID: {process.pid}")
        print(f"[日志] {log_file}")

        # 等待服务启动
        time.sleep(3)

        return True

    except Exception as e:
        print(f"[错误] 启动WebSocket服务失败: {e}")
        return False
