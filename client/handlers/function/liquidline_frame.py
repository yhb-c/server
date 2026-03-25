# -*- coding: utf-8 -*-
"""
液位线字符叠加模块
使用海康威视SDK的字符叠加功能在相机画面上绘制液位线
"""

import os
import sys
import time
from ctypes import *

# 添加HK_SDK路径
current_dir = os.path.dirname(os.path.abspath(__file__))
hk_sdk_path = os.path.join(os.path.dirname(current_dir), 'videopage', 'HK_SDK')
sys.path.insert(0, hk_sdk_path)

from HCNetSDK import *


class LevelLineOverlay:
    """液位线字符叠加类"""

    def __init__(self):
        self.sdk = None
        self.user_id = -1
        self.is_initialized = False

    def initialize_sdk(self):
        """初始化SDK"""
        try:
            # 加载SDK库
            self.sdk = load_library(netsdkdllpath)

            # 初始化SDK
            if not self.sdk.NET_DVR_Init():
                print(f"SDK初始化失败")
                return False

            # 设置连接时间与重连时间
            self.sdk.NET_DVR_SetConnectTime(2000, 1)
            self.sdk.NET_DVR_SetReconnect(10000, True)

            self.is_initialized = True
            print("SDK初始化成功")
            return True

        except Exception as e:
            print(f"初始化SDK异常: {e}")
            return False

    def login_device(self, ip, port, username, password):
        """
        登录设备

        Args:
            ip: 设备IP地址
            port: 设备端口
            username: 用户名
            password: 密码

        Returns:
            bool: 登录是否成功
        """
        if not self.is_initialized:
            print("SDK未初始化")
            return False

        try:
            # 登录参数
            login_info = NET_DVR_USER_LOGIN_INFO()
            login_info.sDeviceAddress = ip.encode('utf-8')
            login_info.wPort = port
            login_info.sUserName = username.encode('utf-8')
            login_info.sPassword = password.encode('utf-8')
            login_info.bUseAsynLogin = 0  # 同步登录

            # 设备信息
            device_info = NET_DVR_DEVICEINFO_V40()

            # 登录设备
            self.user_id = self.sdk.NET_DVR_Login_V40(byref(login_info), byref(device_info))

            if self.user_id < 0:
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"登录失败, 错误码: {error_code}")
                return False

            print(f"登录成功, UserID: {self.user_id}")
            return True

        except Exception as e:
            print(f"登录设备异常: {e}")
            return False

    def draw_level_line(self, channel, y_position, line_text="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"):
        """
        在指定通道绘制液位线

        Args:
            channel: 通道号
            y_position: Y坐标位置(0-576)
            line_text: 液位线文本(使用字符绘制线条)

        Returns:
            bool: 是否成功
        """
        if self.user_id < 0:
            print("设备未登录")
            return False

        try:
            # 定义字符叠加结构体
            class NET_DVR_SHOWSTRING(Structure):
                _fields_ = [
                    ('wShowString', C_WORD),  # 是否显示字符
                    ('wShowStringTopLeftX', C_WORD),  # 字符显示区域X坐标
                    ('wShowStringTopLeftY', C_WORD),  # 字符显示区域Y坐标
                    ('wStringSize', C_WORD),  # 字符串长度
                    ('sString', c_char * 44),  # 字符内容
                ]

            class NET_DVR_SHOWSTRING_V30(Structure):
                _fields_ = [
                    ('dwSize', C_DWORD),
                    ('struStringInfo', NET_DVR_SHOWSTRING * 8),  # 最多8个字符叠加区域
                    ('byRes', C_BYTE * 256),
                ]

            # 获取当前字符叠加配置
            show_string = NET_DVR_SHOWSTRING_V30()
            show_string.dwSize = sizeof(NET_DVR_SHOWSTRING_V30)
            returned_size = C_DWORD(0)

            # NET_DVR_GET_SHOWSTRING_V30 = 1067
            if not self.sdk.NET_DVR_GetDVRConfig(
                    self.user_id,
                    1067,  # NET_DVR_GET_SHOWSTRING_V30
                    channel,
                    byref(show_string),
                    sizeof(NET_DVR_SHOWSTRING_V30),
                    byref(returned_size)
            ):
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"获取字符叠加配置失败, 错误码: {error_code}")
                return False

            # 设置液位线字符叠加
            # 使用第一个字符叠加区域
            show_string.struStringInfo[0].wShowString = 1  # 启用显示
            show_string.struStringInfo[0].wShowStringTopLeftX = 0  # X坐标
            show_string.struStringInfo[0].wShowStringTopLeftY = y_position  # Y坐标

            # 转换文本为字节
            line_bytes = line_text.encode('gbk')[:44]  # 限制长度为44字节
            show_string.struStringInfo[0].wStringSize = len(line_bytes)

            # 复制字符串内容
            for i, byte in enumerate(line_bytes):
                show_string.struStringInfo[0].sString[i] = byte

            # NET_DVR_SET_SHOWSTRING_V30 = 1068
            if not self.sdk.NET_DVR_SetDVRConfig(
                    self.user_id,
                    1068,  # NET_DVR_SET_SHOWSTRING_V30
                    channel,
                    byref(show_string),
                    sizeof(NET_DVR_SHOWSTRING_V30)
            ):
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"设置字符叠加失败, 错误码: {error_code}")
                return False

            print(f"液位线绘制成功 - 通道:{channel}, Y坐标:{y_position}")
            return True

        except Exception as e:
            print(f"绘制液位线异常: {e}")
            return False

    def clear_level_line(self, channel):
        """
        清除指定通道的液位线

        Args:
            channel: 通道号

        Returns:
            bool: 是否成功
        """
        if self.user_id < 0:
            print("设备未登录")
            return False

        try:
            # 定义字符叠加结构体
            class NET_DVR_SHOWSTRING(Structure):
                _fields_ = [
                    ('wShowString', C_WORD),
                    ('wShowStringTopLeftX', C_WORD),
                    ('wShowStringTopLeftY', C_WORD),
                    ('wStringSize', C_WORD),
                    ('sString', c_char * 44),
                ]

            class NET_DVR_SHOWSTRING_V30(Structure):
                _fields_ = [
                    ('dwSize', C_DWORD),
                    ('struStringInfo', NET_DVR_SHOWSTRING * 8),
                    ('byRes', C_BYTE * 256),
                ]

            # 获取当前配置
            show_string = NET_DVR_SHOWSTRING_V30()
            show_string.dwSize = sizeof(NET_DVR_SHOWSTRING_V30)
            returned_size = C_DWORD(0)

            if not self.sdk.NET_DVR_GetDVRConfig(
                    self.user_id,
                    1067,
                    channel,
                    byref(show_string),
                    sizeof(NET_DVR_SHOWSTRING_V30),
                    byref(returned_size)
            ):
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"获取字符叠加配置失败, 错误码: {error_code}")
                return False

            # 禁用字符叠加
            show_string.struStringInfo[0].wShowString = 0

            if not self.sdk.NET_DVR_SetDVRConfig(
                    self.user_id,
                    1068,
                    channel,
                    byref(show_string),
                    sizeof(NET_DVR_SHOWSTRING_V30)
            ):
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"清除字符叠加失败, 错误码: {error_code}")
                return False

            print(f"液位线清除成功 - 通道:{channel}")
            return True

        except Exception as e:
            print(f"清除液位线异常: {e}")
            return False

    def logout(self):
        """注销登录"""
        if self.user_id >= 0:
            self.sdk.NET_DVR_Logout(self.user_id)
            self.user_id = -1
            print("注销成功")

    def cleanup(self):
        """清理资源"""
        self.logout()
        if self.is_initialized and self.sdk:
            self.sdk.NET_DVR_Cleanup()
            self.is_initialized = False
            print("SDK清理完成")


def main():
    """测试函数"""
    # 创建液位线叠加对象
    overlay = LevelLineOverlay()

    # 初始化SDK
    if not overlay.initialize_sdk():
        print("初始化失败")
        return

    # 登录设备
    # 从配置中读取的相机地址: rtsp://admin:cei345678@192.168.0.27:8000/stream2
    ip = "192.168.0.27"
    port = 8000
    username = "admin"
    password = "cei345678"

    if not overlay.login_device(ip, port, username, password):
        print("登录失败")
        overlay.cleanup()
        return

    # 绘制液位线 (通道1, Y坐标300)
    channel = 1
    y_position = 300

    # 使用字符绘制液位线
    line_text = "━" * 40  # 使用横线字符

    if overlay.draw_level_line(channel, y_position, line_text):
        print("液位线已绘制")

        # 等待10秒观察效果
        print("等待10秒...")
        time.sleep(10)

        # 清除液位线
        overlay.clear_level_line(channel)
        print("液位线已清除")

    # 清理资源
    overlay.cleanup()


if __name__ == "__main__":
    main()
