# -*- coding: utf-8 -*-

"""
标注界面业务逻辑处理器

处理标注界面相关的业务逻辑，包括：
- 创建和管理标注引擎
- 处理标注数据的保存和加载
- 物理变焦控制器初始化
"""

from qtpy import QtWidgets, QtCore


class AnnotationHandler:
    """
    标注界面处理器 (Mixin类)
    
    处理标注界面相关的业务逻辑
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.annotation_engine = None
    
    def showAnnotationWidget(self, parent=None):
        """显示标注界面组件"""
        from widgets.videopage.annotation import AnnotationWidget
        
        # 创建标注界面组件
        widget = AnnotationWidget(parent, self.annotation_engine)
        
        # 连接信号
        self.connectAnnotationWidget(widget)
        
        return widget
    
    def connectAnnotationWidget(self, widget):
        """
        连接标注界面组件信号
        
        Args:
            widget: AnnotationWidget实例
        """
        widget.annotationEngineRequested.connect(self._handleAnnotationEngineRequest)
        widget.frameLoadRequested.connect(self._handleFrameLoadRequest)
        widget.annotationDataRequested.connect(
            lambda: self._handleAnnotationDataRequest(widget)
        )
    
    def _handleAnnotationEngineRequest(self):
        """处理标注引擎请求"""
        pass
    
    def _handleFrameLoadRequest(self):
        """处理帧加载请求"""
        pass
    
    def _handleAnnotationDataRequest(self, widget):
        """处理标注数据请求"""
        try:
            if self.annotation_engine and widget:
                boxes = self.annotation_engine.boxes
                bottoms = self.annotation_engine.bottom_points
                tops = self.annotation_engine.top_points
                init_levels = getattr(self.annotation_engine, 'init_level_points', [])
                
                # 发送标注完成信号
                widget.showAnnotationCompleted(boxes, bottoms, tops, init_levels)
        except Exception as e:
            print(f"处理标注数据请求失败: {e}")
    
    def _createAnnotationEngine(self):
        """创建标注引擎"""
        try:
            class SimpleAnnotationEngine:
                def __init__(self):
                    self.step = 0
                    self.boxes = []
                    self.bottom_points = []
                    self.top_points = []
                    self.init_level_points = []  # 初始液位线点列表
                
                def add_box(self, cx, cy, size):
                    """添加检测区域，并自动计算顶部线条、底部线条、初始液位线（默认中间位置）"""
                    self.boxes.append((cx, cy, size))
                    half_size = size / 2
                    bottom_y = cy + half_size - (size * 0.1)
                    self.bottom_points.append((int(cx), int(bottom_y)))
                    top_y = cy - half_size + (size * 0.1)
                    self.top_points.append((int(cx), int(top_y)))
                    # 初始液位线默认在容器中间位置
                    init_level_y = (top_y + bottom_y) / 2
                    self.init_level_points.append((int(cx), int(init_level_y)))
                
                def reset_annotation(self):
                    """重置标注"""
                    self.step = 0
                    self.boxes = []
                    self.bottom_points = []
                    self.top_points = []
                    self.init_level_points = []
                
                def get_results(self):
                    """获取标注结果"""
                    return {
                        'boxes': self.boxes,
                        'bottom_points': self.bottom_points,
                        'top_points': self.top_points,
                        'init_level_points': self.init_level_points
                    }
            
            return SimpleAnnotationEngine()
        except Exception as e:
            print(f"创建标注引擎失败: {e}")
            return None
    
    def _initPhysicalZoomForAnnotation(self, annotation_widget):
        """
        为标注界面初始化物理变焦控制器
        
        Args:
            annotation_widget: AnnotationWidget实例
        """
        try:
            from handlers.videopage.physical_zoom_controller import PhysicalZoomController
            
            # 获取当前通道的设备配置
            if not hasattr(self, 'general_set_panel') or not self.general_set_panel:
                return
            
            channel_id = self.general_set_panel.channel_id
            if not channel_id:
                return
            
            # 从配置文件获取设备信息
            device_config = self._getDeviceConfigForChannel(channel_id)
            if not device_config:
                return
            
            # 创建物理变焦控制器
            controller = PhysicalZoomController(
                device_ip=device_config.get('ip', ''),
                device_port=device_config.get('port', 8000),
                username=device_config.get('username', 'admin'),
                password=device_config.get('password', ''),
                channel=device_config.get('channel', 1)
            )
            
            # 连接设备
            if controller.connect_device():
                annotation_widget.setPhysicalZoomController(controller)
            
        except Exception as e:
            print(f"初始化物理变焦控制器失败: {e}")
    
    def _getDeviceConfigForChannel(self, channel_id):
        """
        获取通道的设备配置
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 设备配置，如果没有返回None
        """
        try:
            import os
            import yaml
            import re
            from urllib.parse import urlparse
            
            # 获取项目根目录
            try:
                from database.config import get_project_root
                project_root = get_project_root()
            except ImportError:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            channel_config = config.get(channel_id, {})
            rtsp_address = channel_config.get('address', '')
            
            if not rtsp_address:
                return None
            
            # 解析RTSP地址
            parsed = urlparse(rtsp_address)
            if not parsed.hostname:
                return None
            
            return {
                'ip': parsed.hostname,
                'port': 8000,
                'username': parsed.username or 'admin',
                'password': parsed.password or '',
                'channel': 1
            }
            
        except Exception as e:
            print(f"获取设备配置失败: {e}")
            return None
