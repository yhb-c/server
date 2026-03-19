# -*- coding: utf-8 -*-
"""
海康SDK视频捕获器 - Linux版本
使用海康SDK解码RTSP流，获取YUV数据用于推理
"""

import os
import sys
import logging
import threading
import queue
import time
import re
from ctypes import *

# 加载海康SDK动态库
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(os.path.dirname(current_dir), 'lib', 'lib')  # 实际库文件在lib/lib目录下

try:
    import platform
    system = platform.system().lower()
    
    if system == 'windows':
        # Windows动态库
        hcnetsdk_lib = os.path.join(lib_path, 'HCNetSDK.dll')
        playctrl_lib = os.path.join(lib_path, 'PlayCtrl.dll')
    else:
        # Linux动态库
        hcnetsdk_lib = os.path.join(lib_path, 'libhcnetsdk.so')
        playctrl_lib = os.path.join(lib_path, 'libPlayCtrl.so')
    
    print(f"尝试加载海康SDK: {hcnetsdk_lib}")
    HikSDK = CDLL(hcnetsdk_lib)
    PlayM4SDK = CDLL(playctrl_lib)
    print("海康SDK加载成功")
except Exception as e:
    print(f"加载海康SDK失败: {e}")
    HikSDK = None
    PlayM4SDK = None

# 海康SDK常量定义
NET_DVR_SYSHEAD = 1
NET_DVR_STREAMDATA = 2

# 回调函数类型定义
REALDATACALLBACK = CFUNCTYPE(None, c_long, c_uint, POINTER(c_ubyte), c_uint, c_void_p)
DECCBFUNWIN = CFUNCTYPE(None, c_long, POINTER(c_ubyte), c_long, c_void_p, c_long, c_long)


class NET_DVR_USER_LOGIN_INFO(Structure):
    """登录参数结构体"""
    _fields_ = [
        ("sDeviceAddress", c_byte * 129),
        ("byUseTransport", c_byte),
        ("wPort", c_ushort),
        ("sUserName", c_byte * 64),
        ("sPassword", c_byte * 64),
        ("cbLoginResult", c_void_p),
        ("pUser", c_void_p),
        ("bUseAsynLogin", c_bool),
        ("byProxyType", c_byte),
        ("byUseUTCTime", c_byte),
        ("byLoginMode", c_byte),
        ("byHttps", c_byte),
        ("iProxyID", c_long),
        ("byVerifyMode", c_byte),
        ("byRes3", c_byte * 119),
    ]


class NET_DVR_DEVICEINFO_V40(Structure):
    """设备信息结构体"""
    _fields_ = [
        ("struDeviceV30", c_byte * 1168),
        ("byRes1", c_byte),
        ("byRes2", c_byte),
        ("wDevType", c_ushort),
        ("byRes3", c_byte * 32),
        ("bySupport", c_byte),
        ("byLoginMode", c_byte),
        ("byRes4", c_byte * 253),
    ]


class NET_DVR_PREVIEWINFO(Structure):
    """预览参数结构体"""
    _fields_ = [
        ("lChannel", c_long),
        ("lLinkMode", c_long),
        ("hPlayWnd", c_void_p),
        ("sMultiCastIP", c_char_p),
        ("byProtoType", c_byte),
        ("byRes", c_byte * 3),
    ]


class FRAME_INFO(Structure):
    """帧信息结构体"""
    _fields_ = [
        ("nWidth", c_int32),      # 使用固定32位整数
        ("nHeight", c_int32),
        ("nStamp", c_int32),
        ("nType", c_int32),
        ("nFrameRate", c_int32),
        ("dwFrameNum", c_uint32),  # 帧序号
    ]


