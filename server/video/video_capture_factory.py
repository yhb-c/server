# -*- coding: utf-8 -*-
"""
视频捕获工厂类
根据系统类型和配置选择合适的视频捕获器
支持海康SDK和OpenCV两种捕获方式
"""

import os
import sys
import logging
import platform
import cv2
from pathlib import Path

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

# 添加lib路径以导入HKcapture
lib_dir = os.path.join(server_dir, 'lib')
sys.path.insert(0, lib_dir)

# 导入lib文件夹中的HKcapture
try:
    # 设置环境变量，确保动态库能被找到
    sdk_lib_path = os.path.join(server_dir, 'lib', 'lib')
    if os.path.exists(sdk_lib_path):
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if sdk_lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
    
    # 导入HKcapture
    sys.path.insert(0, lib_dir)
    from HKcapture import HKcapture
    HK_CAPTURE_AVAILABLE = True
    print(f"[VideoCaptureFactory] HKcapture导入成功，LD_LIBRARY_PATH已设置: {sdk_lib_path}")
except ImportError as e:
    print(f"[VideoCaptureFactory] 导入HKcapture失败: {e}")
    HKcapture = None
    HK_CAPTURE_AVAILABLE = False


class VideoCaptureFactory:
    """视频捕获工厂类"""
    
    def __init__(self):
        """初始化工厂"""
        self.logger = logging.getLogger(__name__)
        self.system = platform.system().lower()
        
        # 设置海康SDK环境变量（Linux系统）
        if self.system == 'linux':
            self._setup_hikvision_env()
    
    def _setup_hikvision_env(self):
        """设置海康SDK环境变量"""
        try:
            # 海康SDK库路径 - 修正为正确的动态库路径
            sdk_lib_path = os.path.join(server_dir, 'lib', 'lib')
            
            if os.path.exists(sdk_lib_path):
                current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
                if sdk_lib_path not in current_ld_path:
                    os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
                    self.logger.info(f"设置LD_LIBRARY_PATH: {sdk_lib_path}")
            else:
                self.logger.warning(f"海康SDK库路径不存在: {sdk_lib_path}")
                
        except Exception as e:
            self.logger.error(f"设置海康SDK环境变量失败: {e}")
    
    def create_capture(self, video_source: str, channel_id: str, prefer_hikvision: bool = True):
        """
        创建视频捕获器

        Args:
            video_source: 视频源（RTSP流地址或本地视频文件路径）
            channel_id: 通道ID
            prefer_hikvision: 是否优先使用海康SDK（仅对RTSP流有效）

        Returns:
            视频捕获器实例
        """
        self.logger.info(f"[{channel_id}] 创建视频捕获器")
        self.logger.info(f"[{channel_id}] 系统类型: {self.system}")
        self.logger.info(f"[{channel_id}] 视频源: {video_source}")

        # 判断是本地文件还是RTSP流
        is_local_file = self._is_local_file(video_source)

        if is_local_file:
            # 本地视频文件，使用OpenCV
            self.logger.info(f"[{channel_id}] 检测到本地视频文件，使用OpenCV")
            return self._create_opencv_capture(video_source, channel_id)
        else:
            # RTSP流，必须使用海康SDK
            if not HK_CAPTURE_AVAILABLE:
                self.logger.error(f"[{channel_id}] 海康SDK不可用，无法连接RTSP摄像机")
                return None

            try:
                self.logger.info(f"[{channel_id}] 使用海康SDK连接RTSP摄像机...")

                # 从RTSP URL解析用户名和密码
                import re
                match = re.match(r'rtsp://([^:]+):([^@]+)@(.+)', video_source)
                if match:
                    username = match.group(1)
                    password = match.group(2)
                    ip_and_path = match.group(3)

                    # 提取IP地址
                    ip_match = re.match(r'([^:/]+)', ip_and_path)
                    if ip_match:
                        ip_address = ip_match.group(1)
                        self.logger.info(f"[{channel_id}] 解析RTSP URL - IP: {ip_address}, 用户名: {username}")
                    else:
                        self.logger.error(f"[{channel_id}] 无法从RTSP URL解析IP地址")
                        return None
                else:
                    self.logger.error(f"[{channel_id}] RTSP URL格式不正确，无法解析用户名和密码")
                    return None

                # 创建HKcapture实例
                hik_capture = HKcapture(
                    source=ip_address,
                    username=username,
                    password=password,
                    port=8000,
                    channel=1,
                    debug=True
                )

                # 启用YUV队列模式（供检测使用）
                hik_capture.enable_yuv_queue(enabled=True, interval=0.1)

                if hik_capture.open():
                    self.logger.info(f"[{channel_id}] 海康SDK连接成功")

                    if hik_capture.start_capture():
                        self.logger.info(f"[{channel_id}] 海康SDK捕获启动成功")

                        # 测试获取一帧
                        import time
                        start_time = time.time()
                        test_frame = None
                        while time.time() - start_time < 10:
                            test_frame = hik_capture.get_yuv_data_nowait()
                            if test_frame:
                                break
                            time.sleep(0.1)

                        if test_frame:
                            yuv_bytes, width, height, timestamp = test_frame
                            self.logger.info(f"[{channel_id}] 海康SDK帧获取测试成功: {width}x{height}")
                            return hik_capture
                        else:
                            self.logger.error(f"[{channel_id}] 海康SDK帧获取测试失败")
                            hik_capture.release()
                            return None
                    else:
                        self.logger.error(f"[{channel_id}] 海康SDK捕获启动失败")
                        hik_capture.release()
                        return None
                else:
                    self.logger.error(f"[{channel_id}] 海康SDK连接失败")
                    return None

            except Exception as e:
                self.logger.error(f"[{channel_id}] 海康SDK创建失败: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return None

    def _is_local_file(self, video_source: str) -> bool:
        """
        判断视频源是否为本地文件

        Args:
            video_source: 视频源路径

        Returns:
            bool: 是否为本地文件
        """
        # 检查是否为RTSP/RTMP/HTTP等流媒体协议
        stream_protocols = ['rtsp://', 'rtmp://', 'http://', 'https://', 'rtp://']
        for protocol in stream_protocols:
            if video_source.lower().startswith(protocol):
                return False

        # 检查文件是否存在
        return os.path.isfile(video_source)

    def _create_opencv_capture(self, video_source: str, channel_id: str):
        """
        创建OpenCV视频捕获器

        Args:
            video_source: 视频源（文件路径或流地址）
            channel_id: 通道ID

        Returns:
            OpenCV捕获器包装实例
        """
        try:
            import cv2

            self.logger.info(f"[{channel_id}] 创建OpenCV捕获器: {video_source}")

            # 创建OpenCV VideoCapture
            cap = cv2.VideoCapture(video_source)

            if not cap.isOpened():
                self.logger.error(f"[{channel_id}] OpenCV无法打开视频源: {video_source}")
                return None

            # 获取视频信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            self.logger.info(f"[{channel_id}] OpenCV捕获器创建成功: {width}x{height} @ {fps}fps")

            # 包装为统一接口
            return OpenCVCaptureWrapper(cap, channel_id, video_source)

        except Exception as e:
            self.logger.error(f"[{channel_id}] 创建OpenCV捕获器失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def get_frame_from_capture(self, capture, channel_id: str):
        """
        从捕获器获取帧数据
        
        Args:
            capture: 捕获器实例
            channel_id: 通道ID
            
        Returns:
            numpy.array: BGR格式的视频帧，失败返回None
        """
        try:
            if hasattr(capture, 'get_yuv_data_nowait'):
                # 海康SDK捕获器（使用lib/HKcapture.py）
                yuv_data = capture.get_yuv_data_nowait()
                if yuv_data:
                    # 将YUV数据转换为BGR格式
                    import numpy as np
                    import cv2
                    
                    yuv_bytes, width, height, timestamp = yuv_data
                    
                    # 将YUV数据转换为numpy数组
                    yuv_array = np.frombuffer(yuv_bytes, dtype=np.uint8)
                    yuv_image = yuv_array.reshape((height * 3 // 2, width))
                    
                    # YUV420转BGR
                    frame = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)
                    return frame
                else:
                    return None
            elif hasattr(capture, 'get_yuv_frame'):
                # 旧版海康SDK捕获器（兼容性）
                yuv_frame = capture.get_yuv_frame()
                if yuv_frame:
                    # 将YUV数据转换为BGR格式
                    import numpy as np
                    import cv2
                    
                    width = yuv_frame['width']
                    height = yuv_frame['height']
                    yuv_data = yuv_frame['data']
                    
                    # 将YUV数据转换为numpy数组
                    yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
                    yuv_image = yuv_array.reshape((height * 3 // 2, width))
                    
                    # YUV420转BGR
                    frame = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)
                    return frame
                else:
                    return None
            else:
                # OpenCV捕获器
                return capture.get_frame()
                
        except Exception as e:
            self.logger.error(f"[{channel_id}] 获取帧数据失败: {e}")
            return None
    
    def is_capture_alive(self, capture):
        """
        检查捕获器是否存活
        
        Args:
            capture: 捕获器实例
            
        Returns:
            bool: 是否存活
        """
        try:
            if hasattr(capture, 'is_opened_status'):
                # 海康SDK捕获器（使用lib/HKcapture.py）
                return capture.is_opened_status() and capture.is_reading
            elif hasattr(capture, 'is_alive'):
                # 其他捕获器
                return capture.is_alive()
            else:
                return False
        except:
            return False
    
    def stop_capture(self, capture, channel_id: str):
        """
        停止捕获器
        
        Args:
            capture: 捕获器实例
            channel_id: 通道ID
        """
        try:
            if hasattr(capture, 'release'):
                # 海康SDK捕获器（使用lib/HKcapture.py）
                capture.release()
            elif hasattr(capture, 'stop'):
                # 其他捕获器
                capture.stop()
            self.logger.info(f"[{channel_id}] 视频捕获器已停止")
        except Exception as e:
            self.logger.error(f"[{channel_id}] 停止视频捕获器失败: {e}")


class OpenCVCaptureWrapper:
    """OpenCV视频捕获器包装类，提供统一接口"""

    def __init__(self, cv_capture, channel_id: str, video_source: str):
        """
        初始化OpenCV捕获器包装

        Args:
            cv_capture: cv2.VideoCapture实例
            channel_id: 通道ID
            video_source: 视频源路径
        """
        self.cv_capture = cv_capture
        self.cap = cv_capture  # 添加cap属性，供frame_id_manager使用
        self.channel_id = channel_id
        self.video_source = video_source
        self.logger = logging.getLogger(__name__)
        self.is_reading = True
        self._is_local_file = os.path.isfile(video_source)
        self.is_video_file = self._is_local_file  # 公开属性，供frame_id_manager判断
        self._video_ended = False  # 视频播放完毕标志

        # 从配置文件读取循环播放开关
        self._loop_enabled = self._load_loop_config()

    def _load_loop_config(self):
        """从配置文件读取循环播放开关"""
        try:
            import yaml
            config_path = os.path.join(server_dir, 'config', 'system_config.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    loop_enabled = config.get('detection', {}).get('local_video_loop', True)
                    self.logger.info(f"[{self.channel_id}] 本地视频循环播放开关: {loop_enabled}")
                    return loop_enabled
        except Exception as e:
            self.logger.warning(f"[{self.channel_id}] 读取循环播放配置失败: {e}，使用默认值True")
        return True

    def read(self):
        """
        读取一帧（兼容OpenCV接口）

        Returns:
            tuple: (ret, frame)
        """
        try:
            ret, frame = self.cv_capture.read()

            # 如果是本地文件且读取到末尾，设置标志
            if not ret and self._is_local_file and not self._video_ended:
                self._video_ended = True
                self.is_reading = False

            return ret, frame

        except Exception as e:
            self.logger.error(f"[{self.channel_id}] 读取帧失败: {e}")
            return False, None

    def get_frame(self):
        """
        获取一帧（统一接口）

        Returns:
            numpy.array: BGR格式的视频帧，失败返回None
        """
        ret, frame = self.read()
        return frame if ret else None

    def is_opened_status(self):
        """
        检查捕获器是否打开

        Returns:
            bool: 是否打开
        """
        return self.cv_capture.isOpened()

    def release(self):
        """释放捕获器资源"""
        try:
            self.is_reading = False
            if self.cv_capture:
                self.cv_capture.release()
            self.logger.info(f"[{self.channel_id}] OpenCV捕获器已释放")
        except Exception as e:
            self.logger.error(f"[{self.channel_id}] 释放OpenCV捕获器失败: {e}")

    def __del__(self):
        """析构函数"""
        self.release()