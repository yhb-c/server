# -*- coding: utf-8 -*-
"""
检测速度测试脚本
测试液位检测引擎在多视频场景下的推理速度
一个模型负责两个视频的检测，所有视频同时并行测试
"""

import sys
import os
import cv2
import yaml
import time
import numpy as np
from pathlib import Path
from threading import Thread, Lock
from queue import Queue
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
    """测试检测速度：所有视频同时并行测试，一个模型负责四个视频"""

    # 配置路径
    model_dir = Path("/home/lqj/liquid/server/database/model/detection_model/testmodel")
    video_dir = Path("/home/lqj/liquid/testvideo")
    config_path = Path("/home/lqj/liquid/server/database/config/annotation_result.yaml")

    # 获取所有模型和视频
    model_files = sorted([f for f in model_dir.glob("*.engine")])
    video_files = sorted([f for f in video_dir.glob("*.mp4")])

    # 只使用模型1、2、3、4
    model_files = [f for f in model_files if f.name in ['1.engine', '2.engine', '3.engine', '4.engine']]

    if not model_files:
        print(f"错误: 未找到模型文件在 {model_dir}")
        return

    if not video_files:
        print(f"错误: 未找到视频文件在 {video_dir}")
        return

    print(f"找到 {len(model_files)} 个模型文件")
    print(f"找到 {len(video_files)} 个视频文件")
    print("-" * 80)

    # 创建模型-视频映射关系（一个模型负责四个视频）
    video_tasks = []
    for model_idx, model_path in enumerate(model_files, 1):
        # 计算该模型负责的视频索引（每个模型4个视频）
        video_start_idx = (model_idx - 1) * 4

        for offset in range(4):
            video_idx = video_start_idx + offset
            if video_idx >= len(video_files):
                break

            video_tasks.append({
                'model_path': model_path,
                'video_path': video_files[video_idx],
                'channel_id': f"channel{video_idx + 1}",
                'model_name': model_path.name,
                'video_name': video_files[video_idx].name
            })

    print(f"\n准备同时测试 {len(video_tasks)} 个视频")
    print(f"{'='*80}\n")

    # 结果存储
    results_lock = Lock()
    all_results = []

    # 创建线程池
    threads = []
    for task in video_tasks:
        thread = Thread(
            target=test_video_thread,
            args=(task, config_path, all_results, results_lock)
        )
        threads.append(thread)

    # 启动所有线程
    start_time = time.time()
    for thread in threads:
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    total_time = time.time() - start_time

    # 输出汇总结果
    print(f"\n\n{'='*80}")
    print("测试汇总 - 每帧模型计算耗时")
    print(f"{'='*80}")
    print(f"总测试时间: {total_time:.2f}s (并行执行)")
    print(f"{'='*80}")
    print(f"{'ROI序号':<10} {'视频':<15} {'每帧耗时(ms)':<15}")
    print("-" * 80)

    # 按ROI序号排序输出
    roi_results = []
    for result in all_results:
        video_name = result['video']
        # 从视频名称提取序号，例如 1.mp4 -> 1
        video_num = int(video_name.split('.')[0])
        # 计算ROI序号：1.mp4对应ROI1和ROI2，2.mp4对应ROI3和ROI4
        base_roi = (video_num - 1) * 2

        for local_idx, latency in enumerate(result['roi_latencies'], 1):
            roi_num = base_roi + local_idx
            roi_results.append({
                'roi_num': roi_num,
                'video': video_name,
                'latency': latency
            })

    # 按ROI序号排序
    roi_results.sort(key=lambda x: x['roi_num'])

    for item in roi_results:
        print(f"{item['roi_num']:<10} {item['video']:<15} {item['latency']:<15.2f}")

    print(f"{'='*80}\n")


