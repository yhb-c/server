#!/usr/bin/env python3
"""
测试20个ROI同时输入到4个模型的检测性能
- 10个视频文件，每个视频作为2个ROI输入
- 20个ROI同时分配给4个模型（每个模型5个ROI）
- 4个模型并行运行
- 统计每个ROI的检测间隔（多少秒被检测一次）
"""

import sys
import os
import time
import cv2
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加项目路径
current_dir = Path(__file__).parent
server_dir = current_dir.parent / "server"
sys.path.insert(0, str(server_dir))

from detection.detection import LiquidDetectionEngine


def test_model_with_videos(model_path, video_paths, model_id, test_frames=100, lock=None):
    """
    测试单个模型处理多个视频

    Args:
        model_path: 模型路径
        video_paths: 视频路径列表
        model_id: 模型ID
        test_frames: 测试帧数
        lock: 线程锁（用于同步输出）
    """
    def log(msg):
        if lock:
            with lock:
                print(msg)
        else:
            print(msg)

    log(f"\n{'='*60}")
    log(f"[模型{model_id}] {Path(model_path).name}")
    log(f"[模型{model_id}] 负责 {len(video_paths)} 个视频文件 → {len(video_paths)*2} 个ROI")
    log(f"{'='*60}")

    try:
        # 初始化检测引擎并加载模型（必须使用GPU）
        log(f"[模型{model_id}] [1/4] 初始化检测引擎...")
        engine = LiquidDetectionEngine(device='cuda')
        log(f"[模型{model_id}]   ✓ 检测引擎初始化成功（GPU模式）")

        log(f"[模型{model_id}]   加载模型: {Path(model_path).name}")
        if not engine.load_model(model_path):
            log(f"[模型{model_id}]   ✗ 模型加载失败")
            return None
        log(f"[模型{model_id}]   ✓ 模型加载成功")

        # 打开所有视频（每个视频打开两次，模拟一个画面有两个ROI的情况）
        log(f"[模型{model_id}] [2/4] 打开视频文件...")
        video_caps = []
        video_names = []  # 记录视频名称
        for i, video_path in enumerate(video_paths):
            # 每个视频打开两次
            cap1 = cv2.VideoCapture(video_path)
            cap2 = cv2.VideoCapture(video_path)
            if cap1.isOpened() and cap2.isOpened():
                video_caps.append(cap1)
                video_caps.append(cap2)
                video_names.append(Path(video_path).name)
                log(f"[模型{model_id}]   ✓ 视频 {i+1}: {Path(video_path).name} (2个ROI)")
            else:
                log(f"[模型{model_id}]   ✗ 视频 {i+1}: 打开失败")
                if cap1.isOpened():
                    cap1.release()
                if cap2.isOpened():
                    cap2.release()

        if not video_caps:
            log(f"[模型{model_id}]   ✗ 没有可用的视频")
            return None

        log(f"[模型{model_id}]   ✓ 成功打开 {len(video_names)} 个视频，共 {len(video_caps)} 个ROI")

        # 准备检测配置（每个视频就是一个ROI，不需要裁剪）
        log(f"[模型{model_id}] [3/4] 准备检测配置...")
        annotation_config = {
            'boxes': [],
            'fixed_bottoms': [],
            'fixed_tops': [],
            'actual_heights': []
        }

        # 为每个视频添加配置
        for i, cap in enumerate(video_caps):
            ret, first_frame = cap.read()
            if ret:
                h, w = first_frame.shape[:2]
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 重置到开头

                # 使用整个帧作为ROI
                annotation_config['boxes'].append([w//2, h//2, min(w, h)])
                annotation_config['fixed_bottoms'].append(h - 30)
                annotation_config['fixed_tops'].append(30)
                annotation_config['actual_heights'].append(20.0)

        log(f"[模型{model_id}]   ✓ 配置完成: {len(annotation_config['boxes'])} 个ROI")

        # 执行检测测试
        log(f"[模型{model_id}] [4/4] 执行检测测试 ({test_frames} 帧)...")

        success_count = 0
        total_time = 0
        video_times = [0.0] * len(video_names)  # 记录每个视频文件的累计时间（不是ROI）
        video_frame_counts = [0] * len(video_names)  # 记录每个视频文件的帧数

        for frame_idx in range(test_frames):
            # 读取所有视频的当前帧
            roi_frames = []
            for cap in video_caps:
                ret, frame = cap.read()
                if not ret:
                    # 视频结束，重新开始
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()

                if ret:
                    roi_frames.append(frame)

            if len(roi_frames) != len(video_caps):
                continue

            # 执行检测
            start_time = time.time()
            result = engine.detect(roi_frames, annotation_config=annotation_config, channel_id=f'model{model_id}')
            end_time = time.time()

            frame_time = end_time - start_time
            total_time += frame_time

            # 将时间分配到每个视频文件（每个视频有2个ROI）
            time_per_video = frame_time / len(video_names)
            for i in range(len(video_names)):
                video_times[i] += time_per_video
                video_frame_counts[i] += 1

            if result and result.get('success'):
                success_count += 1

            # 每10帧输出一次进度
            if (frame_idx + 1) % 10 == 0:
                avg_time = total_time / (frame_idx + 1)
                # FPS = 单帧被检测的速度（一次检测处理len(video_names)个视频帧）
                frame_fps = len(video_names) / avg_time if avg_time > 0 else 0
                log(f"[模型{model_id}]   进度: {frame_idx+1}/{test_frames} 次检测, 平均耗时: {avg_time:.3f}s, 单帧FPS: {frame_fps:.2f}")

        # 释放视频
        for cap in video_caps:
            cap.release()

        # 计算统计
        avg_time = total_time / test_frames if test_frames > 0 else 0
        # 单帧FPS = 每次检测处理的视频帧数 / 平均每次检测耗时
        single_frame_fps = len(video_names) / avg_time if avg_time > 0 else 0
        time_per_roi = avg_time / len(video_caps) if len(video_caps) > 0 else 0

        # 计算每个视频文件的FPS
        video_fps = []
        for i, vt in enumerate(video_times):
            v_fps = video_frame_counts[i] / vt if vt > 0 else 0
            video_fps.append(v_fps)

        log(f"\n[模型{model_id}] 结果统计:")
        log(f"[模型{model_id}]   - 成功检测次数: {success_count}/{test_frames}")
        log(f"[模型{model_id}]   - 总耗时: {total_time:.2f} 秒")
        log(f"[模型{model_id}]   - 平均每次检测: {avg_time:.3f} 秒")
        log(f"[模型{model_id}]   - 单帧FPS: {single_frame_fps:.2f} (每次检测处理{len(video_names)}个视频帧)")
        log(f"[模型{model_id}]   - 每个ROI平均耗时: {time_per_roi*1000:.2f} 毫秒")
        log(f"\n[模型{model_id}]   各ROI的检测性能:")
        log(f"[模型{model_id}]   {'ROI':<15} {'视频文件':<40} {'检测间隔(秒)':<15} {'FPS':<10}")
        log(f"[模型{model_id}]   {'-'*80}")
        for i, (name, v_fps) in enumerate(zip(video_names, video_fps)):
            detection_interval = 1.0 / v_fps if v_fps > 0 else float('inf')
            log(f"[模型{model_id}]   ROI{i*2+1},{i*2+2:<10} {name:<40} {detection_interval:<15.3f} {v_fps:.2f}")

        return {
            'model_id': model_id,
            'num_videos': len(video_names),  # 视频文件数量
            'num_rois': len(video_caps),     # ROI总数
            'success_count': success_count,
            'total_time': total_time,
            'avg_time': avg_time,
            'single_frame_fps': single_frame_fps,  # 单帧FPS
            'time_per_roi': time_per_roi,
            'video_fps': video_fps,  # 每个视频文件的FPS
            'video_names': video_names  # 视频文件名
        }

    except Exception as e:
        log(f"[模型{model_id}]   ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("="*70)
    print("20个ROI同时输入到4个模型的并行检测性能测试")
    print("="*70)
    print("测试场景:")
    print("  - 10个视频文件，每个视频作为2个ROI输入")
    print("  - 20个ROI同时分配给4个模型（每个模型5个ROI）")
    print("  - 4个模型并行运行（GPU模式）")
    print("  - 统计每个ROI的检测间隔（多少秒被检测一次）")
    print("="*70)

    # 配置
    video_dir = Path("/home/lqj/liquid/testvideo")
    model_dir = Path("/home/lqj/liquid/server/database/model/detection_model/testmodel")
    test_frames = 100

    # 查找视频文件
    print(f"\n[1/3] 查找视频文件...")
    video_files = sorted(list(video_dir.glob("*.mp4")))[:10]  # 只取前10个

    if not video_files:
        print(f"  ✗ 未找到视频文件")
        return

    print(f"  ✓ 找到 {len(video_files)} 个视频文件")

    # 查找模型文件
    print(f"\n[2/3] 查找模型文件...")
    model_files = sorted(list(model_dir.glob("*.pt")))[:4]  # 只取4个模型

    if not model_files:
        print(f"  ✗ 未找到模型文件")
        return

    print(f"  ✓ 找到 {len(model_files)} 个模型文件")

    # 分配视频到模型
    print(f"\n[3/3] 分配视频到模型...")
    videos_per_model = len(video_files) // len(model_files)

    model_video_map = []
    for i, model_file in enumerate(model_files):
        start_idx = i * videos_per_model
        end_idx = start_idx + videos_per_model if i < len(model_files) - 1 else len(video_files)
        assigned_videos = video_files[start_idx:end_idx]

        model_video_map.append({
            'model_id': i + 1,
            'model_path': str(model_file),
            'videos': [str(v) for v in assigned_videos]
        })
        print(f"  模型 {i+1}: 负责视频 {start_idx+1}-{end_idx} ({len(assigned_videos)} 个)")

    print(f"\n{'='*70}")
    print("开始性能测试（4个模型并行运行）")
    print(f"{'='*70}")

    # 创建线程锁用于同步输出
    output_lock = threading.Lock()

    # 并行测试所有模型
    results = []
    with ThreadPoolExecutor(max_workers=len(model_video_map)) as executor:
        # 提交所有任务
        future_to_model = {
            executor.submit(
                test_model_with_videos,
                mapping['model_path'],
                mapping['videos'],
                mapping['model_id'],
                test_frames,
                output_lock  # 传递线程锁
            ): mapping['model_id']
            for mapping in model_video_map
        }

        # 收集结果
        for future in as_completed(future_to_model):
            model_id = future_to_model[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                    with output_lock:
                        print(f"\n✓ 模型{model_id}测试完成")
            except Exception as e:
                with output_lock:
                    print(f"\n✗ 模型{model_id}测试失败: {e}")

    # 按model_id排序
    results.sort(key=lambda x: x['model_id'])

    # 输出汇总
    print(f"\n{'='*70}")
    print("测试汇总 - 20个ROI并行检测性能")
    print(f"{'='*70}")
    print(f"{'模型':<8} {'视频数':<8} {'ROI数':<8} {'单帧FPS':<12} {'每次检测(s)':<14} {'每ROI(ms)':<12}")
    print("-"*70)

    total_videos = 0
    total_rois = 0
    total_single_frame_fps = 0

    for result in results:
        print(f"模型{result['model_id']:<4} {result['num_videos']:<8} {result['num_rois']:<8} "
              f"{result['single_frame_fps']:<12.2f} {result['avg_time']:<14.3f} "
              f"{result['time_per_roi']*1000:<12.2f}")
        total_videos += result['num_videos']
        total_rois += result['num_rois']
        total_single_frame_fps += result['single_frame_fps']

    avg_single_frame_fps = total_single_frame_fps / len(results) if results else 0
    # 并行总FPS = 所有模型的单帧FPS之和
    parallel_total_fps = total_single_frame_fps

    print(f"\n{'='*70}")
    print("性能总结")
    print(f"{'='*70}")
    print(f"✓ 总视频文件数: {total_videos}")
    print(f"✓ 总ROI数量: {total_rois} (每个视频2个ROI)")
    print(f"✓ 单模型平均单帧FPS: {avg_single_frame_fps:.2f}")
    print(f"✓ 并行模式总单帧FPS: {parallel_total_fps:.2f} (4个模型同时运行)")

    # 列出所有ROI的检测FPS和检测间隔
    print(f"\n各ROI检测性能详情（最重要指标）:")
    print(f"{'模型':<8} {'ROI编号':<12} {'视频文件':<40} {'检测间隔(秒)':<15} {'FPS':<10}")
    print("-"*85)

    roi_index = 1
    for result in results:
        for i, (name, v_fps) in enumerate(zip(result['video_names'], result['video_fps'])):
            # 每个视频对应2个ROI
            # 检测间隔 = 1 / FPS
            detection_interval = 1.0 / v_fps if v_fps > 0 else float('inf')
            print(f"模型{result['model_id']:<4} ROI{roi_index},{roi_index+1:<6} {name:<40} {detection_interval:<15.3f} {v_fps:.2f}")
            roi_index += 2

    print(f"\n说明:")
    print(f"  - 检测间隔: 每个ROI多少秒被检测一次（最重要指标）")
    print(f"  - 检测间隔 = 1 / FPS，间隔越小，检测越频繁")
    print(f"  - 单帧FPS: 每秒能处理多少个视频帧")
    print(f"  - 每个模型每次检测同时处理{total_videos//len(results)}个视频帧（{total_rois//len(results)}个ROI）")
    print(f"  - 20个ROI同时输入，4个模型并行处理")
    print(f"  - 并行模式下总吞吐量 = 单模型FPS × 4")

    # 性能评估
    if parallel_total_fps >= 40:
        print(f"\n✓ 性能评估: 优秀 (≥40 FPS)")
    elif parallel_total_fps >= 20:
        print(f"\n⚠️  性能评估: 良好 (20-40 FPS)")
    else:
        print(f"\n⚠️  性能评估: 需要优化 (<20 FPS)")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
