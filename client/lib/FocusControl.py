# -*- coding: utf-8 -*-
# @Time : 2024/12/19
# @Author : AI Assistant
# @File : FocusControl.py
# @Description : 海康威视摄像头聚焦控制模块

"""
摄像头聚焦控制模块
提供聚焦模式配置和PTZ聚焦控制功能
"""

from ctypes import *
from enum import IntEnum

# 支持相对导入和绝对导入
try:
    from .HCNetSDK import *
except ImportError:
    from HCNetSDK import *


# ==================== 聚焦模式枚举 ====================
class FocusMode(IntEnum):
    """聚焦模式枚举"""
    MANUAL = 0      # 手动聚焦
    AUTO = 1        # 自动聚焦
    SEMI_AUTO = 2   # 半自动聚焦


# ==================== PTZ聚焦控制命令常量 ====================
# 根据海康威视SDK文档，PTZ控制命令定义
# 聚焦相关命令通常在13-15范围内
FOCUS_NEAR = 13    # 聚焦拉近（焦点前调）
FOCUS_FAR = 14     # 聚焦拉远（焦点后调）
FOCUS_STOP = 15    # 停止聚焦

# 其他常用PTZ命令（供参考）
TILT_UP = 21       # 云台上仰
TILT_DOWN = 22     # 云台下俯
PAN_LEFT = 23      # 云台左转
PAN_RIGHT = 24     # 云台右转
ZOOM_IN = 11       # 变倍放大
ZOOM_OUT = 12      # 变倍缩小


# ==================== 聚焦模式配置结构体 ====================
# 注意：如果HCNetSDK.py中已定义NET_DVR_FOCUSMODE_CFG，则不需要重复定义
# 这里提供一个备用定义，如果SDK中没有的话
try:
    # 尝试从HCNetSDK导入
    _ = NET_DVR_FOCUSMODE_CFG
except (NameError, AttributeError):
    # 如果不存在，则定义结构体
    class NET_DVR_FOCUSMODE_CFG(Structure):
        """聚焦模式配置结构体"""
        _fields_ = [
            ("dwSize", C_DWORD),                    # 结构体大小
            ("byFocusMode", C_BYTE),                # 聚焦模式：0-手动，1-自动，2-半自动
            ("byFocusDefinitionDisplay", C_BYTE),   # 是否显示聚焦清晰度：0-不显示，1-显示
            ("byFocusSpeedLevel", C_BYTE),          # 聚焦速度等级：1-7，数值越大速度越快
            ("byRes", C_BYTE * 253),                # 保留字节
        ]


# ==================== 配置命令常量 ====================
# 如果HCNetSDK.py中没有定义，则在这里定义
try:
    _ = NET_DVR_GET_FOCUSMODECFG
except (NameError, AttributeError):
    NET_DVR_GET_FOCUSMODECFG = 1033  # 获取聚焦模式配置

try:
    _ = NET_DVR_SET_FOCUSMODECFG
except (NameError, AttributeError):
    NET_DVR_SET_FOCUSMODECFG = 1034  # 设置聚焦模式配置


