# -*- coding: utf-8 -*-
"""
检测速度测试脚本
测试单路视频2个ROI的最高检测帧率
"""

import sys
import os
import cv2
import yaml
import time
import numpy as np
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root / 'client'))

from handlers.videopage.detection.detection import LiquidDetectionEngine


def load_annotation_config(config_path, channel_id):
    """加载指定通道的标注配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        all_configs = yaml.safe_load(f)

    if channel_id not in all_configs:
        raise ValueError(f"通道 {channel_id} 不存在于配置文件中")

    config = all_configs[channel_id]
    return {
        'boxes': config['boxes'],
        'fixed_bottoms': config['fixed_bottoms'],
        'fixed_tops': config['fixed_tops'],
        'actual_heights': [area['height'].replace('mm', '') for area in config['areas'].values()],
        'fixed_init_levels': config.get('fixed_init_levels', []),
        'areas': config.get('areas', {}),
        'channel_id': channel_id
    }


def test_detection_speed():
    """测试单路视频2个ROI的最高检测帧率"""

    # 配置路径
    model_path = Path("/home/lqj/liquid/server/database/model/detection_model/testmodel/1.engine")
    video_path = Path("/home/lqj/liquid/testvideo/1.mp4")
    config_path = Path("/home/lqj/liquid/server/database/config/annotation_result.yaml")
    channel_id = "channel1"

    if not model_path.exists():
        print(f"错误: 模型文件不存在 {model_path}")
        return

    if not video_path.exists():
        print(f"错误: 视频文件不存在 {video_path}")
        return

    if not config_path.exists():
        print(f"错误: 配置文件不存在 {config_path}")
        return

    print("=" * 80)
    print("单路视频2个ROI最高帧率测试")
    print("=" * 80)
    print(f"模型: {model_path.name}")
    print(f"视频: {video_path.name}")
    print(f"通道: {channel_id}")
    print("-" * 80)

    # 初始化检测引擎
    print("正在加载模型...")
    engine = LiquidDetectionEngine(model_path=str(model_path), device='cuda')
    if not engine.load_model(str(model_path)):
        print("错误: 无法加载模型")
        return

    print("模型加载成功")
    print("-" * 80)

    # 测试视频
    result = test_single_video(engine, video_path, config_path, channel_id)

    # 清理引擎
    engine.cleanup()

    # 输出结果
    if result:
        print("\n" + "=" * 80)
        print("测试结果")
        print("=" * 80)
        print(f"总帧数: {result['total_frames']}")
        print(f"总耗时: {result['total_time']:.2f}s")
        print(f"平均FPS: {result['avg_fps']:.2f}")
        print(f"最高FPS: {result['max_fps']:.2f}")
        print(f"最低FPS: {result['min_fps']:.2f}")
        print("-" * 80)
        print(f"平均每帧检测耗时: {result['avg_latency']:.2f}ms")
        print(f"最快检测耗时: {result['min_latency']:.2f}ms")
        print(f"最慢检测耗时: {result['max_latency']:.2f}ms")
        print("-" * 80)
        for i, roi_latency in enumerate(result['roi_latencies'], 1):
            print(f"ROI{i} 平均检测耗时: {roi_latency:.2f}ms")
        print("=" * 80)

        # 保存结果到testresult.md
        save_result_to_file(result)


def save_result_to_file(result):
    """保存测试总结到testresult.md"""
    result_path = Path("/home/lqj/liquid/testresult.md")

    with open(result_path, 'w', encoding='utf-8') as f:
        f.write(f"检测路数: {result['num_channels']}, ROI数量: {result['num_rois']}, ROI大小: {result['roi_sizes']}, 平均检测FPS: {result['avg_fps']:.2f}\n")

    print(f"\n测试总结已保存到: {result_path}")


def test_single_video(engine, video_path, config_path, channel_id):
    """测试单个视频的检测速度，计算最高帧率"""

    MAX_FRAMES = 2000  # 最多检测2000帧

    print(f"开始测试 (通道: {channel_id})")

    # 加载标注配置
    try:
        annotation_config = load_annotation_config(config_path, channel_id)
        print(f"\n[调试] 标注配置:")
        print(f"  boxes: {annotation_config['boxes']}")
        print(f"  fixed_bottoms: {annotation_config['fixed_bottoms']}")
        print(f"  fixed_tops: {annotation_config['fixed_tops']}")
        print(f"  actual_heights: {annotation_config['actual_heights']}")
        print(f"  areas: {annotation_config.get('areas', {})}")
    except Exception as e:
        print(f"错误: 无法加载通道 {channel_id} 的配置: {e}")
        return None

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("错误: 无法打开视频")
        return None

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    num_rois = len(annotation_config['boxes'])
    test_frames = min(MAX_FRAMES, total_frames)
    print(f"视频信息: {total_frames} 帧, {fps:.2f} FPS, {num_rois} 个ROI, 测试 {test_frames} 帧")

    # 创建CSV文件并写入表头
    csv_path = Path("/home/lqj/liquid/1.csv")
    csv_file = open(csv_path, 'w', encoding='utf-8')

    # 根据ROI数量生成表头
    header = "时间戳"
    for i in range(1, num_rois + 1):
        header += f",ROI{i}液位线"
    csv_file.write(header + "\n")

    # 测试统计
    frame_count = 0
    detect_times = []  # 每帧检测时间列表(毫秒)
    roi_detect_times = [[] for _ in range(num_rois)]  # 每个ROI的检测时间列表
    start_time = time.time()

    # 逐帧检测
    while frame_count < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # 检测液位
        detect_start = time.time()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        detect_result = engine.detect(frame, annotation_config=annotation_config, channel_id=channel_id)
        detect_end = time.time()

        # 计算单帧检测时间
        detect_time = (detect_end - detect_start) * 1000  # 毫秒
        detect_times.append(detect_time)

        # 调试信息：打印第一帧的检测结果
        if frame_count == 1:
            print(f"\n[调试] 第1帧检测结果:")
            print(f"  detect_result类型: {type(detect_result)}")
            print(f"  detect_result内容: {detect_result}")
            if detect_result:
                print(f"  detect_result的keys: {detect_result.keys() if isinstance(detect_result, dict) else 'N/A'}")
                print(f"  success: {detect_result.get('success', 'N/A')}")
                print(f"  liquid_line_positions: {detect_result.get('liquid_line_positions', 'N/A')}")

        # 保存检测结果到CSV（时间戳和液位线）
        csv_line = timestamp
        if detect_result and detect_result.get('success') and detect_result.get('liquid_line_positions'):
            liquid_positions = detect_result['liquid_line_positions']
            # 按ROI索引顺序提取液位线位置
            for i in range(num_rois):
                if i in liquid_positions:
                    position_data = liquid_positions[i]
                    # 提取液位线的y坐标
                    if isinstance(position_data, dict) and 'liquid_line_y' in position_data:
                        csv_line += f",{position_data['liquid_line_y']}"
                    elif isinstance(position_data, (int, float)):
                        csv_line += f",{position_data}"
                    else:
                        csv_line += ","
                else:
                    csv_line += ","
            # 调试信息：每100帧打印一次液位线数据
            if frame_count % 100 == 0:
                print(f"[调试] 第{frame_count}帧液位线: {liquid_positions}")
        else:
            # 如果没有检测结果，填充空值
            for i in range(num_rois):
                csv_line += ","
            # 调试信息：打印为什么没有液位线数据
            if frame_count <= 5:
                success = detect_result.get('success', False) if detect_result else False
                has_positions = bool(detect_result.get('liquid_line_positions')) if detect_result else False
                print(f"[调试] 第{frame_count}帧没有液位线数据，success={success}, has_positions={has_positions}, positions={detect_result.get('liquid_line_positions') if detect_result else None}")
        csv_file.write(csv_line + "\n")

        if frame_count % 100 == 0:
            csv_file.flush()

        # 所有ROI共享同一个检测时间
        for i in range(num_rois):
            roi_detect_times[i].append(detect_time)

        # 每50帧输出一次进度
        if frame_count % 50 == 0:
            print(f"进度: {frame_count}/{test_frames} 帧")

    cap.release()
    csv_file.close()
    print(f"每帧检测结果已保存到: {csv_path}")

    # 计算统计数据
    total_time = time.time() - start_time

    print(f"测试完成: {frame_count} 帧, 耗时 {total_time:.2f}s")

    # 计算平均检测耗时和FPS
    avg_latency = np.mean(detect_times)
    min_latency = np.min(detect_times)
    max_latency = np.max(detect_times)

    # 平均FPS = 1000ms / 平均每帧耗时(ms)
    avg_fps = 1000.0 / avg_latency if avg_latency > 0 else 0
    max_fps = 1000.0 / min_latency if min_latency > 0 else 0
    min_fps = 1000.0 / max_latency if max_latency > 0 else 0

    # 计算每个ROI的平均检测耗时
    roi_latencies = []
    for i in range(num_rois):
        if roi_detect_times[i]:
            avg_time = np.mean(roi_detect_times[i])
            roi_latencies.append(avg_time)
        else:
            roi_latencies.append(0)

    # 获取ROI大小信息
    roi_sizes = []
    for box in annotation_config['boxes']:
        x, y, width = box
        # 高度从fixed_bottoms和fixed_tops计算
        height = annotation_config['fixed_bottoms'][len(roi_sizes)] - annotation_config['fixed_tops'][len(roi_sizes)]
        roi_sizes.append(f"{width}x{height}")

    return {
        'total_frames': frame_count,
        'total_time': total_time,
        'avg_fps': avg_fps,
        'max_fps': max_fps,
        'min_fps': min_fps,
        'avg_latency': avg_latency,
        'min_latency': min_latency,
        'max_latency': max_latency,
        'num_channels': 1,
        'num_rois': num_rois,
        'roi_sizes': ', '.join(roi_sizes),
        'roi_latencies': roi_latencies
    }


if __name__ == "__main__":
    test_detection_speed()
