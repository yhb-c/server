
import os
import sys
import asyncio
import logging

# 添加路径
sys.path.insert(0, r"F:\liquid_detect\system_client_sever\server")
database_dir = os.path.join(r"F:\liquid_detect\system_client_sever\server", "database")
if os.path.exists(database_dir):
    sys.path.insert(0, database_dir)

async def start_ws_server():
    try:
        from client.websocket.ws_server import WebSocketServer
        ws_server = WebSocketServer(host="localhost", port=8085, channel_manager=None)
        await ws_server.start()
        print("WebSocket服务器启动成功: ws://localhost:8085")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"WebSocket服务器启动失败: {e}")

if __name__ == "__main__":
    asyncio.run(start_ws_server())