# ==================== 聚焦控制类 ====================
class FocusController:
    """
    摄像头聚焦控制器
    
    提供聚焦模式配置和PTZ聚焦控制功能
    """
    
    def __init__(self, sdk_instance, user_id, channel=1):
        """
        初始化聚焦控制器
        
        参数:
            sdk_instance: HCNetSDK库实例（通过load_library加载的SDK对象）
            user_id: 设备登录返回的用户ID
            channel: 通道号，默认1
        """
        self.sdk = sdk_instance
        self.user_id = user_id
        self.channel = channel
        
        # 验证SDK实例
        if not self.sdk:
            raise ValueError("SDK实例不能为空")
        
        # 验证用户ID
        if self.user_id < 0:
            raise ValueError("用户ID无效，请先登录设备")
    
    def get_focus_mode(self):
        """
        获取当前聚焦模式配置
        
        返回:
            dict: 包含聚焦模式信息的字典
                - focus_mode: 聚焦模式 (0-手动, 1-自动, 2-半自动)
                - display_definition: 是否显示聚焦清晰度 (0/1)
                - speed_level: 聚焦速度等级 (1-7)
            None: 获取失败
        """
        try:
            struFocusMode = NET_DVR_FOCUSMODE_CFG()
            struFocusMode.dwSize = sizeof(struFocusMode)
            pInt = c_int(0)
            
            # 获取聚焦模式配置
            b_ret = self.sdk.NET_DVR_GetDVRConfig(
                self.user_id,
                NET_DVR_GET_FOCUSMODECFG,
                self.channel,
                byref(struFocusMode),
                sizeof(struFocusMode),
                byref(pInt)
            )
            
            if not b_ret:
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"获取聚焦模式失败，错误码：{error_code}")
                return None
            
            return {
                'focus_mode': struFocusMode.byFocusMode,
                'display_definition': struFocusMode.byFocusDefinitionDisplay,
                'speed_level': struFocusMode.byFocusSpeedLevel
            }
            
        except Exception as e:
            print(f"获取聚焦模式异常：{e}")
            return None
    
    def set_focus_mode(self, focus_mode=FocusMode.AUTO, display_definition=1, speed_level=3):
        """
        设置聚焦模式配置
        
        参数:
            focus_mode: 聚焦模式
                - FocusMode.MANUAL (0): 手动聚焦
                - FocusMode.AUTO (1): 自动聚焦
                - FocusMode.SEMI_AUTO (2): 半自动聚焦
            display_definition: 是否显示聚焦清晰度，0-不显示，1-显示，默认1
            speed_level: 聚焦速度等级，1-7，数值越大速度越快，默认3
        
        返回:
            bool: 设置成功返回True，失败返回False
        """
        try:
            # 先获取当前配置
            struFocusMode = NET_DVR_FOCUSMODE_CFG()
            struFocusMode.dwSize = sizeof(struFocusMode)
            pInt = c_int(0)
            
            b_get = self.sdk.NET_DVR_GetDVRConfig(
                self.user_id,
                NET_DVR_GET_FOCUSMODECFG,
                self.channel,
                byref(struFocusMode),
                sizeof(struFocusMode),
                byref(pInt)
            )
            
            if not b_get:
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"获取聚焦模式配置失败，错误码：{error_code}")
                return False
            
            # 设置新参数
            struFocusMode.byFocusMode = int(focus_mode)
            struFocusMode.byFocusDefinitionDisplay = display_definition
            struFocusMode.byFocusSpeedLevel = max(1, min(7, speed_level))  # 限制在1-7范围内
            
            # 应用配置
            b_set = self.sdk.NET_DVR_SetDVRConfig(
                self.user_id,
                NET_DVR_SET_FOCUSMODECFG,
                self.channel,
                byref(struFocusMode),
                sizeof(struFocusMode)
            )
            
            if not b_set:
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"设置聚焦模式失败，错误码：{error_code}")
                return False
            
            mode_names = {0: "手动", 1: "自动", 2: "半自动"}
            print(f"聚焦模式设置成功：{mode_names.get(int(focus_mode), '未知')}，速度等级：{speed_level}")
            return True
            
        except Exception as e:
            print(f"设置聚焦模式异常：{e}")
            return False
    
    def control_focus(self, command, param=0):
        """
        PTZ聚焦控制（实时控制）
        
        参数:
            command: 聚焦控制命令
                - FOCUS_NEAR (13): 聚焦拉近（焦点前调）
                - FOCUS_FAR (14): 聚焦拉远（焦点后调）
                - FOCUS_STOP (15): 停止聚焦
            param: 控制参数
                - 0: 停止
                - 1: 开始
                - 2-7: 速度等级（部分设备支持）
        
        返回:
            bool: 控制成功返回True，失败返回False
        """
        try:
            # 调用PTZ控制接口
            # 注意：根据SDK版本，可能是NET_DVR_PTZControl或NET_DVR_PTZControl_Other
            # 优先尝试NET_DVR_PTZControl_Other
            if hasattr(self.sdk, 'NET_DVR_PTZControl_Other'):
                b_ret = self.sdk.NET_DVR_PTZControl_Other(
                    self.user_id,
                    self.channel,
                    command,
                    param
                )
            elif hasattr(self.sdk, 'NET_DVR_PTZControl'):
                b_ret = self.sdk.NET_DVR_PTZControl(
                    self.user_id,
                    self.channel,
                    command,
                    param
                )
            else:
                print("SDK不支持PTZ控制接口")
                return False
            
            if not b_ret:
                error_code = self.sdk.NET_DVR_GetLastError()
                print(f"聚焦控制失败，错误码：{error_code}")
                return False
            
            command_names = {
                FOCUS_NEAR: "聚焦拉近",
                FOCUS_FAR: "聚焦拉远",
                FOCUS_STOP: "停止聚焦"
            }
            print(f"聚焦控制成功：{command_names.get(command, '未知命令')}")
            return True
            
        except Exception as e:
            print(f"聚焦控制异常：{e}")
            return False
    
    def focus_near(self, param=1):
        """
        聚焦拉近（焦点前调）
        
        参数:
            param: 控制参数，0-停止，1-开始，2-7-速度等级
        
        返回:
            bool: 控制成功返回True，失败返回False
        """
        return self.control_focus(FOCUS_NEAR, param)
    
    def focus_far(self, param=1):
        """
        聚焦拉远（焦点后调）
        
        参数:
            param: 控制参数，0-停止，1-开始，2-7-速度等级
        
        返回:
            bool: 控制成功返回True，失败返回False
        """
        return self.control_focus(FOCUS_FAR, param)
    
    def focus_stop(self):
        """
        停止聚焦操作
        
        返回:
            bool: 控制成功返回True，失败返回False
        """
        return self.control_focus(FOCUS_STOP, 0)
    
    def set_auto_focus(self, speed_level=3):
        """
        设置自动聚焦模式（便捷方法）
        
        参数:
            speed_level: 聚焦速度等级，1-7，默认3
        
        返回:
            bool: 设置成功返回True，失败返回False
        """
        return self.set_focus_mode(
            focus_mode=FocusMode.AUTO,
            display_definition=1,
            speed_level=speed_level
        )
    
    def set_manual_focus(self):
        """
        设置手动聚焦模式（便捷方法）
        
        返回:
            bool: 设置成功返回True，失败返回False
        """
        return self.set_focus_mode(
            focus_mode=FocusMode.MANUAL,
            display_definition=1,
            speed_level=3
        )
    
    def set_semi_auto_focus(self, speed_level=3):
        """
        设置半自动聚焦模式（便捷方法）
        
        参数:
            speed_level: 聚焦速度等级，1-7，默认3
        
        返回:
            bool: 设置成功返回True，失败返回False
        """
        return self.set_focus_mode(
            focus_mode=FocusMode.SEMI_AUTO,
            display_definition=1,
            speed_level=speed_level
        )


