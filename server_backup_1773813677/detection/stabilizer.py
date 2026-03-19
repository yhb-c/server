"""
检测结果稳定器 - 基于物理规则的后处理模块
不需要训练，纯规则约束，用于消除检测跳变
"""

from collections import deque
from typing import List, Dict, Optional
import numpy as np


class DetectionStabilizer:
    """基于规则的检测结果稳定器"""
    
    def __init__(self, 
                 history_size=5,
                 pixel_change_threshold=0.20,
                 conf_switch_threshold=0.85,
                 area_tolerance=0.15):
        """
        Args:
            history_size: 历史帧数量
            pixel_change_threshold: 像素数量变化阈值（比例）
            conf_switch_threshold: 类别切换所需的置信度阈值
            area_tolerance: 总面积变化容忍度
        """
        self.history_size = history_size
        self.pixel_change_threshold = pixel_change_threshold
        self.conf_switch_threshold = conf_switch_threshold
        self.area_tolerance = area_tolerance
        
        # 历史记录
        self.history = deque(maxlen=history_size)
        
        # 统计信息
        self.stats = {
            'stabilized_count': 0,
            'rejected_count': 0,
            'total_frames': 0
        }
    
    def process(self, current_detection: Dict) -> Dict:
        """
        处理当前帧的检测结果
        
        Args:
            current_detection: {
                'masks': [
                    {'class': 'liquid', 'conf': 0.87, 'pixels': 2486, 'center_y': 50},
                    {'class': 'air', 'conf': 0.34, 'pixels': 2490, 'center_y': 30}
                ]
            }
        
        Returns:
            稳定后的检测结果
        """
        self.stats['total_frames'] += 1
        
        # 第一帧，直接返回
        if len(self.history) == 0:
            self.history.append(current_detection)
            return current_detection
        
        # 应用规则链
        stable_result = self._apply_rules(current_detection)
        
        # 更新历史
        self.history.append(stable_result)
        
        return stable_result
    
    def _apply_rules(self, current: Dict) -> Dict:
        """应用所有规则"""
        
        # 规则1：空间位置检查（液体应在下方）
        current = self._check_spatial_logic(current)
        
        # 规则2：类别切换检查
        current = self._check_class_transition(current)
        
        # 规则3：像素数量平滑
        current = self._smooth_pixel_counts(current)
        
        # 规则4：总面积守恒检查
        current = self._check_area_conservation(current)
        
        # 规则5：置信度阈值动态调整
        current = self._apply_confidence_filter(current)
        
        return current
    
    def _check_spatial_logic(self, current: Dict) -> Dict:
        """
        规则1：检查空间位置逻辑
        液体应该在容器下方，空气在上方
        """
        masks = current.get('masks', [])
        
        liquid_masks = [m for m in masks if m['class'] == 'liquid']
        air_masks = [m for m in masks if m['class'] == 'air']
        
        # 如果同时存在液体和空气
        if liquid_masks and air_masks:
            liquid_y = np.mean([m.get('center_y', 0) for m in liquid_masks])
            air_y = np.mean([m.get('center_y', 0) for m in air_masks])
            
            # 如果空气在下方，液体在上方（违反物理规律）
            if air_y > liquid_y:
                print(f"[WARNING] 空间逻辑异常：air在下(y={air_y:.1f}), liquid在上(y={liquid_y:.1f})，交换类别")
                # 交换类别标签
                for m in masks:
                    if m['class'] == 'liquid':
                        m['class'] = 'air'
                        m['original_class'] = 'liquid'
                    elif m['class'] == 'air':
                        m['class'] = 'liquid'
                        m['original_class'] = 'air'
                
                self.stats['stabilized_count'] += 1
        
        return current
    
    def _check_class_transition(self, current: Dict) -> Dict:
        """
        规则2：检查类别切换是否合理
        禁止突然从100% air变成100% liquid
        """
        if len(self.history) < 3:
            return current
        
        # 获取历史类别分布
        prev_classes = self._get_class_distribution(self.history[-1])
        curr_classes = self._get_class_distribution(current)
        
        # 检测是否发生完全切换
        prev_dominant = max(prev_classes, key=prev_classes.get) if prev_classes else None
        curr_dominant = max(curr_classes, key=curr_classes.get) if curr_classes else None
        
        if prev_dominant and curr_dominant and prev_dominant != curr_dominant:
            prev_ratio = prev_classes[prev_dominant]
            curr_ratio = curr_classes[curr_dominant]
            
            # 如果上一帧是单一类别(>90%)，当前帧切换到另一类别(>90%)
            if prev_ratio > 0.9 and curr_ratio > 0.9:
                print(f"[WARNING] 类别突变：{prev_dominant}(100%) -> {curr_dominant}(100%)，保持历史")
                # 使用历史结果
                self.stats['rejected_count'] += 1
                return self._copy_result(self.history[-1])
        
        return current
    
    def _smooth_pixel_counts(self, current: Dict) -> Dict:
        """
        规则3：像素数量平滑
        防止像素数突变
        """
        if len(self.history) < 2:
            return current
        
        prev_masks = self.history[-1].get('masks', [])
        curr_masks = current.get('masks', [])
        
        # 按类别匹配历史mask
        for curr_mask in curr_masks:
            class_name = curr_mask['class']
            
            # 查找历史中相同类别的mask
            prev_mask = self._find_mask_by_class(prev_masks, class_name)
            
            if prev_mask:
                prev_pixels = prev_mask['pixels']
                curr_pixels = curr_mask['pixels']
                
                # 计算变化率
                if prev_pixels > 0:
                    change_ratio = abs(curr_pixels - prev_pixels) / prev_pixels
                    
                    # 如果变化超过阈值，进行平滑
                    if change_ratio > self.pixel_change_threshold:
                        # 限制变化幅度
                        max_change = prev_pixels * self.pixel_change_threshold
                        if curr_pixels > prev_pixels:
                            smoothed_pixels = prev_pixels + max_change
                        else:
                            smoothed_pixels = prev_pixels - max_change
                        
                        print(f"[WARNING] 像素突变：{class_name} {prev_pixels} -> {curr_pixels}，"
                              f"平滑为 {int(smoothed_pixels)}")
                        curr_mask['pixels'] = int(smoothed_pixels)
                        curr_mask['smoothed'] = True
                        self.stats['stabilized_count'] += 1
        
        return current
    
    def _check_area_conservation(self, current: Dict) -> Dict:
        """
        规则4：总面积守恒
        ROI内的总像素数应该相对稳定
        """
        if len(self.history) < 2:
            return current
        
        # 计算当前总面积
        curr_total = sum(m['pixels'] for m in current.get('masks', []))
        
        # 计算历史平均总面积
        hist_totals = []
        for h in self.history:
            total = sum(m['pixels'] for m in h.get('masks', []))
            hist_totals.append(total)
        
        hist_avg = np.mean(hist_totals)
        
        if hist_avg > 0:
            deviation = abs(curr_total - hist_avg) / hist_avg
            
            if deviation > self.area_tolerance:
                print(f"[WARNING] 总面积异常：历史均值={hist_avg:.0f}, 当前={curr_total}, "
                      f"偏差={deviation:.1%}，使用历史数据")
                self.stats['rejected_count'] += 1
                return self._copy_result(self.history[-1])
        
        return current
    
    def _apply_confidence_filter(self, current: Dict) -> Dict:
        """
        规则5：动态置信度过滤
        根据历史稳定性调整置信度要求
        """
        if len(self.history) < 3:
            return current
        
        # 评估历史稳定性
        stability = self._calculate_stability()
        
        # 如果历史稳定，提高切换阈值
        if stability > 0.8:
            threshold = self.conf_switch_threshold
        else:
            threshold = 0.70
        
        # 过滤低置信度的mask
        masks = current.get('masks', [])
        filtered_masks = []
        
        for mask in masks:
            if mask['conf'] >= threshold:
                filtered_masks.append(mask)
            else:
                print(f"[WARNING] 低置信度过滤：{mask['class']} conf={mask['conf']:.2f} < {threshold:.2f}")
        
        # 如果过滤后没有mask，使用历史
        if not filtered_masks and masks:
            print(f"[WARNING] 所有mask被过滤，使用历史数据")
            return self._copy_result(self.history[-1])
        
        current['masks'] = filtered_masks
        return current
    
    # ===== 辅助方法 =====
    
    def _get_class_distribution(self, detection: Dict) -> Dict[str, float]:
        """获取类别分布比例"""
        masks = detection.get('masks', [])
        if not masks:
            return {}
        
        total_pixels = sum(m['pixels'] for m in masks)
        if total_pixels == 0:
            return {}
        
        distribution = {}
        for mask in masks:
            class_name = mask['class']
            distribution[class_name] = distribution.get(class_name, 0) + mask['pixels']
        
        # 转换为比例
        for k in distribution:
            distribution[k] /= total_pixels
        
        return distribution
    
    def _find_mask_by_class(self, masks: List[Dict], class_name: str) -> Optional[Dict]:
        """在mask列表中查找指定类别"""
        for mask in masks:
            if mask['class'] == class_name:
                return mask
        return None
    
    def _calculate_stability(self) -> float:
        """计算历史稳定性（0-1）"""
        if len(self.history) < 3:
            return 0.5
        
        # 检查最近N帧的主导类别是否一致
        dominant_classes = []
        for h in self.history:
            dist = self._get_class_distribution(h)
            if dist:
                dominant = max(dist, key=dist.get)
                dominant_classes.append(dominant)
        
        if not dominant_classes:
            return 0.5
        
        # 计算一致性
        from collections import Counter
        counts = Counter(dominant_classes)
        most_common_count = counts.most_common(1)[0][1]
        stability = most_common_count / len(dominant_classes)
        
        return stability
    
    def _copy_result(self, detection: Dict) -> Dict:
        """深拷贝检测结果"""
        import copy
        return copy.deepcopy(detection)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        if self.stats['total_frames'] > 0:
            stabilize_rate = self.stats['stabilized_count'] / self.stats['total_frames']
            reject_rate = self.stats['rejected_count'] / self.stats['total_frames']
        else:
            stabilize_rate = reject_rate = 0.0
        
        return {
            **self.stats,
            'stabilize_rate': f"{stabilize_rate:.1%}",
            'reject_rate': f"{reject_rate:.1%}"
        }
    
    def reset(self):
        """重置稳定器状态"""
        self.history.clear()
        self.stats = {
            'stabilized_count': 0,
            'rejected_count': 0,
            'total_frames': 0
        }


