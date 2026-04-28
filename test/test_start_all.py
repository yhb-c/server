#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试启动所有通道"""

import asyncio
import websockets
import json

async def test_start_all():
    uri = "ws://localhost:8765"

    async with websockets.connect(uri) as websocket:
        # 发送start_all_detection指令
        message = {
            "action": "start_all_detection"
        }

        await websocket.send(json.dumps(message))
        print(f"已发送指令: {message}")

        # 接收响应
        response = await websocket.recv()
        print(f"收到响应: {response}")

if __name__ == "__main__":
    asyncio.run(test_start_all())
