# -*- coding: utf-8 -*-
# @Time : 2024/12/19
# @File : focus_control_example.py
# @Description : 聚焦控制模块使用示例

"""
聚焦控制模块使用示例
演示如何使用FocusControl.py进行摄像头聚焦控制
"""

import time
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from HCNetSDK import *
from FocusControl import FocusController, FocusMode, FOCUS_NEAR, FOCUS_FAR, FOCUS_STOP


def example_basic_usage():
    """基本使用示例"""
    print("=" * 50)
    print("聚焦控制基本使用示例")
    print("=" * 50)
    
    # 1. 加载SDK库
    print("\n1. 加载SDK库...")
    try:
        hikSDK = load_library(netsdkdllpath)
        if not hikSDK.NET_DVR_Init():
            print("SDK初始化失败")
            return
        print("SDK初始化成功")
    except Exception as e:
        print(f"加载SDK失败：{e}")
        return
    
    # 2. 登录设备（示例，需要替换为实际设备信息）
    print("\n2. 登录设备...")
    device_ip = "192.168.1.64"  # 替换为实际IP
    username = "admin"           # 替换为实际用户名
    password = "password"        # 替换为实际密码
    port = 8000
    
    struLoginInfo = NET_DVR_USER_LOGIN_INFO()
    struLoginInfo.bUseAsynLogin = 0
    struLoginInfo.sDeviceAddress = device_ip.encode('utf-8')
    struLoginInfo.wPort = port
    struLoginInfo.sUserName = username.encode('utf-8')
    struLoginInfo.sPassword = password.encode('utf-8')
    struLoginInfo.byLoginMode = 0
    
    struDeviceInfoV40 = NET_DVR_DEVICEINFO_V40()
    user_id = hikSDK.NET_DVR_Login_V40(byref(struLoginInfo), byref(struDeviceInfoV40))
    
    if user_id < 0:
        error_code = hikSDK.NET_DVR_GetLastError()
        print(f"登录失败，错误码：{error_code}")
        hikSDK.NET_DVR_Cleanup()
        return
    
    print(f"登录成功，用户ID：{user_id}")
    
    # 3. 创建聚焦控制器
    print("\n3. 创建聚焦控制器...")
    try:
        focus_ctrl = FocusController(hikSDK, user_id, channel=1)
        print("聚焦控制器创建成功")
    except Exception as e:
        print(f"创建聚焦控制器失败：{e}")
        hikSDK.NET_DVR_Logout(user_id)
        hikSDK.NET_DVR_Cleanup()
        return
    
    # 4. 获取当前聚焦模式
    print("\n4. 获取当前聚焦模式...")
    mode_info = focus_ctrl.get_focus_mode()
    if mode_info:
        mode_names = {0: "手动", 1: "自动", 2: "半自动"}
        print(f"  聚焦模式：{mode_names.get(mode_info['focus_mode'], '未知')}")
        print(f"  显示清晰度：{'是' if mode_info['display_definition'] else '否'}")
        print(f"  速度等级：{mode_info['speed_level']}")
    else:
        print("  获取聚焦模式失败")
    
    # 5. 设置自动聚焦模式
    print("\n5. 设置自动聚焦模式...")
    if focus_ctrl.set_auto_focus(speed_level=5):
        print("  自动聚焦模式设置成功")
    else:
        print("  自动聚焦模式设置失败")
    
    # 6. 手动聚焦控制示例
    print("\n6. 手动聚焦控制示例...")
    print("  聚焦拉近...")
    if focus_ctrl.focus_near():
        time.sleep(2)  # 持续2秒
        print("  停止聚焦...")
        focus_ctrl.focus_stop()
    
    time.sleep(1)
    
    print("  聚焦拉远...")
    if focus_ctrl.focus_far():
        time.sleep(2)  # 持续2秒
        print("  停止聚焦...")
        focus_ctrl.focus_stop()
    
    # 7. 设置手动聚焦模式
    print("\n7. 设置手动聚焦模式...")
    if focus_ctrl.set_manual_focus():
        print("  手动聚焦模式设置成功")
    
    # 8. 清理资源
    print("\n8. 清理资源...")
    hikSDK.NET_DVR_Logout(user_id)
    hikSDK.NET_DVR_Cleanup()
    print("资源清理完成")
    
    print("\n" + "=" * 50)
    print("示例执行完成")
    print("=" * 50)


