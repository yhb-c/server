# -*- coding: utf-8 -*-

"""
全局检测线程 - 极简版（直接YUV数据流，无中间层）

优化重点：
1. 删除帧收集器(FrameCollector)，直接从HKcapture的YUV队列获取数据
2. 删除调度器(SimpleScheduler)，直接按模型分组处理
3. 删除结果分发器(ResultDistributor)，直接写入队列和触发回调
4. 参考demo的高效实现，无帧率限制，全速处理
5. 先裁剪ROI的YUV再转RGB，减少80%开销

数据流（极简）：
  解码回调 → YUV队列 → 检测线程取出 → 裁剪ROI的YUV → YUV转RGB → 模型推理 → 直接分发结果
"""

import time
import threading
import queue
import os
import yaml
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque
import cv2
import numpy as np


class GlobalDetectionThread:
    """全局检测线程类 - 极简版
    
    直接从HKcapture的YUV队列获取数据，无中间层
    """
    
    # 全局单例实例
    _instance = None
    _lock = threading.Lock()
    
    # 全局状态变量：True代表检测线程运行中，False代表关闭
    detection_state = False
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化全局检测线程"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # ========== 线程控制 ==========
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        
        # ========== 核心组件（只保留模型池）==========
        self.model_pool_manager = None      # 模型池管理器（必要）
        
        # ========== 通道管理 ==========
        self.active_channels = set()        # 活跃通道集合
        self.channel_contexts = {}          # 通道上下文字典 {channel_id: context}
        self.channel_callbacks = {}         # 通道回调函数 {channel_id: callback}
        self._ready_channels = []           # 就绪通道缓存（避免每帧检查状态）
        self._ready_channels_lock = threading.Lock()  # 缓存锁
        
        # ========== 配置参数 ==========
        self.batch_processing_enabled = True # 批处理开关
        self.default_batch_size = 4         # 默认批大小
        
        # ========== 性能监控 ==========
        self.stats = {
            'total_frames_processed': 0,
            'total_batches_processed': 0,
            'model_switches': 0,
            'average_batch_size': 0.0,
            'processing_times': deque(maxlen=1000),
            'yuv_convert_times': deque(maxlen=1000),
            'inference_times': deque(maxlen=1000),
            'distribute_times': deque(maxlen=1000)
        }
    
    @classmethod
    def get_instance(cls):
        """获取全局单例实例"""
        return cls()
    
    @classmethod
    def get_detection_state(cls):
        """获取全局检测状态"""
        return cls.detection_state
    
    @classmethod
    def is_detection_running(cls):
        """检查检测线程是否正在运行"""
        return cls.detection_state
    
    def is_running(self) -> bool:
        """检查线程是否正在运行"""
        return self._running
    
    def start(self) -> bool:
        """启动全局检测线程"""
        if self._running:
            return True
        
        try:
            # 加载配置
            self._load_config()
            
            # 初始化核心组件
            self._initialize_components()
            
            # 启动线程
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._main_loop_simplified,
                name="GlobalDetectionThread",
                daemon=True
            )
            self._thread.start()
            self._running = True
            
            # 更新全局状态变量
            GlobalDetectionThread.detection_state = True
            
            print(f"[全局检测线程] 启动成功（简化版，直接YUV数据流）")
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            GlobalDetectionThread.detection_state = False
            self._running = False
            return False
    
    def stop(self) -> bool:
        """停止全局检测线程"""
        if not self._running:
            return True
        
        try:
            self._stop_event.set()
            self._running = False
            GlobalDetectionThread.detection_state = False
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
            
            self._cleanup_resources()
            print(f"🛑 [全局检测线程] 已停止")
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            GlobalDetectionThread.detection_state = False
            self._running = False
            return False
    
    def register_channel(self, channel_id: str, context, callback: Optional[Callable] = None):
        """注册通道到全局检测线程"""
        self.active_channels.add(channel_id)
        self.channel_contexts[channel_id] = context
        if callback:
            self.channel_callbacks[channel_id] = callback
        
        # 启用该通道的YUV队列
        if hasattr(context, 'capture_source') and context.capture_source:
            context.capture_source.enable_yuv_queue(True, interval=0.1)
        
        # 更新就绪通道缓存
        self._update_ready_channels()
        print(f"[全局检测线程] 通道 {channel_id} 已注册")
    
    def unregister_channel(self, channel_id: str):
        """注销通道"""
        # 禁用该通道的YUV队列
        context = self.channel_contexts.get(channel_id)
        if context and hasattr(context, 'capture_source') and context.capture_source:
            context.capture_source.enable_yuv_queue(False)
        
        self.active_channels.discard(channel_id)
        self.channel_contexts.pop(channel_id, None)
        self.channel_callbacks.pop(channel_id, None)
        
        # 更新就绪通道缓存
        self._update_ready_channels()
        print(f"[全局检测线程] 通道 {channel_id} 已注销")
    
    def _update_ready_channels(self):
        """更新就绪通道缓存（在注册/注销/状态变化时调用）"""
        ready = []
        
        for channel_id in self.active_channels:
            context = self.channel_contexts.get(channel_id)
            if not context:
                continue
            
            # 检查通道是否启用检测
            if not getattr(context, 'detection_enabled', False):
                continue
            
            # 获取capture_source
            capture_source = getattr(context, 'capture_source', None)
            if not capture_source:
                continue
            
            # 检查YUV队列是否启用
            if not getattr(capture_source, '_yuv_queue_enabled', False):
                continue
            
            ready.append((channel_id, context, capture_source))
        
        with self._ready_channels_lock:
            self._ready_channels = ready
    
    def update_channel_state(self, channel_id: str):
        """通道状态变化时调用，更新就绪缓存"""
        self._update_ready_channels()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
            config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                self.batch_processing_enabled = config.get('batch_processing_enabled', True)
                self.default_batch_size = config.get('default_batch_size', 4)
                
        except Exception as e:
            pass
    
    def _initialize_components(self):
        """初始化核心组件（极简版 - 只保留模型池）"""
        try:
            # 模型池管理器（必要，管理多模型共享）
            from ..model_pool_manager import ModelPoolManager
            if self.model_pool_manager is None:
                self.model_pool_manager = ModelPoolManager()
            
            if not self.model_pool_manager.is_initialized:
                if not self.model_pool_manager.initialize():
                    raise Exception("模型池管理器初始化失败")
            
            # 不再初始化 ResultDistributor，直接在检测线程内分发结果
            
            print(f"[全局检测线程] 核心组件初始化完成（极简版，无中间层）")
            
        except Exception as e:
            raise
    
    def _main_loop_simplified(self):
        """简化版主循环 - 直接从YUV队列获取数据
        
        参考demo的高效实现：
        1. 遍历就绪通道，从YUV队列获取数据
        2. 先裁剪ROI再转RGB（减少开销）
        3. 按模型分组后批量推理
        4. 分发结果
        5. 无帧时短暂等待5ms
        """
        while not self._stop_event.is_set():
            try:
                # 获取就绪通道快照（避免锁竞争）
                with self._ready_channels_lock:
                    ready_channels = self._ready_channels.copy()
                
                if not ready_channels:
                    time.sleep(0.1)
                    continue
                
                # 1. 直接从各通道的YUV队列收集数据（先裁剪ROI再转RGB）
                collected_data = self._collect_yuv_frames_fast(ready_channels)
                
                if not collected_data:
                    # 没有新帧，短暂等待后继续（类似demo的5ms等待）
                    time.sleep(0.005)
                    continue
                
                loop_start = time.time()
                
                # 2. 按模型分组
                model_groups = self._group_by_model(collected_data)
                
                # 3. 批量推理
                results = self._process_model_groups(model_groups)
                
                # 4. 分发结果
                if results:
                    self._distribute_results_direct(results)
                
                # 5. 更新统计
                loop_time = time.time() - loop_start
                self.stats['processing_times'].append(loop_time)
                self.stats['total_frames_processed'] += len(collected_data)
                
            except Exception as e:
                self.logger.error(f"[DEBUG] 主循环异常: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
    
    def _collect_yuv_frames_fast(self, ready_channels: List) -> List[Dict[str, Any]]:
        """从就绪通道收集YUV帧，先裁剪ROI再转RGB
        
        数据流：YUV队列 → 裁剪ROI的YUV → YUV转RGB → 返回ROI的RGB图像列表
        
        Args:
            ready_channels: 就绪通道列表 [(channel_id, context, capture_source), ...]
            
        Returns:
            List[Dict]: 收集到的帧数据列表，每个ROI一条记录
        """
        collected = []
        
        for channel_id, context, capture_source in ready_channels:
            # 相机姿态异常检查
            if getattr(context, 'camera_position_paused', False):
                continue
            
            # 从YUV队列获取数据（非阻塞）
            yuv_data_tuple = capture_source.get_yuv_data_nowait()
            if not yuv_data_tuple:
                continue
            
            if len(yuv_data_tuple) != 4:
                continue
            
            yuv_data, width, height, timestamp = yuv_data_tuple
            
            # 获取通道的ROI配置
            roi_list = self._get_channel_roi_config(channel_id)
            
            convert_start = time.time()
            
            if roi_list:
                # 有ROI配置：先裁剪ROI区域的YUV，再转RGB（减少80%开销）
                roi_frames = []
                for roi_x, roi_y, roi_w, roi_h in roi_list:
                    rgb_roi = self._crop_yuv_roi_to_rgb(yuv_data, width, height, roi_x, roi_y, roi_w, roi_h)
                    if rgb_roi is not None:
                        roi_frames.append(rgb_roi)
                
                if not roi_frames:
                    continue
                
                convert_time = time.time() - convert_start
                self.stats['yuv_convert_times'].append(convert_time)
                
                # 每个通道返回一条记录，包含所有ROI的RGB图像
                collected.append({
                    'channel_id': channel_id,
                    'width': width,
                    'height': height,
                    'timestamp': timestamp,
                    'frame': roi_frames[0] if len(roi_frames) == 1 else roi_frames,  # 单ROI返回单帧，多ROI返回列表
                    'roi_frames': roi_frames,
                    'frame_shape': roi_frames[0].shape if roi_frames else None
                })
            else:
                # 无ROI配置：转换完整帧（兼容旧逻辑）
                rgb_frame = self._yuv_to_rgb(yuv_data, width, height)
                convert_time = time.time() - convert_start
                self.stats['yuv_convert_times'].append(convert_time)
                
                if rgb_frame is None:
                    continue
                
                collected.append({
                    'channel_id': channel_id,
                    'width': width,
                    'height': height,
                    'timestamp': timestamp,
                    'frame': rgb_frame,
                    'frame_shape': rgb_frame.shape
                })
        
        return collected
    
    def _yuv_to_rgb(self, yuv_data: bytes, width: int, height: int) -> Optional[np.ndarray]:
        """YUV420(I420)转RGB - 完整帧转换
        
        Args:
            yuv_data: YUV420原始数据
            width: 帧宽度
            height: 帧高度
            
        Returns:
            RGB图像，失败返回None
        """
        try:
            expected_size = width * height * 3 // 2
            if len(yuv_data) != expected_size:
                return None
            
            yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
            yuv_reshaped = yuv_array.reshape((height * 3 // 2, width))
            rgb_frame = cv2.cvtColor(yuv_reshaped, cv2.COLOR_YUV2RGB_I420)
            return rgb_frame
        except Exception:
            return None
    
    def _crop_yuv_roi(self, yuv_data: bytes, width: int, height: int, 
                      roi_x: int, roi_y: int, roi_w: int, roi_h: int) -> Optional[tuple]:
        """从I420 YUV数据中裁剪ROI区域
        
        I420格式内存布局：
        - Y平面: width * height 字节（完整分辨率）
        - U平面: (width/2) * (height/2) 字节（1/4分辨率）
        - V平面: (width/2) * (height/2) 字节（1/4分辨率）
        
        Args:
            yuv_data: 完整帧的YUV420数据
            width: 完整帧宽度
            height: 完整帧高度
            roi_x, roi_y: ROI左上角坐标（会对齐到偶数）
            roi_w, roi_h: ROI宽高（会对齐到偶数）
            
        Returns:
            (裁剪后的YUV数据bytes, roi_w, roi_h)，失败返回None
        """
        try:
            # ROI坐标和尺寸必须对齐到偶数（UV平面是Y的1/2）
            roi_x = roi_x & ~1  # 向下对齐到偶数
            roi_y = roi_y & ~1
            roi_w = (roi_w + 1) & ~1  # 向上对齐到偶数
            roi_h = (roi_h + 1) & ~1
            
            # 边界检查
            if roi_x < 0:
                roi_x = 0
            if roi_y < 0:
                roi_y = 0
            if roi_x + roi_w > width:
                roi_w = width - roi_x
            if roi_y + roi_h > height:
                roi_h = height - roi_y
            
            if roi_w <= 0 or roi_h <= 0:
                return None
            
            yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
            
            # 计算各平面偏移
            y_size = width * height
            uv_width = width // 2
            uv_height = height // 2
            u_offset = y_size
            v_offset = y_size + uv_width * uv_height
            
            # 提取Y平面并裁剪
            y_plane = yuv_array[:y_size].reshape((height, width))
            y_roi = y_plane[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w].copy()
            
            # UV坐标是Y的一半
            uv_roi_x = roi_x // 2
            uv_roi_y = roi_y // 2
            uv_roi_w = roi_w // 2
            uv_roi_h = roi_h // 2
            
            # 提取U平面并裁剪
            u_plane = yuv_array[u_offset:v_offset].reshape((uv_height, uv_width))
            u_roi = u_plane[uv_roi_y:uv_roi_y+uv_roi_h, uv_roi_x:uv_roi_x+uv_roi_w].copy()
            
            # 提取V平面并裁剪
            v_plane = yuv_array[v_offset:].reshape((uv_height, uv_width))
            v_roi = v_plane[uv_roi_y:uv_roi_y+uv_roi_h, uv_roi_x:uv_roi_x+uv_roi_w].copy()
            
            # 合并为I420格式
            roi_yuv = np.concatenate([y_roi.flatten(), u_roi.flatten(), v_roi.flatten()])
            
            return (roi_yuv.tobytes(), roi_w, roi_h)
            
        except Exception as e:
            return None
    
    def _crop_yuv_roi_to_rgb(self, yuv_data: bytes, width: int, height: int,
                              roi_x: int, roi_y: int, roi_w: int, roi_h: int) -> Optional[np.ndarray]:
        """裁剪YUV的ROI区域并转换为RGB
        
        先裁剪ROI区域的YUV数据，再转换为RGB，减少不必要的开销
        
        Args:
            yuv_data: 完整帧的YUV420数据
            width: 完整帧宽度
            height: 完整帧高度
            roi_x, roi_y: ROI左上角坐标
            roi_w, roi_h: ROI宽高
            
        Returns:
            ROI区域的RGB图像，失败返回None
        """
        try:
            # 裁剪YUV
            result = self._crop_yuv_roi(yuv_data, width, height, roi_x, roi_y, roi_w, roi_h)
            if result is None:
                return None
            
            roi_yuv_bytes, actual_w, actual_h = result
            
            # 转换为RGB
            roi_yuv_array = np.frombuffer(roi_yuv_bytes, dtype=np.uint8)
            roi_yuv_reshaped = roi_yuv_array.reshape((actual_h * 3 // 2, actual_w))
            rgb_roi = cv2.cvtColor(roi_yuv_reshaped, cv2.COLOR_YUV2RGB_I420)
            
            return rgb_roi
            
        except Exception as e:
            return None
    
    def _get_channel_roi_config(self, channel_id: str) -> Optional[List[tuple]]:
        """获取通道的ROI配置
        
        从model_pool_manager的缓存中获取通道的ROI配置
        
        Args:
            channel_id: 通道ID
            
        Returns:
            ROI列表 [(x, y, w, h), ...] 或 None
        """
        try:
            if not self.model_pool_manager:
                return None
            
            # 从缓存获取标注配置
            annotation_config = self.model_pool_manager._annotation_config_cache.get(channel_id)
            if not annotation_config:
                return None
            
            boxes = annotation_config.get('boxes', [])
            if not boxes:
                return None
            
            # 转换为 (x, y, w, h) 格式
            roi_list = []
            for box in boxes:
                if len(box) >= 3:
                    cx, cy, size = box[0], box[1], box[2]
                    half = size // 2
                    x = cx - half
                    y = cy - half
                    roi_list.append((x, y, size, size))
            
            return roi_list if roi_list else None
            
        except Exception as e:
            return None
    
    def _group_by_model(self, collected_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按模型ID分组帧数据
        
        Args:
            collected_data: 收集到的帧数据列表
            
        Returns:
            Dict: {model_id: [frame_data1, frame_data2, ...]}
        """
        model_groups = defaultdict(list)
        
        for frame_data in collected_data:
            channel_id = frame_data['channel_id']
            model_id = self._get_model_id_for_channel(channel_id)
            if model_id:
                model_groups[model_id].append(frame_data)
        
        return dict(model_groups)
    
    def _get_model_id_for_channel(self, channel_id: str) -> Optional[str]:
        """获取通道对应的模型ID"""
        if self.model_pool_manager and hasattr(self.model_pool_manager, 'channel_model_mapping'):
            return self.model_pool_manager.channel_model_mapping.get(channel_id)
        return None
    
    def _process_model_groups(self, model_groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """处理按模型分组的帧数据
        
        Args:
            model_groups: {model_id: [frame_data1, frame_data2, ...]}
            
        Returns:
            List[Dict]: 检测结果列表
        """
        all_results = []
        
        for model_id, frames in model_groups.items():
            if not frames:
                continue
            
            batch = {
                'model_id': model_id,
                'frames': frames,
                'batch_size': len(frames),
                'priority': 'normal',
                'timestamp': time.time()
            }
            
            inference_start = time.time()
            try:
                batch_results = self.model_pool_manager.process_batches([batch])
                inference_time = time.time() - inference_start
                self.stats['inference_times'].append(inference_time)
                
                if batch_results:
                    all_results.extend(batch_results)
                    self.stats['total_batches_processed'] += 1
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        return all_results
    
    def _distribute_results_direct(self, results: List[Dict[str, Any]]):
        """直接分发检测结果（无中间层，直接写入队列和触发回调）
        
        Args:
            results: 检测结果列表 [{'channel_id': str, 'result': dict}, ...]
        """
        if not results:
            return
        
        distribute_start = time.time()
        
        try:
            for result_data in results:
                channel_id = result_data.get('channel_id')
                detection_result = result_data.get('result')
                
                if not channel_id or not detection_result:
                    continue
                
                context = self.channel_contexts.get(channel_id)
                if not context:
                    continue
                
                # 1. 放入检测结果队列（供曲线绘制使用）
                if hasattr(context, 'detection_mission_results'):
                    try:
                        if context.detection_mission_results.full():
                            context.detection_mission_results.get_nowait()  # 丢弃旧数据
                        context.detection_mission_results.put_nowait(detection_result)
                    except:
                        pass
                
                # 2. 放入存储数据队列（供存储线程使用）
                if 'liquid_line_positions' in detection_result and hasattr(context, 'storage_data'):
                    try:
                        if context.storage_data.full():
                            context.storage_data.get_nowait()
                        context.storage_data.put_nowait(detection_result)
                    except:
                        pass
                
                # 3. 更新最新检测结果（供显示线程使用）
                if hasattr(context, 'detection_lock') and hasattr(context, 'latest_detection'):
                    try:
                        with context.detection_lock:
                            context.latest_detection = detection_result
                    except:
                        pass
                
                # 4. 触发回调函数
                callback = self.channel_callbacks.get(channel_id)
                if callback:
                    try:
                        callback(channel_id, detection_result)
                    except Exception as e:
                        pass
            
            distribute_time = time.time() - distribute_start
            self.stats['distribute_times'].append(distribute_time)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _cleanup_resources(self):
        """清理资源"""
        try:
            # 禁用所有通道的YUV队列
            for channel_id, context in self.channel_contexts.items():
                if hasattr(context, 'capture_source') and context.capture_source:
                    context.capture_source.enable_yuv_queue(False)
            
            self.active_channels.clear()
            self.channel_contexts.clear()
            self.channel_callbacks.clear()
            
        except Exception as e:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = self.stats.copy()
        
        # 计算平均处理时间
        if self.stats['processing_times']:
            stats['avg_loop_time_ms'] = np.mean(list(self.stats['processing_times'])) * 1000
        else:
            stats['avg_loop_time_ms'] = 0.0
        
        # 计算平均YUV转换时间
        if self.stats['yuv_convert_times']:
            stats['avg_yuv_convert_ms'] = np.mean(list(self.stats['yuv_convert_times'])) * 1000
        else:
            stats['avg_yuv_convert_ms'] = 0.0
        
        # 计算平均推理时间
        if self.stats['inference_times']:
            stats['avg_inference_ms'] = np.mean(list(self.stats['inference_times'])) * 1000
        else:
            stats['avg_inference_ms'] = 0.0
        
        # 计算平均分发时间
        if self.stats['distribute_times']:
            stats['avg_distribute_ms'] = np.mean(list(self.stats['distribute_times'])) * 1000
        else:
            stats['avg_distribute_ms'] = 0.0
        
        # 添加模型池统计
        if self.model_pool_manager and hasattr(self.model_pool_manager, 'get_stats'):
            stats['model_pool'] = self.model_pool_manager.get_stats()
        
        return stats
