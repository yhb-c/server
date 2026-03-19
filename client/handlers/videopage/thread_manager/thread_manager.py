# -*- coding: utf-8 -*-

"""
通道线程管理器

为每个通道管理4种线程：
1.显示线程，显示根据检测线程结果绘制的帧
2.检测线程，从YUV队列获取帧，输出结果数据
3.曲线绘制线程，读取检测线程结果数据并实时绘制曲线
4.存储线程，保存检测线程的结果数据到本地

解码渲染线程（由PlayCtrl SDK内部管理）：
- 解码：PlayCtrl SDK内部的解码线程解码输入码流（rtsp相机或本地视频）
- 渲染：PlayCtrl SDK解码后直接渲染到HWND，不需要任何中间文件
- YUV队列：只有检测线程开启时，才将YUV数据缓存到队列供检测使用

架构特点：
- 线程池管理：4个摄像头 × 4种线程 = 16个线程
- 数据流设计：使用队列进行线程间通信
- 资源隔离：每个摄像头的资源完全独立
- 优雅关闭：支持线程安全的启动和停止
"""

import os
import threading
import queue
import time
import cv2
import numpy as np
import yaml
from datetime import datetime
from typing import Dict, Optional, Callable
from collections import deque
from qtpy import QtCore

# 导入独立的ChannelThreadContext类
from .channel_thread_context import ChannelThreadContext


class ProgressSignal(QtCore.QObject):
    """进度信号类，用于跨线程更新进度条"""
    progress_updated = QtCore.Signal(int, str)  # (进度值, 进度文本)


class CameraAlertSignal(QtCore.QObject):
    """相机报警信号类，用于跨线程弹出对话框"""
    alert_triggered = QtCore.Signal(str)  # (channel_id)


