# -*- coding: utf-8 -*-

"""
结果分发器 - 全局检测线程架构核心组件

职责：
1. 接收批处理推理结果
2. 将结果按通道ID分发到对应的队列
3. 更新各通道的latest_detection
4. 触发回调函数
5. 保持现有队列接口完全兼容

设计原则：
- 保持现有接口完全兼容，确保无缝迁移
- 批量队列操作，提高分发效率
- 避免阻塞写入，处理队列满的情况
- 支持并发安全访问
- 完善的错误处理和统计监控
"""

import time
import queue
import threading
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
import copy


class ResultDistributor:
    """结果分发器
    
    将批处理结果分发到各通道队列，保持现有接口兼容性
    """
    
    def __init__(self):
        """初始化结果分发器"""
        # ========== 分发统计 ==========
        self.stats = {
            'total_results_distributed': 0,
            'results_by_channel': defaultdict(int),
            'distribution_times': [],
            'queue_full_events': 0,
            'callback_errors': 0,
            'successful_distributions': 0
        }
        
        # ========== 配置参数 ==========
        self.max_distribution_time = 0.002  # 最大分发时间 2ms
        self.enable_queue_overflow_handling = True  # 启用队列溢出处理
        self.enable_callback_error_handling = True  # 启用回调错误处理
        
        # ========== 线程安全 ==========
        self._lock = threading.RLock()  # 可重入锁
        

    
    def distribute_results(self, results: List[Dict[str, Any]], 
                         channel_contexts: Dict[str, Any], 
                         channel_callbacks: Dict[str, Callable]):
        """分发检测结果到各通道
        
        Args:
            results: 批处理结果列表 [{'channel_id': str, 'result': dict}, ...]
            channel_contexts: 通道上下文字典 {channel_id: context}
            channel_callbacks: 通道回调函数字典 {channel_id: callback}
        """
        if not results:
            return
        
        distribution_start = time.time()
        
        try:
            with self._lock:
                # 按通道分组结果
                channel_results = self._group_results_by_channel(results)
                
                # 分发到各通道
                for channel_id, channel_result_list in channel_results.items():
                    context = channel_contexts.get(channel_id)
                    if not context:
                        continue
                    
                    # 处理该通道的所有结果（通常批处理后每个通道只有一个结果）
                    for result_data in channel_result_list:
                        detection_result = result_data.get('result')
                        if detection_result:
                            success = self._distribute_single_result(
                                channel_id, detection_result, context, channel_callbacks
                            )
                            if success:
                                self.stats['successful_distributions'] += 1
                                self.stats['results_by_channel'][channel_id] += 1
                
                self.stats['total_results_distributed'] += len(results)
                
                # 记录分发时间
                distribution_time = time.time() - distribution_start
                self.stats['distribution_times'].append(distribution_time)
                
                # 如果分发时间过长，记录警告
                if distribution_time > self.max_distribution_time:
                    print(f"[结果分发器] 分发时间过长: {distribution_time*1000:.1f}ms")
                
        except Exception as e:
            print(f"[结果分发器] 分发结果失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _group_results_by_channel(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按通道ID分组结果
        
        Args:
            results: 批处理结果列表
            
        Returns:
            按通道分组的结果字典
        """
        channel_results = defaultdict(list)
        
        for result_data in results:
            channel_id = result_data.get('channel_id')
            if channel_id:
                channel_results[channel_id].append(result_data)
        
        return dict(channel_results)
    
    def _distribute_single_result(self, channel_id: str, detection_result: Dict[str, Any], 
                                context: Any, channel_callbacks: Dict[str, Callable]) -> bool:
        """分发单个检测结果到指定通道
        
        Args:
            channel_id: 通道ID
            detection_result: 检测结果
            context: 通道上下文
            channel_callbacks: 回调函数字典
            
        Returns:
            bool: 分发是否成功
        """
        try:
            success = True
            
            # 🔥 检测相机异常并触发警报
            camera_status = detection_result.get('camera_status', 'normal')
            if camera_status == 'abnormal':
                self._trigger_camera_alert(channel_id, detection_result, context)
            
            # 1. 放入检测结果队列（供曲线绘制使用）
            if hasattr(context, 'detection_mission_results'):
                success &= self._put_to_queue(
                    context.detection_mission_results, 
                    detection_result, 
                    f"{channel_id}_detection_mission_results"
                )
            
            # 2. 放入存储数据队列（供存储线程使用）
            if 'liquid_line_positions' in detection_result and hasattr(context, 'storage_data'):
                success &= self._put_to_queue(
                    context.storage_data, 
                    detection_result, 
                    f"{channel_id}_storage_data"
                )
            
            # 3. 更新最新检测结果（供显示线程使用）
            if hasattr(context, 'detection_lock') and hasattr(context, 'latest_detection'):
                try:
                    with context.detection_lock:
                        context.latest_detection = detection_result
                except Exception as e:
                    print(f"[结果分发器] 更新 {channel_id} latest_detection 失败: {e}")
                    success = False
            
            # 4. 触发回调函数
            callback = channel_callbacks.get(channel_id)
            if callback:
                success &= self._trigger_callback(callback, channel_id, detection_result)
            
            return success
            
        except Exception as e:
            print(f"[结果分发器] 分发单个结果失败 {channel_id}: {e}")
            return False
    
    def _put_to_queue(self, target_queue: queue.Queue, data: Any, queue_name: str) -> bool:
        """安全地将数据放入队列
        
        Args:
            target_queue: 目标队列
            data: 要放入的数据
            queue_name: 队列名称（用于日志）
            
        Returns:
            bool: 是否成功放入
        """
        try:
            if target_queue.full():
                if self.enable_queue_overflow_handling:
                    # 队列满时，丢弃旧数据
                    try:
                        target_queue.get_nowait()
                        self.stats['queue_full_events'] += 1
                    except queue.Empty:
                        pass
                else:
                    print(f"[结果分发器] 队列 {queue_name} 已满，跳过")
                    return False
            
            target_queue.put_nowait(data)
            return True
            
        except queue.Full:
            print(f"[结果分发器] 队列 {queue_name} 放入失败（队列满）")
            self.stats['queue_full_events'] += 1
            return False
        except Exception as e:
            print(f"[结果分发器] 队列 {queue_name} 放入异常: {e}")
            return False
    
    def _trigger_camera_alert(self, channel_id: str, detection_result: Dict[str, Any], context: Any):
        """触发相机异常警报
        
        通过Qt信号机制在主线程弹出警报对话框，使用全局DialogManager
        
        Args:
            channel_id: 通道ID
            detection_result: 检测结果
            context: 通道上下文
        """
        try:
            # 防止重复弹窗：检查是否已经触发过警报
            if not hasattr(self, '_camera_alert_triggered'):
                self._camera_alert_triggered = {}
            
            # 每个通道10秒内只触发一次警报
            current_time = time.time()
            last_alert_time = self._camera_alert_triggered.get(channel_id, 0)
            if current_time - last_alert_time < 10.0:
                return  # 10秒内已触发过，跳过
            
            self._camera_alert_triggered[channel_id] = current_time
            
            camera_message = detection_result.get('camera_message', '相机姿态发生变化')
            
            # 通过context的信号触发主线程警报（如果context有相关信号）
            if hasattr(context, 'camera_alert_signal'):
                context.camera_alert_signal.emit(channel_id, camera_message)
            else:
                # 使用QTimer在主线程执行，应用全局DialogManager
                try:
                    from qtpy.QtCore import QTimer
                    from qtpy.QtWidgets import QApplication
                    
                    def show_alert():
                        app = QApplication.instance()
                        if app:
                            # 使用全局DialogManager显示警告对话框
                            try:
                                from widgets.style_manager import DialogManager
                                DialogManager.show_warning(
                                    None,
                                    "相机姿态异常",
                                    f"通道 {channel_id} 检测到相机姿态异常！\n\n{camera_message}\n\n请检查相机是否发生移动。",
                                    text_alignment=DialogManager.ALIGN_CENTER
                                )
                            except ImportError:
                                # 回退到QMessageBox
                                from qtpy.QtWidgets import QMessageBox
                                QMessageBox.warning(
                                    None,
                                    "相机姿态异常",
                                    f"通道 {channel_id} 检测到相机姿态异常！\n{camera_message}\n\n请检查相机是否发生移动。"
                                )
                    
                    # 使用QTimer.singleShot在主线程执行
                    QTimer.singleShot(0, show_alert)
                    
                except Exception as e:
                    print(f"[相机警报] 无法弹出警报对话框: {e}")
            
            print(f"[相机警报] 通道 {channel_id}: {camera_message}")
            
        except Exception as e:
            print(f"[相机警报] 触发警报失败: {e}")
    
    def _trigger_callback(self, callback: Callable, channel_id: str, detection_result: Dict[str, Any]) -> bool:
        """触发回调函数
        
        Args:
            callback: 回调函数
            channel_id: 通道ID
            detection_result: 检测结果
            
        Returns:
            bool: 回调是否成功
        """
        try:
            if self.enable_callback_error_handling:
                # 在错误处理模式下，回调异常不会影响主流程
                try:
                    callback(channel_id, detection_result)
                    return True
                except Exception as e:
                    print(f"[结果分发器] 回调函数异常 {channel_id}: {e}")
                    self.stats['callback_errors'] += 1
                    return False
            else:
                # 直接调用，异常会向上传播
                callback(channel_id, detection_result)
                return True
                
        except Exception as e:
            print(f"[结果分发器] 触发回调失败 {channel_id}: {e}")
            self.stats['callback_errors'] += 1
            return False
    
    def distribute_results_optimized(self, results: List[Dict[str, Any]], 
                                   channel_contexts: Dict[str, Any], 
                                   channel_callbacks: Dict[str, Callable]):
        """优化的结果分发方法
        
        使用批量操作和并行处理提高分发效率
        
        Args:
            results: 批处理结果列表
            channel_contexts: 通道上下文字典
            channel_callbacks: 通道回调函数字典
        """
        if not results:
            return
        
        distribution_start = time.time()
        
        try:
            with self._lock:
                # 按通道分组结果
                channel_results = self._group_results_by_channel(results)
                
                # 批量分发
                successful_channels = 0
                for channel_id, channel_result_list in channel_results.items():
                    context = channel_contexts.get(channel_id)
                    if not context:
                        continue
                    
                    # 批量处理该通道的结果
                    success = self._distribute_channel_results_batch(
                        channel_id, channel_result_list, context, channel_callbacks
                    )
                    
                    if success:
                        successful_channels += 1
                        self.stats['results_by_channel'][channel_id] += len(channel_result_list)
                
                self.stats['total_results_distributed'] += len(results)
                self.stats['successful_distributions'] += successful_channels
                
                # 记录分发时间
                distribution_time = time.time() - distribution_start
                self.stats['distribution_times'].append(distribution_time)
                
        except Exception as e:
            print(f"[结果分发器] 优化分发失败: {e}")
            # 回退到标准分发方法
            self.distribute_results(results, channel_contexts, channel_callbacks)
    
    def _distribute_channel_results_batch(self, channel_id: str, channel_results: List[Dict[str, Any]], 
                                        context: Any, channel_callbacks: Dict[str, Callable]) -> bool:
        """批量分发单个通道的结果
        
        Args:
            channel_id: 通道ID
            channel_results: 该通道的结果列表
            context: 通道上下文
            channel_callbacks: 回调函数字典
            
        Returns:
            bool: 批量分发是否成功
        """
        try:
            # 通常批处理后每个通道只有一个结果，但这里支持多个结果的情况
            latest_result = None
            
            for result_data in channel_results:
                detection_result = result_data.get('result')
                if not detection_result:
                    continue
                
                latest_result = detection_result
                
                # 分发到队列
                success = self._distribute_single_result(
                    channel_id, detection_result, context, channel_callbacks
                )
                
                if not success:
                    return False
            
            return True
            
        except Exception as e:
            print(f"[结果分发器] 批量分发通道 {channel_id} 失败: {e}")
            return False
    
    def get_distribution_summary(self, results: List[Dict[str, Any]]) -> str:
        """获取分发摘要信息
        
        Args:
            results: 结果列表
            
        Returns:
            摘要字符串
        """
        try:
            if not results:
                return "无结果分发"
            
            channel_counts = defaultdict(int)
            for result_data in results:
                channel_id = result_data.get('channel_id')
                if channel_id:
                    channel_counts[channel_id] += 1
            
            summary_parts = []
            for channel_id, count in channel_counts.items():
                summary_parts.append(f"{channel_id}({count})")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            return f"摘要生成失败: {e}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分发统计信息"""
        with self._lock:
            stats = self.stats.copy()
            
            # 计算平均分发时间
            if self.stats['distribution_times']:
                stats['average_distribution_time'] = sum(self.stats['distribution_times']) / len(self.stats['distribution_times'])
                stats['max_distribution_time'] = max(self.stats['distribution_times'])
            else:
                stats['average_distribution_time'] = 0.0
                stats['max_distribution_time'] = 0.0
            
            # 计算成功率
            if self.stats['total_results_distributed'] > 0:
                stats['success_rate'] = self.stats['successful_distributions'] / self.stats['total_results_distributed']
            else:
                stats['success_rate'] = 0.0
            
            # 计算错误率
            total_operations = self.stats['total_results_distributed']
            if total_operations > 0:
                stats['queue_full_rate'] = self.stats['queue_full_events'] / total_operations
                stats['callback_error_rate'] = self.stats['callback_errors'] / total_operations
            else:
                stats['queue_full_rate'] = 0.0
                stats['callback_error_rate'] = 0.0
            
            return stats
    
    def reset_stats(self):
        """重置统计信息"""
        with self._lock:
            self.stats = {
                'total_results_distributed': 0,
                'results_by_channel': defaultdict(int),
                'distribution_times': [],
                'queue_full_events': 0,
                'callback_errors': 0,
                'successful_distributions': 0
            }
            print("[结果分发器] 统计信息已重置")
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("[结果分发器] 性能统计")
        print("="*50)
        print(f"总分发结果数: {stats['total_results_distributed']}")
        print(f"成功分发数: {stats['successful_distributions']}")
        print(f"成功率: {stats['success_rate']*100:.1f}%")
        print(f"队列满事件: {stats['queue_full_events']}")
        print(f"回调错误数: {stats['callback_errors']}")
        print(f"平均分发时间: {stats['average_distribution_time']*1000:.2f}ms")
        print(f"最大分发时间: {stats['max_distribution_time']*1000:.2f}ms")
        
        print("\n按通道统计:")
        for channel_id, count in stats['results_by_channel'].items():
            print(f"  {channel_id}: {count} 个结果")
        
        print("="*50 + "\n")
    
    def test_distribution(self, channel_contexts: Dict[str, Any], channel_callbacks: Dict[str, Callable]):
        """测试分发功能
        
        Args:
            channel_contexts: 通道上下文字典
            channel_callbacks: 回调函数字典
        """
        print("🧪 [结果分发器] 开始测试分发功能...")
        
        # 创建测试结果
        test_results = [
            {
                'channel_id': 'channel1',
                'result': {
                    'liquid_line_positions': [100, 200, 300],
                    'timestamp': time.time(),
                    'test_data': True
                }
            },
            {
                'channel_id': 'channel2',
                'result': {
                    'liquid_line_positions': [150, 250, 350],
                    'timestamp': time.time(),
                    'test_data': True
                }
            }
        ]
        
        # 执行分发测试
        start_time = time.time()
        self.distribute_results(test_results, channel_contexts, channel_callbacks)
        test_time = time.time() - start_time
        
        print(f"[结果分发器] 测试完成，耗时: {test_time*1000:.2f}ms")
        print(f"   - 测试结果数: {len(test_results)}")
        print(f"   - 分发摘要: {self.get_distribution_summary(test_results)}")
        
        # 打印测试统计
        self.print_stats()