def example_with_hkcapture():
    """与HKcapture类结合使用的示例"""
    print("=" * 50)
    print("与HKcapture类结合使用示例")
    print("=" * 50)
    
    try:
        from HKcapture import HKcapture
        
        # 1. 创建HKcapture实例
        print("\n1. 创建HKcapture实例...")
        cap = HKcapture(
            source="192.168.1.64",
            username="admin",
            password="password",
            port=8000,
            channel=1
        )
        
        # 2. 打开摄像头
        print("\n2. 打开摄像头...")
        if not cap.open():
            print("打开摄像头失败")
            return
        print("摄像头打开成功")
        
        # 3. 创建聚焦控制器（需要SDK实例和用户ID）
        print("\n3. 创建聚焦控制器...")
        # 注意：需要从HKcapture中获取SDK实例和用户ID
        # 如果HKcapture类没有暴露这些属性，需要修改HKcapture类
        if hasattr(cap, 'hikSDK') and hasattr(cap, 'iUserID'):
            focus_ctrl = FocusController(cap.hikSDK, cap.iUserID, cap.channel)
            
            # 4. 使用聚焦控制
            print("\n4. 使用聚焦控制...")
            focus_ctrl.set_auto_focus(speed_level=4)
            
            # 5. 开始捕获
            print("\n5. 开始捕获...")
            cap.start_capture()
            
            # 6. 读取几帧后，进行聚焦调整
            for i in range(10):
                ret, frame = cap.read()
                if ret:
                    print(f"读取第 {i+1} 帧")
                time.sleep(0.1)
            
            # 7. 手动聚焦调整
            print("\n7. 手动聚焦调整...")
            focus_ctrl.focus_near()
            time.sleep(1)
            focus_ctrl.focus_stop()
            
            # 8. 清理资源
            print("\n8. 清理资源...")
            cap.release()
        else:
            print("HKcapture类未暴露SDK实例或用户ID，无法创建聚焦控制器")
            cap.release()
        
    except ImportError:
        print("HKcapture模块未找到")
    except Exception as e:
        print(f"示例执行失败：{e}")
    
    print("\n" + "=" * 50)
    print("示例执行完成")
    print("=" * 50)


def example_advanced_usage():
    """高级使用示例"""
    print("=" * 50)
    print("聚焦控制高级使用示例")
    print("=" * 50)
    
    # 这里展示更多高级功能
    print("\n高级功能：")
    print("1. 使用FocusMode枚举设置聚焦模式")
    print("2. 使用control_focus()进行精确控制")
    print("3. 设置不同的速度等级")
    print("4. 组合使用多种聚焦控制方法")
    
    # 示例代码（需要实际SDK实例）
    """
    focus_ctrl = FocusController(sdk, user_id, channel=1)
    
    # 使用枚举设置聚焦模式
    focus_ctrl.set_focus_mode(
        focus_mode=FocusMode.SEMI_AUTO,
        display_definition=1,
        speed_level=7  # 最高速度
    )
    
    # 使用control_focus进行精确控制
    focus_ctrl.control_focus(FOCUS_NEAR, param=5)  # 速度等级5
    time.sleep(1)
    focus_ctrl.control_focus(FOCUS_STOP, param=0)
    """
    
    print("\n" + "=" * 50)
    print("高级示例说明完成")
    print("=" * 50)


if __name__ == "__main__":
    print("\n聚焦控制模块使用示例")
    print("注意：以下示例需要实际的海康威视设备才能运行")
    print("请根据实际情况修改设备IP、用户名、密码等信息\n")
    
    # 选择要运行的示例
    choice = input("请选择要运行的示例：\n1. 基本使用示例\n2. 与HKcapture结合使用\n3. 高级使用示例\n请输入选项（1-3）：")
    
    if choice == "1":
        example_basic_usage()
    elif choice == "2":
        example_with_hkcapture()
    elif choice == "3":
        example_advanced_usage()
    else:
        print("无效选项，运行基本使用示例...")
        example_basic_usage()









