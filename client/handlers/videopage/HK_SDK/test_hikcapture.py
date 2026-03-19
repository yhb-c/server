# -*- coding: utf-8 -*-

"""
HKcapture测试脚本

用于验证HKcapture是否能正常读取海康威视通道的视频流
"""

import time
import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HK_SDK.HKcapture import HKcapture


def test_hikcapture():
    """测试HKcapture功能"""
    print(" 开始测试HKcapture...")
    
    # 创建HKcapture实例
    cap = HKcapture(
        source="192.168.0.127",
        username="admin",
        password="cei345678",
        port=8000,
        channel=1,
        fps=25
    )
    
    print(f" 创建HKcapture实例: {cap}")
    print(f"   是否为海康威视: {cap.is_hikvision}")
    
    # 打开连接
    print(" 正在打开通道连接...")
    if not cap.open():
        print(" 打开通道连接失败")
        return False
    
    print(" 通道连接已打开")
    
    # 开始捕获
    print(" 正在开始视频捕获...")
    if not cap.start_capture():
        print(" 开始视频捕获失败")
        cap.release()
        return False
    
    print(" 视频捕获已开始")
    
    # 测试读取帧
    print(" 开始测试读取帧...")
    frame_count = 0
    start_time = time.time()
    
    for i in range(100):  # 测试100次读取
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            if frame_count <= 5:  # 前5帧打印详细信息
                print(f" 读取帧 #{frame_count}: shape={frame.shape}")
            elif frame_count % 20 == 0:  # 每20帧打印一次
                print(f" 已读取 {frame_count} 帧")
        else:
            if i < 10:  # 前10次失败打印
                print(f" 第{i+1}次读取失败")
        
        time.sleep(0.1)  # 等待100ms
    
    elapsed_time = time.time() - start_time
    print(f" 测试完成:")
    print(f"   总时间: {elapsed_time:.2f}s")
    print(f"   成功读取: {frame_count} 帧")
    print(f"   平均帧率: {frame_count/elapsed_time:.2f} fps")
    
    # 停止捕获
    print("⏹ 正在停止视频捕获...")
    cap.stop_capture()
    
    # 释放资源
    print(" 正在释放资源...")
    cap.release()
    
    print(" 测试完成")
    return frame_count > 0


if __name__ == "__main__":
    success = test_hikcapture()
    if success:
        print(" HKcapture测试成功！")
    else:
        print(" HKcapture测试失败！")
