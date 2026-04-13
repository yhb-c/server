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

# 全局SDK平台配置
# True: 使用Windows版本SDK（HCNetSDK.dll, PlayCtrl.dll）
# False: 使用Linux版本SDK（libhcnetsdk.so, libPlayCtrl.so）
USE_WINDOWS_SDK = True

# 添加 client 目录到路径
client_path = Path(__file__).parent / 'client'
sys.path.insert(0, str(client_path))

from client.widgets.login import LoginWindow
from client.utils.config import load_config
from client.utils.logger import setup_logging
from client.network.start_service import check_and_start_services


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

    # 网络连接检测并启动服务
    network_status = check_and_start_services(config)

    # 创建并显示登录窗口
    login_window = LoginWindow(config)
    login_window.show()

    # 启动事件循环
    exit_code = app.exec_()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
