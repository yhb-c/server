# -*- coding: utf-8 -*-

"""
帧ID管理模块

负责获取和管理视频帧的ID
- 本地视频：使用帧序号（0, 1, 2, 3...）作为帧ID
- RTSP流：预留使用SCR时间戳作为帧ID
"""


def get_frame_id(capture_source, context):
    """
    获取当前帧的ID

    Args:
        capture_source: HKcapture实例
        context: ChannelThreadContext实例

    Returns:
        int: 当前帧ID，如果无法获取则返回None
    """
    print(f"[frame_id_manager] 开始获取帧ID")
    print(f"[frame_id_manager] capture_source: {capture_source}")
    print(f"[frame_id_manager] context: {context}")

    if not capture_source or not context:
        print(f"[frame_id_manager] capture_source或context为None，无法获取帧ID")
        return None

    # 方法1：从context获取（display_thread更新）
    if hasattr(context, 'latest_frame_id'):
        print(f"[frame_id_manager] context.latest_frame_id = {context.latest_frame_id}")
        if context.latest_frame_id is not None and context.latest_frame_id > 0:
            print(f"[frame_id_manager] 使用方法1: context.latest_frame_id = {context.latest_frame_id}")
            return context.latest_frame_id

    # 方法2：从context.capture_count获取（display_thread使用）
    if hasattr(context, 'capture_count'):
        print(f"[frame_id_manager] context.capture_count = {context.capture_count}")
        if context.capture_count > 0:
            print(f"[frame_id_manager] 使用方法2: context.capture_count = {context.capture_count}")
            return context.capture_count

    # 方法3：从capture_source获取frame_sequence（解码回调更新）
    if hasattr(capture_source, 'frame_sequence'):
        print(f"[frame_id_manager] capture_source.frame_sequence = {capture_source.frame_sequence}")
        if capture_source.frame_sequence > 0:
            print(f"[frame_id_manager] 使用方法3: capture_source.frame_sequence = {capture_source.frame_sequence}")
            return capture_source.frame_sequence

    # 无法获取帧ID
    print(f"[frame_id_manager] 所有方法都无法获取有效的帧ID")
    return None


def get_frame_scr(capture_source):
    """
    获取当前帧的SCR时间戳（RTSP流使用）

    Args:
        capture_source: HKcapture实例

    Returns:
        dict: SCR信息字典，如果是本地视频或无SCR则返回None
    """
    if not capture_source:
        return None

    # 检查是否为本地视频文件
    if hasattr(capture_source, 'is_video_file') and capture_source.is_video_file:
        return None

    # 获取SCR时间戳
    if hasattr(capture_source, 'get_current_scr'):
        return capture_source.get_current_scr()

    return None


def get_current_frame_info(capture_source, context):
    """
    获取当前帧的完整信息

    Args:
        capture_source: HKcapture实例
        context: ChannelThreadContext实例

    Returns:
        dict: 包含frame_id和scr的字典
    """
    frame_id = get_frame_id(capture_source, context)
    frame_scr = get_frame_scr(capture_source)

    return {
        'frame_id': frame_id,
        'scr': frame_scr,
        'is_video_file': hasattr(capture_source, 'is_video_file') and capture_source.is_video_file
    }
