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


def test_single_video(engine, video_path, config_path, channel_id):
    """测试单个视频的检测速度，计算最高帧率"""

    MAX_FRAMES = 2000  # 最多检测2000帧

    # 创建时间日志文件
    log_path = Path(__file__).parent / "detection_timing_log.txt"
    log_file = open(log_path, 'w', encoding='utf-8')
    log_file.write(f"检测时间记录 - {video_path.name}\n")
    log_file.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
    log_file.write("-" * 80 + "\n")
    log_file.write(f"{'帧号':<10} {'时间戳':<30} {'检测耗时(ms)':<15} {'瞬时FPS':<15}\n")
    log_file.write("-" * 80 + "\n")

    print(f"开始测试 (通道: {channel_id})")

    # 加载标注配置
    try:
        annotation_config = load_annotation_config(config_path, channel_id)
    except Exception as e:
        print(f"错误: 无法加载通道 {channel_id} 的配置: {e}")
        log_file.close()
        return None

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("错误: 无法打开视频")
        log_file.close()
        return None

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    num_rois = len(annotation_config['boxes'])
    test_frames = min(MAX_FRAMES, total_frames)
    print(f"视频信息: {total_frames} 帧, {fps:.2f} FPS, {num_rois} 个ROI, 测试 {test_frames} 帧")

    # 测试统计
    frame_count = 0
    detect_times = []  # 每帧检测时间列表(毫秒)
    fps_list = []  # 每帧FPS列表
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
        result = engine.detect(frame, annotation_config=annotation_config, channel_id=channel_id)
        detect_end = time.time()

        # 计算单帧检测时间和瞬时FPS
        detect_time = (detect_end - detect_start) * 1000  # 毫秒
        instant_fps = 1000.0 / detect_time if detect_time > 0 else 0

        detect_times.append(detect_time)
        fps_list.append(instant_fps)

        # 记录到日志
        log_file.write(f"{frame_count:<10} {timestamp:<30} {detect_time:<15.2f} {instant_fps:<15.2f}\n")
        if frame_count % 100 == 0:
            log_file.flush()

        # 所有ROI共享同一个检测时间
        for i in range(num_rois):
            roi_detect_times[i].append(detect_time)

        # 每50帧输出一次进度
        if frame_count % 50 == 0:
            avg_fps_so_far = np.mean(fps_list)
            print(f"进度: {frame_count}/{test_frames} 帧, 当前平均FPS: {avg_fps_so_far:.2f}")

    cap.release()

    # 关闭日志文件
    log_file.write("-" * 80 + "\n")
    log_file.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
    log_file.write(f"总帧数: {frame_count}\n")
    log_file.close()
    print("时间日志已保存")

    # 计算统计数据
    total_time = time.time() - start_time

    print(f"测试完成: {frame_count} 帧, 耗时 {total_time:.2f}s")

    # 计算FPS统计
    avg_fps = np.mean(fps_list)
    max_fps = np.max(fps_list)
    min_fps = np.min(fps_list)

    # 计算检测耗时统计
    avg_latency = np.mean(detect_times)
    min_latency = np.min(detect_times)
    max_latency = np.max(detect_times)

    # 计算每个ROI的平均检测耗时
    roi_latencies = []
    for i in range(num_rois):
        if roi_detect_times[i]:
            avg_time = np.mean(roi_detect_times[i])
            roi_latencies.append(avg_time)
        else:
            roi_latencies.append(0)

    return {
        'total_frames': frame_count,
        'total_time': total_time,
        'avg_fps': avg_fps,
        'max_fps': max_fps,
        'min_fps': min_fps,
        'avg_latency': avg_latency,
        'min_latency': min_latency,
        'max_latency': max_latency,
        'num_rois': num_rois,
        'roi_latencies': roi_latencies
    }


if __name__ == "__main__":
    test_detection_speed()
