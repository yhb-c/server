#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
物理变焦控制器
使用海康威视SDK实现真实的物理层面变焦，替代数字变焦
"""

import time
import threading
from ctypes import *
try:
    from qtpy.QtCore import QObject, Signal as pyqtSignal
except ImportError:
    try:
        from qtpy.QtCore import QObject, pyqtSignal
    except ImportError:
        # 如果qtpy不可用，创建占位符
        class QObject:
            def __init__(self): pass
        def pyqtSignal(*args): return lambda: None

# 导入海康SDK
try:
    from .HK_SDK.HCNetSDK import *
    from .HK_SDK.ParameterConfigurator import login_v40, SetSDKInitCfg, GetPlatform
    # 初始化SDK实例
    sdk = load_library(netsdkdllpath)
except ImportError:
    try:
        from HK_SDK.HCNetSDK import *
        from HK_SDK.ParameterConfigurator import login_v40, SetSDKInitCfg, GetPlatform
        # 初始化SDK实例
        sdk = load_library(netsdkdllpath)
    except ImportError:
        # 如果导入失败，创建占位符
        print("警告: 海康SDK导入失败，物理变焦功能不可用")
        def login_v40(*args, **kwargs): return -1
        def SetSDKInitCfg(*args, **kwargs): pass
        def GetPlatform(*args, **kwargs): pass
        # 创建占位符SDK
        class MockSDK:
            def NET_DVR_Init(self): return False
            def NET_DVR_GetLastError(self): return 0
            def NET_DVR_SetLogToFile(self, *args): pass
            def NET_DVR_Logout(self, *args): return False
            def NET_DVR_Cleanup(self): pass
            def NET_DVR_GetDVRConfig(self, *args): return False
            def NET_DVR_SetDVRConfig(self, *args): return False
            def NET_DVR_PTZControl_Other(self, *args): return False
            def NET_DVR_GetSTDConfig(self, *args): return False
        sdk = MockSDK()


class PhysicalZoomController(QObject):
    """
    物理变焦控制器
    
    功能：
    1. 通过海康SDK控制摄像头的物理变焦
    2. 支持连续变焦和精确定位
    3. 提供变焦状态监控和反馈
    4. 替代原有的数字变焦功能
    """
    
    # 信号定义
    zoomChanged = pyqtSignal(float)  # 变焦倍数变化信号
    focusChanged = pyqtSignal(int)   # 聚焦位置变化信号
    statusChanged = pyqtSignal(str)  # 状态变化信号
    errorOccurred = pyqtSignal(str)  # 错误信号
    
    # PTZ控制命令常量
    ZOOM_IN = 11        # 变焦+（放大）
    ZOOM_OUT = 12       # 变焦-（缩小）
    FOCUS_NEAR = 13     # 聚焦+（近）
    FOCUS_FAR = 14      # 聚焦-（远）
    PAN_LEFT = 1        # 水平向左
    PAN_RIGHT = 2       # 水平向右
    TILT_UP = 3         # 垂直向上
    TILT_DOWN = 4       # 垂直向下
    IRIS_OPEN = 15      # 光圈+（大）
    IRIS_CLOSE = 16     # 光圈-（小）
    
    def __init__(self, device_ip, device_port=8000, username="admin", password="", channel=1):
        """
        初始化物理变焦控制器
        
        Args:
            device_ip: 设备IP地址
            device_port: 设备端口，默认8000
            username: 登录用户名，默认admin
            password: 登录密码
            channel: 通道号，默认1
        """
        super().__init__()
        
        # 设备连接参数
        self.device_ip = device_ip
        self.device_port = device_port
        self.username = username
        self.password = password
        self.channel = channel
        
        # 连接状态
        self.user_id = -1
        self.is_connected = False
        self.sdk_initialized = False
        
        # 变焦参数
        self.current_zoom_pos = 0      # 当前变焦位置 (0-3600)
        self.current_focus_pos = 0     # 当前聚焦位置 (0-3600)
        self.min_zoom_pos = 0          # 最小变焦位置
        self.max_zoom_pos = 3600       # 最大变焦位置
        self.zoom_step = 100           # 变焦步长
        
        # 控制状态
        self.is_zooming = False
        self.is_focusing = False
        self.auto_focus_enabled = True
        
        # 线程锁
        self.control_lock = threading.Lock()
    
    def initialize_sdk(self):
        """初始化海康SDK"""
        try:
            if self.sdk_initialized:
                return True
            
            # 获取系统平台
            GetPlatform()
            
            # 设置SDK初始化配置
            try:
                SetSDKInitCfg()
            except Exception as e:
                return False
            
            # 初始化SDK
            init_result = sdk.NET_DVR_Init()
            
            if not init_result:
                error_code = sdk.NET_DVR_GetLastError()
                error_msg = f"SDK初始化失败，错误码: {error_code}"
                self.errorOccurred.emit(error_msg)
                return False
            
            self.sdk_initialized = True
            self.statusChanged.emit("SDK初始化成功")
            return True
            
        except Exception as e:
            self.errorOccurred.emit(f"SDK初始化异常: {str(e)}")
            return False
    
    def connect_device(self):
        """连接设备"""
        try:
            if not self.sdk_initialized:
                if not self.initialize_sdk():
                    return False
            
            if self.is_connected:
                return True
            
            # 登录设备
            self.user_id = login_v40(self.device_ip, self.device_port, self.username, self.password)
            
            if self.user_id < 0:
                error_code = sdk.NET_DVR_GetLastError()
                self.errorOccurred.emit(f"设备登录失败，错误码: {error_code}")
                return False
            
            self.is_connected = True
            self.statusChanged.emit(f"设备连接成功: {self.device_ip}")
            
            # 获取当前PTZ位置
            self._get_current_ptz_position()
            
            return True
            
        except Exception as e:
            self.errorOccurred.emit(f"设备连接异常: {str(e)}")
            return False
    
    def disconnect_device(self):
        """断开设备连接"""
        try:
            if self.is_connected and self.user_id >= 0:
                sdk.NET_DVR_Logout(self.user_id)
                self.user_id = -1
                self.is_connected = False
                self.statusChanged.emit("设备已断开")
            
            if self.sdk_initialized:
                sdk.NET_DVR_Cleanup()
                self.sdk_initialized = False
                
        except Exception as e:
            self.errorOccurred.emit(f"断开连接异常: {str(e)}")
    
    def _get_current_ptz_position(self):
        """获取当前PTZ位置"""
        try:
            if not self.is_connected:
                return False
            
            struPtzPos = NET_DVR_PTZPOS()
            pUsers = c_int(1)
            
            # 获取PTZ坐标信息
            result = sdk.NET_DVR_GetDVRConfig(
                self.user_id, 
                NET_DVR_GET_PTZPOS, 
                self.channel, 
                byref(struPtzPos), 
                sizeof(struPtzPos),
                byref(pUsers)
            )
            
            if result:
                # 解析变焦和聚焦位置
                self.current_zoom_pos = int(hex(struPtzPos.wZoomPos).replace('0x', ''), 16)
                self.current_focus_pos = int(hex(struPtzPos.wTiltPos).replace('0x', ''), 16)  # 这里用Tilt作为Focus的示例
                
                # 发送信号
                zoom_factor = self._position_to_zoom_factor(self.current_zoom_pos)
                self.zoomChanged.emit(zoom_factor)
                self.focusChanged.emit(self.current_focus_pos)
                
                return True
            else:
                return False
                
        except Exception as e:
            self.errorOccurred.emit(f"获取PTZ位置异常: {str(e)}")
            return False
    
    def _position_to_zoom_factor(self, position):
        """将变焦位置转换为变焦倍数"""
        # 假设位置0对应1倍，位置3600对应30倍变焦
        # 这个映射关系需要根据具体摄像头型号调整
        if position <= 0:
            return 1.0
        
        # 线性映射：0-3600 -> 1.0-30.0
        zoom_factor = 1.0 + (position / 3600.0) * 29.0
        return round(zoom_factor, 1)
    
    def _zoom_factor_to_position(self, zoom_factor):
        """将变焦倍数转换为变焦位置"""
        if zoom_factor <= 1.0:
            return 0
        
        # 反向映射：1.0-30.0 -> 0-3600
        position = int((zoom_factor - 1.0) / 29.0 * 3600)
        return max(0, min(3600, position))
    
    def zoom_in(self, speed=4):
        """
        放大变焦
        
        Args:
            speed: 变焦速度 (1-7)，数值越大速度越快
        """
        return self._ptz_control(self.ZOOM_IN, speed)
    
    def zoom_out(self, speed=4):
        """
        缩小变焦
        
        Args:
            speed: 变焦速度 (1-7)，数值越大速度越快
        """
        return self._ptz_control(self.ZOOM_OUT, speed)
    
    def stop_zoom(self):
        """停止变焦"""
        return self._ptz_control(self.ZOOM_IN, 0)  # 速度为0表示停止
    
    def zoom_to_factor(self, target_zoom_factor, timeout=10.0):
        """
        变焦到指定倍数
        
        Args:
            target_zoom_factor: 目标变焦倍数 (1.0-30.0)
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.control_lock:
                if not self.is_connected:
                    self.errorOccurred.emit("设备未连接")
                    return False
                
                target_position = self._zoom_factor_to_position(target_zoom_factor)
                
                # 使用连续变焦控制（更适合海康威视设备）
                return self._zoom_to_position_continuous(target_position, timeout)
            
        except Exception as e:
            self.errorOccurred.emit(f"设置变焦位置异常: {str(e)}")
            return False
    
    def focus_near(self, speed=4):
        """聚焦近"""
        return self._ptz_control(self.FOCUS_NEAR, speed)
    
    def focus_far(self, speed=4):
        """聚焦远"""
        return self._ptz_control(self.FOCUS_FAR, speed)
    
    def stop_focus(self):
        """停止聚焦"""
        return self._ptz_control(self.FOCUS_NEAR, 0)
    
    def auto_focus(self):
        """自动聚焦"""
        try:
            if not self.is_connected:
                return False
            
            # 获取聚焦模式配置
            struFocusMode = NET_DVR_FOCUSMODE_CFG()
            struFocusMode.dwSize = sizeof(struFocusMode)
            pInt = c_int(0)
            
            # 设置为自动聚焦模式
            struFocusMode.byFocusMode = 0  # 0-自动聚焦，1-手动聚焦，2-半自动聚焦
            
            result = sdk.NET_DVR_SetDVRConfig(
                self.user_id,
                NET_DVR_SET_FOCUSMODECFG,
                self.channel,
                byref(struFocusMode),
                sizeof(struFocusMode)
            )
            
            if result:
                self.statusChanged.emit("自动聚焦已启动")
                return True
            else:
                error_code = sdk.NET_DVR_GetLastError()
                self.errorOccurred.emit(f"自动聚焦失败，错误码: {error_code}")
                return False
                
        except Exception as e:
            self.errorOccurred.emit(f"自动聚焦异常: {str(e)}")
            return False
    
    def _ptz_control(self, command, speed):
        """
        PTZ控制基础方法
        
        Args:
            command: 控制命令
            speed: 控制速度 (0-7)，0表示停止
        
        Returns:
            bool: 是否成功
        """
        try:
            if not self.is_connected:
                return False
            
            result = sdk.NET_DVR_PTZControl_Other(self.user_id, self.channel, command, speed)
            
            if not result:
                return False
            
            return True
            
        except Exception as e:
            self.errorOccurred.emit(f"PTZ控制异常: {str(e)}")
            return False
    
    def get_zoom_capabilities(self):
        """
        获取变焦能力信息
        
        Returns:
            dict: 变焦能力信息
        """
        try:
            if not self.is_connected:
                return None
            
            # 获取高精度PTZ绝对位置配置
            struSTDcfg = NET_DVR_STD_CONFIG()
            lchannel = c_int(self.channel)
            struSTDcfg.lpCondBuffer = addressof(lchannel)
            struSTDcfg.dwCondSize = sizeof(c_int)
            
            struPTZ = NET_DVR_PTZABSOLUTEEX_CFG()
            struSTDcfg.lpOutBuffer = addressof(struPTZ)
            struSTDcfg.dwOutSize = sizeof(struPTZ)
            
            result = sdk.NET_DVR_GetSTDConfig(self.user_id, NET_DVR_GET_PTZABSOLUTEEX, byref(struSTDcfg))
            
            if result:
                capabilities = {
                    'focal_length_range': struPTZ.dwFocalLen,
                    'focus_position': struPTZ.struPTZCtrl.dwFocus,
                    'min_zoom': 1.0,
                    'max_zoom': 30.0,  # 根据实际设备调整
                    'zoom_steps': 3600
                }
                
                return capabilities
            else:
                return None
                
        except Exception as e:
            self.errorOccurred.emit(f"获取变焦能力异常: {str(e)}")
            return None
    
    def get_status(self):
        """
        获取当前状态
        
        Returns:
            dict: 状态信息
        """
        return {
            'connected': self.is_connected,
            'device_ip': self.device_ip,
            'channel': self.channel,
            'current_zoom_pos': self.current_zoom_pos,
            'current_focus_pos': self.current_focus_pos,
            'current_zoom_factor': self._position_to_zoom_factor(self.current_zoom_pos),
            'is_zooming': self.is_zooming,
            'is_focusing': self.is_focusing,
            'auto_focus_enabled': self.auto_focus_enabled
        }
    
    def _zoom_to_position_continuous(self, target_position, timeout=10.0):
        """
        使用连续变焦控制到达指定位置
        这种方法更适合海康威视设备
        
        Args:
            target_position: 目标位置 (0-3600)
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否成功
        """
        try:
            current_pos = self.current_zoom_pos
            diff = target_position - current_pos
            
            if abs(diff) < 20:  # 如果差距很小，认为已经到位
                return True
            
            # 确定变焦方向和速度
            if diff > 0:
                # 需要放大
                zoom_command = self.ZOOM_IN
            else:
                # 需要缩小
                zoom_command = self.ZOOM_OUT
            
            # 根据距离计算速度和时间
            distance = abs(diff)
            speed = min(7, max(1, distance // 200))  # 速度1-7
            duration = distance / 1000.0  # 估算持续时间
            
            # 开始变焦
            if self._ptz_control(zoom_command, speed):
                # 等待变焦完成
                import time
                time.sleep(min(duration, timeout))
                
                # 停止变焦
                self._ptz_control(zoom_command, 0)
                
                # 更新当前位置（估算）
                self.current_zoom_pos = target_position
                zoom_factor = self._position_to_zoom_factor(target_position)
                
                # 发送信号
                self.zoomChanged.emit(zoom_factor)
                self.statusChanged.emit(f"变焦到 {zoom_factor:.1f}x")
                
                return True
            else:
                return False
            
        except Exception as e:
            error_msg = f"连续变焦异常: {str(e)}"
            self.errorOccurred.emit(error_msg)
            return False
    
    # PTZ平移控制方法
    def pan_left(self, speed=4):
        """水平向左平移"""
        return self._ptz_control(self.PAN_LEFT, speed)
    
    def pan_right(self, speed=4):
        """水平向右平移"""
        return self._ptz_control(self.PAN_RIGHT, speed)
    
    def tilt_up(self, speed=4):
        """垂直向上平移"""
        return self._ptz_control(self.TILT_UP, speed)
    
    def tilt_down(self, speed=4):
        """垂直向下平移"""
        return self._ptz_control(self.TILT_DOWN, speed)
    
    def stop_pan(self):
        """停止水平平移"""
        return self._ptz_control(self.PAN_LEFT, 0)  # 速度为0表示停止
    
    def stop_tilt(self):
        """停止垂直平移"""
        return self._ptz_control(self.TILT_UP, 0)  # 速度为0表示停止
    
    def move_to_preset(self, preset_id):
        """移动到预设位置"""
        try:
            if not self.is_connected:
                return False
            
            # 调用预设位置
            result = sdk.NET_DVR_PTZPreset_Other(self.user_id, self.channel, 39, preset_id)
            
            if result:
                self.statusChanged.emit(f"移动到预设位置 {preset_id}")
                return True
            else:
                return False
                
        except Exception as e:
            return False

