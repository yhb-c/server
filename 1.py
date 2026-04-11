# -*- coding: utf-8 -*-
"""
检测速度测试脚本
测试4个视频、8个ROI（每个视频2个ROI）、4个模型的并行检测性能
"""

import sys
import os
import cv2
import yaml
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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

    # 转换boxes格式：从[x, y, width]转换为[cx, cy, size]
    # 其中cx是中心x坐标，cy需要从fixed_bottoms和fixed_tops计算中心y坐标
    boxes = []
    for i, box in enumerate(config['boxes']):
        x, y, width = box
        # 计算中心坐标
        cx = x + width // 2
        # 从fixed_bottoms和fixed_tops计算高度和中心y
        bottom = config['fixed_bottoms'][i]
        top = config['fixed_tops'][i]
        height = bottom - top
        cy = top + height // 2
        # size取宽高的最大值
        size = max(width, height)
        boxes.append([cx, cy, size])

    return {
        'boxes': boxes,
        'fixed_bottoms': config['fixed_bottoms'],
        'fixed_tops': config['fixed_tops'],
        'actual_heights': [float(area['height'].replace('mm', '')) for area in config['areas'].values()],
        'fixed_init_levels': config.get('fixed_init_levels', []),
        'areas': config.get('areas', {}),
        'channel_id': channel_id
    }


def test_detection_speed():
    """测试16个视频、32个ROI、4个模型（每4个视频共用1个模型）的并行检测性能"""

    # 配置路径
    config_path = Path("/home/lqj/liquid/server/config/annotation_result.yaml")

    # 16个视频路径
    video_paths = [
        Path("/home/lqj/liquid/testvideo/1.mp4"),
        Path("/home/lqj/liquid/testvideo/2.mp4"),
        Path("/home/lqj/liquid/testvideo/3.mp4"),
        Path("/home/lqj/liquid/testvideo/4.mp4"),
        Path("/home/lqj/liquid/testvideo/5.mp4"),
        Path("/home/lqj/liquid/testvideo/6.mp4"),
        Path("/home/lqj/liquid/testvideo/7.mp4"),
        Path("/home/lqj/liquid/testvideo/8.mp4"),
        Path("/home/lqj/liquid/testvideo/9.mp4"),
        Path("/home/lqj/liquid/testvideo/10.mp4"),
        Path("/home/lqj/liquid/testvideo/11.mp4"),
        Path("/home/lqj/liquid/testvideo/12.mp4"),
        Path("/home/lqj/liquid/testvideo/13.mp4"),
        Path("/home/lqj/liquid/testvideo/14.mp4"),
        Path("/home/lqj/liquid/testvideo/15.mp4"),
        Path("/home/lqj/liquid/testvideo/16.mp4")
    ]

    # 4个共用模型（每4个视频共用1个模型）
    shared_model_paths = [
        Path("/home/lqj/liquid/server/database/model/detection_model/bestmodel/1.engine"),
        Path("/home/lqj/liquid/server/database/model/detection_model/bestmodel/2.engine"),
        Path("/home/lqj/liquid/server/database/model/detection_model/bestmodel/3.engine"),
        Path("/home/lqj/liquid/server/database/model/detection_model/bestmodel/4.engine")
    ]

    # 16个通道ID
    channel_ids = ["channel1"] * 16

    # 检查文件是否存在
    if not config_path.exists():
        print(f"错误: 配置文件不存在 {config_path}")
        return

    for i, video_path in enumerate(video_paths, 1):
        if not video_path.exists():
            print(f"错误: 视频文件{i}不存在 {video_path}")
            return

    for i, model_path in enumerate(shared_model_paths, 1):
        if not model_path.exists():
            print(f"错误: 模型文件{i}不存在 {model_path}")
            return

    print("=" * 80)
    print("16个视频、32个ROI、4个模型（每4个视频共用1个模型）并行检测测试")
    print("=" * 80)
    print(f"视频数量: {len(video_paths)}")
    print(f"模型数量: {len(shared_model_paths)}")
    print(f"总ROI数量: {len(video_paths) * 2} (每个视频2个ROI)")
    print(f"配置: 视频1-4共用模型1, 视频5-8共用模型2, 视频9-12共用模型3, 视频13-16共用模型4")
    print("-" * 80)

    # 加载4个共用模型
    print("正在加载共用模型...")
    shared_engines = []
    for i, model_path in enumerate(shared_model_paths, 1):
        engine = LiquidDetectionEngine(model_path=str(model_path), device='cuda')
        if not engine.load_model(str(model_path)):
            print(f"错误: 无法加载模型{i}")
            return
        shared_engines.append(engine)
        print(f"模型{i}加载成功")
    print("-" * 80)

    # 使用线程池并行测试
    # 每4个视频共用1个模型
    results = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for i in range(16):
            # 每4个视频使用一个模型
            model_index = i // 4
            future = executor.submit(
                test_single_video_with_shared_model,
                shared_engines[model_index],
                video_paths[i],
                config_path,
                channel_ids[i],
                i + 1
            )
            futures.append(future)

        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"错误: 测试任务失败: {e}")

    # 汇总结果
    if results:
        print("\n" + "=" * 80)
        print("测试结果汇总")
        print("=" * 80)

        total_rois = sum(r['num_rois'] for r in results)
        avg_fps_all = np.mean([r['avg_fps'] for r in results])

        print(f"总视频数: {len(results)}")
        print(f"总ROI数: {total_rois}")
        print(f"平均检测FPS: {avg_fps_all:.2f}")
        print("-" * 80)

        for i, result in enumerate(results, 1):
            print(f"视频{i}: {result['num_rois']}个ROI, 平均FPS: {result['avg_fps']:.2f}, ROI大小: {result['roi_sizes']}")

        print("=" * 80)

        # 保存结果到testresult.md
        save_result_to_file(results, total_rois, avg_fps_all)