# ==================== 便捷函数 ====================
def create_focus_controller(sdk_instance, user_id, channel=1):
    """
    创建聚焦控制器实例（便捷函数）
    
    参数:
        sdk_instance: HCNetSDK库实例
        user_id: 设备登录返回的用户ID
        channel: 通道号，默认1
    
    返回:
        FocusController: 聚焦控制器实例
    """
    return FocusController(sdk_instance, user_id, channel)


# ==================== 使用示例 ====================
if __name__ == "__main__":
    """
    使用示例
    """
    # 注意：以下代码需要在实际环境中测试
    # 1. 加载SDK库
    # sdk = load_library(netsdkdllpath)
    # sdk.NET_DVR_Init()
    
    # 2. 登录设备
    # user_id = login_device(sdk, "192.168.1.64", "admin", "password")
    
    # 3. 创建聚焦控制器
    # focus_ctrl = FocusController(sdk, user_id, channel=1)
    
    # 4. 获取当前聚焦模式
    # mode_info = focus_ctrl.get_focus_mode()
    # print(f"当前聚焦模式：{mode_info}")
    
    # 5. 设置自动聚焦
    # focus_ctrl.set_auto_focus(speed_level=5)
    
    # 6. 手动聚焦控制
    # focus_ctrl.focus_near()  # 聚焦拉近
    # time.sleep(2)
    # focus_ctrl.focus_stop()  # 停止聚焦
    
    # 7. 聚焦拉远
    # focus_ctrl.focus_far()
    # time.sleep(2)
    # focus_ctrl.focus_stop()
    
    print("聚焦控制模块已加载")
    print("使用说明：")
    print("1. 创建FocusController实例")
    print("2. 使用get_focus_mode()获取当前聚焦模式")
    print("3. 使用set_focus_mode()或便捷方法设置聚焦模式")
    print("4. 使用control_focus()或便捷方法进行实时聚焦控制")

