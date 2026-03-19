# -*- coding: utf-8 -*-

"""
帧收集器 - 全局检测线程架构核心组件

职责：
1. 统一收集各通道的帧数据
2. 按模型类型对帧进行分组
3. 维护帧的时间戳和通道元数据
4. 优化帧收集性能，避免不必要的拷贝
5. 🔥 支持YUV直接裁剪ROI模式（高性能）

设计原则：
- 使用非阻塞队列操作，避免线程阻塞
- 按模型类型分组，为智能调度做准备
- 保持帧的完整元数据（通道ID、时间戳等）
- 实现帧丢弃策略，处理队列积压情况
- YUV模式：直接从解码回调获取YUV数据，裁剪ROI后转RGB
"""

import time
import queue
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import cv2
import numpy as np

# 导入YUV处理器
try:
    from .yuv_processor import YUVProcessor
except ImportError:
    from yuv_processor import YUVProcessor


class FrameCollector:
    """帧收集器
    
    统一收集各通道的帧数据并按模型类型分组
    支持两种模式：
    1. 传统模式：从frame_buffer获取RGB帧
    2. YUV模式：从HKcapture的YUV队列获取数据，直接裁剪ROI
    """
    
    def __init__(self, model_pool_manager=None):
        """初始化帧收集器
        
        Args:
            model_pool_manager: 模型池管理器实例，用于获取通道到模型的映射
        """
        # ========== 核心组件 ==========
        self.model_pool_manager = model_pool_manager
        
        # ========== YUV处理器 ==========
        self.yuv_processor = YUVProcessor()
        
        # ========== ROI配置缓存 ==========
        self._roi_cache = {}  # {channel_id: [(x, y, w, h), ...]}
        self._roi_cache_time = {}  # {channel_id: timestamp}
        self._roi_cache_ttl = 5.0  # 缓存有效期（秒）
        
        # ========== 收集统计 ==========
        self.stats = {
            'total_frames_collected': 0,
            'frames_by_channel': defaultdict(int),
            'frames_by_model': defaultdict(int),
            'dropped_frames': 0,
            'collection_times': [],
            'yuv_frames_collected': 0,  # YUV模式收集的帧数
            'yuv_roi_crops': 0,  # YUV ROI裁剪次数
        }
        
        # ========== 配置参数 ==========
        self.max_collection_time = 0.005  # 最大收集时间 5ms
        self.enable_frame_drop = True      # 启用帧丢弃策略
        self.prefer_yuv_mode = True        # 优先使用YUV模式
        

    
    def collect_frames(self, channel_contexts: Dict[str, Any]) -> Dict[str, Any]:
        """收集各通道的帧数据并按模型分组
        
        Args:
            channel_contexts: 通道上下文字典 {channel_id: context}
            
        Returns:
            Dict: 按模型分组的帧数据
            {
                'model_groups': {
                    'model_3': [
                        {'channel_id': 'channel2', 'frame': frame, 'timestamp': time},
                        {'channel_id': 'channel3', 'frame': frame, 'timestamp': time}
                    ],
                    'model_4': [
                        {'channel_id': 'channel4', 'frame': frame, 'timestamp': time}
                    ],
                    'model_5': [
                        {'channel_id': 'channel1', 'frame': frame, 'timestamp': time}
                    ]
                },
                'total_frames': 4,
                'collection_time': 0.003
            }
        """
        collection_start = time.time()
        
        try:
            # 初始化结果结构
            model_groups = defaultdict(list)
            total_frames = 0
            
            # 遍历所有活跃通道
            for channel_id, context in channel_contexts.items():
                if not context or not hasattr(context, 'frame_buffer'):
                    continue
                
                # 检查通道是否启用检测
                if not getattr(context, 'detection_enabled', False):
                    continue
                
                # 检查相机姿态是否异常（暂停输入）
                if getattr(context, 'camera_position_paused', False):
                    continue
                
                # 从通道的frame_buffer收集最新帧
                frame_data = self._collect_channel_frame(channel_id, context)
                if frame_data:
                    # 获取该通道对应的模型ID
                    model_id = self._get_model_id_for_channel(channel_id)
                    if model_id:
                        model_groups[model_id].append(frame_data)
                        total_frames += 1
                        
                        # 更新统计
                        self.stats['frames_by_channel'][channel_id] += 1
                        self.stats['frames_by_model'][model_id] += 1
            
            self.stats['total_frames_collected'] += total_frames
            
            # 计算收集时间
            collection_time = time.time() - collection_start
            self.stats['collection_times'].append(collection_time)
            
            # 如果收集时间过长，记录警告
            if collection_time > self.max_collection_time:
                print(f"⚠️ [帧收集器] 收集时间过长: {collection_time*1000:.1f}ms")
            
            return {
                'model_groups': dict(model_groups),
                'total_frames': total_frames,
                'collection_time': collection_time
            }
            
        except Exception as e:
            print(f"❌ [帧收集器] 收集帧失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'model_groups': {},
                'total_frames': 0,
                'collection_time': time.time() - collection_start
            }
    
    def _collect_channel_frame(self, channel_id: str, context: Any) -> Optional[Dict[str, Any]]:
        """从单个通道收集最新帧
        
        Args:
            channel_id: 通道ID
            context: 通道上下文
            
        Returns:
            帧数据字典，包含channel_id、frame、timestamp等信息
        """
        try:
            frame = None
            frame_timestamp = time.time()
            
            # 从frame_buffer获取最新帧（非消费式读取）
            # 策略：取出所有帧，只保留最新的一帧，丢弃旧帧
            frames_collected = 0
            while not context.frame_buffer.empty():
                try:
                    frame = context.frame_buffer.get_nowait()
                    frames_collected += 1
                except queue.Empty:
                    break
            
            # 如果收集到多帧，记录丢弃的帧数
            if frames_collected > 1:
                dropped = frames_collected - 1
                self.stats['dropped_frames'] += dropped
                if dropped > 5:  # 只在丢帧较多时警告
                    print(f"⚠️ [帧收集器] 通道 {channel_id} 丢弃了 {dropped} 帧")
            
            if frame is not None:
                return {
                    'channel_id': channel_id,
                    'frame': frame,
                    'timestamp': frame_timestamp,
                    'frame_shape': frame.shape if hasattr(frame, 'shape') else None
                }
            
            return None
            
        except Exception as e:
            print(f"❌ [帧收集器] 收集通道 {channel_id} 帧失败: {e}")
            return None
    
    def _get_model_id_for_channel(self, channel_id: str) -> Optional[str]:
        """获取指定通道对应的模型ID
        
        Args:
            channel_id: 通道ID
            
        Returns:
            模型ID，如果未找到返回None
        """
        try:
            if self.model_pool_manager and hasattr(self.model_pool_manager, 'channel_model_mapping'):
                return self.model_pool_manager.channel_model_mapping.get(channel_id)
            
            # 如果没有模型池管理器，使用默认映射（开发模式）
            default_mapping = {
                'channel1': 'model_5',
                'channel2': 'model_3',
                'channel3': 'model_3',
                'channel4': 'model_4'
            }
            return default_mapping.get(channel_id)
            
        except Exception as e:
            print(f"❌ [帧收集器] 获取通道 {channel_id} 模型ID失败: {e}")
            return None
    
    def get_frame_groups_summary(self, model_groups: Dict[str, List[Dict]]) -> str:
        """获取帧分组摘要信息
        
        Args:
            model_groups: 模型分组数据
            
        Returns:
            摘要字符串
        """
        try:
            summary_parts = []
            for model_id, frames in model_groups.items():
                if frames:
                    channels = [f['channel_id'] for f in frames]
                    summary_parts.append(f"{model_id}({len(frames)}帧: {', '.join(channels)})")
            
            return " | ".join(summary_parts) if summary_parts else "无帧数据"
            
        except Exception as e:
            return f"摘要生成失败: {e}"
    
    def optimize_frame_collection(self, channel_contexts: Dict[str, Any]) -> Dict[str, Any]:
        """优化的帧收集方法
        
        支持两种模式：
        1. YUV模式（优先）：直接从HKcapture的YUV队列获取数据，裁剪ROI后转RGB
        2. 传统模式：从frame_buffer获取RGB帧
        
        Args:
            channel_contexts: 通道上下文字典
            
        Returns:
            优化后的帧分组数据
        """
        collection_start = time.time()
        
        try:
            model_groups = defaultdict(list)
            total_frames = 0
            
            channel_frames = {}
            
            # 遍历所有通道
            for channel_id, context in channel_contexts.items():
                if not context:
                    continue
                if not getattr(context, 'detection_enabled', False):
                    continue
                if getattr(context, 'camera_position_paused', False):
                    continue
                
                # 🔥 优先尝试YUV模式
                frame_data = None
                if self.prefer_yuv_mode:
                    frame_data = self._collect_yuv_frame(channel_id, context)
                
                # 如果YUV模式失败，回退到传统模式
                if not frame_data and hasattr(context, 'frame_buffer'):
                    frame_data = self._collect_channel_frame_optimized(channel_id, context)
                
                if frame_data:
                    channel_frames[channel_id] = frame_data
            
            # 按模型分组
            for channel_id, frame_data in channel_frames.items():
                model_id = self._get_model_id_for_channel(channel_id)
                if model_id:
                    model_groups[model_id].append(frame_data)
                    total_frames += 1
                    
                    self.stats['frames_by_channel'][channel_id] += 1
                    self.stats['frames_by_model'][model_id] += 1
            
            self.stats['total_frames_collected'] += total_frames
            
            collection_time = time.time() - collection_start
            self.stats['collection_times'].append(collection_time)
            
            return {
                'model_groups': dict(model_groups),
                'total_frames': total_frames,
                'collection_time': collection_time,
                'optimization_used': True
            }
            
        except Exception as e:
            print(f"❌ [帧收集器] 优化收集失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'model_groups': {},
                'total_frames': 0,
                'collection_time': time.time() - collection_start
            }
    
    def _collect_yuv_frame(self, channel_id: str, context: Any) -> Optional[Dict[str, Any]]:
        """从YUV队列收集帧并裁剪ROI
        
        Args:
            channel_id: 通道ID
            context: 通道上下文
            
        Returns:
            帧数据字典，包含裁剪后的ROI图像列表
        """
        try:
            # 获取capture_source
            capture_source = getattr(context, 'capture_source', None)
            if not capture_source:
                return None
            
            # 检查是否支持YUV队列
            if not hasattr(capture_source, '_yuv_queue_enabled') or not capture_source._yuv_queue_enabled:
                return None
            
            # 获取YUV数据
            yuv_data_tuple = capture_source.get_yuv_data_nowait()
            if not yuv_data_tuple:
                return None
            
            yuv_data, width, height, timestamp = yuv_data_tuple
            
            # 获取ROI配置
            rois = self._get_channel_rois(channel_id, width, height)
            
            if not rois:
                # 没有ROI配置，转换全帧
                rgb_frame = YUVProcessor.yuv420_to_rgb_full(yuv_data, width, height)
                if rgb_frame is not None:
                    self.stats['yuv_frames_collected'] += 1
                    return {
                        'channel_id': channel_id,
                        'frame': rgb_frame,
                        'timestamp': timestamp,
                        'frame_shape': rgb_frame.shape,
                        'yuv_mode': True,
                        'roi_frames': None  # 无ROI裁剪
                    }
                return None
            
            # 🔥 裁剪每个ROI区域的YUV数据并转RGB
            roi_frames = []
            for roi in rois:
                x, y, w, h = roi
                rgb_roi = YUVProcessor.crop_yuv420_roi(
                    yuv_data, width, height, x, y, w, h
                )
                if rgb_roi is not None:
                    roi_frames.append(rgb_roi)
                    self.stats['yuv_roi_crops'] += 1
                else:
                    roi_frames.append(None)
            
            # 同时转换全帧（用于显示叠加等）
            rgb_frame = YUVProcessor.yuv420_to_rgb_full(yuv_data, width, height)
            
            self.stats['yuv_frames_collected'] += 1
            
            return {
                'channel_id': channel_id,
                'frame': rgb_frame,  # 全帧（用于显示）
                'timestamp': timestamp,
                'frame_shape': (height, width, 3),
                'yuv_mode': True,
                'roi_frames': roi_frames,  # ROI裁剪后的帧列表
                'rois': rois  # ROI坐标列表
            }
            
        except Exception as e:
            print(f"❌ [帧收集器] YUV帧收集失败 {channel_id}: {e}")
            return None
    
    def _get_channel_rois(self, channel_id: str, frame_width: int, frame_height: int) -> List[Tuple[int, int, int, int]]:
        """获取通道的ROI配置
        
        Args:
            channel_id: 通道ID
            frame_width: 帧宽度
            frame_height: 帧高度
            
        Returns:
            ROI列表，每个元素为 (x, y, w, h)
        """
        try:
            # 检查缓存
            now = time.time()
            if channel_id in self._roi_cache:
                cache_time = self._roi_cache_time.get(channel_id, 0)
                if now - cache_time < self._roi_cache_ttl:
                    return self._roi_cache[channel_id]
            
            # 从模型池管理器获取标注配置
            if not self.model_pool_manager:
                return []
            
            annotation_config = self.model_pool_manager.get_channel_annotation_config(channel_id)
            if not annotation_config:
                return []
            
            boxes = annotation_config.get('boxes', [])
            if not boxes:
                return []
            
            # 转换boxes为ROI格式并对齐到偶数
            rois = []
            for box in boxes:
                if len(box) >= 4:
                    x1, y1, x2, y2 = box[:4]
                    x = min(x1, x2)
                    y = min(y1, y2)
                    w = abs(x2 - x1)
                    h = abs(y2 - y1)
                    
                    # 对齐到偶数
                    x, y, w, h = YUVProcessor.align_roi_to_even(x, y, w, h, frame_width, frame_height)
                    
                    if w > 0 and h > 0:
                        rois.append((x, y, w, h))
            
            # 更新缓存
            self._roi_cache[channel_id] = rois
            self._roi_cache_time[channel_id] = now
            
            return rois
            
        except Exception as e:
            print(f"❌ [帧收集器] 获取ROI配置失败 {channel_id}: {e}")
            return []
    
    def _collect_channel_frame_optimized(self, channel_id: str, context: Any) -> Optional[Dict[str, Any]]:
        """优化的单通道帧收集
        
        Args:
            channel_id: 通道ID
            context: 通道上下文
            
        Returns:
            帧数据字典
        """
        try:
            # 使用更高效的策略：只检查队列大小，不全部取出
            if context.frame_buffer.empty():
                return None
            
            frame = None
            dropped_count = 0
            
            # 快速获取最新帧，最多检查3次
            for _ in range(3):
                try:
                    if context.frame_buffer.empty():
                        break
                    frame = context.frame_buffer.get_nowait()
                    if not context.frame_buffer.empty():
                        dropped_count += 1
                    else:
                        break
                except queue.Empty:
                    break
            
            if dropped_count > 0:
                self.stats['dropped_frames'] += dropped_count
            
            if frame is not None:
                return {
                    'channel_id': channel_id,
                    'frame': frame,
                    'timestamp': time.time(),
                    'frame_shape': frame.shape if hasattr(frame, 'shape') else None,
                    'dropped_frames': dropped_count
                }
            
            return None
            
        except Exception as e:
            print(f"❌ [帧收集器] 优化收集通道 {channel_id} 失败: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取帧收集统计信息"""
        stats = self.stats.copy()
        
        # 计算平均收集时间
        if self.stats['collection_times']:
            stats['average_collection_time'] = sum(self.stats['collection_times']) / len(self.stats['collection_times'])
            stats['max_collection_time'] = max(self.stats['collection_times'])
        else:
            stats['average_collection_time'] = 0.0
            stats['max_collection_time'] = 0.0
        
        # 计算丢帧率
        if self.stats['total_frames_collected'] > 0:
            stats['drop_rate'] = self.stats['dropped_frames'] / (self.stats['total_frames_collected'] + self.stats['dropped_frames'])
        else:
            stats['drop_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_frames_collected': 0,
            'frames_by_channel': defaultdict(int),
            'frames_by_model': defaultdict(int),
            'dropped_frames': 0,
            'collection_times': []
        }
        print("📊 [帧收集器] 统计信息已重置")
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("📊 [帧收集器] 性能统计")
        print("="*50)
        print(f"总收集帧数: {stats['total_frames_collected']}")
        print(f"丢弃帧数: {stats['dropped_frames']}")
        print(f"丢帧率: {stats['drop_rate']*100:.1f}%")
        print(f"平均收集时间: {stats['average_collection_time']*1000:.2f}ms")
        print(f"最大收集时间: {stats['max_collection_time']*1000:.2f}ms")
        
        print("\n按通道统计:")
        for channel_id, count in stats['frames_by_channel'].items():
            print(f"  {channel_id}: {count} 帧")
        
        print("\n按模型统计:")
        for model_id, count in stats['frames_by_model'].items():
            print(f"  {model_id}: {count} 帧")
        
        print("="*50 + "\n")
