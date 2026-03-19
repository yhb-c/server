# -*- coding: utf-8 -*-
"""
空间后处理逻辑模块

功能：
    根据现实物理条件制定约束规则，对多个ROI的液位高度进行空间一致性校正
    
使用条件：
    只有ROI数量大于1时才触发空间逻辑
    
规则：
    1. (返回码 001) 下方ROI分割结果出现air（没有liquid/foam）且置信度达标 
       → 上方ROI分割结果air占比95%以上
       置信度标准：下方ROI air置信度>0.8，上方ROI liquid置信度<0.3
       
    2. (返回码 002) 上方ROI分割结果出现liquid或foam且置信度达标 
       → 下方ROI分割结果liquid占比95%以上
       置信度标准：上方ROI liquid/foam置信度>0.8，下方ROI air置信度<0.3
    
返回码：
    001: 规则1触发，上方ROI修正为air占比95%以上（液位=0）
    002: 规则2触发，下方ROI修正为liquid占比95%以上（液位=满）
    None: 未触发空间逻辑
"""

import csv
import numpy as np
from datetime import datetime

# 全局调试日志开关
DEBUG_LOG_ENABLED = True

# 模块级状态（用于存储区域信息）
_region_mask_info = {}
_frame_count = 0
_log_initialized = False

# 阈值配置
HIGH_CONF_THRESHOLD = 0.8   # 高置信度阈值
LOW_CONF_THRESHOLD = 0.3    # 低置信度阈值
PIXEL_RATIO_THRESHOLD = 0.95  # 像素占比阈值（95%）
LOG_PATH = "调试日志/空间后处理逻辑.csv"


def _init_csv_log():
    """初始化CSV日志文件"""
    global _log_initialized
    if not DEBUG_LOG_ENABLED or _log_initialized:
        return
    try:
        with open(LOG_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'frame_count', 'num_regions',
                'upper_idx', 'lower_idx',
                'upper_classes', 'upper_confidences', 'upper_pixel_ratios',
                'lower_classes', 'lower_confidences', 'lower_pixel_ratios',
                'rule1_check', 'rule1_lower_air_conf', 'rule1_upper_liquid_conf', 'rule1_lower_has_only_air',
                'rule2_check', 'rule2_upper_lf_conf', 'rule2_lower_air_conf',
                'triggered_rules', 'original_heights', 'corrected_heights', 'action'
            ])
        _log_initialized = True
    except Exception:
        pass


def _log_to_csv(log_data):
    """写入CSV日志"""
    if not DEBUG_LOG_ENABLED:
        return
    try:
        _init_csv_log()
        with open(LOG_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                log_data.get('frame_count', 0),
                log_data.get('num_regions', 0),
                log_data.get('upper_idx', ''),
                log_data.get('lower_idx', ''),
                log_data.get('upper_classes', ''),
                log_data.get('upper_confidences', ''),
                log_data.get('upper_pixel_ratios', ''),
                log_data.get('lower_classes', ''),
                log_data.get('lower_confidences', ''),
                log_data.get('lower_pixel_ratios', ''),
                log_data.get('rule1_check', ''),
                f"{log_data.get('rule1_lower_air_conf', 0):.3f}",
                f"{log_data.get('rule1_upper_liquid_conf', 0):.3f}",
                log_data.get('rule1_lower_has_only_air', ''),
                log_data.get('rule2_check', ''),
                f"{log_data.get('rule2_upper_lf_conf', 0):.3f}",
                f"{log_data.get('rule2_lower_air_conf', 0):.3f}",
                log_data.get('triggered_rules', ''),
                log_data.get('original_heights', ''),
                log_data.get('corrected_heights', ''),
                log_data.get('action', '')
            ])
    except Exception:
        pass


def update_region_info(idx, all_masks_info, container_top_y):
    """
    更新ROI的分割结果信息
    
    Args:
        idx: ROI索引
        all_masks_info: mask信息列表 [(mask, class_name, confidence), ...]
        container_top_y: 容器顶部y坐标（用于判断上下位置）
    """
    global _region_mask_info
    
    classes = []
    confidences = []
    pixel_counts = []
    total_pixels = 0
    
    for mask, class_name, conf in all_masks_info:
        classes.append(class_name)
        confidences.append(conf)
        # 计算每个类别的像素数量
        if mask is not None:
            if isinstance(mask, np.ndarray):
                pixel_count = np.sum(mask > 0)
            else:
                pixel_count = 0
        else:
            pixel_count = 0
        pixel_counts.append(pixel_count)
        total_pixels += pixel_count
    
    # 计算每个类别的像素占比
    pixel_ratios = {}
    for class_name, count in zip(classes, pixel_counts):
        if total_pixels > 0:
            ratio = count / total_pixels
        else:
            ratio = 0.0
        # 同一类别可能有多个mask，累加占比
        if class_name in pixel_ratios:
            pixel_ratios[class_name] += ratio
        else:
            pixel_ratios[class_name] = ratio
    
    _region_mask_info[idx] = {
        'classes': classes,
        'confidences': confidences,
        'pixel_counts': pixel_counts,
        'total_pixels': total_pixels,
        'pixel_ratios': pixel_ratios,  # {class_name: ratio}
        'y_position': container_top_y,
        'masks_info': all_masks_info
    }


