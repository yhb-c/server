#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket服务器启动脚本
"""

import os
import sys
from pathlib import Path

# 首先设置路径
current_dir = Path(__file__).parent
server_dir = current_dir.parent
project_root = server_dir.parent

# 必须在导入任何模块之前设置海康SDK环境变量
sdk_lib_path = os.path.join(server_dir, 'lib', 'lib')
sdk_com_path = os.path.join(sdk_lib_path, 'HCNetSDKCom')
current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{sdk_com_path}:{current_ld_path}"

# 添加项目路径
sys.path.insert(0, str(server_dir))

import asyncio
import logging
import signal

from network.enhanced_ws_server import EnhancedWebSocketServer


# 导入日志工具
sys.path.insert(0, str(project_root))
from server.utils.logger import setup_logging

# 配置日志 - 只输出到文件
logger = setup_logging('websocket', log_level='DEBUG', console_output=False)

# 配置根日志记录器，让网络相关模块的日志输出到websocket.log
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# 清除根日志的处理器
root_logger.handlers.clear()
# 添加文件处理器到根日志
log_dir = project_root / 'logs'
log_file = log_dir / 'websocket.log'
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# 配置server.detection和server.video模块的日志输出到server.log
server_log_file = log_dir / 'server.log'
server_file_handler = logging.FileHandler(server_log_file, mode='a', encoding='utf-8')
server_file_handler.setFormatter(formatter)

# 为server.detection模块配置独立的handler
detection_logger = logging.getLogger('server.detection')
detection_logger.handlers.clear()
detection_logger.addHandler(server_file_handler)
detection_logger.propagate = False  # 不传播到根logger

# 为server.video模块配置独立的handler
video_logger = logging.getLogger('server.video')
video_logger.handlers.clear()
video_logger.addHandler(server_file_handler)
video_logger.propagate = False  # 不传播到根logger


def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"接收到信号 {signum}，准备关闭服务器...")
    sys.exit(0)


async def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 创建并启动WebSocket服务器
    server = EnhancedWebSocketServer(host='0.0.0.0', port=8085)

    logger.info("="*60)
    logger.info("增强液位检测WebSocket服务器")
    logger.info("="*60)
    logger.info(f"监听地址: {server.host}:{server.port}")
    logger.info(f"客户端连接地址: ws://192.168.0.121:{server.port}")
    logger.info("="*60)

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("接收到键盘中断，关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行异常: {e}", exc_info=True)
    finally:
        await server.stop()
        logger.info("服务器已关闭")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
