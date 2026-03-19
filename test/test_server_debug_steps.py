#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
服务端调试步骤测试脚本
逐步测试服务端的各个关键步骤，确定问题所在
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

class ServerDebugTester:
    """服务端调试测试器"""
    
    def __init__(self, server_url='ws://192.168.0.121:8085'):
        self.server_url = server_url
        self.websocket = None
    
    async def connect(self):
        """连接WebSocket服务器"""
        try:
            print(f"连接服务器: {self.server_url}")
            self.websocket = await websockets.connect(self.server_url)
            print("✓ WebSocket连接成功")
            
            # 接收欢迎消息
            welcome = await self.receive_message(timeout=5)
            if welcome:
                print(f"✓ 收到欢迎消息: {welcome.get('message', '')}")
            
            return True
        except Exception as e:
            print(f"✗ WebSocket连接失败: {e}")
            return False
    
    async def send_command(self, command, **kwargs):
        """发送命令"""
        message = {'command': command, **kwargs}
        await self.websocket.send(json.dumps(message))
        print(f"→ 发送命令: {command}")
    
    async def receive_message(self, timeout=10):
        """接收消息"""
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(message)
            print(f"← 收到响应: {data.get('type', 'unknown')}")
            return data
        except asyncio.TimeoutError:
            print(f"✗ 接收消息超时 ({timeout}秒)")
            return None
        except Exception as e:
            print(f"✗ 接收消息失败: {e}")
            return None
    
    async def test_step_1_subscribe(self):
        """步骤1: 测试通道订阅"""
        print("\n" + "="*50)
        print("步骤1: 测试通道订阅")
        print("="*50)
        
        await self.send_command('subscribe', channel_id='channel1')
        response = await self.receive_message()
        
        if response and response.get('success'):
            print("✓ 通道订阅成功")
            return True
        else:
            print("✗ 通道订阅失败")
            return False
    
    async def test_step_2_load_model(self):
        """步骤2: 测试模型加载"""
        print("\n" + "="*50)
        print("步骤2: 测试模型加载")
        print("="*50)
        
        # 使用相对路径，服务器会自动转换为绝对路径
        model_path = "database/model/detection_model/bestmodel/tensor.pt"
        print(f"模型路径: {model_path}")
        print("注意: 服务器将基于项目根目录解析此路径")
        
        await self.send_command(
            'load_model',
            channel_id='channel1',
            model_path=model_path,
            device='cuda'
        )
        
        response = await self.receive_message(timeout=30)  # 模型加载可能需要更长时间
        
        if response and response.get('success'):
            print("✓ 模型加载成功")
            return True
        else:
            print("✗ 模型加载失败")
            if response:
                print(f"  错误信息: {response.get('message', '未知错误')}")
            return False
    
    async def test_step_3_configure_channel(self):
        """步骤3: 测试通道配置"""
        print("\n" + "="*50)
        print("步骤3: 测试通道配置")
        print("="*50)
        
        config = {
            'rtsp_url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
            'boxes': [(320, 240, 200)],
            'fixed_bottoms': [400],
            'fixed_tops': [100],
            'actual_heights': [50.0],
            'annotation_initstatus': [0]
        }
        
        print(f"配置参数:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        await self.send_command(
            'configure_channel',
            channel_id='channel1',
            config=config
        )
        
        response = await self.receive_message()
        
        if response and response.get('success'):
            print("✓ 通道配置成功")
            return True
        else:
            print("✗ 通道配置失败")
            if response:
                print(f"  错误信息: {response.get('message', '未知错误')}")
            return False
    
    async def test_step_4_start_detection(self):
        """步骤4: 测试启动检测"""
        print("\n" + "="*50)
        print("步骤4: 测试启动检测")
        print("="*50)
        
        await self.send_command('start_detection', channel_id='channel1')
        
        response = await self.receive_message(timeout=30)  # 启动检测可能需要更长时间
        
        if response and response.get('success'):
            print("✓ 检测启动成功")
            return True
        else:
            print("✗ 检测启动失败")
            if response:
                print(f"  错误信息: {response.get('message', '未知错误')}")
            return False
    
    async def test_step_5_wait_detection_data(self):
        """步骤5: 等待检测数据"""
        print("\n" + "="*50)
        print("步骤5: 等待检测数据")
        print("="*50)
        
        print("等待检测结果...")
        data_received = False
        
        for i in range(10):  # 最多等待10次消息
            message = await self.receive_message(timeout=5)
            
            if message:
                msg_type = message.get('type')
                
                if msg_type == 'detection_result':
                    print("✓ 收到检测结果!")
                    heights = message.get('heights', [])
                    success = message.get('success', False)
                    print(f"  液位高度: {heights}")
                    print(f"  检测成功: {success}")
                    data_received = True
                    break
                elif msg_type == 'detection_status':
                    status = message.get('status')
                    print(f"  检测状态变化: {status}")
                else:
                    print(f"  收到其他消息: {msg_type}")
        
        if data_received:
            print("✓ 检测数据接收成功")
            return True
        else:
            print("✗ 未收到检测数据")
            return False
    
    async def test_step_6_stop_detection(self):
        """步骤6: 测试停止检测"""
        print("\n" + "="*50)
        print("步骤6: 测试停止检测")
        print("="*50)
        
        await self.send_command('stop_detection', channel_id='channel1')
        
        response = await self.receive_message()
        
        if response and response.get('success'):
            print("✓ 检测停止成功")
            return True
        else:
            print("✗ 检测停止失败")
            if response:
                print(f"  错误信息: {response.get('message', '未知错误')}")
            return False
    
    async def run_debug_test(self):
        """运行调试测试"""
        print("服务端调试步骤测试")
        print("目标: 确定检测流程在哪一步出现问题")
        print(f"服务器: {self.server_url}")
        
        # 连接服务器
        if not await self.connect():
            return
        
        try:
            # 逐步测试
            steps = [
                ("通道订阅", self.test_step_1_subscribe),
                ("模型加载", self.test_step_2_load_model),
                ("通道配置", self.test_step_3_configure_channel),
                ("启动检测", self.test_step_4_start_detection),
                ("等待数据", self.test_step_5_wait_detection_data),
                ("停止检测", self.test_step_6_stop_detection),
            ]
            
            results = {}
            
            for step_name, step_func in steps:
                try:
                    result = await step_func()
                    results[step_name] = result
                    
                    if not result:
                        print(f"\n❌ 测试在 '{step_name}' 步骤失败!")
                        print("请检查服务端日志以获取详细错误信息")
                        break
                    
                    # 步骤间稍作等待
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"\n💥 步骤 '{step_name}' 发生异常: {e}")
                    results[step_name] = False
                    break
            
            # 输出结果摘要
            print("\n" + "="*50)
            print("测试结果摘要")
            print("="*50)
            
            for step_name, result in results.items():
                status = "✓ 成功" if result else "✗ 失败"
                print(f"{step_name:12} {status}")
            
            success_count = sum(1 for r in results.values() if r)
            total_count = len(results)
            
            print(f"\n成功步骤: {success_count}/{total_count}")
            
            if success_count == total_count:
                print("🎉 所有步骤测试通过!")
            else:
                failed_step = next((name for name, result in results.items() if not result), "未知")
                print(f"⚠️  测试在 '{failed_step}' 步骤失败")
                print("建议:")
                print("1. 检查服务端控制台日志")
                print("2. 确认RTSP相机连接正常")
                print("3. 确认模型文件存在")
                print("4. 检查网络连接")
        
        finally:
            if self.websocket:
                await self.websocket.close()
                print("\nWebSocket连接已关闭")

async def main():
    """主函数"""
    print("请确保:")
    print("1. 服务器192.168.0.121已启动WebSocket服务")
    print("2. RTSP相机192.168.0.27可正常访问")
    print("3. 检测模型文件存在")
    print()
    
    input("按回车键开始调试测试...")
    
    tester = ServerDebugTester()
    await tester.run_debug_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()