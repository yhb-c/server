# -*- coding: utf-8 -*-
"""
模型推理异常后处理逻辑模块

功能：
    1. 设置初始液位状态变量 detect_initstatus
    2. 检测模型推理结果与初始状态是否一致
    3. 处理模型推理异常情况（标签转换）
    4. 判断模型推理是否恢复正常
    - 默认 → detect_initstatus = 0（不进入异常处理逻辑）
    - 满   → detect_initstatus = 1（初始状态只有liquid）
    - 空   → detect_initstatus = 2（初始状态只有air）
    
"""

import numpy as np


def calculate_initstatus(num_targets, annotation_initstatus=None):
    """
    从标注结果读取detect_initstatus
    
    标注界面状态对应关系：
    - 默认 → detect_initstatus = 0（不进入异常处理逻辑）
    - 满   → detect_initstatus = 1（初始状态只有liquid）
    - 空   → detect_initstatus = 2（初始状态只有air）
    
    Args:
        num_targets: 目标数量
        annotation_initstatus: 从标注结果读取的初始状态列表 [0/1/2, ...]
    
    Returns:
        list: detect_initstatus 列表
    """
    detect_initstatus = []
    
    for idx in range(num_targets):
        if annotation_initstatus and idx < len(annotation_initstatus):
            status = annotation_initstatus[idx]
            # 确保状态值有效
            if status not in [0, 1, 2]:
                status = 0
        else:
            status = 0  # 默认不处理
        
        detect_initstatus.append(status)
    
    return detect_initstatus


def process_masks(all_masks_info, idx, detect_initstatus, init_mask_pixel_counts, 
                  is_inference_error, channel_id=None):
    """
    处理模型推理结果，检测并修正异常
    
    Args:
        all_masks_info: mask信息列表 [(mask, class_name, confidence), ...]
        idx: ROI索引
        detect_initstatus: 初始状态列表
        init_mask_pixel_counts: 初始掩码像素数量列表
        is_inference_error: 异常状态标记列表
        channel_id: 通道ID（用于日志记录，区分多通道）
    
    Returns:
        tuple: (处理后的mask列表, 更新后的init_mask_pixel_counts, 更新后的is_inference_error)
    """
    # 确保列表长度足够
    while len(detect_initstatus) <= idx:
        detect_initstatus.append(0)
    while len(init_mask_pixel_counts) <= idx:
        init_mask_pixel_counts.append(0)
    while len(is_inference_error) <= idx:
        is_inference_error.append(False)
    
    # 如果 detect_initstatus 为 0，不进入异常处理逻辑
    if detect_initstatus[idx] == 0:
        return all_masks_info, init_mask_pixel_counts, is_inference_error
    
    init_status = detect_initstatus[idx]
    
    # 分析当前mask结果
    liquid_masks = []
    air_masks = []
    other_masks = []
    
    for mask, class_name, conf in all_masks_info:
        if class_name == 'liquid':
            liquid_masks.append((mask, class_name, conf))
        elif class_name == 'air':
            air_masks.append((mask, class_name, conf))
        else:
            other_masks.append((mask, class_name, conf))
    
    # 计算像素数量
    liquid_pixel_count = sum(np.sum(m[0]) for m in liquid_masks) if liquid_masks else 0
    air_pixel_count = sum(np.sum(m[0]) for m in air_masks) if air_masks else 0
    total_pixel_count = liquid_pixel_count + air_pixel_count
    
    # 计算占比
    liquid_ratio = liquid_pixel_count / total_pixel_count if total_pixel_count > 0 else 0
    air_ratio = air_pixel_count / total_pixel_count if total_pixel_count > 0 else 0
    
    # 记录初始掩码像素数量（首次检测时）
    if init_mask_pixel_counts[idx] == 0:
        if init_status == 1 and liquid_pixel_count > 0:
            init_mask_pixel_counts[idx] = liquid_pixel_count
        elif init_status == 2 and air_pixel_count > 0:
            init_mask_pixel_counts[idx] = air_pixel_count
    
    # 恢复正常检查
    if is_inference_error[idx]:
        recovery_result = _check_recovery(liquid_masks, air_masks, idx, init_status, 
                                          liquid_ratio, air_ratio, init_mask_pixel_counts)
        if recovery_result:
            is_inference_error[idx] = False
            return all_masks_info, init_mask_pixel_counts, is_inference_error
        else:
            # 仍处于异常状态，执行持续矫正
            result = _apply_error_correction(liquid_masks, air_masks, other_masks, init_status, idx)
            return result, init_mask_pixel_counts, is_inference_error
    
    # 异常判定（基于像素占比≥90%）
    THRESHOLD = 0.90
    
    if init_status == 1 and air_ratio >= THRESHOLD:
        is_inference_error[idx] = True
        result = _apply_error_correction(liquid_masks, air_masks, other_masks, init_status, idx)
        return result, init_mask_pixel_counts, is_inference_error
    
    if init_status == 2 and liquid_ratio >= THRESHOLD:
        is_inference_error[idx] = True
        result = _apply_error_correction(liquid_masks, air_masks, other_masks, init_status, idx)
        return result, init_mask_pixel_counts, is_inference_error
    
    return all_masks_info, init_mask_pixel_counts, is_inference_error


