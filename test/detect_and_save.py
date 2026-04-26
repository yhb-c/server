#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
液位检测脚本
对测试集图片进行液位检测，保存检测结果到JSON文件
"""

import os
import sys
import cv2
import yaml
import json
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


def draw_detection_result(image, detection_result, annotation_config):
    """在图片上绘制检测结果"""
    img_draw = image.copy()
    img_height, img_width = image.shape[:2]

    liquid_positions = detection_result.get('liquid_line_positions', {})

    for idx, pos_info in liquid_positions.items():
        # 图片已经是裁剪好的ROI，使用图片边界作为绘制范围
        left = 0
        right = img_width
        top = 0
        bottom = img_height

        # 绘制容器顶部和底部线（绿色）
        fixed_bottoms = annotation_config['fixed_bottoms']
        fixed_tops = annotation_config['fixed_tops']
        boxes = annotation_config['boxes']

        # 获取ROI的裁剪偏移量
        if idx < len(boxes):
            box = boxes[idx]
            center_x, center_y, crop_size = box
            half_size = crop_size // 2
            crop_top_y = center_y - half_size

            # 将原始坐标系的容器线转换为ROI坐标系
            if idx < len(fixed_bottoms):
                container_bottom = fixed_bottoms[idx] - crop_top_y
                cv2.line(img_draw, (left, container_bottom), (right, container_bottom), (0, 255, 0), 2)

            if idx < len(fixed_tops):
                container_top = fixed_tops[idx] - crop_top_y
                cv2.line(img_draw, (left, container_top), (right, container_top), (0, 255, 0), 2)

            # 将液位线y坐标转换为ROI坐标系
            liquid_y_original = pos_info['y']
            liquid_y = liquid_y_original - crop_top_y
            cv2.line(img_draw, (left, liquid_y), (right, liquid_y), (0, 0, 255), 3)

            # 标注液位高度文本
            height_mm = pos_info['height_mm']
            is_full = pos_info.get('is_full', False)
            error_flag = pos_info.get('error_flag', None)

            text = f"{height_mm:.2f}mm"
            if is_full:
                text += " (FULL)"
            if error_flag:
                text += f" [{error_flag}]"

            # 在液位线旁边显示文本
            text_y = max(liquid_y - 10, 20)
            cv2.putText(img_draw, text, (10, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    return img_draw


def main():
    # 配置路径
    image_dir = project_root / "testpicture" / "images"
    output_dir = project_root / "testpicture" / "output"
    output_file = project_root / "testpicture" / "detection_results.json"
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

    # 存储所有检测结果
    all_results = {}

    # 处理每张图片
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
            all_results[img_path.name] = {
                'success': False,
                'error': '检测失败'
            }
            continue

        # 提取检测结果
        liquid_positions = detection_result.get('liquid_line_positions', {})

        result_data = {
            'success': True,
            'image_size': {
                'width': image.shape[1],
                'height': image.shape[0]
            },
            'detections': {}
        }

        for idx, pos_info in liquid_positions.items():
            height_mm = pos_info['height_mm']
            is_full = pos_info.get('is_full', False)
            error_flag = pos_info.get('error_flag', None)

            result_data['detections'][f'area_{idx+1}'] = {
                'height_mm': round(height_mm, 2),
                'is_full': is_full,
                'error_flag': error_flag,
                'liquid_y': pos_info['y'],
                'height_px': pos_info['height_px']
            }

            print(f"  区域{idx+1}: {height_mm:.2f}mm", end="")
            if is_full:
                print(" (满液)", end="")
            if error_flag:
                print(f" [{error_flag}]", end="")
            print()

        all_results[img_path.name] = result_data

        # 绘制检测结果并保存图片
        img_with_detection = draw_detection_result(image, detection_result, annotation_config)
        output_path = output_dir / img_path.name
        cv2.imwrite(str(output_path), img_with_detection)
        print(f"  保存到: {output_path}")

    # 保存结果到JSON文件
    print(f"\n保存检测结果到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n检测完成，共处理 {len(all_results)} 张图片")
    print(f"结果已保存到: {output_file}")

    # 清理资源
    engine.cleanup()


if __name__ == "__main__":
    main()
