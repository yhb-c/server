#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
客户端液位高度数据接收测试脚本
测试客户端网络命令管理器接收液位高度数据的功能
"""

import sys
import time
from pathlib import Path
from qtpy import QtCore, QtWidgets

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.network.command_manager import NetworkCommandManager

class LiquidHeightReceiver(QtCore.QObject):
    """液位高度数据接收器"""
    
    def __init__(self):
        super().__init__()
        self.command_manager = None
        self.received_heights = []
        self.connection_status = False
    
    def init_network(self):
        """初始化网络连接"""
        print("初始化网络命令管理器...")
        self.command_manager = NetworkCommandManager(
            server_url='ws://192.168.0.121:8085'
        )
        
        # 连接信号
        self.command_manager.connectionStatusChanged.connect(self.on_connection_status_changed)
        self.command_manager.liquidHeightReceived.connect(self.on_liquid_height_received)
        self.command_manager.detectionResultReceived.connect(self.on_detection_result_received)
        
        # 启动连接
        success = self.command_manager.start_connection()
        if success:
            print("网络连接启动成功")
        else:
            print("网络连接启动失败")
        
        return success
    
    def on_connection_status_changed(self, is_connected, message):
        """连接状态变化处理"""
        self.connection_status = is_connected
        status_text = "已连接" if is_connected else "未连接"
        print(f"连接状态变化: {status_text} - {message}")
        
        if is_connected:
            # 连接成功后订阅通道
            self.subscribe_channels()
    
    def subscribe_channels(self):
        """订阅通道"""
        print("订阅通道...")
        
        # 订阅channel1
        success = self.command_manager.send_subscribe_command('channel1')
        if success:
            print("订阅channel1成功")
        else:
            print("订阅channel1失败")
    
    def on_liquid_height_received(self, channel_id, heights):
        """液位高度数据接收处理"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] 收到液位高度数据:")
        print(f"  通道: {channel_id}")
        print(f"  高度: {heights} mm")
        
        # 保存数据
        self.received_heights.append({
            'timestamp': timestamp,
            'channel_id': channel_id,
            'heights': heights
        })
        
        # 显示统计信息
        print(f"  累计接收: {len(self.received_heights)} 次")
    
    def on_detection_result_received(self, data):
        """检测结果接收处理"""
        result_type = data.get('type', 'unknown')
        channel_id = data.get('channel_id', 'unknown')
        
        if result_type == 'detection_result':
            heights = data.get('heights', [])
            success = data.get('success', False)
            camera_status = data.get('camera_status', 'unknown')
            
            print(f"检测结果详情:")
            print(f"  通道: {channel_id}")
            print(f"  成功: {success}")
            print(f"  高度数量: {len(heights)}")
            print(f"  相机状态: {camera_status}")
        else:
            print(f"收到其他消息: {result_type}")
    
    def start_test_commands(self):
        """开始测试命令"""
        if not self.connection_status:
            print("等待连接建立...")
            return
        
        print("\n开始发送测试命令...")
        
        # 1. 加载模型
        print("1. 加载检测模型...")
        model_path = "database/model/detection_model/bestmodel/tensor.pt"
        success = self.command_manager.send_model_load_command(
            'channel1', model_path, 'cuda'
        )
        if success:
            print("模型加载命令发送成功")
        else:
            print("模型加载命令发送失败")
        
        # 等待一下
        QtCore.QTimer.singleShot(2000, self.configure_channel)
    
    def configure_channel(self):
        """配置通道"""
        print("2. 配置检测通道...")
        
        config = {
            'rtsp_url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
            'boxes': [(320, 240, 200)],  # 中心点和尺寸
            'fixed_bottoms': [400],
            'fixed_tops': [100],
            'actual_heights': [50.0],  # 毫米
            'annotation_initstatus': [0]
        }
        
        success = self.command_manager.send_configure_channel_command('channel1', config)
        if success:
            print("通道配置命令发送成功")
        else:
            print("通道配置命令发送失败")
        
        # 等待一下
        QtCore.QTimer.singleShot(2000, self.start_detection)
    
    def start_detection(self):
        """启动检测"""
        print("3. 启动液位检测...")
        
        success = self.command_manager.send_detection_command('channel1', 'start_detection')
        if success:
            print("检测启动命令发送成功")
            print("等待液位高度数据...")
        else:
            print("检测启动命令发送失败")
    
    def stop_detection(self):
        """停止检测"""
        print("停止液位检测...")
        
        success = self.command_manager.send_detection_command('channel1', 'stop_detection')
        if success:
            print("检测停止命令发送成功")
        else:
            print("检测停止命令发送失败")
    
    def print_statistics(self):
        """打印统计信息"""
        print(f"\n=== 接收统计 ===")
        print(f"总接收次数: {len(self.received_heights)}")
        
        if self.received_heights:
            print("最近5次数据:")
            for data in self.received_heights[-5:]:
                print(f"  {data['timestamp']} - {data['channel_id']}: {data['heights']}")

class TestApplication(QtWidgets.QApplication):
    """测试应用程序"""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        self.receiver = LiquidHeightReceiver()
        self.test_timer = QtCore.QTimer()
        self.stats_timer = QtCore.QTimer()
        
        # 设置定时器
        self.test_timer.timeout.connect(self.run_test_sequence)
        self.stats_timer.timeout.connect(self.receiver.print_statistics)
        
        # 每30秒打印一次统计
        self.stats_timer.start(30000)
    
    def run_test_sequence(self):
        """运行测试序列"""
        print("\n" + "="*50)
        print("开始液位高度数据接收测试")
        print("="*50)
        
        # 初始化网络
        success = self.receiver.init_network()
        if not success:
            print("网络初始化失败，测试终止")
            self.quit()
            return
        
        # 等待连接建立后开始测试命令
        QtCore.QTimer.singleShot(3000, self.receiver.start_test_commands)
        
        # 30秒后停止检测
        QtCore.QTimer.singleShot(30000, self.receiver.stop_detection)
        
        # 35秒后退出
        QtCore.QTimer.singleShot(35000, self.quit)
    
    def start_test(self):
        """启动测试"""
        # 延迟启动测试，确保事件循环已开始
        QtCore.QTimer.singleShot(1000, self.run_test_sequence)

def main():
    """主函数"""
    app = TestApplication(sys.argv)
    
    print("客户端液位高度数据接收测试")
    print("确保服务器已启动: python server/websocket/start_websocket_server.py")
    print("按 Ctrl+C 可随时停止测试")
    
    # 启动测试
    app.start_test()
    
    try:
        return app.exec_()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 0

if __name__ == "__main__":
    sys.exit(main())