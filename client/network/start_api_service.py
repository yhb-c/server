# -*- coding: utf-8 -*-
"""
API服务启动模块
"""

import subprocess
import time
from pathlib import Path


def start_api_service():
    """
    启动API服务

    Returns:
        bool: 启动成功返回True，否则返回False
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        api_dir = project_root / 'api'
        api_executable = api_dir / 'liquid-api'
        log_dir = project_root / 'logs'

        # 创建日志目录
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'api_service.log'

        # 检查可执行文件是否存在
        if not api_executable.exists():
            print(f"[错误] API可执行文件不存在: {api_executable}")
            return False

        print(f"[启动] 正在启动API服务...")

        # 启动API服务（后台运行）
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                [str(api_executable)],
                cwd=str(api_dir),
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        print(f"[启动] API服务已启动，PID: {process.pid}")
        print(f"[日志] {log_file}")

        # 等待服务启动
        time.sleep(2)

        return True

    except Exception as e:
        print(f"[错误] 启动API服务失败: {e}")
        return False
