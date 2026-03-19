# -*- coding: utf-8 -*-

"""
简单智能调度器 - 临时实现

职责：
1. 将收集到的帧按模型分组转换为批处理任务
2. 保证数据流的连续性
3. 为完整的智能调度器实现做准备

注意：这是一个简化实现，主要目的是让数据流正常工作
"""

from typing import Dict, List, Any
import time


class SimpleScheduler:
    """简单调度器
    
    将帧收集结果直接转换为批处理任务，不做复杂的调度优化
    """
    
    def __init__(self):
        """初始化简单调度器"""
        self.stats = {
            'total_schedules': 0,
            'total_batches_created': 0,
            'schedule_times': []
        }
        

    
    def schedule(self, collected_frames: Dict[str, Any]) -> List[Dict[str, Any]]:
        """调度处理 - 简单实现
        
        Args:
            collected_frames: 帧收集结果
            {
                'model_groups': {
                    'model_3': [frame_data1, frame_data2],
                    'model_5': [frame_data3]
                },
                'total_frames': 3,
                'collection_time': 0.002
            }
            
        Returns:
            List[Dict]: 批处理任务列表
            [
                {
                    'model_id': 'model_3',
                    'frames': [frame_data1, frame_data2],
                    'batch_size': 2,
                    'priority': 'normal'
                },
                {
                    'model_id': 'model_5', 
                    'frames': [frame_data3],
                    'batch_size': 1,
                    'priority': 'normal'
                }
            ]
        """
        schedule_start = time.time()
        
        try:
            model_groups = collected_frames.get('model_groups', {})
            if not model_groups:
                return []
            
            scheduled_batches = []
            
            # 为每个模型组创建一个批处理任务
            for model_id, frames in model_groups.items():
                if frames:  # 确保有帧数据
                    batch = {
                        'model_id': model_id,
                        'frames': frames,
                        'batch_size': len(frames),
                        'priority': 'normal',
                        'timestamp': time.time()
                    }
                    scheduled_batches.append(batch)
            
            # 更新统计
            self.stats['total_schedules'] += 1
            self.stats['total_batches_created'] += len(scheduled_batches)
            
            schedule_time = time.time() - schedule_start
            self.stats['schedule_times'].append(schedule_time)
            
            return scheduled_batches
            
        except Exception as e:
            print(f"[简单调度器] 调度失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计信息"""
        stats = self.stats.copy()
        
        # 计算平均调度时间
        if self.stats['schedule_times']:
            stats['average_schedule_time'] = sum(self.stats['schedule_times']) / len(self.stats['schedule_times'])
        else:
            stats['average_schedule_time'] = 0.0
        
        return stats
