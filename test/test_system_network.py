# 系统网络初始化测试脚本
# 用于测试系统窗口中网络命令管理器的初始化

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtWidgets, QtCore

def test_system_network_init():
    """测试系统网络初始化"""
    app = QtWidgets.QApplication(sys.argv)
    
    try:
        # 直接测试网络命令管理器初始化
        from client.network.command_manager import NetworkCommandManager
        
        print("创建网络命令管理器...")
        command_manager = NetworkCommandManager('ws://192.168.0.121:8085')
        
        connection_established = False
        
        def on_connection_status(is_connected, message):
            nonlocal connection_established
            print(f"连接状态: {'已连接' if is_connected else '未连接'} - {message}")
            
            if is_connected:
                connection_established = True
                print("网络连接成功建立！")
                
                # 测试检测命令发送
                print("测试检测命令发送...")
                success = command_manager.send_detection_command("channel1", "start_detection")
                print(f"检测命令发送结果: {success}")
                
                # 测试模型加载命令
                print("测试模型加载命令...")
                success = command_manager.send_model_load_command(
                    "channel1", 
                    "/home/lqj/liquid/server/database/model/detection_model/bestmodel/tensor.pt"
                )
                print(f"模型加载命令发送结果: {success}")
                
                # 3秒后退出
                QtCore.QTimer.singleShot(3000, app.quit)
        
        def on_detection_result(data):
            print(f"收到检测结果: {data}")
        
        # 连接信号
        command_manager.connectionStatusChanged.connect(on_connection_status)
        command_manager.detectionResultReceived.connect(on_detection_result)
        
        # 启动连接
        print("启动网络连接...")
        command_manager.start_connection()
        
        # 设置超时
        def timeout_check():
            if not connection_established:
                print("连接超时，测试结束")
                app.quit()
        
        QtCore.QTimer.singleShot(8000, timeout_check)  # 8秒超时
        
        # 运行应用
        print("等待网络连接...")
        app.exec_()
        
        # 清理
        command_manager.stop_connection()
        
        if connection_established:
            print("✓ 系统网络初始化测试成功")
            return True
        else:
            print("✗ 系统网络初始化测试失败")
            return False
            
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system_network_init()
    sys.exit(0 if success else 1)