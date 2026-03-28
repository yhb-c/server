import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://192.168.0.121:8085"
    try:
        async with websockets.connect(uri) as websocket:
            print("连接成功")
            
            # 接收欢迎消息
            welcome = await websocket.recv()
            print(f"收到欢迎消息: {welcome}")
            
            # 发送ping命令
            await websocket.send(json.dumps({"command": "ping"}))
            print("已发送ping命令")
            
            # 接收响应
            response = await websocket.recv()
            print(f"收到响应: {response}")
            
            await asyncio.sleep(1)
            print("测试完成")
            
    except Exception as e:
        print(f"连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