class ChannelThreadManager:
    """通道线程管理器
    
    统一管理所有通道的线程，支持：
    - 启动/停止各种线程
    - 线程状态监控
    - 异常处理和恢复
    """
    
    def __init__(self, max_channels: int = 4):
        """
        Args:
            max_channels: 最大支持通道数量
        """
        self.max_channels = max_channels
        
        # 通道上下文字典 {channel_id: ChannelThreadContext}
        self.contexts: Dict[str, ChannelThreadContext] = {}
        
        # 全局回调函数
        self.on_frame_captured: Optional[Callable] = None       # 帧捕获回调
        self.on_frame_displayed: Optional[Callable] = None      # 帧显示回调
        self.on_detection_mission_result: Optional[Callable] = None     # 检测结果回调
        self.on_curve_updated: Optional[Callable] = None        # 曲线更新回调
        
        # 检测模型（可选，由外部设置）
        self.detection_model = None
        
        #  存储线程同步控制变量
        # same = 1: 存储线程与检测线程同步启动/停止
        # same = 0: 存储线程与检测线程不同步（需手动控制）
        self.same = 1
        
        #  曲线模式标记（由外部设置，用于检测线程启动时自动启动曲线线程）
        self.is_curve_mode = False
        
        # 主窗口引用（用于访问 curvemission）
        self.main_window = None
        
        # 应用配置（用于获取编译模式）
        self.config = None
        
        # 相机报警信号（用于跨线程弹出对话框）
        self._camera_alert_signal = CameraAlertSignal()
        self._camera_alert_signal.alert_triggered.connect(self._on_camera_alert_triggered)
    
    def _on_camera_alert_triggered(self, channel_id: str):
        """相机报警信号槽函数（在主线程中执行）
        
        注意：此时检测输入已在 DisplayThread 中被暂停
        对话框提供两个选项：
        1. 确定：重置基准帧并恢复检测
        2. 重新标注：打开标注界面重新标注ROI
        """
        try:
            from qtpy import QtWidgets
            
            parent = self.main_window if self.main_window else None
            
            # 创建自定义对话框
            msg_box = QtWidgets.QMessageBox(parent)
            msg_box.setWindowTitle("相机姿态警告")
            msg_box.setText(
                f"检测到 {channel_id} 相机位置发生变化！\n\n"
                f"检测输入已暂停。\n"
                f"请检查相机是否被移动或震动。"
            )
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            
            # 添加按钮
            ok_btn = msg_box.addButton("确定", QtWidgets.QMessageBox.AcceptRole)
            annotate_btn = msg_box.addButton("重新标注", QtWidgets.QMessageBox.ActionRole)
            
            # 设置默认按钮
            msg_box.setDefaultButton(ok_btn)
            
            # 显示对话框
            msg_box.exec_()
            
            clicked_btn = msg_box.clickedButton()
            
            if clicked_btn == annotate_btn:
                # 点击"重新标注"按钮：触发标注信号
                print(f"[相机报警] {channel_id} 用户选择重新标注")
                self._trigger_annotation_request(channel_id)
            else:
                # 点击"确定"按钮：重置基准帧并恢复检测
                print(f"[相机报警] {channel_id} 用户选择重置基准帧")
                self._reset_camera_and_resume(channel_id)
            
        except Exception as e:
            print(f"[相机报警] 对话框显示失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _trigger_annotation_request(self, channel_id: str):
        """触发标注请求（打开通道设置对话框并自动开始标注）
        
        标注完成后自动重置基准帧并恢复检测。
        
        Args:
            channel_id: 通道ID
        """
        try:
            from qtpy import QtCore
            
            if not self.main_window:
                print(f"[相机报警] main_window 未设置")
                return
            
            # 获取通道名称
            channel_name = channel_id
            if hasattr(self.main_window, '_channel_panels_map'):
                panel = self.main_window._channel_panels_map.get(channel_id)
                if panel and hasattr(panel, 'getChannelName'):
                    try:
                        channel_name = panel.getChannelName() or channel_id
                    except:
                        pass
            
            # 检查是否有 showGeneralSetDialog 方法
            if not hasattr(self.main_window, 'showGeneralSetDialog'):
                print(f"[相机报警] 未找到 showGeneralSetDialog 方法")
                return
            
            print(f"[相机报警] 打开 {channel_id} 设置对话框并自动开始标注")
            
            # 创建对话框
            task_info = {'task_id': '', 'task_name': ''}
            dialog = self.main_window.showGeneralSetDialog(
                channel_name=channel_name,
                channel_id=channel_id,
                task_info=task_info
            )
            
            if not dialog:
                print(f"[相机报警] 创建对话框失败")
                return
            
            # 获取面板
            panel = dialog.getPanel()
            
            # 连接标注完成信号 - 标注完成后重置基准帧并恢复检测
            if panel and hasattr(panel, 'annotationCompleted'):
                def on_annotation_completed(result):
                    print(f"[相机报警] {channel_id} 标注完成，准备重置基准帧并恢复检测")
                    # 延迟执行，确保标注数据已保存
                    QtCore.QTimer.singleShot(500, lambda: self._reset_camera_and_resume(channel_id))
                
                panel.annotationCompleted.connect(on_annotation_completed)
            
            # 连接对话框关闭信号 - 对话框关闭时也恢复检测（用户可能取消标注）
            def on_dialog_finished(result):
                print(f"[相机报警] {channel_id} 设置对话框已关闭")
                # 无论如何都恢复检测输入
                QtCore.QTimer.singleShot(300, lambda: self._reset_camera_and_resume(channel_id))
            
            dialog.finished.connect(on_dialog_finished)
            
            # 延迟触发标注
            if panel and hasattr(panel, 'annotationRequested'):
                def auto_trigger_annotation():
                    try:
                        print(f"[相机报警] 自动触发 {channel_id} 标注请求")
                        panel.annotationRequested.emit()
                    except Exception as e:
                        print(f"[相机报警] 自动触发标注失败: {e}")
                
                QtCore.QTimer.singleShot(200, auto_trigger_annotation)
            
            # 显示对话框（非阻塞方式）
            dialog.show()
            
        except Exception as e:
            print(f"[相机报警] 触发标注请求失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _reset_camera_and_resume(self, channel_id: str):
        """重置相机基准帧并恢复检测输入
        
        Args:
            channel_id: 通道ID
        """
        try:
            # 重置相机姿态检测器
            from utils.cameraposition import reset_camera_detector
            reset_camera_detector(channel_id)
            print(f"[相机报警] {channel_id} 相机基准帧已重置")
            
            # 恢复检测输入
            context = self.get_channel_context(channel_id)
            if context:
                context.camera_position_paused = False
                print(f"[相机报警] {channel_id} 检测输入已恢复")
                
        except Exception as e:
            print(f"[相机报警] 重置相机并恢复检测失败: {e}")
    
    def _show_camera_moved_alert(self, channel_id: str):
        """弹出相机移动报警对话框（通过信号在主线程执行）
        
        Args:
            channel_id: 通道ID
        """
        print(f"[相机报警触发] {channel_id} 发送信号到主线程...")
        
        try:
            # 通过信号触发，确保在主线程中执行对话框
            self._camera_alert_signal.alert_triggered.emit(channel_id)
        except Exception as e:
            print(f"[相机报警] 发送信号失败: {e}")
    
    # ==================== 上下文管理 ====================
    
    def create_channel_context(self, channel_id: str) -> ChannelThreadContext:
        """创建通道上下文"""
        if channel_id in self.contexts:
            pass
        self.destroy_channel_context(channel_id)
        
        context = ChannelThreadContext(channel_id)
        self.contexts[channel_id] = context
        return context
    
    def get_channel_context(self, channel_id: str) -> Optional[ChannelThreadContext]:
        """获取通道上下文"""
        return self.contexts.get(channel_id)
    
    def destroy_channel_context(self, channel_id: str):
        """销毁通道上下文"""
        if channel_id not in self.contexts:
            return
        
        # 先停止所有线程
        self.stop_all_threads(channel_id)
        
        # 清空队列
        context = self.contexts[channel_id]
        context.clear_queues()
        
        # 删除上下文
        del self.contexts[channel_id]
    
    def cleanup_global_detection_thread(self):
        """清理全局检测线程资源"""
        try:
            from .threads.global_detection_thread import GlobalDetectionThread
            
            # 获取全局检测线程实例
            global_thread = GlobalDetectionThread.get_instance()
            
            # 停止全局检测线程
            # 使用新的全局状态变量检查
            if GlobalDetectionThread.is_detection_running():
                global_thread.stop()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    # ==================== 线程启动 ====================
    
    def start_channel_threads(self, channel_id: str, capture_source, callbacks: dict = None, 
                              detection_enabled: bool = False, hwnd: int = None) -> bool:
        """启动通道的基本线程（HWND直接渲染模式）
        
        解码渲染线程架构：
        1. PlayCtrl SDK 内部解码线程解码输入码流
        2. PlayCtrl SDK 解码后直接渲染到 HWND，不需要任何中间文件
        3. 显示线程仅负责叠加检测结果（液位线等）
        4. 检测启用时，YUV数据入队供检测线程使用
        
        Args:
            channel_id: 通道ID
            capture_source: HKcapture 实例
            callbacks: 回调函数字典
            detection_enabled: 是否启用检测线程（暂不使用）
            hwnd: 渲染窗口句柄（从Qt的winId()获取）
            
        Returns:
            bool: 是否启动成功
        """
        try:
            print(f"[线程管理器] {channel_id} 启动通道线程（解码渲染线程架构，无捕获线程）")
            
            # 创建通道上下文
            self.create_channel_context(channel_id)
            
            # 设置回调函数
            context = self.get_channel_context(channel_id)
            if callbacks and context:
                if 'on_frame_displayed' in callbacks:
                    context.on_frame_displayed = callbacks['on_frame_displayed']
                if 'on_detection_mission_result' in callbacks:
                    context.on_detection_mission_result = callbacks['on_detection_mission_result']
            
            # 保存capture_source到context（供后续检测启用时使用）
            context.capture_source = capture_source
            
            # HWND直接渲染模式：PlayCtrl SDK解码后直接渲染到HWND
            # HWND已在_connectChannelThread中设置并开始播放
            if hwnd:
                context.hwnd_render_mode = True
                print(f"[线程管理器] {channel_id} HWND渲染模式已启用（解码渲染由PlayCtrl SDK内部管理，无需捕获线程）")
            
            # 启动显示线程（仅用于叠加检测结果）
            if not self.start_display_thread(channel_id):
                return False
            
            print(f"[线程管理器] {channel_id} 通道线程启动完成（仅显示线程，无捕获线程）")
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def stop_channel_threads(self, channel_id: str) -> bool:
        """停止通道的所有线程
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 是否停止成功
        """
        try:
            # 停止所有线程
            self.stop_all_threads(channel_id)
            
            # 销毁上下文
            self.destroy_channel_context(channel_id)
            
            return True
            
        except Exception as e:
            return False
    
    def start_display_thread(self, channel_id: str):
        """启动显示线程（使用独立的 DisplayThread 类）"""
        context = self.get_channel_context(channel_id)
        if not context:
            return False
        
        if context.display_flag:
            return True
        
        # 导入 DisplayThread 类
        from .threads.display_thread import DisplayThread
        
        # 启用FPS调试日志（根据配置文件）
        try:
            from utils.debug_logger import get_debug_logger
            if self.config and self.config.get('fps_log', False):
                get_debug_logger().enable(True)
        except Exception as e:
            pass
        
        # 设置相机报警信号、主窗口引用和线程管理器引用（供 DisplayThread 使用）
        DisplayThread.set_camera_alert_signal(self._camera_alert_signal)
        DisplayThread.set_main_window(self.main_window)
        DisplayThread.set_thread_manager(self)  # 设置线程管理器引用，用于停止检测线程
        
        # 获取显示帧率（默认30fps）
        display_frame_rate = 30.0
        if self.config:
            display_frame_rate = self.config.get('display_frame_rate', 30.0)
        
        # 获取回调函数（从context中获取，在start_channel_threads中已设置）
        on_frame_displayed = getattr(context, 'on_frame_displayed', None)
        
        context.display_flag = True
        context.display_thread = threading.Thread(
            target=DisplayThread.run,
            args=(context, display_frame_rate, on_frame_displayed, None, self.config),
            name=f"Display-{channel_id}",
            daemon=True
        )
        context.display_thread.start()
        return True
    
    def start_detection_thread(self, channel_id: str, detection_model=None):
        """启动检测线程（使用全局检测线程架构）
        
        解码渲染线程模式下，此方法会：
        1. 启用HKcapture的YUV队列（解码回调将YUV数据入队）
        2. 注册通道到全局检测线程
        
        注意：不再需要启动捕获线程，YUV数据直接从解码回调获取
        
        Args:
            channel_id: 通道ID
            detection_model: 检测模型对象（可选）
        """
        print(f"[DEBUG-TM] start_detection_thread 被调用: channel_id={channel_id}")
        
        context = self.get_channel_context(channel_id)
        if not context:
            print(f"[DEBUG-TM] context为空!")
            return False
        
        print(f"[DEBUG-TM] channel_detect_status={context.channel_detect_status}")
        
        if context.channel_detect_status:
            print(f"[DEBUG-TM] 检测已启动，跳过")
            return True
        
        try:
            print(f"[线程管理器] {channel_id} 启动检测线程（直接从YUV队列获取数据，无捕获线程）")
            
            # 启用YUV队列（解码回调将YUV数据入队，供检测线程使用）
            if hasattr(context, 'capture_source') and context.capture_source:
                if hasattr(context.capture_source, 'enable_yuv_queue'):
                    context.capture_source.enable_yuv_queue(True, interval=0.1)  # 100ms间隔=10fps
                    print(f"[线程管理器] {channel_id} YUV队列已启用（解码回调直接入队，无需捕获线程中转）")
            
            # 导入全局检测线程
            from .threads.global_detection_thread import GlobalDetectionThread
            
            # 获取全局检测线程实例
            global_thread = GlobalDetectionThread.get_instance()
            
            # 启动全局检测线程（如果尚未启动）
            if not GlobalDetectionThread.is_detection_running():
                if not global_thread.start():
                    return False
            
            # 设置检测回调函数
            callback = context.on_detection_mission_result if hasattr(context, 'on_detection_mission_result') else None
            if not callback and self.on_detection_mission_result:
                callback = lambda ch_id, result: self.on_detection_mission_result(ch_id, result)
            
            # 🔥 先设置detection_enabled，再注册通道（register_channel内部会检查此状态）
            context.channel_detect_status = True
            context.detection_enabled = True
            
            # 注册通道到全局检测线程
            global_thread.register_channel(channel_id, context, callback)
            
            # 更新主窗口中的通道检测变量
            if self.main_window:
                detect_var_name = f'{channel_id}detect'
                setattr(self.main_window, detect_var_name, True)
                
                if hasattr(self.main_window, '_updateChannelColumnColor'):
                    self.main_window._updateChannelColumnColor()
            
            # 保持兼容性：设置一个占位符线程对象
            context.detection_thread = threading.Thread(
                target=lambda: None,
                name=f"Detection-{channel_id}-Placeholder",
                daemon=True
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
        
        #  检测线程启动时，根据 same 变量决定是否同步启动存储线程
        if self.same == 1:
            storage_success = self.start_storage_thread(channel_id)
        
        # 注意：曲线线程已改为全局单例，不再在检测线程启动时自动启动
        # 曲线线程的启动由 start_all_curve_threads() 统一管理
        
        return True
    
    def start_curve_thread(self, channel_id: str = None):
        """启动曲线绘制线程（全局单例版本）
        
        注意：此方法已改为全局单例管理，channel_id参数保留仅为向后兼容
        实际应该调用 start_global_curve_thread() 来启动全局曲线线程
        """
        # 向后兼容：如果没有指定channel_id，直接启动全局线程
        if channel_id is None:
            return self.start_global_curve_thread()
        
        # 如果指定了channel_id，设置统一的回调函数（如果还没有设置）
        # 线程由 start_global_curve_thread() 统一管理
        if self.on_curve_updated:
            from .threads.curve_thread import CurveThread
            CurveThread.set_callback(self.on_curve_updated)
        
        return True
    
    def start_global_curve_thread(self):
        """启动全局单例曲线线程（基于CSV文件的增量读取，支持进度条）
        
        数据流：
        1. 启动时：加载本地CSV文件的历史数据
        2. 同步模式（检测运行中）：从存储线程内存缓冲区读取实时数据
        3. 历史模式（检测停止）：监控CSV文件变化，增量读取
        """
        import os
        from .threads.curve_thread import CurveThread
        
        # 如果已经运行，直接返回
        if CurveThread.is_running():
            return True
        
        # 🔥 从主窗口的 curvemission 获取任务路径
        current_mission_path = None
        if self.main_window and hasattr(self.main_window, '_getCurveMissionPath'):
            current_mission_path = self.main_window._getCurveMissionPath()
        else:
            return False
        
        # 🔥 检查是否有检测线程运行，决定是否启用同步模式
        detection_running = False
        if self.main_window and hasattr(self.main_window, '_getCurrentDetectionState'):
            detection_running = self.main_window._getCurrentDetectionState()
        
        # 设置同步模式：检测运行中时从内存读取实时数据
        CurveThread.set_sync_mode(detection_running)
        CurveThread.reset_memory_indices()  # 重置内存数据索引
        
        # 🔥 检查是否需要显示进度条
        show_progress = False
        progress_dialog = None
        
        if current_mission_path and os.path.exists(current_mission_path):
            # 查找所有CSV文件
            csv_files = [f for f in os.listdir(current_mission_path) if f.endswith('.csv')]
            
            if len(csv_files) > 1:
                # 条件1：多个CSV文件
                show_progress = True
            elif len(csv_files) == 1:
                # 条件2：单个CSV文件大小超过8MB
                csv_path = os.path.join(current_mission_path, csv_files[0])
                file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
                if file_size_mb > 8:
                    show_progress = True
        
        # 🔥 创建进度对话框（仅在需要时）
        progress_dialog = None
        progress_signal = None
        
        if show_progress:
            try:
                from qtpy import QtWidgets, QtCore
                from widgets.style_manager import DialogManager
                
                # 🔥 使用全局DialogManager创建进度对话框
                progress_dialog = DialogManager.create_progress_dialog(
                    parent=None,  # 全局进度条，无父窗口
                    title="曲线数据加载进度",
                    label_text="正在加载曲线数据...",
                    icon_name="动态曲线",
                    cancelable=False  # 不可取消
                )
                progress_dialog.setWindowModality(QtCore.Qt.ApplicationModal)
                progress_dialog.setMinimumWidth(400)
                progress_dialog.show()
                QtWidgets.QApplication.processEvents()
                
                # 🔥 创建进度信号对象并连接到槽函数
                progress_signal = ProgressSignal()
                progress_signal.progress_updated.connect(
                    lambda value, text: self._updateProgressDialog(progress_dialog, value, text)
                )
                
                # 🔥 设置进度回调到全局曲线线程（使用信号发射）
                CurveThread.set_progress_callback(
                    lambda value, text: progress_signal.progress_updated.emit(value, text)
                )
                
                # 🔥 强制刷新UI，确保进度对话框完全显示
                QtWidgets.QApplication.processEvents()
                import time
                time.sleep(0.05)  # 给进度对话框50ms时间完全显示
            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_dialog = None
        
        # 使用统一的回调函数（回调函数内部根据channel_id参数区分通道）
        callback = self.on_curve_updated if self.on_curve_updated else None
        
        # 启动全局曲线线程
        curve_thread = threading.Thread(
            target=CurveThread.run,
            args=(current_mission_path, callback),
            name="GlobalCurveThread",
            daemon=True
        )
        curve_thread.start()
        
        return True
    
    def _updateProgressDialog(self, progress_dialog, value, text):
        """更新进度对话框（通过Qt信号机制，确保在主线程执行）"""
        try:
            if not progress_dialog:
                return
            
            # 🔥 直接更新进度条（已经通过信号机制在主线程中）
            from qtpy import QtWidgets, QtCore
            
            progress_dialog.setValue(value)
            progress_dialog.setLabelText(text)
            
            # 强制刷新UI，确保进度条立即显示
            QtWidgets.QApplication.processEvents()
            
            # 加载完成时关闭进度条
            if value >= 100:
                QtCore.QTimer.singleShot(100, lambda: self._closeProgressDialog(progress_dialog))
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _closeProgressDialog(self, progress_dialog):
        """关闭进度对话框"""
        try:
            if progress_dialog:
                progress_dialog.close()
                progress_dialog.deleteLater()
        except Exception as e:
            pass
    
    def start_storage_thread(self, channel_id: str, storage_path: str = None):
        """启动存储线程
        
        Args:
            channel_id: 通道ID
            storage_path: 存储路径（已废弃，现在从通道配置读取）
        """
        context = self.get_channel_context(channel_id)
        if not context:
            return False
        
        if context.storage_flag:
            return True
        
        # 存储路径现在从通道配置读取，不再使用 recordings 路径
        # storage_path 参数保留但不使用，保持向后兼容
        
        context.storage_flag = True
        context.storage_thread = threading.Thread(
            target=self._storage_loop,
            args=(channel_id,),
            name=f"Storage-{channel_id}",
            daemon=True
        )
        context.storage_thread.start()
        return True
    
    # ==================== 线程停止 ====================
    
    def stop_display_thread(self, channel_id: str):
        """停止显示线程"""
        context = self.get_channel_context(channel_id)
        if not context:
            return
        
        context.display_flag = False
        if context.display_thread and context.display_thread.is_alive():
            context.display_thread.join(timeout=2.0)
    
    def stop_detection_thread(self, channel_id: str):
        """停止检测线程（使用全局检测线程架构）
        
        解码渲染线程模式下，此方法会：
        1. 禁用HKcapture的YUV队列
        2. 从全局检测线程注销通道
        
        注意：渲染继续由PlayCtrl SDK内部管理，只是不再缓存YUV数据
        """
        context = self.get_channel_context(channel_id)
        if not context:
            return
        
        try:
            print(f"[线程管理器] {channel_id} 停止检测线程（禁用YUV队列，渲染继续）")
            
            # 禁用YUV队列（停止缓存YUV数据，渲染继续）
            if hasattr(context, 'capture_source') and context.capture_source:
                if hasattr(context.capture_source, 'enable_yuv_queue'):
                    context.capture_source.enable_yuv_queue(False)
                    print(f"[线程管理器] {channel_id} YUV队列已禁用（渲染继续由PlayCtrl SDK管理）")
            
            # 导入全局检测线程
            from .threads.global_detection_thread import GlobalDetectionThread
            
            # 获取全局检测线程实例
            global_thread = GlobalDetectionThread.get_instance()
            
            # 从全局检测线程注销通道
            global_thread.unregister_channel(channel_id)
            
            # 更新通道状态
            context.channel_detect_status = False
            context.detection_enabled = False
            
            # 更新主窗口中的通道检测变量
            if self.main_window:
                detect_var_name = f'{channel_id}detect'
                setattr(self.main_window, detect_var_name, False)
                
                if hasattr(self.main_window, '_updateChannelColumnColor'):
                    self.main_window._updateChannelColumnColor()
            
            # 检查是否还有其他活跃通道，如果没有则停止全局线程
            if not global_thread.active_channels:
                global_thread.stop()
            
            print(f"[线程管理器] {channel_id} 检测线程已停止")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        # 检测线程停止时，根据 same 变量决定是否同步停止存储线程
        if self.same == 1:
            self.stop_storage_thread(channel_id)
    
    def stop_curve_thread(self, channel_id: str = None):
        """停止曲线绘制线程（全局单例版本）
        
        注意：此方法已改为全局单例管理，channel_id参数保留仅为向后兼容
        实际应该调用 stop_global_curve_thread() 来停止全局曲线线程
        """
        # 向后兼容：如果没有指定channel_id，直接停止全局线程
        if channel_id is None:
            return self.stop_global_curve_thread()
        
        # 注意：曲线线程使用统一的回调函数，不需要按通道取消注册
        # 停止线程时统一清除回调即可
    
    def stop_global_curve_thread(self):
        """停止全局单例曲线线程"""
        from .threads.curve_thread import CurveThread
        
        # 清除进度回调
        CurveThread.clear_progress_callback()
        
        CurveThread.stop()
        
        # 等待线程结束
        import time
        timeout = 2.0
        start_time = time.time()
        while CurveThread.is_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        pass
    
    def stop_storage_thread(self, channel_id: str):
        """停止存储线程"""
        context = self.get_channel_context(channel_id)
        if not context:
            return
        
        context.storage_flag = False
        if context.storage_thread and context.storage_thread.is_alive():
            context.storage_thread.join(timeout=2.0)
    
    def stop_all_threads(self, channel_id: str):
        """停止指定通道的所有线程"""
        self.stop_display_thread(channel_id)
        self.stop_detection_thread(channel_id)
        # 注意：曲线线程已改为全局单例，不在这里停止
        # 曲线线程的停止由 stop_all_curve_threads() 统一管理
        self.stop_storage_thread(channel_id)
    
    def start_all_curve_threads(self):
        """
        启动全局单例曲线线程（支持所有通道）
        
        ️ 重要：此方法只应在 _video_layout_mode == 1（曲线模式）时调用
        由 ViewHandler._startAllCurveThreads() 调用，已在外部做模式检查
        
        用于切换到曲线模式布局时启动全局曲线线程
        """
        # 🔥 不要在这里设置回调，start_global_curve_thread 会处理
        # 避免重复设置导致数据被处理两次
        
        # 启动全局曲线线程（如果尚未启动）
        return self.start_global_curve_thread()
    
    def stop_all_curve_threads(self):
        """
        停止全局单例曲线线程
        
        强制停止全局曲线线程，确保不在后台运行
        用于切换回默认模式（_video_layout_mode != 1）时停止曲线线程
        """
        # 清除统一的回调函数
        from .threads.curve_thread import CurveThread
        CurveThread.clear_callback()
        
        # 停止全局曲线线程
        self.stop_global_curve_thread()
    
    # ==================== 线程循环实现 ====================
    
    def _detection_loop(self, channel_id: str):
        """检测线程循环
        
        职责：
        1. 从 latest_frame 读取最新帧（非消费性读取）
        2. 使用检测引擎进行推理
        3. 输出检测结果到检测结果队列
        4. 更新 latest_detection（供显示线程使用）
        """
        context = self.contexts[channel_id]
        
        # 使用独立的 DetectionThread 类执行检测
        from .threads.detection_thread import DetectionThread
        
        # 获取检测帧率
        detection_frame_rate = getattr(self, 'detection_frame_rate', 25.0)
        
        #  从远程配置读取批处理设置
        batch_processing_enabled = False # 默认值
        default_batch_size = 4  # 默认值
        
        try:
            # 使用远程配置管理器
            try:
                from ....utils.config import RemoteConfigManager
            except ImportError:
                from utils.config import RemoteConfigManager
            
            remote_config_manager = RemoteConfigManager()
            config = remote_config_manager.load_default_config()
            
            if config:
                batch_processing_enabled = config.get('batch_processing_enabled', True)
                default_batch_size = config.get('default_batch_size', 4)
                
                print(f" [{channel_id}] 批处理配置: enabled={batch_processing_enabled}, batch_size={default_batch_size}")
            else:
                print(f"️  [{channel_id}] 无法加载远程配置，使用默认值")
        except Exception as e:
            print(f"️  [{channel_id}] 加载配置失败，使用默认值: {e}")
        
        #  使用 context 中独立的检测模型（而不是全局的 self.detection_model）
        # 运行检测线程（使用context中的独立回调）
        DetectionThread.run(
            context=context,
            frame_rate=detection_frame_rate,
            detection_model=context.detection_model,  #  从 context 获取
            on_detection_mission_result=context.on_detection_mission_result,
            batch_size=default_batch_size,  #  从配置文件读取
            use_batch=batch_processing_enabled  #  从配置文件读取
        )
    
    def _storage_loop(self, channel_id: str):
        """存储线程循环
        
        职责：
        1. 从检测结果队列读取液位数据，保存为CSV曲线文件
        2. 从原始帧队列读取帧（原始视频）- 占坑
        3. 从显示帧队列读取帧（检测结果视频）- 占坑
        """
        context = self.contexts[channel_id]
        
        # 使用独立的 StorageThread 类执行存储
        from .threads.storage_thread import StorageThread
        
        # 获取存储帧率
        storage_frame_rate = getattr(self, 'save_data_rate', 25.0)
        
        # 🔥 传递主窗口实例，让存储线程从通道的 channelmission 标签获取路径
        # 运行存储线程
        StorageThread.run(
            context=context,
            frame_rate=storage_frame_rate,
            main_window=self.main_window
        )
    
    # ==================== 辅助方法 ====================
    
    def _run_detection(self, frame):
        """执行检测
        
        Args:
            frame: 输入图像帧
        
        Returns:
            dict: 检测结果，格式：
            {
                'timestamp': float,
                'boxes': [[x1, y1, x2, y2], ...],
                'scores': [0.95, 0.87, ...],
                'classes': [0, 1, ...],
                'class_names': ['person', 'car', ...],
                'count': int,
                'custom_data': {}  # 自定义数据
            }
        """
        mission_result = {
            'timestamp': time.time(),
            'boxes': [],
            'scores': [],
            'classes': [],
            'class_names': [],
            'count': 0,
            'custom_data': {}
        }
        
        try:
            if self.detection_model is not None:
                # 使用实际的检测模型
                predictions = self.detection_model.predict(frame)
                
                # 解析模型输出（根据实际模型调整）
                if hasattr(predictions, 'boxes'):
                    mission_result['boxes'] = predictions.boxes.xyxy.cpu().numpy().tolist()
                    mission_result['scores'] = predictions.boxes.conf.cpu().numpy().tolist()
                    mission_result['classes'] = predictions.boxes.cls.cpu().numpy().tolist()
                    mission_result['count'] = len(mission_result['boxes'])
            else:
                # 无模型时返回空结果
                pass
                
        except Exception as e:
            pass
        
        return mission_result
    
    def _draw_detection_mission_result(self, frame, detection_mission_result):
        """在帧上绘制检测结果
        
        Args:
            frame: 输入图像帧
            detection_mission_result: 检测结果字典
        
        Returns:
            numpy.ndarray: 绘制后的图像
        """
        frame_draw = frame.copy()
        
        try:
            boxes = detection_mission_result.get('boxes', [])
            scores = detection_mission_result.get('scores', [])
            class_names = detection_mission_result.get('class_names', [])
            
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                score = scores[i] if i < len(scores) else 0
                class_name = class_names[i] if i < len(class_names) else f"Class {i}"
                
                # 绘制边界框
                cv2.rectangle(frame_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # 绘制标签
                label = f"{class_name}: {score:.2f}"
                cv2.putText(
                    frame_draw, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
                )
            
            # 绘制统计信息
            count = detection_mission_result.get('count', 0)
            info_text = f"Objects: {count}"
            cv2.putText(
                frame_draw, info_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
            
        except Exception as e:
            pass
        
        return frame_draw
    
    # ==================== 状态查询 ====================
    
    def get_thread_status(self, channel_id: str) -> dict:
        """获取线程状态
        
        Returns:
            dict: 线程状态信息
        """
        context = self.get_channel_context(channel_id)
        if not context:
            return {}
        
        return {
            'channel_id': channel_id,
            'display': {
                'running': context.display_flag,
                'count': context.display_count
            },
            'detection': {
                'running': context.channel_detect_status,
                'count': context.detection_count,
                'enabled': context.detection_enabled
            },
            'curve': {
                'running': False,  # 注意：曲线线程已改为全局单例，不再存储在context中
                'data_points': len(context.curve_data)
            },
            'storage': {
                'running': context.storage_flag,
                'count': context.storage_count,
                'path': context.storage_path
            }
        }
    
    def get_all_status(self) -> dict:
        """获取所有通道的线程状态"""
        return {
            channel_id: self.get_thread_status(channel_id)
            for channel_id in self.contexts.keys()
        }

