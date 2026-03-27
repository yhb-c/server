# -*- coding: utf-8 -*-
"""
检测时间记录脚本
只记录1.mp4每次生成检测结果的时间戳
"""

import sys
import os
import cv2
import yaml
import time
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).resolve().parent.parent
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


def test_detection_timing():
    """测试1.mp4的检测时间，记录每次检测的时间戳"""

    # 配置路径
    model_path = Path("/home/lqj/liquid/server/database/model/detection_model/testmodel/1.engine")
    video_path = Path("/home/lqj/liquid/testvideo/1.mp4")
    config_path = Path("/home/lqj/liquid/server/database/config/annotation_result.yaml")
    log_path = Path("/home/lqj/liquid/test/detection_timing_log.txt")

    channel_id = "channel1"

    print(f"开始测试视频: {video_path.name}")
    print(f"使用模型: {model_path.name}")
    print(f"日志文件: {log_path}")
    print("-" * 80)

    # 初始化检测引擎
    engine = LiquidDetectionEngine(model_path=str(model_path), device='cuda')
    if not engine.load_model(str(model_path)):
        print(f"错误: 无法加载模型 {model_path}")
        return

    # 加载标注配置
    try:
        annotation_config = load_annotation_config(config_path, channel_id)
    except Exception as e:
        print(f"错误: 无法加载通道 {channel_id} 的配置: {e}")
        return

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"错误: 无法打开视频")
        return

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"视频信息: {total_frames} 帧, {fps:.2f} FPS")
    print(f"开始检测...\n")

    # 打开日志文件
    with open(log_path, 'w', encoding='utf-8') as log_file:
        # 写入表头
        log_file.write(f"检测时间记录 - {video_path.name}\n")
        log_file.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        log_file.write("-" * 80 + "\n")
        log_file.write(f"{'帧号':<10} {'时间戳':<30} {'检测耗时(ms)':<15}\n")
        log_file.write("-" * 80 + "\n")

        frame_count = 0

        # 逐帧检测
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # 记录检测开始时间
            detect_start = time.time()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            # 执行检测
            result = engine.detect(frame, annotation_config=annotation_config, channel_id=channel_id)

            # 计算检测耗时
            detect_time = (time.time() - detect_start) * 1000

            # 写入日志
            log_file.write(f"{frame_count:<10} {timestamp:<30} {detect_time:<15.2f}\n")

            # 每100帧输出一次进度
            if frame_count % 100 == 0:
                print(f"已处理 {frame_count}/{total_frames} 帧")
                log_file.flush()

        # 写入结束信息
        log_file.write("-" * 80 + "\n")
        log_file.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        log_file.write(f"总帧数: {frame_count}\n")

    cap.release()
    engine.cleanup()

    print(f"\n检测完成!")
    print(f"总帧数: {frame_count}")
    print(f"日志已保存到: {log_path}")


if __name__ == "__main__":
    test_detection_timing()
