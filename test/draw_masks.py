#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
液位掩码绘制脚本
对测试集图片进行液位检测，绘制模型输出的掩码区域
"""

import os
import sys
import cv2
import yaml
import numpy as np
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "server"))

from server.detection.detection import LiquidDetectionEngine


def load_annotation_config(config_path, channel_id):
    """加载标注配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if channel_id not in config:
        raise ValueError(f"通道 {channel_id} 不存在于配置文件中")

    channel_config = config[channel_id]

    # 提取配置信息
    boxes = channel_config.get('boxes', [])
    fixed_bottoms = channel_config.get('fixed_bottoms', [])
    fixed_tops = channel_config.get('fixed_tops', [])
    fixed_init_levels = channel_config.get('fixed_init_levels', [])
    areas = channel_config.get('areas', {})

    # 计算实际高度
    actual_heights = []
    annotation_initstatus = []
    for i in range(len(boxes)):
        area_key = f'area_{i+1}'
        area_info = areas.get(area_key, {})
        height_str = area_info.get('height', '20mm')
        height_mm = float(height_str.replace('mm', ''))
        actual_heights.append(height_mm)

        init_status = area_info.get('init_status', 0)
        annotation_initstatus.append(init_status)

    return {
        'boxes': boxes,
        'fixed_bottoms': fixed_bottoms,
        'fixed_tops': fixed_tops,
        'actual_heights': actual_heights,
        'fixed_init_levels': fixed_init_levels,
        'annotation_initstatus': annotation_initstatus,
        'areas': areas,
        'channel_id': channel_id
    }


def get_class_color(class_name):
    """为不同类别分配颜色"""
    color_map = {
        'liquid': (0, 255, 0),    # 绿色
        'foam': (255, 0, 0),       # 蓝色
        'air': (0, 0, 255),        # 红色
    }
    return color_map.get(class_name, (128, 128, 128))


def draw_masks(image, detection_result, annotation_config):
    """在图片上绘制掩码区域"""
    img_draw = image.copy()
    img_height, img_width = image.shape[:2]

    liquid_positions = detection_result.get('liquid_line_positions', {})

    for idx, pos_info in liquid_positions.items():
        # 获取观测掩码
        observation_mask = pos_info.get('observation_mask', [])

        if not observation_mask:
            continue

        # 创建掩码叠加层
        mask_overlay = np.zeros_like(img_draw)

        # 绘制每个掩码
        for mask, class_name, confidence in observation_mask:
            color = get_class_color(class_name)

            # 调整掩码尺寸以匹配图片
            if mask.shape != (img_height, img_width):
                mask_resized = cv2.resize(mask.astype(np.uint8), (img_width, img_height), interpolation=cv2.INTER_NEAREST)
                mask_resized = mask_resized.astype(bool)
            else:
                mask_resized = mask

            # 将掩码应用到叠加层
            mask_overlay[mask_resized > 0] = color

        # 将掩码叠加到原图（半透明）
        alpha = 0.5
        img_draw = cv2.addWeighted(img_draw, 1, mask_overlay, alpha, 0)

        # 绘制容器顶部和底部线
        fixed_bottoms = annotation_config['fixed_bottoms']
        fixed_tops = annotation_config['fixed_tops']
        boxes = annotation_config['boxes']

        if idx < len(boxes):
            box = boxes[idx]
            center_x, center_y, crop_size = box
            half_size = crop_size // 2
            crop_top_y = center_y - half_size

            # 转换坐标系
            if idx < len(fixed_bottoms):
                container_bottom = fixed_bottoms[idx] - crop_top_y
                cv2.line(img_draw, (0, container_bottom), (img_width, container_bottom), (255, 255, 255), 2)

            if idx < len(fixed_tops):
                container_top = fixed_tops[idx] - crop_top_y
                cv2.line(img_draw, (0, container_top), (img_width, container_top), (255, 255, 255), 2)

            # 绘制液位线
            liquid_y_original = pos_info['y']
            liquid_y = liquid_y_original - crop_top_y
            cv2.line(img_draw, (0, liquid_y), (img_width, liquid_y), (0, 255, 255), 3)

            # 标注信息
            height_mm = pos_info['height_mm']
            is_full = pos_info.get('is_full', False)
            error_flag = pos_info.get('error_flag', None)

            text = f"{height_mm:.2f}mm"
            if is_full:
                text += " (FULL)"
            if error_flag:
                text += f" [{error_flag}]"

            text_y = max(liquid_y - 10, 20)
            cv2.putText(img_draw, text, (10, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 绘制图例
        legend_y = 30
        cv2.putText(img_draw, "Liquid", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(img_draw, "Foam", (120, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.putText(img_draw, "Air", (220, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    return img_draw


def main():
    # 配置路径
    image_dir = project_root / "testpicture" / "images"
    output_dir = project_root / "testpicture" / "masks_output"
    config_path = project_root / "server" / "config" / "annotation_result.yaml"
    model_path = project_root / "server" / "database" / "model" / "detection_model" / "bestmodel" / "2.engine"

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 通道ID
    channel_id = "channel2"

    print(f"加载配置文件: {config_path}")
    annotation_config = load_annotation_config(config_path, channel_id)

    print(f"初始化液位检测引擎...")
    engine = LiquidDetectionEngine(device='cuda')

    # 启用模型调试模式，获取掩码信息
    engine.modeldebug = True

    print(f"加载模型: {model_path}")
    if not engine.load_model(str(model_path)):
        print("模型加载失败")
        return

    print(f"配置检测参数...")
    engine.configure(
        boxes=annotation_config['boxes'],
        fixed_bottoms=annotation_config['fixed_bottoms'],
        fixed_tops=annotation_config['fixed_tops'],
        actual_heights=annotation_config['actual_heights'],
        annotation_initstatus=annotation_config['annotation_initstatus']
    )

    # 获取所有图片文件
    image_files = sorted(image_dir.glob("*.jpg"))

    if not image_files:
        print(f"未找到图片文件: {image_dir}")
        return

    print(f"找到 {len(image_files)} 张图片")

    # 处理每张图片
    success_count = 0
    for img_path in image_files:
        print(f"\n处理图片: {img_path.name}")

        # 读取图片
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"  无法读取图片: {img_path}")
            continue

        # 检测液位
        detection_result = engine.detect(image, annotation_config, channel_id=channel_id)

        if not detection_result['success']:
            print(f"  检测失败")
            continue

        # 提取检测结果
        liquid_positions = detection_result.get('liquid_line_positions', {})

        for idx, pos_info in liquid_positions.items():
            height_mm = pos_info['height_mm']
            is_full = pos_info.get('is_full', False)
            error_flag = pos_info.get('error_flag', None)

            print(f"  区域{idx+1}: {height_mm:.2f}mm", end="")
            if is_full:
                print(" (满液)", end="")
            if error_flag:
                print(f" [{error_flag}]", end="")
            print()

        # 绘制掩码并保存
        img_with_masks = draw_masks(image, detection_result, annotation_config)
        output_path = output_dir / img_path.name
        cv2.imwrite(str(output_path), img_with_masks)
        print(f"  保存到: {output_path}")
        success_count += 1

    print(f"\n处理完成，成功处理 {success_count} 张图片")
    print(f"结果保存在: {output_dir}")

    # 清理资源
    engine.cleanup()


if __name__ == "__main__":
    main()