def _get_class_max_confidence(idx, target_classes):
    """获取指定区域中目标类别的最高置信度"""
    if idx not in _region_mask_info:
        return 0.0
    
    info = _region_mask_info[idx]
    max_conf = 0.0
    
    for class_name, conf in zip(info['classes'], info['confidences']):
        if class_name in target_classes:
            max_conf = max(max_conf, conf)
    
    return max_conf


def _get_class_pixel_ratio(idx, target_classes):
    """获取指定区域中目标类别的像素占比总和"""
    if idx not in _region_mask_info:
        return 0.0
    
    info = _region_mask_info[idx]
    pixel_ratios = info.get('pixel_ratios', {})
    
    total_ratio = 0.0
    for class_name in target_classes:
        total_ratio += pixel_ratios.get(class_name, 0.0)
    
    return total_ratio


def _check_has_only_air(idx):
    """
    检查指定区域是否只有air（没有liquid/foam）
    
    Returns:
        bool: True表示只有air，没有liquid和foam
    """
    if idx not in _region_mask_info:
        return False
    
    info = _region_mask_info[idx]
    classes = info.get('classes', [])
    
    has_air = 'air' in classes
    has_liquid = 'liquid' in classes
    has_foam = 'foam' in classes
    
    return has_air and not has_liquid and not has_foam


def _check_rule1_condition(lower_idx, upper_idx):
    """
    检查规则1：下方ROI出现air（没有liquid/foam）且置信度达标 
              → 上方ROI的air占比≥95%
    
    置信度标准：下方air置信度>0.8，上方liquid置信度<0.3
    
    Returns:
        tuple: (是否满足条件, 下方air置信度, 上方liquid置信度, 下方是否只有air)
    """
    # 检查下方ROI是否只有air（没有liquid/foam）
    lower_has_only_air = _check_has_only_air(lower_idx)
    
    # 获取置信度
    lower_air_conf = _get_class_max_confidence(lower_idx, ['air'])
    upper_liquid_conf = _get_class_max_confidence(upper_idx, ['liquid'])
    
    # 置信度条件：下方air>0.8 且 上方liquid<0.3
    confidence_met = (lower_air_conf > HIGH_CONF_THRESHOLD and 
                     upper_liquid_conf < LOW_CONF_THRESHOLD)
    
    # 规则1触发条件：下方只有air + 置信度达标
    condition_met = lower_has_only_air and confidence_met
    
    return condition_met, lower_air_conf, upper_liquid_conf, lower_has_only_air


def _check_rule2_condition(upper_idx, lower_idx):
    """
    检查规则2：上方ROI出现liquid或foam且置信度达标 
              → 下方ROI的liquid占比≥95%
    
    置信度标准：上方liquid/foam置信度>0.8，下方air置信度<0.3
    
    Returns:
        tuple: (是否满足条件, 上方liquid/foam置信度, 下方air置信度)
    """
    # 获取上方liquid/foam的最高置信度
    upper_liquid_conf = _get_class_max_confidence(upper_idx, ['liquid'])
    upper_foam_conf = _get_class_max_confidence(upper_idx, ['foam'])
    upper_lf_conf = max(upper_liquid_conf, upper_foam_conf)
    
    # 获取下方air置信度
    lower_air_conf = _get_class_max_confidence(lower_idx, ['air'])
    
    # 置信度条件：上方liquid/foam>0.8 且 下方air<0.3
    condition_met = (upper_lf_conf > HIGH_CONF_THRESHOLD and 
                    lower_air_conf < LOW_CONF_THRESHOLD)
    
    return condition_met, upper_lf_conf, lower_air_conf


