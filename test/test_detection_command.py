# 检测命令发送测试脚本
# 用于测试网络命令管理器的检测命令发送功能

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtWidgets, QtCore
from client.network.command_manager import NetworkCommandManager

def test_detection_command():
    """测试检测命令发送"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建网络命令管理器
    command_manager = NetworkCommandManager('ws://192.168.0.121:8085')
    
    def on_connection_status(is_connected, message):
        print(f"连接状态变化: {'已连接' if is_connected else '未连接'} - {message}")
        
        if is_connected:
            # 连接成功后发送检测命令
            print("连接成功，发送检测命令...")
            channel_id = "channel1"
            success = command_manager.send_detection_command(channel_id, 'start_detection')
            print(f"检测命令发送结果: {success}")
            
            # 等待一段时间后退出
            QtCore.QTimer.singleShot(3000, app.quit)
    
    def on_detection_result(data):
        print(f"收到检测结果: {data}")
    
    # 连接信号
    command_manager.connectionStatusChanged.connect(on_connection_status)
    command_manager.detectionResultReceived.connect(on_detection_result)
    
    # 启动连接
    print("启动网络连接...")
    command_manager.start_connection()
    
    # 设置超时退出
    QtCore.QTimer.singleShot(10000, app.quit)  # 10秒后自动退出
    
    # 运行应用
    app.exec_()
    
    # 清理
    command_manager.stop_connection()
    print("测试完成")

if __name__ == "__main__":
    test_detection_command()