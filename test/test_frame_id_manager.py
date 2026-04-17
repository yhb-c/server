#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试frame_id_manager模块
测试本地视频时能否读取所有帧ID
"""

import os
import sys
import cv2
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 直接导入frame_id_manager模块，避免导入整个detection包
import importlib.util
spec = importlib.util.spec_from_file_location(
    "frame_id_manager",
    os.path.join(project_root, "server", "detection", "frame_id_manager.py")
)
frame_id_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frame_id_manager)

get_frame_id = frame_id_manager.get_frame_id
get_current_frame_info = frame_id_manager.get_current_frame_info

from server.video.video_capture_factory import VideoCaptureFactory

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockContext:
    """模拟ChannelThreadContext"""
    def __init__(self):
        self.latest_frame_id = None
        self.capture_count = 0


def test_local_video_frame_ids(video_path, max_frames=100):
    """
    测试本地视频的帧ID读取

    Args:
        video_path: 视频文件路径
        max_frames: 最多读取的帧数
    """
    logger.info(f"=" * 80)
    logger.info(f"开始测试视频: {video_path}")
    logger.info(f"=" * 80)

    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return False

    # 创建视频捕获器
    factory = VideoCaptureFactory()
    capture = factory.create_capture(video_path, "test_channel")

    if not capture:
        logger.error("创建视频捕获器失败")
        return False

    # 获取视频信息
    if hasattr(capture, 'cv_capture'):
        cap = capture.cv_capture
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"视频信息:")
        logger.info(f"  - 总帧数: {total_frames}")
        logger.info(f"  - 帧率: {fps} fps")
        logger.info(f"  - 分辨率: {width}x{height}")
    else:
        logger.warning("无法获取视频详细信息")
        total_frames = "未知"

    # 创建模拟上下文
    context = MockContext()

    # 测试读取帧ID
    frame_count = 0
    success_count = 0
    failed_count = 0
    frame_ids = []

    logger.info(f"\n开始读取帧ID (最多读取 {max_frames} 帧)...")
    logger.info("-" * 80)

    while frame_count < max_frames:
        # 读取一帧
        ret, frame = capture.read()

        if not ret or frame is None:
            logger.info(f"视频读取结束，共读取 {frame_count} 帧")
            break

        frame_count += 1

        # 更新context（模拟display_thread的行为）
        context.capture_count = frame_count
        context.latest_frame_id = frame_count

        # 如果capture有frame_sequence属性，也更新它
        if hasattr(capture, 'frame_sequence'):
            capture.frame_sequence = frame_count

        # 测试get_frame_id
        frame_id = get_frame_id(capture, context)

        if frame_id is not None:
            success_count += 1
            frame_ids.append(frame_id)

            # 每10帧输出一次
            if frame_count % 10 == 0:
                logger.info(f"帧 {frame_count:4d}: frame_id = {frame_id}")
        else:
            failed_count += 1
            logger.warning(f"帧 {frame_count:4d}: 无法获取frame_id")

        # 测试get_current_frame_info
        if frame_count == 1 or frame_count == max_frames // 2:
            frame_info = get_current_frame_info(capture, context)
            logger.info(f"\n完整帧信息 (帧 {frame_count}):")
            logger.info(f"  - frame_id: {frame_info['frame_id']}")
            logger.info(f"  - scr: {frame_info['scr']}")
            logger.info(f"  - is_video_file: {frame_info['is_video_file']}\n")

    # 释放资源
    capture.release()

    # 输出统计结果
    logger.info("-" * 80)
    logger.info(f"测试完成!")
    logger.info(f"统计结果:")
    logger.info(f"  - 总读取帧数: {frame_count}")
    logger.info(f"  - 成功获取frame_id: {success_count} 帧")
    logger.info(f"  - 失败获取frame_id: {failed_count} 帧")
    logger.info(f"  - 成功率: {success_count/frame_count*100:.2f}%")

    if frame_ids:
        logger.info(f"  - frame_id范围: {min(frame_ids)} ~ {max(frame_ids)}")
        logger.info(f"  - frame_id是否连续: {frame_ids == list(range(1, frame_count + 1))}")

    logger.info("=" * 80)

    return success_count == frame_count


def test_multiple_videos():
    """测试多个视频文件"""
    # 测试视频列表
    test_videos = [
        os.path.join(project_root, "testvideo", "1.mp4"),
        os.path.join(project_root, "testvideo", "2.mp4"),
    ]

    results = {}

    for video_path in test_videos:
        if os.path.exists(video_path):
            success = test_local_video_frame_ids(video_path, max_frames=50)
            results[video_path] = success
        else:
            logger.warning(f"跳过不存在的视频: {video_path}")

    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("所有测试总结:")
    logger.info("=" * 80)
    for video_path, success in results.items():
        status = "通过" if success else "失败"
        logger.info(f"{os.path.basename(video_path)}: {status}")
    logger.info("=" * 80)


if __name__ == "__main__":
    # 测试单个视频
    video_path = os.path.join(project_root, "testvideo", "1.mp4")

    if len(sys.argv) > 1:
        # 从命令行参数获取视频路径
        video_path = sys.argv[1]

    if os.path.exists(video_path):
        test_local_video_frame_ids(video_path, max_frames=100)
    else:
        logger.error(f"视频文件不存在: {video_path}")
        logger.info("使用方法: python test_frame_id_manager.py [视频路径]")
        logger.info(f"默认测试视频: {video_path}")
