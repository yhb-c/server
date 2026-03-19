#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket服务端独立启动脚本
用于在服务器上单独启动WebSocket服务
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def start_ws_server():
    """启动WebSocket服务器"""
    try:
        from websocket.ws_server import WebSocketServer

        # 创建WebSocket服务器
        # host='0.0.0.0' 表示监听所有网络接口，可以接受远程连接
        ws_server = WebSocketServer(host="0.0.0.0", port=8085, channel_manager=None)

        print("=" * 60)
        print("WebSocket服务器配置:")
        print(f"  监听地址: 0.0.0.0:8085")
        print(f"  客户端连接地址: ws://192.168.0.121:8085")
        print("=" * 60)

        # 启动服务器
        await ws_server.start()
        print("✓ WebSocket服务器启动成功!")
        print("按 Ctrl+C 停止服务器")

        # 保持运行
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"✗ WebSocket服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    try:
        asyncio.run(start_ws_server())
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        print("服务器已停止")