def _apply_error_correction(liquid_masks, air_masks, other_masks, init_status, idx):
    """应用异常矫正逻辑（调试信息写入CSV日志）"""
    if init_status == 1:
        # 初始只有liquid，将air标签转为liquid
        corrected_masks = [(mask, 'liquid', conf) for mask, class_name, conf in air_masks]
        return corrected_masks + other_masks
    elif init_status == 2:
        # 初始只有air，过滤liquid只保留air
        return air_masks + other_masks
    else:
        return liquid_masks + air_masks + other_masks


def _check_recovery(liquid_masks, air_masks, idx, init_status, liquid_ratio, air_ratio, 
                    init_mask_pixel_counts):
    """检查模型推理是否恢复正常"""
    RECOVERY_THRESHOLD = 0.90
    init_pixel_count = init_mask_pixel_counts[idx] if idx < len(init_mask_pixel_counts) else 0
    
    # 恢复条件1: init_status=1 且 liquid占比≥90%
    if init_status == 1 and liquid_ratio >= RECOVERY_THRESHOLD:
        return True
    
    # 恢复条件2: init_status=2 且 air占比≥90%
    if init_status == 2 and air_ratio >= RECOVERY_THRESHOLD:
        return True
    
    # 恢复条件3: init_status=1 且 位置+像素数量判断
    if init_status == 1 and liquid_masks and air_masks and init_pixel_count > 0:
        try:
            air_min_y = min(np.min(np.where(m[0])[0]) for m in air_masks if np.sum(m[0]) > 0)
            liquid_min_y = min(np.min(np.where(m[0])[0]) for m in liquid_masks if np.sum(m[0]) > 0)
            
            if air_min_y < liquid_min_y:
                air_pixel_count = sum(np.sum(m[0]) for m in air_masks)
                if air_pixel_count <= init_pixel_count * 0.2:
                    return True
        except (ValueError, StopIteration):
            pass
    
    # 恢复条件4: init_status=2 且 位置+像素数量判断
    if init_status == 2 and liquid_masks and air_masks and init_pixel_count > 0:
        try:
            liquid_max_y = max(np.max(np.where(m[0])[0]) for m in liquid_masks if np.sum(m[0]) > 0)
            air_max_y = max(np.max(np.where(m[0])[0]) for m in air_masks if np.sum(m[0]) > 0)
            
            if liquid_max_y > air_max_y:
                liquid_pixel_count = sum(np.sum(m[0]) for m in liquid_masks)
                if liquid_pixel_count <= init_pixel_count * 0.2:
                    return True
        except (ValueError, StopIteration):
            pass
    
    return False


def reset_init_error_state():
    """重置模块状态"""
    pass