class HikCapture:
    """海康SDK视频捕获器"""
    
    def __init__(self, rtsp_url, channel_id):
        """
        初始化捕获器
        
        Args:
            rtsp_url: RTSP流地址
            channel_id: 通道ID
        """
        self.logger = logging.getLogger(__name__)
        self.rtsp_url = rtsp_url
        self.channel_id = channel_id
        
        self.is_running = False
        self.yuv_queue = queue.Queue(maxsize=10)
        
        # 海康SDK句柄
        self.user_id = -1
        self.real_play_handle = -1
        self.play_port = c_long(-1)
        
        # 解析RTSP URL
        self.ip, self.port, self.username, self.password = self._parse_rtsp_url(rtsp_url)
        
        # 初始化SDK
        self._init_sdk()
        
        self.logger.info(f"海康捕获器初始化: {rtsp_url}")
    
    def _parse_rtsp_url(self, url):
        """解析RTSP URL
        
        格式: rtsp://username:password@ip:port/path
        """
        pattern = r'rtsp://([^:]+):([^@]+)@([^:]+):(\d+)'
        match = re.match(pattern, url)
        
        if match:
            username = match.group(1)
            password = match.group(2)
            ip = match.group(3)
            port = int(match.group(4))
            return ip, port, username, password
        else:
            self.logger.error(f"无法解析RTSP URL: {url}")
            return None, 8000, None, None
    
    def _init_sdk(self):
        """初始化海康SDK"""
        if HikSDK is None or PlayM4SDK is None:
            self.logger.error("海康SDK未加载")
            return False
        
        # 初始化SDK（只需要初始化一次）
        try:
            ret = HikSDK.NET_DVR_Init()
            if not ret:
                self.logger.warning("SDK初始化失败（可能已初始化）")
            
            # 设置日志路径
            log_dir = os.path.join(os.path.dirname(current_dir), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            HikSDK.NET_DVR_SetLogToFile(3, log_dir.encode('utf-8'), False)
            
            return True
        except Exception as e:
            self.logger.error(f"SDK初始化异常: {e}")
            return False
    
    def start(self):
        """启动捕获"""
        try:
            # 登录设备
            if not self._login():
                return False
            
            # 获取播放端口
            if not PlayM4SDK.PlayM4_GetPort(byref(self.play_port)):
                self.logger.error("获取播放端口失败")
                return False
            
            # 开始预览
            if not self._start_preview():
                return False
            
            self.is_running = True
            self.logger.info(f"视频捕获启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动捕获失败: {e}", exc_info=True)
            return False
    
    def _login(self):
        """登录设备"""
        if not self.ip or not self.username or not self.password:
            self.logger.error("登录参数不完整")
            return False
        
        login_info = NET_DVR_USER_LOGIN_INFO()
        
        # 正确的字节数组赋值方式
        ip_bytes = self.ip.encode('utf-8')
        for i, b in enumerate(ip_bytes):
            if i < 129:
                login_info.sDeviceAddress[i] = b
        
        login_info.wPort = self.port
        
        user_bytes = self.username.encode('utf-8')
        for i, b in enumerate(user_bytes):
            if i < 64:
                login_info.sUserName[i] = b
        
        pass_bytes = self.password.encode('utf-8')
        for i, b in enumerate(pass_bytes):
            if i < 64:
                login_info.sPassword[i] = b
        
        login_info.bUseAsynLogin = False
        login_info.byLoginMode = 0
        
        device_info = NET_DVR_DEVICEINFO_V40()
        
        self.user_id = HikSDK.NET_DVR_Login_V40(
            byref(login_info),
            byref(device_info)
        )
        
        if self.user_id < 0:
            error_code = HikSDK.NET_DVR_GetLastError()
            self.logger.error(f"登录失败，错误码: {error_code}")
            return False
        
        self.logger.info(f"登录成功，UserID: {self.user_id}")
        return True
    
    def _start_preview(self):
        """开始预览"""
        # 创建回调函数
        self.real_data_callback = REALDATACALLBACK(self._on_real_data)
        
        # 预览参数
        preview_info = NET_DVR_PREVIEWINFO()
        preview_info.lChannel = 1  # 通道号
        preview_info.lLinkMode = 0  # TCP
        preview_info.hPlayWnd = None  # 不渲染到窗口
        
        # 开始预览
        self.real_play_handle = HikSDK.NET_DVR_RealPlay_V40(
            self.user_id,
            byref(preview_info),
            self.real_data_callback,
            None
        )
        
        if self.real_play_handle < 0:
            error_code = HikSDK.NET_DVR_GetLastError()
            self.logger.error(f"开始预览失败，错误码: {error_code}")
            return False
        
        self.logger.info(f"开始预览成功，Handle: {self.real_play_handle}")
        return True
    
    def _on_real_data(self, lRealHandle, dwDataType, pBuffer, dwBufSize, pUser):
        """实时数据回调"""
        try:
            if dwDataType == NET_DVR_SYSHEAD:
                # 系统头，初始化解码器
                PlayM4SDK.PlayM4_SetStreamOpenMode(self.play_port, 0)
                
                if PlayM4SDK.PlayM4_OpenStream(self.play_port, pBuffer, dwBufSize, 1024 * 1024):
                    # 设置解码回调
                    self.decode_callback = DECCBFUNWIN(self._on_decode)
                    PlayM4SDK.PlayM4_SetDecCallBackExMend(
                        self.play_port,
                        self.decode_callback,
                        None,
                        0,
                        None
                    )
                    
                    # 开始播放（不渲染）
                    PlayM4SDK.PlayM4_Play(self.play_port, None)
                    self.logger.info("解码器启动成功")
                    
            elif dwDataType == NET_DVR_STREAMDATA:
                # 流数据，输入到解码器
                PlayM4SDK.PlayM4_InputData(self.play_port, pBuffer, dwBufSize)
                
        except Exception as e:
            self.logger.error(f"实时数据回调异常: {e}")
    
    def _on_decode(self, nPort, pBuf, nSize, pFrameInfo, nUser, nReserved2):
        """解码回调，获取YUV数据"""
        try:
            frame_info = cast(pFrameInfo, POINTER(FRAME_INFO)).contents
            
            # 添加日志：记录帧类型
            if not hasattr(self, '_frame_type_logged'):
                self._frame_type_logged = {}
            
            if frame_info.nType not in self._frame_type_logged:
                self.logger.info(f"收到帧类型: {frame_info.nType}, 尺寸: {frame_info.nWidth}x{frame_info.nHeight}")
                self._frame_type_logged[frame_info.nType] = True
            
            if frame_info.nType == 3:  # YUV数据
                width = frame_info.nWidth
                height = frame_info.nHeight
                
                # 计算YUV数据大小（I420格式）
                yuv_size = width * height * 3 // 2
                
                # 复制YUV数据
                yuv_data = string_at(pBuf, yuv_size)
                
                # 放入队列
                yuv_frame = {
                    'data': yuv_data,
                    'width': width,
                    'height': height,
                    'timestamp': time.time()
                }
                
                try:
                    if self.yuv_queue.full():
                        self.yuv_queue.get_nowait()  # 丢弃旧帧
                    self.yuv_queue.put_nowait(yuv_frame)
                    
                    # 第一次成功放入队列时记录日志
                    if not hasattr(self, '_first_frame_logged'):
                        self.logger.info(f"成功获取第一帧YUV数据: {width}x{height}")
                        self._first_frame_logged = True
                except:
                    pass
                    
        except Exception as e:
            if not hasattr(self, '_decode_error_logged'):
                self.logger.error(f"解码回调异常: {e}")
                self._decode_error_logged = True
    
    def stop(self):
        """停止捕获"""
        self.is_running = False
        
        # 停止预览
        if self.real_play_handle > -1:
            HikSDK.NET_DVR_StopRealPlay(self.real_play_handle)
            self.real_play_handle = -1
        
        # 停止播放
        if self.play_port.value > -1:
            PlayM4SDK.PlayM4_Stop(self.play_port)
            PlayM4SDK.PlayM4_CloseStream(self.play_port)
            PlayM4SDK.PlayM4_FreePort(self.play_port)
            self.play_port = c_long(-1)
        
        # 登出
        if self.user_id > -1:
            HikSDK.NET_DVR_Logout(self.user_id)
            self.user_id = -1
        
        self.logger.info("视频捕获已停止")
    
    def get_yuv_frame(self):
        """
        获取YUV帧数据
        
        Returns:
            dict: YUV帧数据，包含data, width, height, timestamp
        """
        try:
            return self.yuv_queue.get(timeout=0.1)
        except queue.Empty:
            return None
    
    def is_alive(self):
        """检查捕获是否还在运行"""
        return self.is_running
