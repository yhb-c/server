#!/usr/bin/env python3
"""
简单的WebSocket测试服务器
用于测试消息推送性能
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def handle_client(websocket):
    """处理客户端连接"""
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"客户端连接: {client_id}")

    try:
        # 发送欢迎消息
        welcome = {
            'type': 'welcome',
            'message': 'WebSocket测试服务器已连接',
            'timestamp': datetime.now().isoformat()
        }
        await websocket.send(json.dumps(welcome))

        # 接收并回显消息
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.debug(f"收到消息: {data.get('type', 'unknown')}")

                # 简单回显确认
                response = {
                    'type': 'ack',
                    'timestamp': datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))

            except json.JSONDecodeError:
                logger.warning(f"无效的JSON消息")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"客户端断开: {client_id}")
    except Exception as e:
        logger.error(f"处理客户端错误: {e}")


async def main():
    """启动服务器"""
    host = '0.0.0.0'
    port = 8085

    # 设置最大消息大小为10MB
    server = await websockets.serve(
        handle_client,
        host,
        port,
        max_size=10 * 1024 * 1024,  # 10MB
        ping_interval=20,
        ping_timeout=10
    )

    logger.info(f"WebSocket测试服务器启动: ws://{host}:{port}")
    logger.info(f"最大消息大小: 10MB")
    logger.info("等待客户端连接...")

    await asyncio.Future()  # 永久运行


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n服务器已停止")