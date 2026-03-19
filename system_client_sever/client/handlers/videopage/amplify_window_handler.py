# -*- coding: utf-8 -*-

"""
AmplifyWindow业务逻辑处理器

负责处理全屏放大窗口的所有业务逻辑，包括物理变焦控制、画质增强、状态管理等
只支持物理变焦，需要海康威视PTZ设备支持
"""

import cv2
import numpy as np
import os
import yaml
import re
from urllib.parse import urlparse
from qtpy.QtCore import Qt, QTimer
try:
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QKeySequence
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeySequence

# 导入物理变焦控制器
try:
    from utils.physical_zoom_controller import PhysicalZoomController
except ImportError:
    # 如果都失败，创建一个空的类作为占位符
    print("警告: 无法导入PhysicalZoomController")
    class PhysicalZoomController:
        def __init__(self, *args, **kwargs):
            self.zoom_factor = 1.0
        def connect_device(self): return False
        def get_zoom_capabilities(self): return None
        def get_status(self): return "不可用"
        def disconnect_device(self): pass
        def zoom_to_factor(self, factor): pass
        def auto_focus(self): pass


class AmplifyWindowHandler:
    """全屏放大窗口业务逻辑处理器"""
    
    # 来源常量
    SOURCE_AMPLIFY = 'amplifysource'        # 点击放大显示按钮进入
    SOURCE_ANNOTATION = 'annotationsource'  # 点击开始标注按钮进入
    
    def __init__(self, amplify_window, device_config=None, source=None):
        """
        初始化处理器
        
        Args:
            amplify_window: AmplifyWindow实例
            device_config: 设备配置字典，包含IP、端口、用户名、密码等
            source: 来源标记，可选值：
                    - 'amplifysource': 点击放大显示按钮进入
                    - 'annotationsource': 点击开始标注按钮进入
        """
        self.amplify_window = amplify_window
        self.channel_id = amplify_window._channel_id
        
        # 来源标记（用于区分不同入口，显示不同控件）
        self.source = source or self.SOURCE_AMPLIFY
        
        # 物理变焦控制器
        self.physical_zoom_controller = None
        self.physical_zoom_enabled = False
        self.device_config = device_config or {}
        
        # 变焦参数
        self.zoom_factor = 1.0  # 当前变焦倍数
        self.min_zoom = 1.0
        self.max_zoom = 30.0  # 支持更大倍数变焦
        self.zoom_step = 0.1
        self.zoom_center_x = 0  # 变焦中心X坐标（将根据图片尺寸自适应设置）
        self.zoom_center_y = 0  # 变焦中心Y坐标（将根据图片尺寸自适应设置）
        self._zoom_center_initialized = False  # 标记放大中心是否已初始化
        
        # 当前帧缓存
        self._current_frame = None
        self._frame_width = 0   # 帧宽度
        self._frame_height = 0  # 帧高度
        
        # 连接信号
        self._connectSignals()
        
        # 初始化物理变焦控制器
        self._initPhysicalZoomController()
        
    
    def _loadDeviceConfigFromFile(self):
        """从配置文件的RTSP地址解析设备配置"""
        try:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 根据通道ID获取配置
            channel_config = config.get(self.channel_id, {})
            rtsp_address = channel_config.get('address', '')
            
            if not rtsp_address:
                return None
            
            # 解析RTSP地址获取设备信息
            device_config = self._parseRtspAddress(rtsp_address)
            if device_config:
                return device_config
            else:
                return None
            
        except Exception as e:
            return None
    
    def _parseRtspAddress(self, rtsp_url):
        """
        解析RTSP地址获取设备配置信息
        
        Args:
            rtsp_url: RTSP地址，如 rtsp://admin:cei345678@192.168.0.127:8000/stream1
        
        Returns:
            dict: 设备配置信息，如果解析失败返回None
        """
        try:
            # 解析URL
            parsed = urlparse(rtsp_url)
            
            if not parsed.hostname:
                return None
            
            # 提取设备信息
            device_config = {
                'ip': parsed.hostname,
                'port': 8000,  # PTZ控制端口，通常是8000
                'username': parsed.username or 'admin',
                'password': parsed.password or '',
                'channel': 1  # 默认通道1
            }
            
            # 如果密码为空，跳过物理变焦（避免无密码设备的连接问题）
            if not device_config['password']:
                return None
            
            return device_config
            
        except Exception as e:
            return None
    
    def _connectSignals(self):
        """连接AmplifyWindow的信号"""
        self.amplify_window.mouseClicked.connect(self.onMouseClicked)
        self.amplify_window.wheelScrolled.connect(self.onWheelScrolled)
        self.amplify_window.keyPressed.connect(self.onKeyPressed)
    
    def _initPhysicalZoomController(self):
        """初始化物理变焦控制器"""
        try:
            # 优先从配置文件读取设备配置
            config_from_file = self._loadDeviceConfigFromFile()
            if config_from_file:
                self.device_config = config_from_file
            
            # 检查是否有设备配置
            if not self.device_config:
                return
            
            # 获取设备连接参数
            device_ip = self.device_config.get('ip', '')
            device_port = self.device_config.get('port', 8000)
            username = self.device_config.get('username', 'admin')
            password = self.device_config.get('password', '')
            channel = self.device_config.get('channel', 1)
            
            if not device_ip:
                return
            
            # 创建物理变焦控制器
            self.physical_zoom_controller = PhysicalZoomController(
                device_ip=device_ip,
                device_port=device_port,
                username=username,
                password=password,
                channel=channel
            )
            
            # 连接物理变焦控制器信号（如果有的话）
            if hasattr(self.physical_zoom_controller, 'zoomChanged'):
                self.physical_zoom_controller.zoomChanged.connect(self._onPhysicalZoomChanged)
            if hasattr(self.physical_zoom_controller, 'statusChanged'):
                self.physical_zoom_controller.statusChanged.connect(self._onPhysicalZoomStatusChanged)
            if hasattr(self.physical_zoom_controller, 'errorOccurred'):
                self.physical_zoom_controller.errorOccurred.connect(self._onPhysicalZoomError)
            
            # 尝试连接设备
            if self.physical_zoom_controller.connect_device():
                self.physical_zoom_enabled = True
                
                # 获取变焦能力
                capabilities = self.physical_zoom_controller.get_zoom_capabilities()
                if capabilities:
                    self.min_zoom = capabilities.get('min_zoom', 1.0)
                    self.max_zoom = capabilities.get('max_zoom', 30.0)
                
                pass
            else:
                self.physical_zoom_controller = None
                
        except Exception as e:
            self.physical_zoom_controller = None
    
    def _onPhysicalZoomChanged(self, zoom_factor):
        """物理变焦倍数变化回调"""
        self.zoom_factor = zoom_factor
        
        # 更新UI状态显示
        if hasattr(self.amplify_window, 'updateStatusHint'):
            self.amplify_window.updateStatusHint(
                zoom_factor=self.zoom_factor
            )
    
    def _onPhysicalZoomStatusChanged(self, status):
        """物理变焦状态变化回调"""
        pass
    
    def _onPhysicalZoomError(self, error):
        """物理变焦错误回调"""
        pass
        
        # 发生错误时禁用物理变焦
        self.physical_zoom_enabled = False
    
    def processFrame(self, frame):
        """
        处理视频帧（物理变焦模式下直接返回原始帧）
        
        Args:
            frame: 原始视频帧
            
        Returns:
            处理后的视频帧
        """
        if frame is None:
            return None
        
        try:
            # 缓存当前帧
            self._current_frame = frame.copy()
            
            # 获取帧尺寸并自适应设置放大中心
            height, width = frame.shape[:2]
            self._updateZoomCenter(width, height)
            
            # 物理变焦模式下，变焦由硬件完成，直接返回帧
            return frame
            
        except Exception as e:
            return frame
    
    def _updateZoomCenter(self, width, height):
        """
        根据图片尺寸和ROI自适应更新放大中心
        
        优先使用ROI的中心作为变焦中心，如果没有ROI则使用图片中心
        
        Args:
            width: 图片宽度
            height: 图片高度
        """
        # 检查尺寸是否变化
        if width != self._frame_width or height != self._frame_height:
            self._frame_width = width
            self._frame_height = height
            
            # 尝试从ROI配置计算变焦中心
            detection_center = self._calculateDetectionAreaCenter()
            
            if detection_center:
                # 使用ROI中心作为变焦中心
                self.zoom_center_x, self.zoom_center_y = detection_center
            else:
                # 没有ROI配置，使用图片中心
                self.zoom_center_x = width // 2
                self.zoom_center_y = height // 2
            
            self._zoom_center_initialized = True
    
    def _calculateDetectionAreaCenter(self):
        """
        从配置文件读取ROI并计算中心点
        
        Returns:
            tuple: (center_x, center_y) ROI中心坐标，如果没有配置返回None
        """
        try:
            # 获取配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            annotation_config_path = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if not os.path.exists(annotation_config_path):
                return None
            
            with open(annotation_config_path, 'r', encoding='utf-8') as f:
                annotation_config = yaml.safe_load(f)
            
            if not annotation_config:
                return None
            
            # 获取当前通道的ROI配置
            channel_config = annotation_config.get(self.channel_id, {})
            
            if not channel_config:
                return None
            
            # 获取检测框列表 boxes: [[cx, cy, size], ...]
            boxes = channel_config.get('boxes', [])
            fixed_tops = channel_config.get('fixed_tops', [])
            fixed_bottoms = channel_config.get('fixed_bottoms', [])
            
            if not boxes:
                return None
            
            # 计算所有ROI的综合中心
            all_x = []
            all_y = []
            
            for i, box in enumerate(boxes):
                if len(box) >= 2:
                    cx, cy = box[0], box[1]
                    all_x.append(cx)
                    
                    # 如果有fixed_tops和fixed_bottoms，使用它们计算更准确的垂直中心
                    if i < len(fixed_tops) and i < len(fixed_bottoms):
                        top = fixed_tops[i]
                        bottom = fixed_bottoms[i]
                        vertical_center = (top + bottom) // 2
                        all_y.append(vertical_center)
                    else:
                        all_y.append(cy)
            
            if not all_x or not all_y:
                return None
            
            # 计算所有区域的中心点
            center_x = sum(all_x) // len(all_x)
            center_y = sum(all_y) // len(all_y)
            
            # 确保中心点在图片范围内
            if self._frame_width > 0 and self._frame_height > 0:
                center_x = max(0, min(center_x, self._frame_width))
                center_y = max(0, min(center_y, self._frame_height))
            
            return (center_x, center_y)
            
        except Exception as e:
            return None
    
    def setZoomCenter(self, x, y):
        """
        手动设置放大中心点
        
        Args:
            x: 中心点X坐标
            y: 中心点Y坐标
        """
        # 确保坐标在有效范围内
        if self._frame_width > 0 and self._frame_height > 0:
            self.zoom_center_x = max(0, min(x, self._frame_width))
            self.zoom_center_y = max(0, min(y, self._frame_height))
        else:
            self.zoom_center_x = x
            self.zoom_center_y = y
        self._zoom_center_initialized = True
    
    def getZoomCenter(self):
        """
        获取当前放大中心点
        
        Returns:
            tuple: (x, y) 放大中心坐标
        """
        return (self.zoom_center_x, self.zoom_center_y)
    
    def onMouseClicked(self, click_x, click_y):
        """处理鼠标点击事件 - 物理变焦中心点设置"""
        try:
            if not self.physical_zoom_controller or not self.physical_zoom_enabled:
                return
            
            # 获取当前显示区域大小和实际视频尺寸
            # 尝试从不同的窗口引用获取videoLabel
            video_label = None
            if hasattr(self, 'amplify_window') and hasattr(self.amplify_window, 'videoLabel'):
                video_label = self.amplify_window.videoLabel
            elif hasattr(self, 'window') and hasattr(self.window, 'videoLabel'):
                video_label = self.window.videoLabel
            
            if video_label:
                # 获取显示控件的尺寸
                label_size = video_label.size()
                display_width = label_size.width()
                display_height = label_size.height()
                
                # 获取实际视频尺寸（如果可用）
                video_width = display_width
                video_height = display_height
                
                # 尝试从视频流获取真实尺寸
                if hasattr(self, 'video_thread') and hasattr(self.video_thread, 'frame_width'):
                    video_width = self.video_thread.frame_width or display_width
                    video_height = self.video_thread.frame_height or display_height
                
                # 计算视频在显示区域中的实际位置和尺寸（考虑缩放和居中）
                scale_x = display_width / video_width if video_width > 0 else 1
                scale_y = display_height / video_height if video_height > 0 else 1
                scale = min(scale_x, scale_y)  # 保持宽高比
                
                # 实际视频显示尺寸
                actual_video_width = video_width * scale
                actual_video_height = video_height * scale
                
                # 视频在显示区域中的偏移（居中显示）
                video_offset_x = (display_width - actual_video_width) / 2
                video_offset_y = (display_height - actual_video_height) / 2
                
                # 转换点击坐标到视频坐标系
                video_x = click_x - video_offset_x
                video_y = click_y - video_offset_y
                
                # 检查点击是否在视频区域内
                if video_x < 0 or video_x > actual_video_width or video_y < 0 or video_y > actual_video_height:
                    return
                
                # 计算相对于视频中心的偏移（归一化到-1到1）
                video_center_x = actual_video_width / 2
                video_center_y = actual_video_height / 2
                offset_x = (video_x - video_center_x) / video_center_x
                offset_y = (video_y - video_center_y) / video_center_y
                
                # 执行PTZ平移到目标点
                if self._move_to_point(offset_x, offset_y):
                    # 更新焦点坐标
                    self.zoom_center_x = int(click_x)
                    self.zoom_center_y = int(click_y)
                    # 更新UI状态显示
                    if hasattr(self.amplify_window, 'updateStatusHint'):
                        self.amplify_window.updateStatusHint(
                            zoom_factor=self.zoom_factor,
                            center_x=self.zoom_center_x,
                            center_y=self.zoom_center_y
                        )
                else:
                    pass
            else:
                pass
            
        except Exception as e:
            pass
    
    def _updateUI(self):
        """更新UI状态"""
        try:
            # 这里可以添加UI状态更新逻辑
            # 例如更新变焦倍数显示等
            pass
        except Exception as e:
            pass
    
    def _move_to_point(self, offset_x, offset_y):
        """
        PTZ平移到指定点
        
        Args:
            offset_x: X轴偏移 (-1到1)
            offset_y: Y轴偏移 (-1到1)
        
        Returns:
            bool: 是否成功
        """
        try:
            # 限制偏移范围
            offset_x = max(-1.0, min(1.0, offset_x))
            offset_y = max(-1.0, min(1.0, offset_y))
            
            # 如果偏移很小，不需要移动
            if abs(offset_x) < 0.1 and abs(offset_y) < 0.1:
                return True
            
            # 计算平移速度（根据偏移距离）
            speed_x = int(abs(offset_x) * 7)  # 速度1-7
            speed_y = int(abs(offset_y) * 7)
            speed_x = max(1, min(7, speed_x))
            speed_y = max(1, min(7, speed_y))
            
            # 计算平移时间（根据偏移距离）
            duration_x = abs(offset_x) * 0.5  # 最多0.5秒
            duration_y = abs(offset_y) * 0.5
            
            # 执行水平平移
            if abs(offset_x) > 0.1:
                if offset_x > 0:
                    # 向右平移
                    if hasattr(self.physical_zoom_controller, 'pan_right'):
                        self.physical_zoom_controller.pan_right(speed_x)
                        import time
                        time.sleep(duration_x)
                        self.physical_zoom_controller.stop_pan()
                else:
                    # 向左平移
                    if hasattr(self.physical_zoom_controller, 'pan_left'):
                        self.physical_zoom_controller.pan_left(speed_x)
                        import time
                        time.sleep(duration_x)
                        self.physical_zoom_controller.stop_pan()
            
            # 执行垂直平移
            if abs(offset_y) > 0.1:
                if offset_y > 0:
                    # 向下平移
                    if hasattr(self.physical_zoom_controller, 'tilt_down'):
                        self.physical_zoom_controller.tilt_down(speed_y)
                        import time
                        time.sleep(duration_y)
                        self.physical_zoom_controller.stop_tilt()
                else:
                    # 向上平移
                    if hasattr(self.physical_zoom_controller, 'tilt_up'):
                        self.physical_zoom_controller.tilt_up(speed_y)
                        import time
                        time.sleep(duration_y)
                        self.physical_zoom_controller.stop_tilt()
            
            return True
            
        except Exception as e:
            return False
    
    def onWheelScrolled(self, direction):
        """处理鼠标滚轮事件 - 物理变焦"""
        try:
            if not self.physical_zoom_controller or not self.physical_zoom_enabled:
                return
                
            if direction > 0:
                # 向上滚动 - 放大
                target_zoom = min(self.max_zoom, self.zoom_factor + self.zoom_step)
                if target_zoom != self.zoom_factor:
                    self.zoom_factor = target_zoom  # 更新变焦倍数
                    self.physical_zoom_controller.zoom_to_factor(target_zoom)
                    # 更新UI状态显示（包括变焦倍数和焦点坐标）
                    if hasattr(self.amplify_window, 'updateStatusHint'):
                        self.amplify_window.updateStatusHint(
                            zoom_factor=self.zoom_factor,
                            center_x=self.zoom_center_x,
                            center_y=self.zoom_center_y
                        )
            else:
                # 向下滚动 - 缩小
                target_zoom = max(self.min_zoom, self.zoom_factor - self.zoom_step)
                if target_zoom != self.zoom_factor:
                    self.zoom_factor = target_zoom  # 更新变焦倍数
                    self.physical_zoom_controller.zoom_to_factor(target_zoom)
                    # 更新UI状态显示（包括变焦倍数和焦点坐标）
                    if hasattr(self.amplify_window, 'updateStatusHint'):
                        self.amplify_window.updateStatusHint(
                            zoom_factor=self.zoom_factor,
                            center_x=self.zoom_center_x,
                            center_y=self.zoom_center_y
                        )
                    
        except Exception as e:
            pass
    
    def onKeyPressed(self, key):
        """处理键盘按键事件"""
        try:
            if key == Qt.Key_R:
                # R键：重置变焦
                if self.physical_zoom_controller and self.physical_zoom_enabled:
                    self.physical_zoom_controller.zoom_to_factor(1.0)
                
            elif key == Qt.Key_H:
                # H键：显示/隐藏交互说明
                self.amplify_window.toggleHelpVisibility()
            
            elif key == Qt.Key_D:
                # D键：显示物理变焦状态
                pass
                
            elif key == Qt.Key_F:
                # F键：自动聚焦
                if self.physical_zoom_controller and self.physical_zoom_enabled:
                    self.physical_zoom_controller.auto_focus()
            
            # 更新UI状态显示
            if hasattr(self.amplify_window, 'updateStatusHint'):
                self.amplify_window.updateStatusHint(
                    zoom_factor=self.zoom_factor
                )
                        
        except Exception as e:
            print(f" 键盘事件处理失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.physical_zoom_controller:
                self.physical_zoom_controller.disconnect_device()
                self.physical_zoom_controller = None
        except Exception:
            pass
    
    def get_zoom_status(self):
        """
        获取当前物理变焦状态
        
        Returns:
            dict: 变焦状态信息
        """
        status = {
            'zoom_factor': self.zoom_factor,
            'physical_zoom_available': self.physical_zoom_enabled,
            'min_zoom': self.min_zoom,
            'max_zoom': self.max_zoom,
            'zoom_step': self.zoom_step
        }
        
        if self.physical_zoom_controller:
            physical_status = self.physical_zoom_controller.get_status()
            status['physical_status'] = physical_status
        
        return status
    
    # ========== 来源判断辅助方法 ==========
    
    def isAmplifySource(self):
        """
        判断是否从放大显示按钮进入
        
        Returns:
            bool: 是则返回True
        """
        return self.source == self.SOURCE_AMPLIFY
    
    def isAnnotationSource(self):
        """
        判断是否从开始标注按钮进入
        
        Returns:
            bool: 是则返回True
        """
        return self.source == self.SOURCE_ANNOTATION
    
    def getSource(self):
        """
        获取当前来源标记
        
        Returns:
            str: 来源标记 ('amplifysource' 或 'annotationsource')
        """
        return self.source
    
    def setSource(self, source):
        """
        设置来源标记
        
        Args:
            source: 来源标记
        """
        self.source = source