# ===== 使用示例 =====

if __name__ == "__main__":
    # 创建稳定器
    stabilizer = DetectionStabilizer(
        history_size=5,
        pixel_change_threshold=0.20,  # 像素变化不超过20%
        conf_switch_threshold=0.85,   # 类别切换需要85%置信度
        area_tolerance=0.15           # 总面积变化容忍15%
    )
    
    # 模拟检测结果
    test_sequence = [
        # 帧1-5：稳定的air
        {'masks': [{'class': 'air', 'conf': 0.93, 'pixels': 2400, 'center_y': 30}]},
        {'masks': [{'class': 'air', 'conf': 0.94, 'pixels': 2410, 'center_y': 30}]},
        {'masks': [{'class': 'air', 'conf': 0.92, 'pixels': 2395, 'center_y': 30}]},
        {'masks': [{'class': 'air', 'conf': 0.95, 'pixels': 2405, 'center_y': 30}]},
        {'masks': [{'class': 'air', 'conf': 0.93, 'pixels': 2400, 'center_y': 30}]},
        
        # 帧6：突然变成liquid（异常，应被拒绝）
        {'masks': [{'class': 'liquid', 'conf': 0.87, 'pixels': 2486, 'center_y': 50}]},
        
        # 帧7：恢复air
        {'masks': [{'class': 'air', 'conf': 0.94, 'pixels': 2400, 'center_y': 30}]},
        
        # 帧8-10：开始真正过渡
        {'masks': [
            {'class': 'air', 'conf': 0.90, 'pixels': 2300, 'center_y': 25},
            {'class': 'liquid', 'conf': 0.75, 'pixels': 200, 'center_y': 55}
        ]},
        {'masks': [
            {'class': 'air', 'conf': 0.85, 'pixels': 2000, 'center_y': 20},
            {'class': 'liquid', 'conf': 0.82, 'pixels': 500, 'center_y': 55}
        ]},
        {'masks': [
            {'class': 'air', 'conf': 0.78, 'pixels': 1500, 'center_y': 15},
            {'class': 'liquid', 'conf': 0.88, 'pixels': 1000, 'center_y': 55}
        ]},
    ]
    
    print("=" * 60)
    print("检测结果稳定器测试")
    print("=" * 60)
    
    for i, detection in enumerate(test_sequence, 1):
        print(f"\n--- 帧 {i} ---")
        print(f"原始: {detection}")
        
        stable = stabilizer.process(detection)
        print(f"稳定: {stable}")
    
    print("\n" + "=" * 60)
    print("统计信息:")
    for k, v in stabilizer.get_stats().items():
        print(f"  {k}: {v}")