def save_result_to_file(results, total_rois, avg_fps_all):
    """保存测试总结到testresult.md第二行"""
    result_path = Path("/home/lqj/liquid/testresult.md")

    # 读取现有内容
    existing_lines = []
    if result_path.exists():
        with open(result_path, 'r', encoding='utf-8') as f:
            existing_lines = f.readlines()

    # 构建新的结果行
    roi_sizes_list = [r['roi_sizes'] for r in results]
    new_line = f"检测路数: {len(results)}, ROI数量: {total_rois}, ROI大小: {', '.join(roi_sizes_list)}, 平均检测FPS: {avg_fps_all:.2f}\n"

    # 插入到第二行
    if len(existing_lines) >= 1:
        # 如果已有内容，插入到第二行
        existing_lines.insert(1, new_line)
    else:
        # 如果文件为空，直接写入
        existing_lines = [new_line]

    # 写回文件
    with open(result_path, 'w', encoding='utf-8') as f:
        f.writelines(existing_lines)

    print(f"\n测试总结已保存到: {result_path}")


def test_single_video_with_shared_model(shared_engine, video_path, config_path, channel_id, video_num):
    """测试单个视频使用共用模型的检测速度"""
    print(f"\n[视频{video_num}] 开始测试")
    print(f"  视频: {video_path}")
    print(f"  通道: {channel_id}")
    print(f"  使用共用模型")

    # 测试视频（使用共用的引擎）
    result = test_single_video(shared_engine, video_path, config_path, channel_id, video_num)

    return result


def test_single_video_with_model(model_path, video_path, config_path, channel_id, video_num):
    """测试单个视频+单个模型的检测速度"""
    print(f"\n[视频{video_num}] 开始测试")
    print(f"  模型: {model_path}")
    print(f"  视频: {video_path}")
    print(f"  通道: {channel_id}")

    # 初始化检测引擎
    engine = LiquidDetectionEngine(model_path=str(model_path), device='cuda')
    if not engine.load_model(str(model_path)):
        print(f"[视频{video_num}] 错误: 无法加载模型")
        return None

    print(f"[视频{video_num}] 模型加载成功")

    # 测试视频
    result = test_single_video(engine, video_path, config_path, channel_id, video_num)

    # 清理引擎
    engine.cleanup()

    return result


def test_single_video(engine, video_path, config_path, channel_id, video_num):
    """测试单个视频的检测速度，计算最高帧率"""

    MAX_FRAMES = 2000  # 最多检测2000帧

    # 加载标注配置
    try:
        annotation_config = load_annotation_config(config_path, channel_id)
    except Exception as e:
        print(f"[视频{video_num}] 错误: 无法加载通道 {channel_id} 的配置: {e}")
        return None

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[视频{video_num}] 错误: 无法打开视频")
        return None

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    num_rois = len(annotation_config['boxes'])
    test_frames = min(MAX_FRAMES, total_frames)
    print(f"[视频{video_num}] 视频信息: {total_frames} 帧, {fps:.2f} FPS, {num_rois} 个ROI, 测试 {test_frames} 帧")

    # 创建CSV文件并写入表头
    csv_path = Path(f"/home/lqj/liquid/{video_num}.csv")
    csv_file = open(csv_path, 'w', encoding='utf-8')

    # 根据ROI数量生成表头
    header = "时间戳"
    for i in range(1, num_rois + 1):
        header += f",ROI{i}液位高度(mm)"
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

        # 保存检测结果到CSV（时间戳和液位高度）
        csv_line = timestamp
        if detect_result and detect_result.get('success') and detect_result.get('liquid_line_positions'):
            liquid_positions = detect_result['liquid_line_positions']
            # 按ROI索引顺序提取液位高度
            for i in range(num_rois):
                if i in liquid_positions:
                    position_data = liquid_positions[i]
                    # 提取液位高度(mm)
                    if isinstance(position_data, dict) and 'height_mm' in position_data:
                        csv_line += f",{position_data['height_mm']}"
                    else:
                        csv_line += ","
                else:
                    csv_line += ","
        else:
            # 如果没有检测结果，填充空值
            for i in range(num_rois):
                csv_line += ","
        csv_file.write(csv_line + "\n")

        if frame_count % 100 == 0:
            csv_file.flush()

        # 所有ROI共享同一个检测时间
        for i in range(num_rois):
            roi_detect_times[i].append(detect_time)

        # 每200帧输出一次进度
        if frame_count % 200 == 0:
            print(f"[视频{video_num}] 进度: {frame_count}/{test_frames} 帧")

    cap.release()
    csv_file.close()
    print(f"[视频{video_num}] 每帧检测结果已保存到: {csv_path}")

    # 计算统计数据
    total_time = time.time() - start_time

    print(f"[视频{video_num}] 测试完成: {frame_count} 帧, 耗时 {total_time:.2f}s")

    # 计算平均检测耗时和FPS
    avg_latency = np.mean(detect_times)
    min_latency = np.min(detect_times)
    max_latency = np.max(detect_times)

    # 平均FPS = 1000ms / 平均每帧耗时(ms)
    avg_fps = 1000.0 / avg_latency if avg_latency > 0 else 0
    max_fps = 1000.0 / min_latency if min_latency > 0 else 0
    min_fps = 1000.0 / max_latency if max_latency > 0 else 0

    print(f"[视频{video_num}] 平均FPS: {avg_fps:.2f}, 平均检测耗时: {avg_latency:.2f}ms")

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
    for idx, box in enumerate(annotation_config['boxes']):
        cx, cy, size = box
        roi_sizes.append(f"{size}x{size}")

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
