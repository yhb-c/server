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
    
    def create_capture(self, rtsp_url: str, channel_id: str, prefer_hikvision: bool = True):
        """
        创建视频捕获器
        
        Args:
            rtsp_url: RTSP流地址
            channel_id: 通道ID
            prefer_hikvision: 是否优先使用海康SDK（Linux系统）
            
        Returns:
            视频捕获器实例
        """
        self.logger.info(f"[{channel_id}] 创建视频捕获器")
        self.logger.info(f"[{channel_id}] 系统类型: {self.system}")
        self.logger.info(f"[{channel_id}] RTSP地址: {rtsp_url}")
        
        if self.system == 'linux' and prefer_hikvision and HK_CAPTURE_AVAILABLE:
            # Linux系统优先尝试海康SDK
            try:
                self.logger.info(f"[{channel_id}] 尝试使用海康SDK...")
                
                # 创建HKcapture实例
                hik_capture = HKcapture(
                    source=rtsp_url,
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
                        while time.time() - start_time < 10:  # 等待最多10秒
                            test_frame = hik_capture.get_yuv_data_nowait()
                            if test_frame:
                                break
                            time.sleep(0.1)
                        
                        if test_frame:
                            yuv_bytes, width, height, timestamp = test_frame
                            self.logger.info(f"[{channel_id}] 海康SDK帧获取测试成功: {width}x{height}")
                            return hik_capture
                        else:
                            self.logger.warning(f"[{channel_id}] 海康SDK帧获取测试失败，回退到OpenCV")
                            hik_capture.release()
                    else:
                        self.logger.warning(f"[{channel_id}] 海康SDK捕获启动失败，回退到OpenCV")
                        hik_capture.release()
                else:
                    self.logger.warning(f"[{channel_id}] 海康SDK连接失败，回退到OpenCV")
                    
            except Exception as e:
                self.logger.error(f"[{channel_id}] 海康SDK创建失败: {e}")

        # 海康SDK失败
        self.logger.error(f"[{channel_id}] 视频捕获失败")
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