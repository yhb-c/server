#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket液位检测集成测试脚本
测试服务端液位检测和数据推送功能
"""

import asyncio
import websockets
import json
import time
import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class WebSocketDetectionTester:
    """WebSocket液位检测测试器"""
    
    def __init__(self, server_url='ws://192.168.0.121:8085'):
        self.server_url = server_url
        self.websocket = None
        self.received_messages = []
        self.test_results = {}
    
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            print(f"正在连接到服务器: {self.server_url}")
            self.websocket = await websockets.connect(self.server_url)
            print("WebSocket连接成功")
            return True
        except Exception as e:
            print(f"WebSocket连接失败: {e}")
            return False
    
    async def send_command(self, command, **kwargs):
        """发送命令到服务器"""
        if not self.websocket:
            print("WebSocket未连接")
            return False
        
        try:
            message = {
                'command': command,
                **kwargs
            }
            await self.websocket.send(json.dumps(message))
            print(f"发送命令: {command}")
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            return False
    
    async def receive_messages(self, timeout=30):
        """接收服务器消息"""
        try:
            message = await asyncio.wait_for(
                self.websocket.recv(), 
                timeout=timeout
            )
            data = json.loads(message)
            self.received_messages.append(data)
            print(f"收到消息: {data.get('type', 'unknown')}")
            return data
        except asyncio.TimeoutError:
            print("接收消息超时")
            return None
        except Exception as e:
            print(f"接收消息失败: {e}")
            return None
    
    async def test_basic_connection(self):
        """测试基本连接功能"""
        print("\n=== 测试基本连接 ===")
        
        # 发送ping命令
        await self.send_command('ping')
        
        # 接收pong响应
        response = await self.receive_messages(timeout=5)
        if response and response.get('type') == 'pong':
            print("✓ Ping/Pong测试通过")
            self.test_results['basic_connection'] = True
        else:
            print("✗ Ping/Pong测试失败")
            self.test_results['basic_connection'] = False
    
    async def test_channel_subscription(self):
        """测试通道订阅功能"""
        print("\n=== 测试通道订阅 ===")
        
        channel_id = 'channel1'
        
        # 订阅通道
        await self.send_command('subscribe', channel_id=channel_id)
        
        # 接收订阅响应
        response = await self.receive_messages(timeout=5)
        if response and response.get('success') == True:
            print(f"✓ 通道订阅成功: {channel_id}")
            self.test_results['channel_subscription'] = True
        else:
            print(f"✗ 通道订阅失败: {channel_id}")
            self.test_results['channel_subscription'] = False
    
    async def test_model_loading(self):
        """测试模型加载功能"""
        print("\n=== 测试模型加载 ===")
        
        channel_id = 'channel1'
        model_path = '/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt'
        
        # 加载模型
        await self.send_command(
            'load_model',
            channel_id=channel_id,
            model_path=model_path,
            device='cuda'
        )
        
        # 接收加载响应
        response = await self.receive_messages(timeout=10)
        if response and response.get('success') == True:
            print(f"✓ 模型加载成功: {model_path}")
            self.test_results['model_loading'] = True
        else:
            print(f"✗ 模型加载失败: {model_path}")
            self.test_results['model_loading'] = False
    
    async def test_channel_configuration(self):
        """测试通道配置功能"""
        print("\n=== 测试通道配置 ===")
        
        channel_id = 'channel1'
        config = {
            'rtsp_url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
            'boxes': [(320, 240, 200)],  # 中心点和尺寸
            'fixed_bottoms': [400],
            'fixed_tops': [100],
            'actual_heights': [50.0],  # 毫米
            'annotation_initstatus': [0]
        }
        
        # 配置通道
        await self.send_command(
            'configure_channel',
            channel_id=channel_id,
            config=config
        )
        
        # 接收配置响应
        response = await self.receive_messages(timeout=5)
        if response and response.get('success') == True:
            print(f"✓ 通道配置成功: {channel_id}")
            self.test_results['channel_configuration'] = True
        else:
            print(f"✗ 通道配置失败: {channel_id}")
            self.test_results['channel_configuration'] = False
    
    async def test_detection_start_stop(self):
        """测试检测启动和停止"""
        print("\n=== 测试检测启动停止 ===")
        
        channel_id = 'channel1'
        
        # 启动检测
        print("启动检测...")
        await self.send_command('start_detection', channel_id=channel_id)
        
        # 接收启动响应
        response = await self.receive_messages(timeout=10)
        if response and response.get('success') == True:
            print(f"✓ 检测启动成功: {channel_id}")
            
            # 等待检测结果
            print("等待检测结果...")
            detection_received = False
            for i in range(10):  # 最多等待10次消息
                result = await self.receive_messages(timeout=5)
                if result and result.get('type') == 'detection_result':
                    print(f"✓ 收到检测结果: 高度={result.get('heights', [])}")
                    detection_received = True
                    break
            
            if detection_received:
                self.test_results['detection_results'] = True
            else:
                print("✗ 未收到检测结果")
                self.test_results['detection_results'] = False
            
            # 停止检测
            print("停止检测...")
            await self.send_command('stop_detection', channel_id=channel_id)
            
            # 接收停止响应
            stop_response = await self.receive_messages(timeout=5)
            if stop_response and stop_response.get('success') == True:
                print(f"✓ 检测停止成功: {channel_id}")
                self.test_results['detection_start_stop'] = True
            else:
                print(f"✗ 检测停止失败: {channel_id}")
                self.test_results['detection_start_stop'] = False
        else:
            print(f"✗ 检测启动失败: {channel_id}")
            self.test_results['detection_start_stop'] = False
    
    async def test_status_query(self):
        """测试状态查询功能"""
        print("\n=== 测试状态查询 ===")
        
        # 查询所有状态
        await self.send_command('get_status')
        
        # 接收状态响应
        response = await self.receive_messages(timeout=5)
        if response and response.get('success') == True:
            print("✓ 状态查询成功")
            status_data = response.get('data', {})
            print(f"  活跃通道数: {len(status_data)}")
            self.test_results['status_query'] = True
        else:
            print("✗ 状态查询失败")
            self.test_results['status_query'] = False
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("开始WebSocket液位检测集成测试")
        print(f"服务器地址: {self.server_url}")
        
        # 连接服务器
        if not await self.connect():
            print("无法连接到服务器，测试终止")
            return
        
        try:
            # 接收欢迎消息
            welcome = await self.receive_messages(timeout=5)
            if welcome:
                print(f"收到欢迎消息: {welcome.get('message', '')}")
            
            # 运行测试
            await self.test_basic_connection()
            await self.test_channel_subscription()
            await self.test_model_loading()
            await self.test_channel_configuration()
            await self.test_detection_start_stop()
            await self.test_status_query()
            
        except Exception as e:
            print(f"测试过程中发生异常: {e}")
        finally:
            # 关闭连接
            if self.websocket:
                await self.websocket.close()
                print("WebSocket连接已关闭")
        
        # 输出测试结果
        self.print_test_summary()
    
    def print_test_summary(self):
        """输出测试结果摘要"""
        print("\n" + "="*50)
        print("测试结果摘要")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, result in self.test_results.items():
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name:25} {status}")
        
        print("-"*50)
        print(f"总测试数: {total_tests}")
        print(f"通过数量: {passed_tests}")
        print(f"失败数量: {total_tests - passed_tests}")
        print(f"通过率: {passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "0%")
        
        if passed_tests == total_tests:
            print("\n🎉 所有测试通过！液位检测系统集成成功！")
        else:
            print(f"\n⚠️  有 {total_tests - passed_tests} 个测试失败，请检查系统配置")

async def main():
    """主函数"""
    tester = WebSocketDetectionTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("WebSocket液位检测集成测试")
    print("确保服务器已启动: python server/websocket/start_websocket_server.py")
    print("按 Ctrl+C 可随时停止测试")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")