def apply_space_logic(liquid_heights, container_heights, fixed_tops):
    """
    应用空间后处理逻辑
    
    调试信息受本模块 DEBUG_LOG_ENABLED 控制
    
    规则1 (返回码 001)：下方ROI分割结果出现air（没有liquid/foam）且置信度达标 
                       → 上方ROI分割结果air占比95%以上（液位=0）
    规则2 (返回码 002)：上方ROI分割结果出现liquid或foam且置信度达标 
                       → 下方ROI分割结果liquid占比95%以上（液位=满）
    
    Args:
        liquid_heights: 液位高度字典 {idx: height_mm, ...}
        container_heights: 容器高度字典 {idx: height_mm, ...}
        fixed_tops: 容器顶部y坐标字典 {idx: y, ...}
    
    Returns:
        tuple: (修正后的液位高度字典, 触发的规则码列表)
    """
    global _frame_count
    _frame_count += 1
    
    num_regions = len(liquid_heights)
    if num_regions <= 1:
        if DEBUG_LOG_ENABLED:
            print(f"  ⏭️ [SpaceLogic] ROI数量={num_regions}，跳过空间逻辑")
        _log_to_csv({
            'frame_count': _frame_count,
            'num_regions': num_regions,
            'action': f'跳过(区域数={num_regions}<=1)'
        })
        return liquid_heights, []
    
    # 按y坐标排序（y越小越上）
    sorted_indices = sorted(fixed_tops.keys(), key=lambda x: fixed_tops[x])
    
    if DEBUG_LOG_ENABLED:
        print(f"  🔍 [SpaceLogic] ROI排序（从上到下）: {sorted_indices}")
    
    corrected_heights = dict(liquid_heights)
    triggered_rules = []
    
    for i in range(len(sorted_indices) - 1):
        upper_idx = sorted_indices[i]
        lower_idx = sorted_indices[i + 1]
        
        upper_info = _region_mask_info.get(upper_idx, {})
        lower_info = _region_mask_info.get(lower_idx, {})
        
        # 获取类别和置信度信息
        upper_classes = ','.join(upper_info.get('classes', []))
        upper_confs = ','.join([f'{c:.2f}' for c in upper_info.get('confidences', [])])
        lower_classes = ','.join(lower_info.get('classes', []))
        lower_confs = ','.join([f'{c:.2f}' for c in lower_info.get('confidences', [])])
        
        # 获取像素占比信息
        upper_ratios = upper_info.get('pixel_ratios', {})
        lower_ratios = lower_info.get('pixel_ratios', {})
        upper_ratios_str = ','.join([f'{k}:{v:.2%}' for k, v in upper_ratios.items()])
        lower_ratios_str = ','.join([f'{k}:{v:.2%}' for k, v in lower_ratios.items()])
        
        # 检查规则条件
        rule1_met, lower_air_conf, upper_liquid_conf, lower_has_only_air = _check_rule1_condition(lower_idx, upper_idx)
        rule2_met, upper_lf_conf, lower_air_conf2 = _check_rule2_condition(upper_idx, lower_idx)
        
        pair_triggered_rules = []
        action = '无修正'
        
        # 规则1：下方只有air且置信度达标 → 上方air占比≥95%（液位=0）
        if rule1_met:
            upper_air_ratio = _get_class_pixel_ratio(upper_idx, ['air'])
            if DEBUG_LOG_ENABLED:
                print(f"  📏 [SpaceLogic] 规则1触发: 下方区域{lower_idx}只有air(conf={lower_air_conf:.2f}>0.8), "
                      f"上方区域{upper_idx} liquid_conf={upper_liquid_conf:.2f}<0.3 "
                      f"→ 上方修正为air≥95%(当前{upper_air_ratio:.1%}), 液位=0")
            corrected_heights[upper_idx] = 0.0
            triggered_rules.append('001')
            pair_triggered_rules.append('001')
            action = f'规则1:上方区域{upper_idx}修正为air≥95%,液位→0'
        
        # 规则2：上方有liquid/foam且置信度达标 → 下方liquid占比≥95%（液位=满）
        if rule2_met:
            container_height = container_heights.get(lower_idx, 0)
            lower_liquid_ratio = _get_class_pixel_ratio(lower_idx, ['liquid'])
            if container_height > 0:
                if DEBUG_LOG_ENABLED:
                    print(f"  📏 [SpaceLogic] 规则2触发: 上方区域{upper_idx} liquid/foam_conf={upper_lf_conf:.2f}>0.8, "
                          f"下方区域{lower_idx} air_conf={lower_air_conf2:.2f}<0.3 "
                          f"→ 下方修正为liquid≥95%(当前{lower_liquid_ratio:.1%}), 液位={container_height}mm(满)")
                corrected_heights[lower_idx] = container_height
                triggered_rules.append('002')
                pair_triggered_rules.append('002')
                if action == '无修正':
                    action = f'规则2:下方区域{lower_idx}修正为liquid≥95%,液位→{container_height}mm'
                else:
                    action += f'; 规则2:下方区域{lower_idx}修正为liquid≥95%,液位→{container_height}mm'
        
        _log_to_csv({
            'frame_count': _frame_count,
            'num_regions': num_regions,
            'upper_idx': upper_idx,
            'lower_idx': lower_idx,
            'upper_classes': upper_classes,
            'upper_confidences': upper_confs,
            'upper_pixel_ratios': upper_ratios_str,
            'lower_classes': lower_classes,
            'lower_confidences': lower_confs,
            'lower_pixel_ratios': lower_ratios_str,
            'rule1_check': 'PASS' if rule1_met else 'FAIL',
            'rule1_lower_air_conf': lower_air_conf,
            'rule1_upper_liquid_conf': upper_liquid_conf,
            'rule1_lower_has_only_air': 'YES' if lower_has_only_air else 'NO',
            'rule2_check': 'PASS' if rule2_met else 'FAIL',
            'rule2_upper_lf_conf': upper_lf_conf,
            'rule2_lower_air_conf': lower_air_conf2,
            'triggered_rules': ','.join(pair_triggered_rules) if pair_triggered_rules else 'None',
            'original_heights': f'上:{liquid_heights.get(upper_idx, 0):.2f},下:{liquid_heights.get(lower_idx, 0):.2f}',
            'corrected_heights': f'上:{corrected_heights.get(upper_idx, 0):.2f},下:{corrected_heights.get(lower_idx, 0):.2f}',
            'action': action
        })
    
    return corrected_heights, triggered_rules


