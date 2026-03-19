#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
部署脚本 - 将服务端代码部署到192.168.0.121
"""

import os
import sys
import subprocess
from pathlib import Path

# 服务器配置
SERVER_IP = "192.168.0.121"
SERVER_USER = "lqj"
SERVER_PASSWORD = "admin"
SERVER_PATH = "/home/lqj/liquid/server"
CONDA_ENV = "liquid"

def main():
    print("=" * 60)
    print("WebSocket服务端部署脚本")
    print("=" * 60)

    # 当前项目路径
    project_root = Path(__file__).parent
    server_dir = project_root / "server"

    if not server_dir.exists():
        print(f"错误: 服务端目录不存在: {server_dir}")
        return 1

    print(f"\n1. 准备部署文件...")
    print(f"   源目录: {server_dir}")
    print(f"   目标服务器: {SERVER_USER}@{SERVER_IP}:{SERVER_PATH}")

    # 使用scp命令上传文件（需要手动输入密码）
    print(f"\n2. 上传文件到服务器...")
    print(f"   提示: 请输入密码 'admin'")

    # 使用rsync或scp上传
    scp_cmd = f'scp -r "{server_dir}" {SERVER_USER}@{SERVER_IP}:/home/lqj/liquid/'
    print(f"   执行命令: {scp_cmd}")
    print("\n请在下方输入密码...")

    result = subprocess.run(scp_cmd, shell=True)

    if result.returncode != 0:
        print("\n错误: 文件上传失败")
        return 1

    print("\n✓ 文件上传成功")

    # 生成SSH命令脚本
    print(f"\n3. 生成服务器启动命令...")

    ssh_commands = f"""
# 激活conda环境
source ~/anaconda3/bin/activate {CONDA_ENV}

# 进入服务端目录
cd {SERVER_PATH}

# 安装依赖
pip install websockets

# 启动WebSocket服务
echo "启动WebSocket服务..."
python websocket/start_websocket_server.py
"""

    print("\n请手动执行以下命令连接到服务器并启动服务:")
    print("-" * 60)
    print(f"ssh {SERVER_USER}@{SERVER_IP}")
    print(ssh_commands)
    print("-" * 60)

    # 或者直接执行SSH命令
    print("\n是否立即通过SSH启动服务? (需要输入密码)")
    choice = input("输入 y 继续, 其他键跳过: ").strip().lower()

    if choice == 'y':
        ssh_cmd = f'ssh {SERVER_USER}@{SERVER_IP} "{ssh_commands}"'
        print(f"\n执行SSH命令...")
        subprocess.run(ssh_cmd, shell=True)

    print("\n部署完成!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
