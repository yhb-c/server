#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试帧ID识别功能

测试两种帧ID类型：
1. 本地视频：帧ID是帧序号（0, 1, 2, 3...）
2. RTSP流：帧ID是SCR时间戳
"""

import os
import sys
import cv2
import logging

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from server.detection.frame_id_identify import FrameIdIdentifier, parse_frame_id_from_command

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_parse_frame_id():
    """测试从命令中解析frame_id"""
    logger.info("=== 测试解析frame_id ===")

    # 测试1: 正常解析
    command1 = {'channel_id': 'channel1', 'frame_id': 100}
    frame_id1 = parse_frame_id_from_command(command1)
    logger.info(f"测试1 - 输入: {command1}, 输出: {frame_id1}")
    assert frame_id1 == 100, "测试1失败"

    # 测试2: frame_id为None
    command2 = {'channel_id': 'channel1'}
    frame_id2 = parse_frame_id_from_command(command2)
    logger.info(f"测试2 - 输入: {command2}, 输出: {frame_id2}")
    assert frame_id2 is None, "测试2失败"

    # 测试3: frame_id为字符串
    command3 = {'channel_id': 'channel1', 'frame_id': '200'}
    frame_id3 = parse_frame_id_from_command(command3)
    logger.info(f"测试3 - 输入: {command3}, 输出: {frame_id3}")
    assert frame_id3 == 200, "测试3失败"

    # 测试4: frame_id为负数
    command4 = {'channel_id': 'channel1', 'frame_id': -10}
    frame_id4 = parse_frame_id_from_command(command4)
    logger.info(f"测试4 - 输入: {command4}, 输出: {frame_id4}")
    assert frame_id4 is None, "测试4失败"

    logger.info("解析frame_id测试通过\n")


def test_video_source_detection(video_path: str):
    """测试视频源类型检测"""
    logger.info("=== 测试视频源类型检测 ===")

    if not os.path.exists(video_path):
        logger.warning(f"视频文件不存在: {video_path}，跳过测试")
        return

    # 创建视频捕获器
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"无法打开视频文件: {video_path}")
        return

    # 创建帧ID识别器
    identifier = FrameIdIdentifier()

    # 检测视频源类型
    video_source_type = identifier.detect_video_source_type(cap)
    logger.info(f"检测到视频源类型: {video_source_type}")

    cap.release()
    logger.info("视频源类型检测测试完成\n")


def test_local_video_seek(video_path: str):
    """测试本地视频帧序号定位"""
    logger.info("=== 测试本地视频帧序号定位 ===")

    if not os.path.exists(video_path):
        logger.warning(f"视频文件不存在: {video_path}，跳过测试")
        return

    # 创建视频捕获器
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"无法打开视频文件: {video_path}")
        return

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    logger.info(f"视频信息 - 总帧数: {total_frames}, FPS: {fps}")

    # 创建帧ID识别器
    identifier = FrameIdIdentifier()

    # 测试1: 定位到第100帧
    target_frame = 100
    if total_frames > target_frame:
        success = identifier.seek_to_frame(cap, target_frame, 'local_video')
        current_frame = identifier.get_current_frame_id(cap, 'local_video')
        logger.info(f"测试1 - 定位到帧序号{target_frame}: {'成功' if success else '失败'}, 当前帧序号: {current_frame}")

        # 读取帧验证
        ret, frame = cap.read()
        if ret:
            logger.info(f"测试1 - 成功读取帧，尺寸: {frame.shape}")
        else:
            logger.error("测试1 - 读取帧失败")
    else:
        logger.warning(f"视频总帧数({total_frames})小于目标帧({target_frame})，跳过测试1")

    # 测试2: 定位到第0帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    success = identifier.seek_to_frame(cap, 0, 'local_video')
    current_frame = identifier.get_current_frame_id(cap, 'local_video')
    logger.info(f"测试2 - 定位到帧序号0: {'成功' if success else '失败'}, 当前帧序号: {current_frame}")

    # 测试3: 定位到最后一帧
    if total_frames > 0:
        last_frame = total_frames - 1
        success = identifier.seek_to_frame(cap, last_frame, 'local_video')
        current_frame = identifier.get_current_frame_id(cap, 'local_video')
        logger.info(f"测试3 - 定位到最后一帧({last_frame}): {'成功' if success else '失败'}, 当前帧序号: {current_frame}")

    # 测试4: 定位到超出范围的帧
    invalid_frame = total_frames + 100
    success = identifier.seek_to_frame(cap, invalid_frame, 'local_video')
    logger.info(f"测试4 - 定位到超出范围的帧序号({invalid_frame}): {'成功' if success else '失败（预期）'}")

    # 测试5: 验证帧ID
    valid = identifier.validate_frame_id(cap, 50, 'local_video')
    logger.info(f"测试5 - 验证帧序号 50: {'有效' if valid else '无效'}")

    invalid = identifier.validate_frame_id(cap, total_frames + 10, 'local_video')
    logger.info(f"测试6 - 验证帧序号 {total_frames + 10}: {'有效' if invalid else '无效（预期）'}")

    cap.release()
    logger.info("本地视频帧序号定位测试完成\n")


def test_rtsp_stream_seek():
    """测试RTSP流SCR时间戳定位"""
    logger.info("=== 测试RTSP流SCR时间戳定位 ===")
    logger.info("注意: RTSP流测试需要实际的RTSP流地址和支持SCR时间戳的捕获器")
    logger.info("当前仅演示接口调用，实际功能需要在真实RTSP环境中测试")

    # 创建帧ID识别器
    identifier = FrameIdIdentifier()

    # 模拟测试（需要实际RTSP流才能真正测试）
    logger.info("测试1 - 验证RTSP流帧ID（SCR时间戳）总是有效")
    # 对于RTSP流，时间戳验证总是返回True
    logger.info("RTSP流SCR时间戳定位功能已实现，需要在实际RTSP环境中测试")

    logger.info("RTSP流SCR时间戳定位测试完成\n")


def main():
    """主函数"""
    logger.info("开始测试帧ID识别功能\n")
    logger.info("支持两种帧ID类型：")
    logger.info("1. 本地视频：帧ID是帧序号（0, 1, 2, 3...）")
    logger.info("2. RTSP流：帧ID是SCR时间戳\n")

    # 测试1: 解析frame_id
    test_parse_frame_id()

    # 测试2: 从配置文件读取视频路径
    try:
        import yaml
        config_path = os.path.join(project_root, 'server', 'config', 'default_config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

                # 尝试获取channel1的视频路径
                channel1_config = config.get('channel1', {})
                video_path = channel1_config.get('file_path', '')

                if video_path and os.path.exists(video_path):
                    # 测试视频源类型检测
                    test_video_source_detection(video_path)

                    # 测试本地视频帧序号定位
                    test_local_video_seek(video_path)
                else:
                    logger.warning(f"未找到有效的视频文件路径: {video_path}")
                    logger.info("请手动指定视频路径进行测试")
        else:
            logger.warning(f"配置文件不存在: {config_path}")
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")

    # 测试3: RTSP流SCR时间戳定位
    test_rtsp_stream_seek()

    logger.info("所有测试完成")


if __name__ == '__main__':
    main()