def process_space_logic(detection_results, container_heights, fixed_tops):
    """
    处理检测结果，应用空间后处理逻辑（主调用接口）
    
    调试信息受本模块 DEBUG_LOG_ENABLED 控制
    
    Args:
        detection_results: 检测结果字典
            {
                'liquid_line_positions': {idx: {'height_mm': float, 'y': int, ...}, ...},
                'success': bool
            }
        container_heights: 容器高度列表或字典
        fixed_tops: 容器顶部y坐标列表或字典
    
    Returns:
        dict: 修正后的检测结果
    """
    if not detection_results.get('success', False):
        return detection_results
    
    liquid_positions = detection_results.get('liquid_line_positions', {})
    
    if len(liquid_positions) <= 1:
        return detection_results
    
    # 转换为字典格式
    if isinstance(container_heights, list):
        container_heights = {i: h for i, h in enumerate(container_heights)}
    if isinstance(fixed_tops, list):
        fixed_tops = {i: y for i, y in enumerate(fixed_tops)}
    
    # 提取液位高度
    liquid_heights = {idx: pos_info.get('height_mm', 0) for idx, pos_info in liquid_positions.items()}
    
    # 应用空间逻辑
    corrected_heights, triggered_rules = apply_space_logic(
        liquid_heights, container_heights, fixed_tops
    )
    
    # 更新检测结果
    corrected_results = dict(detection_results)
    corrected_positions = dict(liquid_positions)
    
    for idx, new_height in corrected_heights.items():
        if idx in corrected_positions:
            old_height = corrected_positions[idx].get('height_mm', 0)
            if new_height != old_height:
                corrected_positions[idx] = dict(corrected_positions[idx])
                corrected_positions[idx]['height_mm'] = new_height
                corrected_positions[idx]['space_logic_applied'] = True
                
                pixel_per_mm = corrected_positions[idx].get('pixel_per_mm', 0)
                if pixel_per_mm <= 0:
                    original_height_px = corrected_positions[idx].get('height_px', 0)
                    if old_height > 0:
                        pixel_per_mm = original_height_px / old_height
                    else:
                        pixel_per_mm = 10.0
                
                new_height_px = int(new_height * pixel_per_mm)
                corrected_positions[idx]['height_px'] = new_height_px
                
                old_height_px = int(old_height * pixel_per_mm)
                container_bottom_y = corrected_positions[idx].get('y', 0) + old_height_px
                corrected_positions[idx]['y'] = container_bottom_y - new_height_px
    
    corrected_results['liquid_line_positions'] = corrected_positions
    corrected_results['space_logic_rules'] = triggered_rules
    
    return corrected_results


def reset_space_logic():
    """重置空间逻辑状态"""
    global _region_mask_info, _frame_count
    _region_mask_info = {}
    _frame_count = 0