def test_video_thread(task, config_path, results_list, results_lock):
    """线程函数：测试单个视频"""
    model_path = task['model_path']
    video_path = task['video_path']
    channel_id = task['channel_id']
    model_name = task['model_name']
    video_name = task['video_name']

    print(f"[线程启动] 模型: {model_name}, 视频: {video_name}, 通道: {channel_id}")

    # 初始化检测引擎
    engine = LiquidDetectionEngine(model_path=str(model_path), device='cuda')
    if not engine.load_model(str(model_path)):
        print(f"[错误] 无法加载模型 {model_path}")
        return

    # 测试视频
    result = test_single_video(engine, video_path, config_path, channel_id, model_name, video_name)

    # 清理引擎
    engine.cleanup()

    # 保存结果
    if result:
        with results_lock:
            results_list.append(result)

    print(f"[线程完成] 模型: {model_name}, 视频: {video_name}")


def test_single_video(engine, video_path, config_path, channel_id, model_name, video_name):
    """测试单个视频的检测速度，输出每个ROI的检测速度"""

    MAX_FRAMES = 2000 # 最多检测2000帧

    # 如果是1.mp4，创建时间日志文件
    log_file = None
    if video_name == "1.mp4":
        log_path = Path(__file__).parent / "detection_timing_log.txt"
        log_file = open(log_path, 'w', encoding='utf-8')
        log_file.write(f"检测时间记录 - {video_name}\n")
        log_file.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        log_file.write("-" * 80 + "\n")
        log_file.write(f"{'帧号':<10} {'时间戳':<30} {'检测耗时(ms)':<15}\n")
        log_file.write("-" * 80 + "\n")

    print(f"[{video_name}] 开始测试 (通道: {channel_id})")

    # 加载标注配置
    try:
        annotation_config = load_annotation_config(config_path, channel_id)
    except Exception as e:
        print(f"[{video_name}] 错误: 无法加载通道 {channel_id} 的配置: {e}")
        return None

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[{video_name}] 错误: 无法打开视频")
        return None

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    num_rois = len(annotation_config['boxes'])
    test_frames = min(MAX_FRAMES, total_frames)
    print(f"[{video_name}] 视频信息: {total_frames} 帧, {fps:.2f} FPS, {num_rois} 个ROI, 测试 {test_frames} 帧")

    # 测试统计 - 按ROI分别统计
    frame_count = 0
    roi_detect_times = [[] for _ in range(num_rois)]  # 每个ROI的检测时间列表
    start_time = time.time()

    # 逐帧检测，最多500帧
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

        # 计算单帧总检测时间
        total_detect_time = (detect_end - detect_start) * 1000  # 毫秒

        # 如果是1.mp4，记录到日志
        if log_file:
            log_file.write(f"{frame_count:<10} {timestamp:<30} {total_detect_time:<15.2f}\n")
            if frame_count % 100 == 0:
                log_file.flush()

        # 所有ROI共享同一个检测时间（因为是在同一次detect调用中处理的）
        for i in range(num_rois):
            roi_detect_times[i].append(total_detect_time)

        # 每50帧输出一次进度
        if frame_count % 50 == 0:
            print(f"[{video_name}] 进度: {frame_count}/{test_frames} 帧")

    cap.release()

    # 如果是1.mp4，关闭日志文件
    if log_file:
        log_file.write("-" * 80 + "\n")
        log_file.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        log_file.write(f"总帧数: {frame_count}\n")
        log_file.close()
        print(f"[{video_name}] 时间日志已保存")

    # 计算每个ROI的平均检测耗时
    total_time = time.time() - start_time

    print(f"[{video_name}] 测试完成: {frame_count} 帧, 耗时 {total_time:.2f}s")

    roi_latencies = []
    for i in range(num_rois):
        if roi_detect_times[i]:
            avg_time = np.mean(roi_detect_times[i])  # 平均每帧耗时(毫秒)
            roi_latencies.append(avg_time)
        else:
            roi_latencies.append(0)

    return {
        'model': model_name,
        'video': video_name,
        'total_frames': frame_count,
        'total_time': total_time,
        'num_rois': num_rois,
        'roi_latencies': roi_latencies  # 每个ROI的平均每帧耗时(ms)
    }


if __name__ == "__main__":
    test_detection_speed()
