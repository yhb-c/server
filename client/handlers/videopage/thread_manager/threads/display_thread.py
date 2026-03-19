# -*- coding: utf-8 -*-

"""
显示线程

职责：
1. HWND模式：从检测结果队列读取液位线数据，通过回调更新InfoOverlay叠加层
2. 传统Qt模式：从frame_buffer读取原始帧，叠加液位线后显示

注意：
- HWND模式下，视频由PlayCtrl SDK直接渲染，显示线程只负责更新叠加层
- 回调函数会在子线程中调用，调用方需要确保线程安全（使用Qt信号槽）
"""

import time
import queue
from typing import Callable, Optional

# 导入调试日志重置函数
# 注意：调试日志重置功能已移至服务端，客户端不再直接调用
def reset_debug_log():
    """
    调试日志重置功能（客户端占位函数）
    实际的日志重置功能在服务端执行
    """
    pass


class DisplayThread:
    """显示线程类
    
    职责：
    1. HWND模式：从检测结果队列读取液位线数据，通过回调更新InfoOverlay
    2. 传统Qt模式：从latest_frame读取帧，叠加液位线后通过回调显示
    """
    
    # 相机报警信号（类级别）
    _camera_alert_signal = None
    _main_window = None
    _thread_manager = None
    
    @classmethod
    def set_camera_alert_signal(cls, signal):
        cls._camera_alert_signal = signal
    
    @classmethod
    def set_main_window(cls, main_window):
        cls._main_window = main_window
    
    @classmethod
    def set_thread_manager(cls, thread_manager):
        cls._thread_manager = thread_manager
    
    @classmethod
    def _pause_channel_detection_input(cls, channel_id: str) -> bool:
        try:
            if cls._thread_manager:
                context = cls._thread_manager.get_channel_context(channel_id)
                if context:
                    context.camera_position_paused = True
                    return True
            return False
        except:
            return False
    
    @classmethod
    def _show_camera_moved_alert(cls, channel_id: str):
        cls._pause_channel_detection_input(channel_id)
        try:
            if cls._camera_alert_signal:
                cls._camera_alert_signal.alert_triggered.emit(channel_id)
        except:
            pass
    
    @staticmethod
    def run(context, frame_rate: float, on_frame_displayed: Optional[Callable] = None,
            draw_detection_func: Optional[Callable] = None, config: Optional[dict] = None):
        """显示线程主循环
        
        Args:
            context: ChannelThreadContext 实例
            frame_rate: 显示帧率
            on_frame_displayed: 回调函数
                - HWND模式：callback(channel_id, dict) - dict包含液位线数据
                - Qt模式：callback(channel_id, frame)
            draw_detection_func: 绘制检测结果函数（仅Qt模式）
            config: 应用配置
        """
        channel_id = context.channel_id
        frame_interval = 1.0 / frame_rate if frame_rate > 0 else 0.033
        
        # 历史数据缓存
        last_liquid_positions = {}
        last_full_detection_result = {}
        last_detection_enabled = False
        camera_alert_shown = False
        
        # 从 capture_source 获取视频尺寸
        video_width = 0
        video_height = 0
        if context.capture_source:
            try:
                video_width, video_height = context.capture_source.get_frame_size()
            except:
                pass
        
        while context.display_flag:
            try:
                frame_start_time = time.time()
                
                # HWND模式：只处理检测结果
                if context.hwnd_render_mode:
                    if context.detection_enabled and not last_detection_enabled:
                        camera_alert_shown = False
                        reset_debug_log()
                    last_detection_enabled = context.detection_enabled
                    
                    if context.detection_enabled:
                        liquid_positions = {}
                        is_new_data = False
                        
                        # 动态获取视频尺寸（如果还没有获取到）
                        if video_width == 0 or video_height == 0:
                            if context.capture_source:
                                try:
                                    video_width, video_height = context.capture_source.get_frame_size()
                                except:
                                    pass
                        
                        try:
                            detection_result = context.detection_mission_results.get_nowait()
                            if detection_result and 'liquid_line_positions' in detection_result:
                                liquid_positions = detection_result['liquid_line_positions']
                                last_liquid_positions = liquid_positions
                                last_full_detection_result = detection_result
                                is_new_data = True
                                video_width = detection_result.get('video_width', video_width)
                                video_height = detection_result.get('video_height', video_height)
                        except queue.Empty:
                            if last_liquid_positions:
                                liquid_positions = last_liquid_positions
                                is_new_data = False
                        
                        # 通过回调更新叠加层
                        if on_frame_displayed and liquid_positions:
                            overlay_data = {
                                'liquid_positions': liquid_positions,
                                'is_new_data': is_new_data,
                                'video_width': video_width,
                                'video_height': video_height
                            }
                            on_frame_displayed(channel_id, overlay_data)
                        
                        # 相机移动报警
                        camera_moved = last_full_detection_result.get('camera_moved', False)
                        if camera_moved and not camera_alert_shown:
                            camera_alert_shown = True
                            DisplayThread._show_camera_moved_alert(channel_id)
                        elif not camera_moved:
                            camera_alert_shown = False
                    
                    # HWND模式下，检测未启动时不调用回调，只等待
                    # 不需要更新叠加层
                
                else:
                    # 传统Qt模式
                    with context.frame_lock:
                        if context.latest_frame is None:
                            time.sleep(0.01)
                            continue
                        frame = context.latest_frame.copy() if context.detection_enabled else context.latest_frame
                    
                    context.display_count += 1
                    display_frame = frame
                    
                    if context.detection_enabled and not last_detection_enabled:
                        camera_alert_shown = False
                        reset_debug_log()
                    last_detection_enabled = context.detection_enabled
                    
                    if context.detection_enabled:
                        liquid_positions = {}
                        is_new_data = False
                        
                        try:
                            detection_result = context.detection_mission_results.get_nowait()
                            if detection_result and 'liquid_line_positions' in detection_result:
                                liquid_positions = detection_result['liquid_line_positions']
                                last_liquid_positions = liquid_positions
                                last_full_detection_result = detection_result
                                is_new_data = True
                        except queue.Empty:
                            if last_liquid_positions:
                                liquid_positions = last_liquid_positions
                                is_new_data = False
                        
                        if liquid_positions and draw_detection_func:
                            detection_draw_data = {
                                'liquid_line_positions': liquid_positions,
                                'is_new_data': is_new_data
                            }
                            display_frame = draw_detection_func(display_frame, detection_draw_data)
                        
                        camera_moved = last_full_detection_result.get('camera_moved', False)
                        if camera_moved and not camera_alert_shown:
                            camera_alert_shown = True
                            DisplayThread._show_camera_moved_alert(channel_id)
                        elif not camera_moved:
                            camera_alert_shown = False
                    
                    callback = on_frame_displayed or getattr(context, 'on_frame_displayed', None)
                    if callback:
                        callback(channel_id, display_frame)
                
                # 帧率控制
                elapsed = time.time() - frame_start_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                time.sleep(0.1)
