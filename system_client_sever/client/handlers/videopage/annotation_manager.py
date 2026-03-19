# -*- coding: utf-8 -*-

"""
标注管理器模块

职责：
- 获取通道最新帧作为标注帧
- 管理用户ROI选取界面
- 将标注配置推送到服务器
- 处理标注结果的保存和同步
"""

import os
import json
import yaml
import cv2
import numpy as np
from qtpy import QtCore, QtWidgets, QtGui
from qtpy.QtCore import Qt

# 导入远程配置管理器
try:
    from ...utils.config import RemoteConfigManager
except ImportError:
    try:
        from utils.config import RemoteConfigManager
    except ImportError:
        RemoteConfigManager = None

# 导入项目根目录函数
try:
    from ...database.config import get_project_root
except ImportError:
    try:
        from database.config import get_project_root
    except ImportError:
        def get_project_root():
            return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class AnnotationManager(QtCore.QObject):
    """
    标注管理器
    
    负责整个标注流程的管理：
    1. 获取通道最新帧
    2. 启动标注界面
    3. 处理标注结果
    4. 推送配置到服务器
    """
    
    # 信号定义（按照原系统方式）
    annotationCompleted = QtCore.Signal(str, dict)  # (channel_id, annotation_data)
    annotationFailed = QtCore.Signal(str, str)      # (channel_id, error_message)
    
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.remote_config_manager = RemoteConfigManager() if RemoteConfigManager else None
        
        # 当前标注状态
        self.current_channel_id = None
        self.current_frame = None
        self.annotation_widget = None
        
    def start_annotation(self, channel_id):
        """
        开始标注流程
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            
        Returns:
            bool: 是否成功启动标注
        """
        try:
            print(f"[标注管理器] 开始为通道 {channel_id} 启动标注流程")
            
            # 1. 获取最新帧
            frame = self._get_latest_frame(channel_id)
            if frame is None:
                error_msg = f"无法获取通道 {channel_id} 的画面帧"
                print(f"[标注管理器] 错误: {error_msg}")
                self.annotationFailed.emit(channel_id, error_msg)
                return False
            
            print(f"[标注管理器] 成功获取画面帧，尺寸: {frame.shape}")
            
            # 2. 保存当前状态
            self.current_channel_id = channel_id
            self.current_frame = frame.copy()
            
            # 3. 加载历史标注数据（如果有）
            history_data = self._load_history_annotation(channel_id)
            
            # 4. 启动标注界面
            success = self._show_annotation_widget(frame, history_data)
            
            if success:
                print(f"[标注管理器] 标注界面已启动")
                return True
            else:
                error_msg = "标注界面启动失败"
                print(f"[标注管理器] 错误: {error_msg}")
                self.annotationFailed.emit(channel_id, error_msg)
                return False
                
        except Exception as e:
            error_msg = f"标注流程启动异常: {str(e)}"
            print(f"[标注管理器] 异常: {error_msg}")
            import traceback
            traceback.print_exc()
            self.annotationFailed.emit(channel_id, error_msg)
            return False
    
    def _get_latest_frame(self, channel_id):
        """
        获取指定通道的最新帧
        
        Args:
            channel_id: 通道ID
            
        Returns:
            numpy.ndarray: 图像帧，获取失败返回None
        """
        try:
            print(f"[标注管理器] 开始获取通道 {channel_id} 的最新帧")
            
            if not self.main_window:
                print(f"[标注管理器] main_window 未设置")
                return None
            
            # 方法1: 通过thread_manager获取
            if hasattr(self.main_window, 'thread_manager') and self.main_window.thread_manager:
                print(f"[标注管理器] 尝试通过thread_manager获取帧")
                context = self.main_window.thread_manager.get_channel_context(channel_id)
                if context and hasattr(context, 'frame_lock') and hasattr(context, 'latest_frame'):
                    with context.frame_lock:
                        if context.latest_frame is not None:
                            print(f"[标注管理器] 通过thread_manager成功获取帧")
                            return context.latest_frame.copy()
                        else:
                            print(f"[标注管理器] thread_manager中latest_frame为None")
                else:
                    print(f"[标注管理器] thread_manager中未找到有效上下文")
            
            # 方法2: 通过getLatestFrame方法获取
            if hasattr(self.main_window, 'getLatestFrame'):
                print(f"[标注管理器] 尝试通过getLatestFrame方法获取帧")
                frame = self.main_window.getLatestFrame(channel_id)
                if frame is not None:
                    print(f"[标注管理器] 通过getLatestFrame成功获取帧")
                    return frame
                else:
                    print(f"[标注管理器] getLatestFrame返回None")
            
            # 方法3: 直接从捕获对象获取
            if hasattr(self.main_window, '_channel_captures'):
                print(f"[标注管理器] 尝试直接从捕获对象获取帧")
                capture = self.main_window._channel_captures.get(channel_id)
                if capture:
                    print(f"[标注管理器] 找到捕获对象: {type(capture).__name__}")
                    
                    # 尝试不同的获取方法
                    if hasattr(capture, 'get_frame'):
                        frame = capture.get_frame()
                        if frame is not None:
                            print(f"[标注管理器] 通过get_frame成功获取帧")
                            return frame
                    
                    if hasattr(capture, 'read'):
                        ret, frame = capture.read()
                        if ret and frame is not None:
                            print(f"[标注管理器] 通过read成功获取帧")
                            return frame
                    
                    if hasattr(capture, 'read_latest'):
                        ret, frame = capture.read_latest()
                        if ret and frame is not None:
                            print(f"[标注管理器] 通过read_latest成功获取帧")
                            return frame
                    
                    print(f"[标注管理器] 捕获对象的所有获取方法都失败")
                else:
                    print(f"[标注管理器] 未找到通道 {channel_id} 的捕获对象")
            
            # 方法4: 从frame_buffers获取（已禁用 - 不再使用帧存储）
            # if hasattr(self.main_window, '_frame_buffers'):
            #     print(f"[标注管理器] 尝试从frame_buffers获取帧")
            #     buffer = self.main_window._frame_buffers.get(channel_id)
            #     if buffer and not buffer.empty():
            #         # 获取最新帧（丢弃中间的旧帧）
            #         frame = None
            #         frame_count = 0
            #         while not buffer.empty():
            #             try:
            #                 frame = buffer.get_nowait()
            #                 frame_count += 1
            #             except:
            #                 break
            #         
            #         if frame is not None:
            #             print(f"[标注管理器] 从frame_buffers成功获取帧（丢弃了{frame_count-1}个旧帧）")
            #             return frame
            #         else:
            #             print(f"[标注管理器] frame_buffers中没有有效帧")
            #     else:
            #         print(f"[标注管理器] frame_buffers为空或不存在")
            
            print(f"[标注管理器] 所有获取帧的方法都失败")
            return None
            
        except Exception as e:
            print(f"[标注管理器] 获取帧异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _load_history_annotation(self, channel_id):
        """
        加载历史标注数据
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 历史标注数据，没有则返回None
        """
        try:
            print(f"[标注管理器] 加载通道 {channel_id} 的历史标注数据")
            
            # 从本地配置文件加载
            project_root = get_project_root()
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if os.path.exists(annotation_file):
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    annotation_data = yaml.safe_load(f)
                
                if annotation_data and channel_id in annotation_data:
                    history_data = annotation_data[channel_id]
                    print(f"[标注管理器] 找到历史标注数据: {list(history_data.keys())}")
                    return history_data
            
            print(f"[标注管理器] 未找到历史标注数据")
            return None
            
        except Exception as e:
            print(f"[标注管理器] 加载历史标注数据异常: {e}")
            return None
    
    def _show_annotation_widget(self, frame, history_data=None):
        """
        显示标注界面
        
        Args:
            frame: 要标注的图像帧
            history_data: 历史标注数据（可选）
            
        Returns:
            bool: 是否成功显示
        """
        try:
            print(f"[标注管理器] 显示标注界面")
            print(f"[标注管理器] 输入参数检查:")
            print(f"  - frame类型: {type(frame)}")
            print(f"  - frame形状: {frame.shape if frame is not None else 'None'}")
            print(f"  - history_data存在: {history_data is not None}")
            
            # 导入标注界面组件
            print(f"[标注管理器] 尝试导入AnnotationWidget...")
            annotation_widget_class = None
            
            try:
                from ...widgets.videopage.annotation import AnnotationWidget
                annotation_widget_class = AnnotationWidget
                print(f"[标注管理器] 成功导入AnnotationWidget (相对导入)")
            except ImportError as e1:
                print(f"[标注管理器] 相对导入失败: {e1}")
                try:
                    from widgets.videopage.annotation import AnnotationWidget
                    annotation_widget_class = AnnotationWidget
                    print(f"[标注管理器] 成功导入AnnotationWidget (绝对导入)")
                except ImportError as e2:
                    print(f"[标注管理器] 绝对导入失败: {e2}")
                    try:
                        from client.widgets.videopage.annotation import AnnotationWidget
                        annotation_widget_class = AnnotationWidget
                        print(f"[标注管理器] 成功导入AnnotationWidget (完整路径导入)")
                    except ImportError as e3:
                        print(f"[标注管理器] 完整路径导入失败: {e3}")
                        print(f"[标注管理器] 无法导入AnnotationWidget")
                        return False
            
            if not annotation_widget_class:
                print(f"[标注管理器] AnnotationWidget类未找到")
                return False
            
            # 创建标注界面
            print(f"[标注管理器] 创建AnnotationWidget实例...")
            try:
                # 首先创建标注引擎
                annotation_engine = self._create_annotation_engine()
                if not annotation_engine:
                    print(f"[标注管理器] 创建标注引擎失败")
                    return False
                
                # 创建标注界面并传入标注引擎
                self.annotation_widget = annotation_widget_class(parent=None, annotation_engine=annotation_engine)
                print(f"[标注管理器] AnnotationWidget实例创建成功")
                print(f"  - 实例类型: {type(self.annotation_widget)}")
                print(f"  - 标注引擎: {type(annotation_engine)}")
                print(f"  - 实例方法检查:")
                print(f"    - hasattr(setChannelName): {hasattr(self.annotation_widget, 'setChannelName')}")
                print(f"    - hasattr(loadFrame): {hasattr(self.annotation_widget, 'loadFrame')}")
                print(f"    - hasattr(show): {hasattr(self.annotation_widget, 'show')}")
                print(f"    - hasattr(annotationCompleted): {hasattr(self.annotation_widget, 'annotationCompleted')}")
                print(f"    - hasattr(annotationCancelled): {hasattr(self.annotation_widget, 'annotationCancelled')}")
            except Exception as e:
                print(f"[标注管理器] 创建AnnotationWidget实例失败: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # 设置通道信息
            print(f"[标注管理器] 设置通道信息...")
            if self.current_channel_id:
                channel_name = self._get_channel_name(self.current_channel_id)
                print(f"  - 通道ID: {self.current_channel_id}")
                print(f"  - 通道名称: {channel_name}")
                
                if hasattr(self.annotation_widget, 'setChannelName'):
                    try:
                        self.annotation_widget.setChannelName(channel_name)
                        print(f"  - 通道名称设置成功")
                    except Exception as e:
                        print(f"  - 通道名称设置失败: {e}")
                else:
                    print(f"  - AnnotationWidget没有setChannelName方法")
            else:
                print(f"  - 当前通道ID为空")
            
            # 连接信号（按照原系统方式）
            print(f"[标注管理器] 连接信号...")
            try:
                if hasattr(self.annotation_widget, 'annotationCompleted'):
                    # 按照原系统格式：annotationCompleted = QtCore.Signal(list, list, list, list)
                    # 参数：(boxes, bottoms, tops, init_levels)
                    self.annotation_widget.annotationCompleted.connect(self._on_annotation_completed)
                    print(f"  - annotationCompleted信号连接成功")
                else:
                    print(f"  - AnnotationWidget没有annotationCompleted信号")
                
                if hasattr(self.annotation_widget, 'annotationCancelled'):
                    # 按照原系统格式：annotationCancelled = QtCore.Signal()
                    self.annotation_widget.annotationCancelled.connect(self._on_annotation_cancelled)
                    print(f"  - annotationCancelled信号连接成功")
                else:
                    print(f"  - AnnotationWidget没有annotationCancelled信号")
                    
                # 检查信号对象类型
                if hasattr(self.annotation_widget, 'annotationCompleted'):
                    signal_obj = self.annotation_widget.annotationCompleted
                    print(f"  - annotationCompleted信号类型: {type(signal_obj)}")
                    
            except Exception as e:
                print(f"  - 信号连接失败: {e}")
                import traceback
                traceback.print_exc()
            
            # 加载图像
            print(f"[标注管理器] 加载图像到标注界面...")
            if hasattr(self.annotation_widget, 'loadFrame'):
                try:
                    load_result = self.annotation_widget.loadFrame(frame)
                    print(f"  - loadFrame返回结果: {load_result}")
                    if not load_result:
                        print(f"[标注管理器] 加载图像到标注界面失败")
                        return False
                    else:
                        print(f"  - 图像加载成功")
                except Exception as e:
                    print(f"  - loadFrame调用异常: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            else:
                print(f"  - AnnotationWidget没有loadFrame方法")
                return False
            
            # 应用历史标注数据
            if history_data:
                print(f"[标注管理器] 应用历史标注数据...")
                try:
                    self._apply_history_annotation(history_data)
                    print(f"  - 历史标注数据应用完成")
                except Exception as e:
                    print(f"  - 应用历史标注数据失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[标注管理器] 无历史标注数据")
            
            # 初始化物理变焦控制器（移植自原系统）
            try:
                self._init_physical_zoom_for_annotation()
                print(f"  - 物理变焦控制器初始化完成")
            except Exception as e:
                print(f"  - 物理变焦控制器初始化失败: {e}")
                # 物理变焦失败不影响标注功能
            
            # 显示界面
            print(f"[标注管理器] 显示标注界面...")
            try:
                if hasattr(self.annotation_widget, 'show'):
                    self.annotation_widget.show()
                    print(f"  - show()调用成功")
                    
                    # 检查窗口是否真的显示了
                    if hasattr(self.annotation_widget, 'isVisible'):
                        is_visible = self.annotation_widget.isVisible()
                        print(f"  - 窗口可见性: {is_visible}")
                    
                    if hasattr(self.annotation_widget, 'windowTitle'):
                        title = self.annotation_widget.windowTitle()
                        print(f"  - 窗口标题: {title}")
                    
                    print(f"[标注管理器] 标注界面已显示")
                    return True
                else:
                    print(f"  - AnnotationWidget没有show方法")
                    return False
            except Exception as e:
                print(f"  - show()调用失败: {e}")
                import traceback
                traceback.print_exc()
                return False
            
        except Exception as e:
            print(f"[标注管理器] 显示标注界面异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_channel_name(self, channel_id):
        """
        获取通道显示名称
        
        Args:
            channel_id: 通道ID
            
        Returns:
            str: 通道名称
        """
        try:
            if self.main_window and hasattr(self.main_window, 'getChannelDisplayName'):
                # 提取通道编号
                channel_number = int(channel_id.replace('channel', '')) if 'channel' in channel_id else 1
                return self.main_window.getChannelDisplayName(channel_id, channel_number)
            else:
                # 默认名称
                channel_number = channel_id.replace('channel', '') if 'channel' in channel_id else '?'
                return f"通道{channel_number}"
        except:
            return f"通道{channel_id}"
    
    def _apply_history_annotation(self, history_data):
        """
        应用历史标注数据到标注界面（按照原系统格式解析）
        
        Args:
            history_data: 历史标注数据
        """
        try:
            if not self.annotation_widget or not history_data:
                return
            
            print(f"[标注管理器] 应用历史标注数据")
            
            # 提取标注数据（按照原系统格式）
            boxes = history_data.get('boxes', [])
            fixed_bottoms = history_data.get('fixed_bottoms', [])
            fixed_tops = history_data.get('fixed_tops', [])
            init_levels = history_data.get('init_levels', [])
            areas_config = history_data.get('areas', {})
            
            if not boxes:
                return
            
            # 重建坐标点（按照原系统格式）
            bottom_points = []
            top_points = []
            init_level_points = []
            area_names = []
            area_heights = []
            area_states = []
            
            for i, (cx, cy, size) in enumerate(boxes):
                cx = int(cx)
                
                # 底部和顶部点（使用cx作为x坐标，fixed_bottoms/fixed_tops作为y坐标）
                if i < len(fixed_bottoms):
                    bottom_points.append((cx, int(fixed_bottoms[i])))
                if i < len(fixed_tops):
                    top_points.append((cx, int(fixed_tops[i])))
                
                # 初始液位点（使用完整的坐标信息）
                if i < len(init_levels) and len(init_levels[i]) >= 2:
                    init_level_points.append((int(init_levels[i][0]), int(init_levels[i][1])))
                elif i < len(fixed_bottoms) and i < len(fixed_tops):
                    # 默认在中间位置
                    mid_y = (fixed_tops[i] + fixed_bottoms[i]) / 2
                    init_level_points.append((cx, int(mid_y)))
                
                # 区域配置（按照原系统格式）
                area_key = f'area_{i+1}'
                area_info = areas_config.get(area_key, {})
                area_names.append(area_info.get('name', f'{self.current_channel_id}_区域{i+1}'))
                area_heights.append(area_info.get('height', '20mm'))
                area_states.append(area_info.get('state', '默认'))
            
            # 应用到标注界面
            if hasattr(self.annotation_widget, 'loadHistoryAnnotation'):
                self.annotation_widget.loadHistoryAnnotation(
                    boxes=boxes,
                    bottom_points=bottom_points,
                    top_points=top_points,
                    init_level_points=init_level_points,
                    area_names=area_names,
                    area_heights=area_heights,
                    area_states=area_states
                )
                print(f"[标注管理器] 历史标注数据已应用到界面")
            
        except Exception as e:
            print(f"[标注管理器] 应用历史标注数据异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_annotation_completed(self, boxes, bottoms, tops, init_levels=None):
        """
        处理标注完成事件（按照原系统信号格式）
        
        Args:
            boxes: 检测框列表 - 格式：[(cx, cy, size), ...]
            bottoms: 底部线条列表 - 格式：[(x, y), ...]
            tops: 顶部线条列表 - 格式：[(x, y), ...]
            init_levels: 初始液位线列表 - 格式：[(x, y), ...]（可选）
        """
        try:
            print(f"[标注管理器] 标注完成，开始处理结果")
            print(f"  - boxes: {boxes}")
            print(f"  - bottoms: {bottoms}")
            print(f"  - tops: {tops}")
            print(f"  - init_levels: {init_levels}")
            
            if not self.current_channel_id:
                print(f"[标注管理器] 当前通道ID为空")
                return
            
            # 获取区域配置（从标注界面获取）
            area_names = getattr(self.annotation_widget, 'area_names', [])
            area_heights = getattr(self.annotation_widget, 'area_heights', [])
            area_states = getattr(self.annotation_widget, 'area_states', [])
            
            print(f"  - area_names: {area_names}")
            print(f"  - area_heights: {area_heights}")
            print(f"  - area_states: {area_states}")
            
            # 构建标注数据
            annotation_data = {
                'boxes': boxes,
                'bottoms': bottoms,
                'tops': tops,
                'init_levels': init_levels or [],
                'area_names': area_names,
                'area_heights': area_heights,
                'area_states': area_states
            }
            
            # 1. 保存到本地配置文件
            self._save_local_annotation(self.current_channel_id, annotation_data)
            
            # 2. 推送到服务器
            success = self._push_to_server(self.current_channel_id, annotation_data)
            
            if success:
                print(f"[标注管理器] 标注结果已成功推送到服务器")
            else:
                print(f"[标注管理器] 推送到服务器失败，但本地已保存")
            
            # 3. 发射完成信号
            self.annotationCompleted.emit(self.current_channel_id, annotation_data)
            
            # 4. 清理状态
            self._cleanup_annotation()
            
        except Exception as e:
            print(f"[标注管理器] 处理标注完成异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_annotation_cancelled(self):
        """
        处理标注取消事件
        """
        try:
            print(f"[标注管理器] 标注已取消")
            self._cleanup_annotation()
        except Exception as e:
            print(f"[标注管理器] 处理标注取消异常: {e}")
    
    def _save_local_annotation(self, channel_id, annotation_data):
        """
        保存标注结果到本地配置文件（按照原系统格式）
        
        Args:
            channel_id: 通道ID
            annotation_data: 标注数据
        """
        try:
            print(f"[标注管理器] 保存标注结果到本地")
            
            project_root = get_project_root()
            config_dir = os.path.join(project_root, 'database', 'config')
            annotation_file = os.path.join(config_dir, 'annotation_result.yaml')
            
            # 确保目录存在
            os.makedirs(config_dir, exist_ok=True)
            
            # 读取现有配置
            if os.path.exists(annotation_file):
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # 构建保存数据（按照原系统格式）
            from datetime import datetime
            import re
            
            boxes = annotation_data['boxes']
            bottoms = annotation_data['bottoms']
            tops = annotation_data['tops']
            init_levels = annotation_data.get('init_levels', [])
            area_names = annotation_data.get('area_names', [])
            area_heights = annotation_data.get('area_heights', [])
            area_states = annotation_data.get('area_states', [])
            
            # 提取坐标数据（按照原格式）
            fixed_bottoms = [point[1] for point in bottoms] if bottoms else []
            fixed_tops = [point[1] for point in tops] if tops else []
            
            # 构建区域配置（按照原格式）
            areas_dict = {}
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                # 获取状态并转换为init_status值：默认=0, 满=1, 空=2
                state_str = area_states[i] if area_states and i < len(area_states) else "默认"
                if state_str == "满":
                    init_status = 1
                elif state_str == "空":
                    init_status = 2
                else:
                    init_status = 0
                
                areas_dict[area_key] = {
                    'name': area_names[i] if area_names and i < len(area_names) else f'{channel_id}_区域{i+1}',
                    'height': area_heights[i] if area_heights and i < len(area_heights) else '20mm',
                    'state': state_str,
                    'init_status': init_status
                }
            
            # 处理初始液位线数据 - 转换为实际高度（毫米）
            fixed_init_levels = []
            if init_levels:
                for i, pt in enumerate(init_levels):
                    init_level_y = pt[1] if isinstance(pt, (tuple, list)) else pt
                    # 获取对应区域的容器底部、顶部和实际高度
                    if i < len(fixed_bottoms) and i < len(fixed_tops):
                        bottom_y = fixed_bottoms[i]
                        top_y = fixed_tops[i]
                        container_pixel_height = bottom_y - top_y
                        
                        # 获取实际容器高度（毫米）
                        area_key = f'area_{i+1}'
                        height_str = areas_dict.get(area_key, {}).get('height', '20mm')
                        height_match = re.search(r'([\d.]+)', str(height_str))
                        actual_height_mm = float(height_match.group(1)) if height_match else 20.0
                        
                        # 计算初始液位高度（从底部到初始液位线的像素距离）
                        if container_pixel_height > 0:
                            init_level_pixel_height = bottom_y - init_level_y
                            # 映射到实际高度（毫米）
                            init_level_mm = (init_level_pixel_height / container_pixel_height) * actual_height_mm
                            fixed_init_levels.append(round(init_level_mm, 2))
                        else:
                            fixed_init_levels.append(actual_height_mm / 2)  # 默认中间位置
                    else:
                        fixed_init_levels.append(10.0)  # 默认10mm
            
            # 保存到配置（按照原系统格式）
            config[channel_id] = {
                'boxes': [list(box) for box in boxes],  # 转换为列表格式
                'fixed_bottoms': fixed_bottoms,
                'fixed_tops': fixed_tops,
                'init_levels': [list(pt) for pt in init_levels] if init_levels else [],  # 保存完整坐标 [(x, y), ...]
                'fixed_init_levels': fixed_init_levels,  # 保存实际高度（毫米）
                'annotation_count': len(boxes),
                'areas': areas_dict,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 写入文件
            with open(annotation_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            print(f"[标注管理器] 本地标注结果已保存")
            
        except Exception as e:
            print(f"[标注管理器] 保存本地标注结果异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _push_to_server(self, channel_id, annotation_data):
        """
        推送标注配置到服务器
        
        Args:
            channel_id: 通道ID
            annotation_data: 标注数据
            
        Returns:
            bool: 是否成功推送
        """
        try:
            print(f"[标注管理器] 推送标注配置到服务器")
            
            if not self.remote_config_manager:
                print(f"[标注管理器] 远程配置管理器不可用")
                return False
            
            # 构建服务器配置格式
            server_config = self._build_server_config(channel_id, annotation_data)
            
            # 推送到服务器
            success = self.remote_config_manager.push_annotation_config(channel_id, server_config)
            
            if success:
                print(f"[标注管理器] 成功推送到服务器")
                return True
            else:
                print(f"[标注管理器] 推送到服务器失败")
                return False
                
        except Exception as e:
            print(f"[标注管理器] 推送到服务器异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _build_server_config(self, channel_id, annotation_data):
        """
        构建服务器配置格式（按照原系统格式）
        
        Args:
            channel_id: 通道ID
            annotation_data: 标注数据
            
        Returns:
            dict: 服务器配置格式的数据
        """
        try:
            from datetime import datetime
            import re
            
            boxes = annotation_data['boxes']
            bottoms = annotation_data['bottoms']
            tops = annotation_data['tops']
            init_levels = annotation_data.get('init_levels', [])
            area_names = annotation_data.get('area_names', [])
            area_heights = annotation_data.get('area_heights', [])
            area_states = annotation_data.get('area_states', [])
            
            # 提取坐标数据（按照原格式）
            fixed_bottoms = [point[1] for point in bottoms] if bottoms else []
            fixed_tops = [point[1] for point in tops] if tops else []
            
            # 构建区域配置（按照原格式）
            areas_dict = {}
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                # 获取状态并转换为init_status值：默认=0, 满=1, 空=2
                state_str = area_states[i] if area_states and i < len(area_states) else "默认"
                if state_str == "满":
                    init_status = 1
                elif state_str == "空":
                    init_status = 2
                else:
                    init_status = 0
                
                areas_dict[area_key] = {
                    'name': area_names[i] if area_names and i < len(area_names) else f'{channel_id}_区域{i+1}',
                    'height': area_heights[i] if area_heights and i < len(area_heights) else '20mm',
                    'state': state_str,
                    'init_status': init_status
                }
            
            # 处理初始液位线数据 - 转换为实际高度（毫米）
            fixed_init_levels = []
            if init_levels:
                for i, pt in enumerate(init_levels):
                    init_level_y = pt[1] if isinstance(pt, (tuple, list)) else pt
                    # 获取对应区域的容器底部、顶部和实际高度
                    if i < len(fixed_bottoms) and i < len(fixed_tops):
                        bottom_y = fixed_bottoms[i]
                        top_y = fixed_tops[i]
                        container_pixel_height = bottom_y - top_y
                        
                        # 获取实际容器高度（毫米）
                        area_key = f'area_{i+1}'
                        height_str = areas_dict.get(area_key, {}).get('height', '20mm')
                        height_match = re.search(r'([\d.]+)', str(height_str))
                        actual_height_mm = float(height_match.group(1)) if height_match else 20.0
                        
                        # 计算初始液位高度（从底部到初始液位线的像素距离）
                        if container_pixel_height > 0:
                            init_level_pixel_height = bottom_y - init_level_y
                            # 映射到实际高度（毫米）
                            init_level_mm = (init_level_pixel_height / container_pixel_height) * actual_height_mm
                            fixed_init_levels.append(round(init_level_mm, 2))
                        else:
                            fixed_init_levels.append(actual_height_mm / 2)  # 默认中间位置
                    else:
                        fixed_init_levels.append(10.0)  # 默认10mm
            
            # 按照原系统格式构建配置
            server_config = {
                'boxes': [list(box) for box in boxes],  # 转换为列表格式
                'fixed_bottoms': fixed_bottoms,
                'fixed_tops': fixed_tops,
                'init_levels': [list(pt) for pt in init_levels] if init_levels else [],  # 保存完整坐标 [(x, y), ...]
                'fixed_init_levels': fixed_init_levels,  # 保存实际高度（毫米）
                'annotation_count': len(boxes),
                'areas': areas_dict,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return server_config
            
        except Exception as e:
            print(f"[标注管理器] 构建服务器配置异常: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _init_physical_zoom_for_annotation(self):
        """
        为标注界面初始化物理变焦控制器（移植自原系统）
        """
        try:
            if not self.annotation_widget or not self.current_channel_id:
                return
            
            print(f"[标注管理器] 初始化物理变焦控制器...")
            
            # 尝试导入物理变焦控制器
            try:
                from ..physical_zoom_controller import PhysicalZoomController
            except ImportError:
                try:
                    from handlers.videopage.physical_zoom_controller import PhysicalZoomController
                except ImportError:
                    print(f"[标注管理器] 物理变焦控制器模块不可用")
                    return
            
            # 获取设备配置
            device_config = self._get_device_config_for_channel(self.current_channel_id)
            if not device_config:
                print(f"[标注管理器] 未找到通道 {self.current_channel_id} 的设备配置")
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
                self.annotation_widget.setPhysicalZoomController(controller)
                print(f"[标注管理器] 物理变焦控制器连接成功")
            else:
                print(f"[标注管理器] 物理变焦控制器连接失败")
            
        except Exception as e:
            print(f"[标注管理器] 初始化物理变焦控制器异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_device_config_for_channel(self, channel_id):
        """
        获取通道的设备配置（移植自原系统）
        
        Args:
            channel_id: 通道ID
            
        Returns:
            dict: 设备配置，如果没有返回None
        """
        try:
            import os
            import yaml
            from urllib.parse import urlparse
            
            # 获取项目根目录
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                print(f"[标注管理器] 配置文件不存在: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            channel_config = config.get(channel_id, {})
            rtsp_address = channel_config.get('address', '')
            
            if not rtsp_address:
                print(f"[标注管理器] 通道 {channel_id} 没有RTSP地址配置")
                return None
            
            # 解析RTSP地址
            parsed = urlparse(rtsp_address)
            if not parsed.hostname:
                print(f"[标注管理器] 无法解析RTSP地址: {rtsp_address}")
                return None
            
            device_config = {
                'ip': parsed.hostname,
                'port': 8000,
                'username': parsed.username or 'admin',
                'password': parsed.password or '',
                'channel': 1
            }
            
            print(f"[标注管理器] 设备配置: {device_config}")
            return device_config
            
        except Exception as e:
            print(f"[标注管理器] 获取设备配置异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_annotation_engine(self):
        """
        创建标注引擎（移植自原系统）
        
        Returns:
            SimpleAnnotationEngine: 标注引擎实例，失败返回None
        """
        try:
            print(f"[标注管理器] 创建标注引擎...")
            
            # 创建标注引擎类（移植自原系统）
            class SimpleAnnotationEngine:
                def __init__(self):
                    self.step = 0  # 0=画框模式, 1=标记液位模式
                    self.boxes = []  # 存储ROI (cx, cy, size) 格式
                    self.bottom_points = []  # 存储底部标记点
                    self.top_points = []  # 存储顶部标记点
                    self.init_level_points = []  # 存储初始液位线点
                
                def add_box(self, cx, cy, size):
                    """
                    添加ROI，并自动计算顶部线条、底部线条、初始液位线
                    
                    Args:
                        cx: 框中心x坐标
                        cy: 框中心y坐标
                        size: 框的边长
                    """
                    self.boxes.append((cx, cy, size))
                    
                    # 自动计算并添加底部线条和顶部线条
                    # 底部线条：box底边y坐标 - box高度的10%，x为中心
                    half_size = size / 2
                    bottom_y = cy + half_size - (size * 0.1)  # 底边y - 10%高度
                    bottom_x = cx  # x位置为box轴对称中心
                    self.bottom_points.append((int(bottom_x), int(bottom_y)))
                    
                    # 顶部线条：box顶边y坐标 + box高度的10%，x为中心
                    top_y = cy - half_size + (size * 0.1)  # 顶边y + 10%高度
                    top_x = cx  # x位置为box轴对称中心
                    self.top_points.append((int(top_x), int(top_y)))
                    
                    # 初始液位线：默认在容器中间位置
                    init_level_y = (top_y + bottom_y) / 2
                    self.init_level_points.append((int(cx), int(init_level_y)))
                
                def add_bottom(self, x, y):
                    """添加底部标记点"""
                    self.bottom_points.append((int(x), int(y)))
                
                def add_top(self, x, y):
                    """添加顶部标记点"""
                    self.top_points.append((int(x), int(y)))
                
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
                
                def get_mission_results(self):
                    """获取标注结果（兼容性方法）"""
                    return self.get_results()
            
            engine = SimpleAnnotationEngine()
            print(f"[标注管理器] 标注引擎创建成功: {type(engine)}")
            return engine
            
        except Exception as e:
            print(f"[标注管理器] 创建标注引擎异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _cleanup_annotation(self):
        """
        清理标注状态
        """
        try:
            if self.annotation_widget:
                self.annotation_widget.close()
                self.annotation_widget = None
            
            self.current_channel_id = None
            self.current_frame = None
            
            print(f"[标注管理器] 标注状态已清理")
            
        except Exception as e:
            print(f"[标注管理器] 清理标注状态异常: {e}")