# -*- coding: utf-8 -*-
import time
import threading
import queue
import numpy as np
import cv2
import re
from ctypes import *

# 支持相对导入和绝对导入
try:
    from .HCNetSDK import *
    from .PlayCtrl import *
except ImportError:
    from HCNetSDK import *
    from PlayCtrl import *


# 全局SDK操作锁，保护海康SDK的关键操作
_HK_SDK_LOCK = threading.RLock()

# 全局SDK初始化标志
_HK_SDK_INITIALIZED = False


class HKcapture:
    """
    统一的视频捕获类
    支持海康威视摄像头（使用SDK）和其他RTSP通道（使用OpenCV）
    提供类似cv2.VideoCapture的接口
    """ 
    
    def __init__(self, source, username=None, password=None, port=8000, channel=1, fps=25, debug=False, decode_device='cpu'):
        """
        初始化视频捕获对象
        
        参数:
            source: 视频源，可以是IP地址(海康威视)或RTSP URL (str)
            username: 登录用户名 (str，海康威视必需) 
            password: 登录密码 (str，海康威视必需)
            port: 设备端口，默认8000 (int，仅海康威视使用)
            channel: 通道号，默认1 (int，仅海康威视使用)
            fps: 期望帧率，默认25 (int，用于配置通道和OpenCV)
            debug: 是否输出调试信息，默认False
            decode_device: 解码设备，'hardware'=硬件解码(HXVA)，'cpu'=软件解码
        """
        self.source = source
        self.username = username
        self.password = password
        self.port = port
        self.channel = channel
        self.target_fps = fps  # 保存期望帧率
        self.debug = debug  # 调试开关
        self.decode_device = decode_device.lower()  # 解码设备配置
        
        # 检测是否为海康威视设备
        self.is_hikvision = self._detect_hikvision()
        
        # 🔥 检测是否为本地视频文件
        self.is_video_file = self._detect_video_file()
        
        # 通用变量
        self.is_opened = False
        self.is_reading = False
        self.frame_width = 0
        self.frame_height = 0
        self.fps = self.target_fps  # 使用配置的帧率
        self.original_fps = 0  # 🔥 视频文件的原始帧率
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # 帧序列号，用于判断是否有新帧
        self.frame_sequence = 0
        self.last_read_sequence = -1
        
        # 健康检查相关
        self.last_frame_time = time.time()
        self.no_frame_warning_printed = False
        
        # ========== HWND直接渲染模式相关 ==========
        self._hwnd = None                    # 渲染窗口句柄
        self._render_mode = False            # 是否启用HWND直接渲染
        self._qsv_decode_enabled = False     # QSV解码状态
        
        # ========== YUV直接传递模式（高性能检测）==========
        self._yuv_queue_enabled = False      # 是否启用YUV队列
        self._yuv_queue = queue.Queue(maxsize=8)  # YUV数据队列
        self._yuv_send_interval = 0.1        # YUV发送间隔（秒）
        self._last_yuv_send_time = 0         # 上次发送YUV的时间
        
        if self.is_hikvision:
            # 海康威视SDK相关变量
            self.hikSDK = None
            self.playM4SDK = None
            self.iUserID = -1
            self.lRealPlayHandle = -1
            self.PlayCtrlPort = C_LONG(-1)
            # 不使用队列！SDK回调直接更新 current_frame（最新帧）
            self.funcRealDataCallBack_V30 = REALDATACALLBACK(self._real_data_callback)
            self.FuncDecCB = None
            
            # 初始化海康威视SDK
            self._init_hikvision_sdk()
        elif self.is_video_file:
            # 🔥 本地视频文件使用 PlayCtrl SDK
            self.playM4SDK = None
            self.PlayCtrlPort = C_LONG(-1)
            self.FuncDecCB = None
            # OpenCV 相关变量（不使用，但保持兼容）
            self.cv_cap = None
            self.capture_thread = None
            self.stop_thread = False
        else:
            # OpenCV VideoCapture相关变量（RTSP流）
            self.cv_cap = None
            self.capture_thread = None
            self.stop_thread = False
            
        # 摄像头捕获对象已初始化
    
    # ==================== HWND直接渲染模式API ====================
    
    def set_hwnd(self, hwnd):
        """设置渲染窗口句柄
        
        Args:
            hwnd: 窗口句柄（Windows HWND，可以从Qt的winId()获取）
        
        🔥 修复：设置HWND时同时启用渲染模式
        """
        self._hwnd = hwnd
        # 🔥 关键修复：设置HWND时自动启用渲染模式
        if hwnd:
            self._render_mode = True
        if self.debug:
            print(f"[HKcapture] 设置HWND: {hwnd}, _render_mode={self._render_mode}")
    
    def enable_frame_grab(self, enabled=True):
        """启用/禁用帧抓取（已废弃，保留接口兼容性）
        
        注意：现在使用YUV队列模式，此方法仅保留接口兼容性
        实际帧数据通过 enable_yuv_queue() 获取
        """
        if self.debug:
            print(f"[HKcapture] enable_frame_grab已废弃，请使用enable_yuv_queue")
        pass
    
    def start_render(self):
        """开始HWND直接渲染模式
        
        Returns:
            bool: 是否成功启动
        """
        if not self._hwnd:
            return False
        
        if not self.is_opened:
            return False
        
        self._render_mode = True
        
        # 🔥 如果已经在播放（HWND=0），需要停止后重新启动到正确的HWND
        if self.is_reading and self.is_video_file:
            # 停止当前播放
            port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
            self.playM4SDK.PlayM4_Stop(c_long(port))
            self.playM4SDK.PlayM4_CloseFile(c_long(port))
            self.is_reading = False
        
        result = self.start_capture()
        return result
    
    def stop_render(self):
        """停止HWND直接渲染"""
        self._render_mode = False
        self.stop_capture()
    
    def refresh_hwnd(self, hwnd):
        """刷新渲染窗口句柄（窗口大小改变时调用）
        
        Args:
            hwnd: 新的窗口句柄
        """
        self._hwnd = hwnd
    
    # ==================== YUV直接传递模式API（高性能检测）====================
    
    def enable_yuv_queue(self, enabled=True, interval=0.1):
        """启用/禁用YUV数据队列（供检测线程直接使用）
        
        YUV直接传递模式优势：
        - 解码回调直接送YUV数据，无需额外的帧抓取线程
        - 检测线程直接裁剪ROI区域的YUV数据再转RGB
        - 减少全帧转换开销，提高检测帧率
        
        Args:
            enabled: True启用YUV队列，False禁用
            interval: YUV发送间隔（秒），默认0.1秒=10fps
        """
        self._yuv_queue_enabled = enabled
        self._yuv_send_interval = interval
        
        print(f"[HKcapture] YUV队列设置: enabled={enabled}, interval={interval}s, _yuv_queue_enabled={self._yuv_queue_enabled}")
        
        if not enabled:
            # 清空队列
            while not self._yuv_queue.empty():
                try:
                    self._yuv_queue.get_nowait()
                except:
                    break
        
        if self.debug:
            print(f"[HKcapture] YUV队列: {'启用' if enabled else '禁用'}, 间隔: {interval}s")
    
    def get_yuv_data(self, timeout=0.1):
        """获取YUV数据（供检测线程调用）
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            tuple: (yuv_data, width, height, timestamp) 或 None
        """
        try:
            return self._yuv_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_yuv_data_nowait(self):
        """非阻塞获取YUV数据
        
        Returns:
            tuple: (yuv_data, width, height, timestamp) 或 None
        """
        try:
            return self._yuv_queue.get_nowait()
        except queue.Empty:
            return None
    
    def has_yuv_data(self):
        """检查是否有YUV数据可用
        
        Returns:
            bool: 是否有数据
        """
        return not self._yuv_queue.empty()
        
        # 如果正在播放，刷新播放窗口
        if self.is_reading and self.PlayCtrlPort.value > -1:
            port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
            try:
                self.playM4SDK.PlayM4_RefreshPlay(c_long(port))
            except:
                pass
    
    def _detect_video_file(self):
        """
        检测source是否为本地视频文件
        
        返回:
            bool: 是否为本地视频文件
        """
        import os
        if not self.source:
            return False
        
        # 视频文件扩展名列表
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg']
        
        # 检查是否为文件路径（不是URL）
        if self.source.startswith('rtsp://') or self.source.startswith('http://') or self.source.startswith('https://'):
            return False
        
        # 检查文件扩展名
        _, ext = os.path.splitext(self.source.lower())
        if ext in video_extensions:
            # 检查文件是否存在
            if os.path.isfile(self.source):
                return True
        
        return False
    
    def _detect_hikvision(self):
        """检测是否为海康威视设备
        
        🔥 修复：所有包含用户名密码的RTSP流都使用海康SDK处理
        这样可以利用PlayCtrl SDK的HWND直接渲染功能
        """
        # 🔥 如果是本地视频文件，不是海康威视设备
        if hasattr(self, 'is_video_file') and self.is_video_file:
            return False
        
        # 🔥 关键修复：如果是RTSP URL且包含用户名密码，都使用海康SDK
        # 这样可以利用PlayCtrl SDK的HWND直接渲染功能
        if self.source and self.source.startswith('rtsp://'):
            # 检查URL中是否包含认证信息（格式：rtsp://user:pass@ip）
            if '@' in self.source:
                print(f"[HKcapture] RTSP流包含认证信息，使用海康SDK处理")
                return True
        
        # 如果source包含admin:cei345678字段，则认为是海康威视设备
        if self.source and 'admin:cei345678' in self.source:
            return True
        # 如果source包含admin:123456aA@字段，则认为是海康威视设备
        if self.source and 'admin:123456aA@' in self.source:
            return True
            
        # 如果source是IP地址格式且提供了用户名密码，则认为是海康威视
        if self.username and self.password:
            # 检查是否为IP地址格式
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if self.source and re.match(ip_pattern, self.source):
                return True
        
        # 如果source包含rtsp://，检查是否包含海康威视特征
        if self.source and self.source.startswith('rtsp://'):
            # 如果RTSP URL包含admin:cei345678，认为是海康威视
            if 'admin:cei345678' in self.source:
                return True
            # 如果RTSP URL包含admin:123456aA@，认为是海康威视
            if 'admin:123456aA@' in self.source:
                return True
            # 否则认为是其他RTSP通道
            return False
            
        # 默认情况下，如果提供了用户名密码，认为是海康威视
        return bool(self.username and self.password)
    
    def _extract_ip_from_source(self):
        """从source中提取IP地址"""
        if not self.source:
            return None
            
        # 如果source是纯IP地址
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ip_pattern, self.source):
            return self.source
            
        # 如果source是RTSP URL，提取IP
        # 支持密码中包含@符号的情况
        if self.source.startswith('rtsp://'):
            try:
                # 去掉 rtsp:// 前缀
                url_part = self.source[7:]
                if self.debug:
                    print(f"[HKcapture调试] _extract_ip: url_part={url_part}")
                
                # 找到最后一个 @ 符号（IP地址前的那个）
                last_at_index = url_part.rfind('@')
                if self.debug:
                    print(f"[HKcapture调试] _extract_ip: last_at_index={last_at_index}")
                
                if last_at_index != -1:
                    # @ 后面是 ip:port/path
                    host_part = url_part[last_at_index + 1:]
                else:
                    # 没有认证信息，直接是 ip:port/path
                    host_part = url_part
                if self.debug:
                    print(f"[HKcapture调试] _extract_ip: host_part={host_part}")
                
                # 提取IP（到:或/为止）
                ip_end = len(host_part)
                colon_idx = host_part.find(':')
                slash_idx = host_part.find('/')
                if colon_idx != -1:
                    ip_end = min(ip_end, colon_idx)
                if slash_idx != -1:
                    ip_end = min(ip_end, slash_idx)
                
                extracted_ip = host_part[:ip_end]
                if self.debug:
                    print(f"[HKcapture调试] _extract_ip: 提取的IP={extracted_ip}")
                return extracted_ip
            except Exception as e:
                if self.debug:
                    print(f"[HKcapture调试] _extract_ip: 异常={e}")
                pass
                
        return None
    
    def _extract_credentials_from_source(self):
        """从source中提取用户名和密码
        
        支持密码中包含特殊字符（如@）的情况
        URL格式: rtsp://username:password@ip:port/path
        """
        if self.debug:
            print(f"[HKcapture调试] _extract_credentials_from_source 被调用")
            print(f"[HKcapture调试] 原始source: {self.source}")
        
        if not self.source or not self.source.startswith('rtsp://'):
            if self.debug:
                print(f"[HKcapture调试] source为空或不是rtsp://开头，返回None")
            return None, None
        
        try:
            # 去掉 rtsp:// 前缀
            url_part = self.source[7:]  # 去掉 "rtsp://"
            if self.debug:
                print(f"[HKcapture调试] 去掉rtsp://后: {url_part}")
            
            # 找到最后一个 @ 符号（IP地址前的那个）
            # 这样可以正确处理密码中包含 @ 的情况
            last_at_index = url_part.rfind('@')
            if self.debug:
                print(f"[HKcapture调试] 最后一个@的位置: {last_at_index}")
            
            if last_at_index == -1:
                if self.debug:
                    print(f"[HKcapture调试] 未找到@符号，返回None")
                return None, None
            
            # 提取用户名:密码部分
            credentials_part = url_part[:last_at_index]
            host_part = url_part[last_at_index + 1:]
            if self.debug:
                print(f"[HKcapture调试] 凭证部分: {credentials_part}")
                print(f"[HKcapture调试] 主机部分: {host_part}")
            
            # 找到第一个 : 分隔用户名和密码
            first_colon_index = credentials_part.find(':')
            if self.debug:
                print(f"[HKcapture调试] 第一个:的位置: {first_colon_index}")
            
            if first_colon_index == -1:
                if self.debug:
                    print(f"[HKcapture调试] 凭证部分未找到:，返回None")
                return None, None
            
            username = credentials_part[:first_colon_index]
            password = credentials_part[first_colon_index + 1:]
            if self.debug:
                print(f"[HKcapture调试] 解析出用户名: {username}")
                print(f"[HKcapture调试] 解析出密码(解码前): {password}")
            
            # URL解码密码（处理 %40 等编码的特殊字符）
            from urllib.parse import unquote
            password = unquote(password)
            if self.debug:
                print(f"[HKcapture调试] 解析出密码(解码后): {password}")
            
            return username, password
            
        except Exception as e:
            if self.debug:
                print(f"[HKcapture调试] 解析异常: {e}")
            # 回退到旧的正则解析方式
            pattern = r'rtsp://([^:]+):([^@]+)@'
            match = re.match(pattern, self.source)
            if match:
                return match.group(1), match.group(2)
            return None, None
    
    def _init_hikvision_sdk(self):
        """初始化海康威视SDK库（线程安全）"""
        global _HK_SDK_INITIALIZED
        
        try:
            with _HK_SDK_LOCK:
                self.hikSDK = load_library(netsdkdllpath)
                self.playM4SDK = load_library(playM4dllpath)
                
                # SDK只需要初始化一次（全局共享）
                if not _HK_SDK_INITIALIZED:
                    # 设置SDK初始化配置
                    self._set_sdk_init_cfg()
                    
                    # 初始化SDK
                    if not self.hikSDK.NET_DVR_Init():
                        return False
                    
                    # 设置日志
                    self.hikSDK.NET_DVR_SetLogToFile(3, b'./SdkLog_Python/', False)
                    
                    _HK_SDK_INITIALIZED = True
                
                return True

        except Exception as e:
            if self.debug:
                print(f"[HKcapture调试] SDK初始化异常: {e}")
                import traceback
                traceback.print_exc()
            return False

    def _set_sdk_init_cfg(self):
        """设置海康威视SDK初始化依赖库路径"""
        if sys_platform == 'windows':
            # 使用脚本所在目录而不是当前工作目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            basePath = script_dir.encode('gbk')
            strPath = basePath + b'\lib'
            sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
            sdk_ComPath.sPath = strPath
            
            self.hikSDK.NET_DVR_SetSDKInitCfg(
                NET_SDK_INIT_CFG_TYPE.NET_SDK_INIT_CFG_SDK_PATH.value,
                byref(sdk_ComPath)
            )
            self.hikSDK.NET_DVR_SetSDKInitCfg(
                NET_SDK_INIT_CFG_TYPE.NET_SDK_INIT_CFG_LIBEAY_PATH.value,
                create_string_buffer(strPath + b'\libcrypto-1_1-x64.dll')
            )
            self.hikSDK.NET_DVR_SetSDKInitCfg(
                NET_SDK_INIT_CFG_TYPE.NET_SDK_INIT_CFG_SSLEAY_PATH.value,
                create_string_buffer(strPath + b'\libssl-1_1-x64.dll')
            )
    
    def open(self):
        """
        打开摄像头连接
        
        返回:
            bool: 成功返回True，失败返回False
        """
        if self.is_opened:
            return True
            
        if self.is_hikvision:
            return self._open_hikvision()
        else:
            return self._open_rtsp()
    
    def _open_hikvision(self):
        """打开海康威视摄像头连接（优化锁策略）"""
        # 初始化SDK（必须在登录前完成）
        if not self._init_hikvision_sdk():
            if self.debug:
                print("[HKcapture调试] SDK初始化失败")
            return False

        # 登录设备（无需锁，每个通道独立登录）
        if not self._login_device():
            return False
        
        # 获取播放句柄（需要锁，避免端口分配冲突）
        with _HK_SDK_LOCK:
            if not self.playM4SDK.PlayM4_GetPort(byref(self.PlayCtrlPort)):
                return False
        
        self.is_opened = True
        return True
    
    def _open_rtsp(self):
        """打开RTSP摄像头连接或本地视频文件"""
        # 🔥 本地视频文件使用 PlayCtrl SDK
        if self.is_video_file:
            return self._open_video_file()
        
        # RTSP流使用 OpenCV
        try:
            self.cv_cap = cv2.VideoCapture(self.source)
            if not self.cv_cap.isOpened():
                return False
            
            # 获取视频属性
            self.frame_width = int(self.cv_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.cv_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cv_cap.get(cv2.CAP_PROP_FPS)
            
            # RTSP流：尝试设置帧率（通常不生效，由服务器控制）
            if self.target_fps > 0:
                self.cv_cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            # 使用配置的帧率（RTSP流的FPS通常不准确）
            self.fps = self.target_fps if self.target_fps > 0 else (int(actual_fps) or 25)
            
            self.is_opened = True
            return True
            
        except Exception as e:
            return False
    
    def _open_video_file(self):
        """打开本地视频文件（使用 PlayCtrl SDK）"""
        try:
            # 初始化 PlayCtrl SDK（如果尚未初始化）
            if not hasattr(self, 'playM4SDK') or self.playM4SDK is None:
                self.playM4SDK = load_library(playM4dllpath)
            
            # 获取播放句柄
            with _HK_SDK_LOCK:
                ret = self.playM4SDK.PlayM4_GetPort(byref(self.PlayCtrlPort))
                if not ret:
                    error = self.playM4SDK.PlayM4_GetLastError(c_long(0))
                    return False
            
            self.is_opened = True
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _login_device(self):
        """登录海康威视设备（已在_open_hikvision中持有锁）"""
        if self.debug:
            print(f"[HKcapture调试] _login_device 被调用")
            print(f"[HKcapture调试] self.source: {self.source}")
            print(f"[HKcapture调试] self.username: {self.username}")
            print(f"[HKcapture调试] self.password: {self.password}")
        
        # 从source中提取IP地址
        ip_address = self._extract_ip_from_source()
        if self.debug:
            print(f"[HKcapture调试] 提取的IP地址: {ip_address}")
        if not ip_address:
            if self.debug:
                print(f"[HKcapture调试] IP地址为空，登录失败")
            return False
            
        # 从source中提取用户名和密码（如果RTSP URL中包含）
        username, password = self._extract_credentials_from_source()
        if self.debug:
            print(f"[HKcapture调试] 从URL提取的用户名: {username}")
            print(f"[HKcapture调试] 从URL提取的密码: {password}")
        
        # 使用提供的用户名密码，或者从URL中提取的
        login_username = self.username or username
        login_password = self.password or password
        if self.debug:
            print(f"[HKcapture调试] 最终登录用户名: {login_username}")
            print(f"[HKcapture调试] 最终登录密码: {login_password}")
        
        if not login_username or not login_password:
            if self.debug:
                print(f"[HKcapture调试] 用户名或密码为空，登录失败")
            return False
        
        if self.debug:
            print(f"[HKcapture调试] 准备登录设备: IP={ip_address}, Port={self.port}, User={login_username}, Pass={login_password}")
        
        # 编码字节数据
        ip_bytes = ip_address.encode('utf-8')
        user_bytes = login_username.encode('utf-8')
        pass_bytes = login_password.encode('utf-8')
        if self.debug:
            print(f"[HKcapture调试] IP字节: {ip_bytes}, 长度={len(ip_bytes)}")
            print(f"[HKcapture调试] 用户名字节: {user_bytes}, 长度={len(user_bytes)}")
            print(f"[HKcapture调试] 密码字节: {pass_bytes}, 长度={len(pass_bytes)}")
            print(f"[HKcapture调试] 密码字符列表: {[c for c in login_password]}")
            print(f"[HKcapture调试] 密码ASCII码: {[ord(c) for c in login_password]}")
            
        struLoginInfo = NET_DVR_USER_LOGIN_INFO()
        struLoginInfo.bUseAsynLogin = 0
        struLoginInfo.sDeviceAddress = ip_bytes
        struLoginInfo.wPort = self.port
        struLoginInfo.sUserName = user_bytes
        struLoginInfo.sPassword = pass_bytes
        struLoginInfo.byLoginMode = 0
        
        struDeviceInfoV40 = NET_DVR_DEVICEINFO_V40()
        
        self.iUserID = self.hikSDK.NET_DVR_Login_V40(
            byref(struLoginInfo), 
            byref(struDeviceInfoV40)
        )
        
        if self.iUserID < 0:
            error_code = self.hikSDK.NET_DVR_GetLastError()
            # 海康威视SDK错误码解释
            error_messages = {
                1: "用户名或密码错误",
                2: "权限不足",
                3: "SDK未初始化",
                4: "通道号错误",
                5: "连接设备失败",
                6: "向设备发送失败",
                7: "从设备接收数据失败",
                8: "等待超时",
                9: "参数错误",
                10: "设备不支持",
                11: "设备资源不足",
                12: "设备离线",
                17: "设备不存在",
                28: "密码错误",
                29: "用户名不存在",
                47: "用户被锁定",
                153: "设备不在线",
            }
            error_msg = error_messages.get(error_code, f"未知错误")
            if self.debug:
                print(f"[HKcapture调试] 登录失败! iUserID={self.iUserID}, 错误码={error_code}, 错误信息={error_msg}")
                print(f"[HKcapture调试] ===== 登录参数详情 =====")
                print(f"[HKcapture调试] sDeviceAddress: {struLoginInfo.sDeviceAddress}")
                print(f"[HKcapture调试] wPort: {struLoginInfo.wPort}")
                print(f"[HKcapture调试] sUserName: {struLoginInfo.sUserName}")
                print(f"[HKcapture调试] sPassword: {struLoginInfo.sPassword}")
                print(f"[HKcapture调试] byLoginMode: {struLoginInfo.byLoginMode}")
                print(f"[HKcapture调试] ========================")
            return False
        else:
            if self.debug:
                print(f"[HKcapture调试] 登录成功! iUserID={self.iUserID}")
            return True
    
    def start_capture(self):
        """开始视频捕获"""
        import sys
        print(f"[HKcapture] start_capture: is_opened={self.is_opened}, is_reading={self.is_reading}")
        print(f"[HKcapture] start_capture: is_hikvision={self.is_hikvision}, is_video_file={self.is_video_file}")
        sys.stdout.flush()
        
        if not self.is_opened:
            print(f"[HKcapture] start_capture: 视频源未打开")
            sys.stdout.flush()
            return False
            
        if self.is_reading:
            print(f"[HKcapture] start_capture: 已在读取中，跳过")
            sys.stdout.flush()
            return True
            
        if self.is_hikvision:
            print(f"[HKcapture] start_capture: 走海康威视分支")
            sys.stdout.flush()
            return self._start_hikvision_capture()
        else:
            print(f"[HKcapture] start_capture: 走RTSP/本地视频分支")
            sys.stdout.flush()
            return self._start_rtsp_capture()
    
    def _start_hikvision_capture(self):
        """开始海康威视视频捕获（支持HWND直接渲染模式）"""
        import sys
        
        # 🔥 调试日志：确认HWND渲染模式状态
        print(f"[HKcapture] _start_hikvision_capture: _render_mode={self._render_mode}, _hwnd={self._hwnd}")
        sys.stdout.flush()
        
        # 根据是否设置HWND选择回调函数
        if self._render_mode and self._hwnd:
            print(f"[HKcapture] 使用HWND直接渲染回调 (_real_data_callback_hwnd)")
            self.funcRealDataCallBack_V30 = REALDATACALLBACK(self._real_data_callback_hwnd)
        else:
            print(f"[HKcapture] 使用传统回调 (_real_data_callback)，不渲染到窗口")
            self.funcRealDataCallBack_V30 = REALDATACALLBACK(self._real_data_callback)
        sys.stdout.flush()
        
        # 开始预览（无需锁，每个通道独立预览）
        preview_info = NET_DVR_PREVIEWINFO()
        preview_info.hPlayWnd = 0  # 不使用SDK的窗口渲染，由PlayCtrl处理
        preview_info.lChannel = self.channel
        preview_info.dwStreamType = 0  # 主码流
        preview_info.dwLinkMode = 0    # TCP
        preview_info.bBlocked = 0      # 非阻塞取流
        
        self.lRealPlayHandle = self.hikSDK.NET_DVR_RealPlay_V40(
            self.iUserID,
            byref(preview_info),
            self.funcRealDataCallBack_V30,
            None
        )
        
        if self.lRealPlayHandle < 0:
            return False
        
        self.is_reading = True
        return True
    
    def _start_rtsp_capture(self):
        """开始RTSP视频捕获"""
        import sys
        print(f"[HKcapture] _start_rtsp_capture: is_video_file={self.is_video_file}")
        sys.stdout.flush()
        
        # 🔥 本地视频文件使用 PlayCtrl SDK 播放
        if self.is_video_file:
            print(f"[HKcapture] _start_rtsp_capture: 走本地视频文件分支")
            sys.stdout.flush()
            return self._start_video_file_capture()
        
        # RTSP流使用 OpenCV
        print(f"[HKcapture] _start_rtsp_capture: 走OpenCV RTSP分支")
        sys.stdout.flush()
        self.stop_thread = False
        self.capture_thread = threading.Thread(target=self._rtsp_capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        self.is_reading = True
        return True
    
    def _start_video_file_capture(self):
        """开始本地视频文件播放（使用 PlayCtrl SDK 直接渲染到 HWND）"""
        import sys
        
        print(f"[HKcapture] ========== 开始本地视频播放 ==========")
        print(f"[HKcapture] 视频源: {self.source}")
        print(f"[HKcapture] HWND: {self._hwnd}")
        print(f"[HKcapture] 渲染模式: {self._render_mode}")
        sys.stdout.flush()
        
        # 初始化调试日志记录器（用于FPS统计）
        try:
            from utils.debug_logger import get_debug_logger
            import yaml
            self._debug_logger = get_debug_logger()
            # 从配置文件读取fps_log开关并启用
            config_path = "database/config/default_config.yaml"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config.get('fps_log', False):
                        self._debug_logger.enable(True)
        except:
            self._debug_logger = None
        
        try:
            port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
            print(f"[HKcapture] 播放端口: {port}")
            sys.stdout.flush()
            
            # 检查文件是否存在
            import os
            if not os.path.exists(self.source):
                print(f"[HKcapture] 视频文件不存在: {self.source}")
                sys.stdout.flush()
                return False
            
            print(f"[HKcapture] 视频文件存在, 大小: {os.path.getsize(self.source)} bytes")
            sys.stdout.flush()
            
            # 打开视频文件
            file_bytes = self.source.encode('gbk')
            print(f"[HKcapture] 调用 PlayM4_OpenFile, 文件路径: {file_bytes}")
            sys.stdout.flush()
            
            ret = self.playM4SDK.PlayM4_OpenFile(c_long(port), c_char_p(file_bytes))
            print(f"[HKcapture] PlayM4_OpenFile 返回: {ret}")
            sys.stdout.flush()
            
            if not ret:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] 打开视频文件失败, 错误码: {error}")
                sys.stdout.flush()
                return False
            
            print(f"[HKcapture] 视频文件已打开")
            sys.stdout.flush()
            
            # 设置解码回调（用于FPS记录和帧抓取）
            # 在HWND直接渲染模式下，总是设置解码回调来记录FPS
            print(f"[HKcapture] 设置解码回调...")
            sys.stdout.flush()
            self._setup_video_file_decode_callback()
            
            # 🔥 启用QSV解码（Intel Quick Sync Video）
            self._try_enable_qsv_decode()
            
            # 🔥 查询当前解码方式（调试信息）
            self._print_decode_mode_info(port)
            
            # 获取 HWND 值
            hwnd_value = self._hwnd if self._hwnd else 0
            print(f"[HKcapture] 准备播放到 HWND: {hwnd_value}")
            print(f"[HKcapture] HWND 类型: {type(hwnd_value)}")
            sys.stdout.flush()
            
            # 开始播放到 HWND
            print(f"[HKcapture] 调用 PlayM4_Play(port={port}, hwnd={hwnd_value})...")
            sys.stdout.flush()
            
            ret = self.playM4SDK.PlayM4_Play(c_long(port), c_void_p(hwnd_value))
            print(f"[HKcapture] PlayM4_Play 返回: {ret}")
            sys.stdout.flush()
            
            if ret:
                print(f"[HKcapture] 本地视频 PlayCtrl 播放已启动!")
                print(f"[HKcapture]    - Port: {port}")
                print(f"[HKcapture]    - HWND: {hwnd_value}")
                print(f"[HKcapture]    - 渲染模式: HWND直接渲染")
                sys.stdout.flush()
                self.is_reading = True
                return True
            else:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] 本地视频播放失败, 错误码: {error}")
                # 常见错误码解释
                error_msgs = {
                    1: "输入参数非法",
                    2: "调用顺序不对",
                    3: "创建文件映射失败",
                    4: "创建线程失败",
                    5: "打开文件失败",
                    6: "创建DirectDraw失败",
                    7: "创建offscreen失败",
                    8: "缓冲区太小",
                    9: "创建音频设备失败",
                    10: "设置音量失败",
                    11: "不支持的格式",
                    12: "内存不足",
                }
                if error in error_msgs:
                    print(f"[HKcapture]    错误说明: {error_msgs[error]}")
                sys.stdout.flush()
                return False
                
        except Exception as e:
            print(f"[HKcapture] 本地视频播放异常: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return False
    
    def _setup_video_file_decode_callback(self):
        """设置本地视频文件的解码回调（用于帧抓取）"""
        try:
            port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
            
            # 创建解码回调函数
            self.FuncDecCB = DECCBFUNWIN(self._video_file_decode_callback)
            
            # 设置解码回调
            ret = self.playM4SDK.PlayM4_SetDecCallBackExMend(
                c_long(port), 
                self.FuncDecCB, 
                None, 
                0, 
                None
            )
            
            if ret:
                if self.debug:
                    print(f"[HKcapture] 视频文件解码回调已设置")
            else:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] 设置解码回调失败, 错误码: {error}")
                
        except Exception as e:
            print(f"[HKcapture] 设置解码回调异常: {e}")
    
    def _video_file_decode_callback(self, nPort, pBuf, nSize, pFrameInfo, nUser, nReserved2):
        """本地视频文件解码回调（用于获取帧尺寸和YUV数据传递）
        
        YUV直接传递模式：解码回调直接将YUV数据送入队列，供检测线程使用
        """
        try:
            frame_info = pFrameInfo.contents
            if frame_info.nType == 3:  # YUV数据
                width = frame_info.nWidth
                height = frame_info.nHeight
                
                # 获取channel_id（如果未设置则使用默认值）
                channel_id = getattr(self, '_channel_id', 'channel1')
                
                # 第一次获取到分辨率时记录视频源信息
                if hasattr(self, '_debug_logger') and self._debug_logger and not hasattr(self, '_video_info_logged'):
                    resolution = f"{width}x{height}"
                    self._debug_logger.log_video_source_info(
                        channel_id, 
                        self.source, 
                        self.target_fps, 
                        resolution
                    )
                    self._video_info_logged = True  # 标记已记录，避免重复
                
                # 更新帧尺寸
                self.frame_width = width
                self.frame_height = height
                self.frame_sequence += 1
                self.last_frame_time = time.time()
                
                # 记录解码帧到调试日志（用于FPS统计）
                if hasattr(self, '_debug_logger') and self._debug_logger:
                    self._debug_logger.record_decode_frame(channel_id)
                    
                    # 在HWND模式下，解码后立即渲染到HWND，所以同时记录渲染FPS
                    if self._hwnd and self._hwnd != 0:
                        self._debug_logger.record_render_frame(channel_id)
                
                # ========== YUV直接传递模式 ==========
                # 如果启用YUV队列，按间隔发送YUV数据到队列
                if self._yuv_queue_enabled:
                    now = time.time()
                    if now - self._last_yuv_send_time >= self._yuv_send_interval:
                        self._last_yuv_send_time = now
                        
                        # 计算YUV数据大小（I420格式：Y + U + V = w*h + w*h/4 + w*h/4 = w*h*1.5）
                        yuv_size = width * height * 3 // 2
                        
                        # 从回调缓冲区复制YUV数据
                        yuv_data = string_at(pBuf, yuv_size)
                        
                        # 放入队列（非阻塞，队列满则丢弃旧数据）
                        try:
                            if self._yuv_queue.full():
                                self._yuv_queue.get_nowait()  # 丢弃旧数据
                            self._yuv_queue.put_nowait((yuv_data, width, height, now))
                        except:
                            pass
                
        except Exception as e:
            pass
    
    def _rtsp_capture_loop(self):
        """RTSP流捕获循环线程（仅用于非海康RTSP流）"""
        while not self.stop_thread and self.cv_cap and self.cv_cap.isOpened():
            ret, frame = self.cv_cap.read()
            if ret and frame is not None:
                with self.frame_lock:
                    self.current_frame = frame
                    self.frame_sequence += 1  # 新帧，序列号+1
                    self.last_frame_time = time.time()
            else:
                time.sleep(0.1)
                
    def _real_data_callback(self, lPlayHandle, dwDataType, pBuffer, dwBufSize, pUser):
        """海康威视实时数据回调函数（传统模式：帧抓取）"""
        if dwDataType == NET_DVR_SYSHEAD:
            print(f"[HKcapture] 收到系统头数据，准备初始化QSV解码器...")
            import sys
            sys.stdout.flush()
            
            # 设置流播放模式
            self.playM4SDK.PlayM4_SetStreamOpenMode(self.PlayCtrlPort, 0)
            
            # 打开码流
            if self.playM4SDK.PlayM4_OpenStream(self.PlayCtrlPort, pBuffer, dwBufSize, 1024 * 1024):
                print(f"[HKcapture] 码流打开成功，启用QSV解码...")
                sys.stdout.flush()

                # 启用QSV硬件解码（Intel Quick Sync Video）
                qsv_enabled = self._try_enable_qsv_decode()

                if not qsv_enabled:
                    print(f"[HKcapture] QSV解码启用失败！请检查Intel核显驱动")
                    sys.stdout.flush()

                # 设置解码回调（必须在Play之前）
                self._setup_hikvision_decode_callback()

                # 开始解码播放（不渲染到窗口）
                self.playM4SDK.PlayM4_Play(self.PlayCtrlPort, None)
                print(f"[HKcapture] QSV解码播放已启动")
                sys.stdout.flush()
            else:
                print(f"[HKcapture] 码流打开失败!")
                sys.stdout.flush()
                
        elif dwDataType == NET_DVR_STREAMDATA:
            # 输入流数据
            self.playM4SDK.PlayM4_InputData(self.PlayCtrlPort, pBuffer, dwBufSize)
    
    def _real_data_callback_hwnd(self, lPlayHandle, dwDataType, pBuffer, dwBufSize, pUser):
        """海康威视实时数据回调函数（HWND直接渲染模式）
        
        数据流：
        1. 收到系统头：初始化PlayCtrl解码器，设置HWND渲染，设置解码回调
        2. 收到流数据：输入到PlayCtrl解码器
        3. PlayCtrl自动解码并渲染到HWND
        4. 解码回调获取YUV数据，送入YUV队列供检测线程使用
        """
        if dwDataType == NET_DVR_SYSHEAD:
            if self.debug:
                print(f"[HKcapture] 收到系统头数据，初始化HWND直接渲染...")
            import sys
            sys.stdout.flush()
            
            # 设置流播放模式
            self.playM4SDK.PlayM4_SetStreamOpenMode(self.PlayCtrlPort, 0)
            
            # 打开码流
            if self.playM4SDK.PlayM4_OpenStream(self.PlayCtrlPort, pBuffer, dwBufSize, 1024 * 1024):
                # 启用QSV解码（Intel Quick Sync Video）
                self._try_enable_qsv_decode()
                
                # 🔥 设置解码回调（用于获取YUV数据送检测线程）
                self._setup_hikvision_decode_callback()
                
                # 获取HWND值
                hwnd_value = self._hwnd if self._hwnd else 0
                
                # 开始播放到HWND（关键：传入窗口句柄）
                if self.playM4SDK.PlayM4_Play(self.PlayCtrlPort, c_void_p(hwnd_value)):
                    print(f"[HKcapture] HWND直接渲染已启动，HWND={hwnd_value}")
                    sys.stdout.flush()
                else:
                    error = self.playM4SDK.PlayM4_GetLastError(self.PlayCtrlPort)
                    print(f"[HKcapture] HWND渲染启动失败，错误码: {error}")
                    sys.stdout.flush()
            else:
                print(f"[HKcapture] 码流打开失败")
                sys.stdout.flush()
                
        elif dwDataType == NET_DVR_STREAMDATA:
            # 输入流数据到解码器
            self.playM4SDK.PlayM4_InputData(self.PlayCtrlPort, pBuffer, dwBufSize)
    
    def _setup_hikvision_decode_callback(self):
        """设置海康威视实时流的解码回调（用于获取YUV数据）"""
        try:
            port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
            
            # 创建解码回调函数（复用本地视频的回调，逻辑相同）
            self.FuncDecCB = DECCBFUNWIN(self._hikvision_decode_callback)
            
            # 设置解码回调
            ret = self.playM4SDK.PlayM4_SetDecCallBackExMend(
                c_long(port), 
                self.FuncDecCB, 
                None, 
                0, 
                None
            )
            
            if ret:
                print(f"[HKcapture] 海康实时流解码回调已设置（YUV队列模式），Port={port}")
                import sys
                sys.stdout.flush()
            else:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] 设置解码回调失败, 错误码: {error}")
                
        except Exception as e:
            print(f"[HKcapture] 设置解码回调异常: {e}")
    
    def _hikvision_decode_callback(self, nPort, pBuf, nSize, pFrameInfo, nUser, nReserved2):
        """海康威视实时流解码回调（用于获取YUV数据送检测线程）

        YUV直接传递模式：解码回调直接将YUV数据送入队列，供检测线程使用
        不阻塞解码线程，转换在检测线程完成
        """
        try:
            frame_info = pFrameInfo.contents
            if self.debug and not hasattr(self, '_decode_callback_triggered'):
                print(f"[HKcapture-解码回调] 首次触发，nType={frame_info.nType}")
                self._decode_callback_triggered = True
            if frame_info.nType == 3:  # YUV数据
                width = frame_info.nWidth
                height = frame_info.nHeight
                
                # 获取channel_id（如果未设置则使用默认值）
                channel_id = getattr(self, '_channel_id', 'channel1')
                
                # 初始化debug_logger（仅首次）
                if not hasattr(self, '_debug_logger') or self._debug_logger is None:
                    try:
                        from utils.debug_logger import get_debug_logger
                        import yaml
                        import os
                        self._debug_logger = get_debug_logger()
                        config_path = "database/config/default_config.yaml"
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = yaml.safe_load(f)
                                if config.get('fps_log', False):
                                    self._debug_logger.enable(True)
                    except:
                        self._debug_logger = None
                
                # 第一次获取到分辨率时记录视频源信息
                if hasattr(self, '_debug_logger') and self._debug_logger and not hasattr(self, '_hik_video_info_logged'):
                    resolution = f"{width}x{height}"
                    self._debug_logger.log_video_source_info(
                        channel_id, 
                        self.source, 
                        self.target_fps, 
                        resolution
                    )
                    self._hik_video_info_logged = True
                
                # 更新帧尺寸
                self.frame_width = width
                self.frame_height = height
                self.frame_sequence += 1
                self.last_frame_time = time.time()
                
                # 记录解码帧到调试日志（用于FPS统计）
                if hasattr(self, '_debug_logger') and self._debug_logger:
                    self._debug_logger.record_decode_frame(channel_id)
                    
                    # 在HWND模式下，解码后立即渲染到HWND，所以同时记录渲染FPS
                    if self._hwnd and self._hwnd != 0:
                        self._debug_logger.record_render_frame(channel_id)
                
                # ========== YUV直接传递模式 ==========
                # 如果启用YUV队列，按间隔发送YUV数据到队列
                if self._yuv_queue_enabled:
                    now = time.time()
                    if now - self._last_yuv_send_time >= self._yuv_send_interval:
                        self._last_yuv_send_time = now

                        # 计算YUV数据大小（I420格式）
                        yuv_size = width * height * 3 // 2

                        # 从回调缓冲区复制YUV数据
                        yuv_data = string_at(pBuf, yuv_size)

                        # 放入队列（非阻塞，队列满则丢弃旧数据）
                        try:
                            if self._yuv_queue.full():
                                self._yuv_queue.get_nowait()  # 丢弃旧数据
                            self._yuv_queue.put_nowait((yuv_data, width, height, now))
                        except:
                            pass

                # ========== 更新 current_frame（供标注功能和read()使用）==========
                # 在所有模式下都需要更新 current_frame
                # 每隔一定时间更新一次 current_frame（避免频繁转换影响性能）
                now = time.time()
                if not hasattr(self, '_last_frame_update_time'):
                    self._last_frame_update_time = 0

                # 降低更新频率到每0.04秒一次（约25fps）
                if now - self._last_frame_update_time >= 0.04:
                    self._last_frame_update_time = now

                    try:
                        # 计算YUV数据大小（I420格式）
                        yuv_size = width * height * 3 // 2
                        yuv_data = string_at(pBuf, yuv_size)

                        # 转换为 BGR
                        yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
                        yuv_frame = yuv_array.reshape((height * 3 // 2, width))
                        frame = cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2BGR_I420)

                        # 更新 current_frame
                        with self.frame_lock:
                            self.current_frame = frame
                    except Exception as frame_update_error:
                        print(f"[HKcapture-解码回调] 更新current_frame失败: {frame_update_error}")

        except Exception as e:
            print(f"[HKcapture-解码回调] 异常: {e}")
            import traceback
            traceback.print_exc()

    def _setup_decode_engine(self):
        """根据decode_device配置设置解码引擎
        
        decode_device配置：
        - 'hardware': 硬件解码 (HXVA，自动选择GPU/QSV)
        - 'cpu': 软件解码 (CPU)
        
        海康PlayM4库解码引擎：
        - PlayM4_SetDecodeEngine(nPort, 0): 软件解码 (CPU)
        - PlayM4_SetDecodeEngine(nPort, 1): 硬件解码 (HXVA)
        
        注意：必须在PlayM4_Play之前调用
        
        Returns:
            bool: 解码引擎设置是否成功
        """
        import sys
        
        self._qsv_decode_enabled = False
        
        port = self.PlayCtrlPort.value if hasattr(self.PlayCtrlPort, 'value') else self.PlayCtrlPort
        
        # 根据配置选择解码模式
        if self.decode_device == 'cpu':
            decode_engine = 0
            decode_name = "CPU软件解码"
        else:  # 默认hardware
            decode_engine = 1
            decode_name = "硬件解码(HXVA)"
        
        print(f"[HKcapture] 设置解码引擎: {decode_name}, Port={port}")
        sys.stdout.flush()
        
        # 方案1：PlayM4_SetDecodeEngine（旧版API，更兼容）
        try:
            ret = self.playM4SDK.PlayM4_SetDecodeEngine(c_long(port), c_long(decode_engine))
            if ret:
                if decode_engine == 1:
                    self._qsv_decode_enabled = True
                print(f"[HKcapture] {decode_name}已启用 (PlayM4_SetDecodeEngine={decode_engine})")
                sys.stdout.flush()
                return True
            else:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] PlayM4_SetDecodeEngine 失败, 错误码={error}")
                sys.stdout.flush()
        except AttributeError:
            print(f"[HKcapture] PlayM4_SetDecodeEngine API不存在，尝试Ex版本")
            sys.stdout.flush()
        except Exception as e:
            print(f"[HKcapture] PlayM4_SetDecodeEngine 异常: {e}")
            sys.stdout.flush()
        
        # 方案2：PlayM4_SetDecodeEngineEx（新版API）
        try:
            ret = self.playM4SDK.PlayM4_SetDecodeEngineEx(c_long(port), c_long(decode_engine))
            if ret:
                if decode_engine == 1:
                    self._qsv_decode_enabled = True
                print(f"[HKcapture] {decode_name}已启用 (PlayM4_SetDecodeEngineEx={decode_engine})")
                sys.stdout.flush()
                return True
            else:
                error = self.playM4SDK.PlayM4_GetLastError(c_long(port))
                print(f"[HKcapture] PlayM4_SetDecodeEngineEx 失败, 错误码={error}")
                sys.stdout.flush()
        except AttributeError:
            print(f"[HKcapture] PlayM4_SetDecodeEngineEx API不存在")
            sys.stdout.flush()
        except Exception as e:
            print(f"[HKcapture] PlayM4_SetDecodeEngineEx 异常: {e}")
            sys.stdout.flush()
        
        # 解码引擎设置失败
        print(f"[HKcapture] 解码引擎设置失败，将使用默认解码方式")
        sys.stdout.flush()
        return False
    
    # 保留旧方法名作为别名，兼容现有代码
    def _try_enable_qsv_decode(self):
        """启用硬件解码（兼容旧代码）"""
        return self._setup_decode_engine()
    
    def _print_decode_mode_info(self, port):
        """打印当前解码模式信息（调试用）
        
        PlayCtrl SDK 解码引擎类型：
        - 0: 软件解码 (CPU)
        - 1: 硬件解码 (HXVA，自动选择GPU/QSV)
        """
        import sys
        
        print(f"[HKcapture] ========== 解码模式调试信息 ==========")
        print(f"[HKcapture] 配置 decode_device: {self.decode_device}")
        sys.stdout.flush()
        
        # 1. 检查HXVA.dll是否存在（硬解码依赖）
        import os
        hxva_paths = [
            os.path.join(os.path.dirname(__file__), 'lib', 'HXVA.dll'),
            os.path.join(os.path.dirname(__file__), 'HXVA.dll'),
            'HXVA.dll'
        ]
        hxva_found = False
        for path in hxva_paths:
            if os.path.exists(path):
                hxva_found = True
                print(f"[HKcapture] HXVA.dll 已找到: {path}")
                sys.stdout.flush()
                break
        if not hxva_found:
            print(f"[HKcapture] HXVA.dll 未找到（硬解码可能不可用）")
            sys.stdout.flush()
        
        # 2. 列出PlayCtrl SDK可用的解码相关API
        decode_apis = [
            'PlayM4_SetDecodeEngine',
            'PlayM4_GetDecodeEngine', 
            'PlayM4_SetDecodeEngineEx',
            'PlayM4_GetDecodeEngineEx',
            'PlayM4_SetHardDecode',
            'PlayM4_GetHardDecode'
        ]
        available_apis = []
        for api in decode_apis:
            if hasattr(self.playM4SDK, api):
                available_apis.append(api)
        print(f"[HKcapture] 可用解码API: {available_apis}")
        sys.stdout.flush()
        
        # 3. 尝试获取当前解码引擎类型
        engine_type = None
        try:
            if hasattr(self.playM4SDK, 'PlayM4_GetDecodeEngine'):
                engine_type = self.playM4SDK.PlayM4_GetDecodeEngine(c_long(port))
                engine_names = {0: "CPU软解码", 1: "硬件解码(HXVA)"}
                engine_name = engine_names.get(engine_type, f"未知({engine_type})")
                print(f"[HKcapture] PlayM4_GetDecodeEngine 返回: {engine_type} ({engine_name})")
                sys.stdout.flush()
        except Exception as e:
            print(f"[HKcapture] PlayM4_GetDecodeEngine 调用失败: {e}")
            sys.stdout.flush()
        
        try:
            if hasattr(self.playM4SDK, 'PlayM4_GetDecodeEngineEx'):
                engine_type_ex = self.playM4SDK.PlayM4_GetDecodeEngineEx(c_long(port))
                print(f"[HKcapture] PlayM4_GetDecodeEngineEx 返回: {engine_type_ex}")
                sys.stdout.flush()
        except Exception as e:
            print(f"[HKcapture] PlayM4_GetDecodeEngineEx 调用失败: {e}")
            sys.stdout.flush()
        
        # 4. 检查内部状态变量
        qsv_enabled = getattr(self, '_qsv_decode_enabled', False)
        print(f"[HKcapture] 内部状态 _qsv_decode_enabled: {qsv_enabled}")
        sys.stdout.flush()
        
        # 5. 结论
        if self.decode_device == 'cpu':
            print(f"[HKcapture] 当前使用: CPU软件解码（配置指定）")
        elif qsv_enabled and engine_type == 1:
            print(f"[HKcapture] 当前使用: 硬件解码(HXVA) - Intel QSV/NVIDIA NVDEC")
        elif qsv_enabled:
            print(f"[HKcapture] 硬件解码已设置，等待播放后生效")
        else:
            print(f"[HKcapture] 硬件解码设置失败，回退到CPU软解码")
        print(f"[HKcapture] ==========================================")
        sys.stdout.flush()
    
    def read(self):
        """
        读取一帧图像（只有新帧时返回True，带健康检查）
        
        返回:
            tuple: (ret, frame) 
                   ret: bool，是否有新帧
                   frame: numpy.ndarray，图像数据（如果有新帧）
                   
        性能优化：
            - 直接返回引用，无需复制（current_frame每次都是新对象赋值）
            - Python引用计数机制保证对象在被使用时不会被回收
        """
        if not self.is_reading:
            return False, None
        
        # 检查是否有新帧（通过序列号判断）
        #  优化：减少锁持有时间，快速获取数据后立即释放锁
        with self.frame_lock:
            current_seq = self.frame_sequence
            current_frame_ref = self.current_frame
            last_frame_time = self.last_frame_time
        
        # 锁外进行判断和处理
        if current_frame_ref is not None and current_seq > self.last_read_sequence:
            # 有新帧
            self.last_read_sequence = current_seq
            self.no_frame_warning_printed = False
            return True, current_frame_ref
        else:
            # 没有新帧 - 健康检查
            elapsed = time.time() - last_frame_time
            if elapsed > 5.0 and not self.no_frame_warning_printed:
                self.no_frame_warning_printed = True
            return False, None
    
    def read_latest(self):
        """
        读取最新的一帧图像（与read()相同，只有新帧时返回True）
        
        返回:
            tuple: (ret, frame)
                   ret: bool，是否有新帧
                   frame: numpy.ndarray，图像数据（如果有新帧）
        """
        # read() 已经实现了新帧检测，read_latest() 和 read() 完全相同
        return self.read()
    
    def get_frame_size(self):
        """
        获取视频帧尺寸
        
        返回:
            tuple: (width, height)
        """
        return self.frame_width, self.frame_height
    
    def get_fps(self):
        """
        获取视频帧率
        
        返回:
            int: 帧率
        """
        return self.fps
    
    def is_opened_status(self):
        """
        检查摄像头是否已打开
        
        返回:
            bool: 是否已打开
        """
        return self.is_opened
    
    def stop_capture(self):
        """停止视频捕获"""
        if not self.is_reading:
            return
            
        if self.is_hikvision:
            self._stop_hikvision_capture()
        else:
            self._stop_rtsp_capture()
            
        self.is_reading = False
    
    def _stop_hikvision_capture(self):
        """停止海康威视视频捕获（优化锁策略）"""
        # 停止预览（无需锁）
        if self.lRealPlayHandle > -1:
            self.hikSDK.NET_DVR_StopRealPlay(self.lRealPlayHandle)
            self.lRealPlayHandle = -1
        
        # 停止播放库（需要锁，避免端口释放冲突）
        if self.PlayCtrlPort.value > -1:
            with _HK_SDK_LOCK:
                self.playM4SDK.PlayM4_Stop(self.PlayCtrlPort)
                self.playM4SDK.PlayM4_CloseStream(self.PlayCtrlPort)
                self.playM4SDK.PlayM4_FreePort(self.PlayCtrlPort)
            self.PlayCtrlPort = C_LONG(-1)
    
    def _stop_rtsp_capture(self):
        """停止RTSP视频捕获"""
        # 🔥 本地视频文件使用 PlayCtrl SDK
        if self.is_video_file:
            self._stop_video_file_capture()
            return
        
        # RTSP流使用 OpenCV
        self.stop_thread = True
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2)
    
    def _stop_video_file_capture(self):
        """停止本地视频文件播放"""
        # 停止 PlayCtrl 播放
        if self.PlayCtrlPort.value > -1:
            with _HK_SDK_LOCK:
                self.playM4SDK.PlayM4_Stop(self.PlayCtrlPort)
                self.playM4SDK.PlayM4_CloseFile(self.PlayCtrlPort)
                self.playM4SDK.PlayM4_FreePort(self.PlayCtrlPort)
            self.PlayCtrlPort = C_LONG(-1)
    
    def release(self):
        """释放资源"""
        # 停止捕获
        self.stop_capture()
        
        if self.is_hikvision:
            self._release_hikvision()
        else:
            self._release_rtsp()
            
        self.is_opened = False
    

    def _release_hikvision(self):
        """释放海康威视资源（优化锁策略）"""
        # 登出设备（无需锁，每个通道独立登出）
        if self.iUserID > -1:
            self.hikSDK.NET_DVR_Logout(self.iUserID)
            self.iUserID = -1
        
        # 注意：不调用NET_DVR_Cleanup()，因为其他通道可能还在使用SDK
        # SDK清理应该在程序退出时统一进行
        
        # 清理当前帧和序列号
        with self.frame_lock:
            self.current_frame = None
            self.frame_sequence = 0
            self.last_read_sequence = -1
    
    def _release_rtsp(self):
        """释放RTSP资源"""
        # 🔥 本地视频文件使用 PlayCtrl SDK
        if self.is_video_file:
            # PlayCtrl 资源已在 _stop_video_file_capture 中释放
            # 清理当前帧和序列号
            with self.frame_lock:
                self.current_frame = None
                self.frame_sequence = 0
                self.last_read_sequence = -1
            return
        
        # RTSP流使用 OpenCV
        if self.cv_cap:
            self.cv_cap.release()
            self.cv_cap = None
    
    def __enter__(self):
        """支持with语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持with语句"""
        self.release()
        # 使用示例
if __name__ == "__main__":
    import cv2
    
    # # 示例1: 海康威视摄像头
    # hik_cap = HKcapture(
    #     source="192.168.0.127",
    #     username="admin", 
    #     password="cei345678",
    #     port=8000,
    #     channel=1
    # )
    
    # 示例2: 其他RTSP摄像头
    rtsp_cap = HKcapture(
        source="rtsp://admin:cei345678@192.168.0.127/stream1"
    )
    
    # 选择使用哪个摄像头
    cap = rtsp_cap  # 或者 cap = rtsp_cap
    
    try:
        # 打开摄像头
        if cap.open():
            # 开始捕获
            if cap.start_capture():
                # 等待一段时间让数据开始流入
                time.sleep(2)
                
                while True:
                    # 读取帧
                    ret, frame = cap.read()
                    
                    if ret and frame is not None:
                        # 显示图像
                        cv2.imshow('Unified Channel', frame)
                        
                        # 按'q'退出
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    else:
                        time.sleep(0.1)
                        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
    finally:
        # 释放资源
        cap.release()
        cv2.destroyAllWindows()