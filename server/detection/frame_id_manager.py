# -*- coding: utf-8 -*-

"""
帧ID管理模块

负责获取和管理视频帧的ID
- 本地视频：使用PTS时间戳（毫秒）作为帧ID
- RTSP流：使用帧序号或SCR时间戳作为帧ID
"""

import cv2


def get_local_video_frame_id(capture_source):
    """
    获取本地视频的帧ID（使用PTS时间戳）

    Args:
        capture_source: HKcapture实例或cv2.VideoCapture实例

    Returns:
        int: PTS时间戳（毫秒），如果无法获取则返回None
    """
    print(f"[frame_id_manager] 获取本地视频帧ID（PTS）")

    if not capture_source:
        print(f"[frame_id_manager] capture_source为None")
        return None

    # 方法1：从capture_source获取PTS（如果支持）
    if hasattr(capture_source, 'get_current_pts'):
        pts_ms = capture_source.get_current_pts()
        if pts_ms is not None:
            frame_id = int(pts_ms)
            print(f"[frame_id_manager] 本地视频 - 使用get_current_pts(): {frame_id}ms")
            return frame_id

    # 方法2：如果capture_source是cv2.VideoCapture，直接获取PTS
    if isinstance(capture_source, cv2.VideoCapture):
        try:
            pts_ms = capture_source.get(cv2.CAP_PROP_POS_MSEC)
            if pts_ms is not None and pts_ms >= 0:
                frame_id = int(pts_ms)
                print(f"[frame_id_manager] 本地视频 - 使用cv2.VideoCapture的PTS: {frame_id}ms")
                return frame_id
        except Exception as e:
            print(f"[frame_id_manager] 获取PTS失败: {e}")

    # 方法3：从HKcapture的cap属性获取PTS
    if hasattr(capture_source, 'cap') and isinstance(capture_source.cap, cv2.VideoCapture):
        try:
            pts_ms = capture_source.cap.get(cv2.CAP_PROP_POS_MSEC)
            if pts_ms is not None and pts_ms >= 0:
                frame_id = int(pts_ms)
                print(f"[frame_id_manager] 本地视频 - 使用HKcapture.cap的PTS: {frame_id}ms")
                return frame_id
        except Exception as e:
            print(f"[frame_id_manager] 从HKcapture.cap获取PTS失败: {e}")

    print(f"[frame_id_manager] 无法获取本地视频的PTS")
    return None


def get_rtsp_frame_id(capture_source, context):
    """
    获取RTSP流的帧ID（暂不支持，返回None）

    Args:
        capture_source: HKcapture实例
        context: ChannelThreadContext实例

    Returns:
        None: RTSP流暂不支持帧ID
    """
    print(f"[frame_id_manager] RTSP流暂不支持帧ID")
    return None


def get_frame_id(capture_source, context):
    """
    获取当前帧的ID（自动判断本地视频或RTSP流）

    Args:
        capture_source: HKcapture实例或cv2.VideoCapture实例
        context: ChannelThreadContext实例

    Returns:
        int: 当前帧ID，如果无法获取则返回None
    """
    print(f"[frame_id_manager] 开始获取帧ID")

    if not capture_source or not context:
        print(f"[frame_id_manager] capture_source或context为None，无法获取帧ID")
        return None

    # 检查是否为本地视频文件
    is_video_file = hasattr(capture_source, 'is_video_file') and capture_source.is_video_file

    if is_video_file:
        # 本地视频：使用PTS时间戳
        return get_local_video_frame_id(capture_source)
    else:
        # RTSP流：使用帧序号
        return get_rtsp_frame_id(capture_source, context)


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
