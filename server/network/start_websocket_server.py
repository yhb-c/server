#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket服务器启动脚本
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
server_dir = current_dir.parent
project_root = server_dir.parent
sys.path.insert(0, str(server_dir))

from network.enhanced_ws_server import EnhancedWebSocketServer


# 配置日志
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'websocket_server.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


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
