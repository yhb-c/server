#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单WebSocket连接测试脚本
测试基本的WebSocket通信功能
"""

import asyncio
import websockets
import json
import time
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_basic_websocket():
    """测试基本WebSocket功能"""
    server_url = 'ws://192.168.0.121:8085'
    
    try:
        print(f"连接服务器: {server_url}")
        websocket = await websockets.connect(server_url)
        print("✓ WebSocket连接成功")
        
        # 测试1: 接收欢迎消息
        try:
            welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            welcome_data = json.loads(welcome_msg)
            print(f"✓ 收到欢迎消息: {welcome_data.get('message', '')}")
        except asyncio.TimeoutError:
            print("⚠️  未收到欢迎消息（可能正常）")
        
        # 测试2: 发送ping命令
        print("\n测试ping命令...")
        ping_msg = {'command': 'ping'}
        await websocket.send(json.dumps(ping_msg))
        print("→ 发送ping命令")
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"← 收到响应: {response_data.get('type', 'unknown')}")
            
            if response_data.get('type') == 'pong':
                print("✓ Ping/Pong测试成功")
            else:
                print(f"⚠️  收到意外响应: {response_data}")
        except asyncio.TimeoutError:
            print("✗ Ping命令响应超时")
        
        # 测试3: 发送订阅命令
        print("\n测试订阅命令...")
        subscribe_msg = {'command': 'subscribe', 'channel_id': 'channel1'}
        await websocket.send(json.dumps(subscribe_msg))
        print("→ 发送订阅命令")
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"← 收到响应: {response_data}")
            
            if response_data.get('success'):
                print("✓ 订阅命令成功")
            else:
                print(f"✗ 订阅命令失败: {response_data.get('message', '未知错误')}")
        except asyncio.TimeoutError:
            print("✗ 订阅命令响应超时")
        
        # 测试4: 发送状态查询命令
        print("\n测试状态查询命令...")
        status_msg = {'command': 'get_status'}
        await websocket.send(json.dumps(status_msg))
        print("→ 发送状态查询命令")
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"← 收到响应类型: {response_data.get('type', 'unknown')}")
            
            if response_data.get('success'):
                print("✓ 状态查询成功")
                data = response_data.get('data', {})
                print(f"  服务器状态: {len(data)} 个通道")
            else:
                print(f"✗ 状态查询失败: {response_data.get('message', '未知错误')}")
        except asyncio.TimeoutError:
            print("✗ 状态查询响应超时")
        
        # 测试5: 发送一个简单的模型加载命令（不等待完成）
        print("\n测试模型加载命令发送...")
        model_msg = {
            'command': 'load_model',
            'channel_id': 'channel1',
            'model_path': 'database/model/detection_model/bestmodel/tensor.pt',
            'device': 'cuda'
        }
        await websocket.send(json.dumps(model_msg))
        print("→ 发送模型加载命令")
        print("  注意: 不等待响应，只测试命令发送")
        
        await websocket.close()
        print("\n✓ WebSocket连接已关闭")
        
        print("\n=== 基本WebSocket通信测试完成 ===")
        print("如果ping/pong和订阅命令都成功，说明WebSocket通信正常")
        print("模型加载超时可能是由于:")
        print("1. 模型文件不存在或路径错误")
        print("2. CUDA环境问题")
        print("3. 模型加载过程中的异常")
        print("4. 服务端代码逻辑问题")
        
    except Exception as e:
        print(f"✗ WebSocket测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("简单WebSocket连接测试")
    print("测试基本的WebSocket通信功能")
    print()
    
    await test_basic_websocket()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()