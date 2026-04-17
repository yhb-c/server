#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧ID识别模块
负责根据start_detection指令中的frame_id信息，从指定帧开始检测

支持两种帧ID类型：
1. 本地视频：帧ID是帧序号（0, 1, 2, 3...）
2. RTSP流：帧ID是SCR时间戳
"""

import os
import sys
import logging
import cv2
import time
from typing import Optional, Any, Tuple

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class FrameIdIdentifier:
    """帧ID识别器，用于定位和跳转到指定帧"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_video_source_type(self, video_capture: Any) -> str:
        """
        检测视频源类型

        Args:
            video_capture: 视频捕获对象

        Returns:
            str: 'local_video' 或 'rtsp_stream'
        """
        try:
            # 检测是否为本地视频文件
            if hasattr(video_capture, 'is_video_file') and video_capture.is_video_file:
                return 'local_video'
            elif hasattr(video_capture, '_is_local_file') and video_capture._is_local_file:
                return 'local_video'
            elif hasattr(video_capture, 'cap') and isinstance(video_capture.cap, cv2.VideoCapture):
                # 检查是否为文件路径
                backend = video_capture.cap.getBackendName()
                if 'FILE' in backend.upper():
                    return 'local_video'
                else:
                    return 'rtsp_stream'
            elif isinstance(video_capture, cv2.VideoCapture):
                backend = video_capture.getBackendName()
                if 'FILE' in backend.upper():
                    return 'local_video'
                else:
                    return 'rtsp_stream'
            else:
                # 默认假设为RTSP流
                return 'rtsp_stream'

        except Exception as e:
            self.logger.error(f"检测视频源类型失败: {e}")
            return 'rtsp_stream'

    def seek_to_frame(self, video_capture: Any, target_frame_id: Any, video_source: str = None) -> bool:
        """
        将视频捕获器定位到指定帧ID

        Args:
            video_capture: 视频捕获对象
            target_frame_id: 目标帧ID
                - 本地视频：帧序号（int，0, 1, 2, 3...）
                - RTSP流：SCR时间戳（int或float）
            video_source: 视频源类型（'local_video' 或 'rtsp_stream'），None则自动检测

        Returns:
            bool: 是否成功定位到目标帧
        """
        try:
            # 自动检测视频源类型
            if video_source is None:
                video_source = self.detect_video_source_type(video_capture)

            self.logger.info(f"视频源类型: {video_source}, 目标帧ID: {target_frame_id}")

            if video_source == 'local_video':
                # 本地视频：帧ID是帧序号
                return self._seek_local_video(video_capture, int(target_frame_id))
            elif video_source == 'rtsp_stream':
                # RTSP流：帧ID是SCR时间戳
                return self._seek_rtsp_stream(video_capture, target_frame_id)
            else:
                self.logger.error(f"未知的视频源类型: {video_source}")
                return False

        except Exception as e:
            self.logger.error(f"定位到帧 {target_frame_id} 失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _seek_local_video(self, video_capture: Any, target_frame_index: int) -> bool:
        """
        本地视频定位到指定帧序号

        Args:
            video_capture: 视频捕获对象
            target_frame_index: 目标帧序号（0, 1, 2, 3...）

        Returns:
            bool: 是否成功定位
        """
        try:
            if target_frame_index < 0:
                self.logger.error(f"无效的帧序号: {target_frame_index}，必须 >= 0")
                return False

            # 检测视频捕获器类型
            if hasattr(video_capture, 'cap') and isinstance(video_capture.cap, cv2.VideoCapture):
                return self._seek_opencv_capture(video_capture.cap, target_frame_index)
            elif isinstance(video_capture, cv2.VideoCapture):
                return self._seek_opencv_capture(video_capture, target_frame_index)
            elif hasattr(video_capture, 'seek_to_frame'):
                return video_capture.seek_to_frame(target_frame_index)
            else:
                self.logger.warning(f"视频捕获器类型不支持帧跳转: {type(video_capture)}")
                return False

        except Exception as e:
            self.logger.error(f"本地视频定位失败: {e}")
            return False

    def _seek_rtsp_stream(self, video_capture: Any, target_scr_timestamp: Any) -> bool:
        """
        RTSP流定位到指定SCR时间戳

        Args:
            video_capture: 视频捕获对象
            target_scr_timestamp: 目标SCR时间戳

        Returns:
            bool: 是否成功定位
        """
        try:
            # 检查视频捕获器是否支持SCR时间戳定位
            if hasattr(video_capture, 'seek_to_scr_timestamp'):
                # 自定义捕获器支持SCR时间戳定位
                success = video_capture.seek_to_scr_timestamp(target_scr_timestamp)
                if success:
                    self.logger.info(f"成功定位到SCR时间戳: {target_scr_timestamp}")
                else:
                    self.logger.error(f"定位到SCR时间戳失败: {target_scr_timestamp}")
                return success
            else:
                # 不支持SCR时间戳定位，需要逐帧读取查找
                self.logger.warning("视频捕获器不支持SCR时间戳定位，尝试逐帧查找")
                return self._seek_rtsp_by_reading(video_capture, target_scr_timestamp)

        except Exception as e:
            self.logger.error(f"RTSP流定位失败: {e}")
            return False

    def _seek_rtsp_by_reading(self, video_capture: Any, target_scr_timestamp: Any) -> bool:
        """
        通过逐帧读取查找目标SCR时间戳

        Args:
            video_capture: 视频捕获对象
            target_scr_timestamp: 目标SCR时间戳

        Returns:
            bool: 是否成功定位
        """
        try:
            max_frames_to_read = 1000  # 最多读取1000帧
            frame_count = 0

            while frame_count < max_frames_to_read:
                ret, frame = video_capture.read()
                if not ret:
                    self.logger.error("读取帧失败，无法继续查找")
                    return False

                # 获取当前帧的SCR时间戳
                current_scr = None
                if hasattr(video_capture, 'get_current_scr_timestamp'):
                    current_scr = video_capture.get_current_scr_timestamp()

                if current_scr is not None:
                    # 比较时间戳
                    if abs(current_scr - target_scr_timestamp) < 1000:  # 允许1秒误差
                        self.logger.info(f"找到目标SCR时间戳: {current_scr} (目标: {target_scr_timestamp})")
                        return True
                    elif current_scr > target_scr_timestamp:
                        self.logger.warning(f"已超过目标时间戳: 当前={current_scr}, 目标={target_scr_timestamp}")
                        return False

                frame_count += 1

            self.logger.error(f"读取{max_frames_to_read}帧后仍未找到目标时间戳")
            return False

        except Exception as e:
            self.logger.error(f"逐帧查找失败: {e}")
            return False

    def _seek_opencv_capture(self, cap: cv2.VideoCapture, target_frame_index: int) -> bool:
        """
        OpenCV VideoCapture定位到指定帧序号

        Args:
            cap: OpenCV VideoCapture对象
            target_frame_index: 目标帧序号

        Returns:
            bool: 是否成功定位
        """
        try:
            # 获取视频总帧数
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if total_frames > 0 and target_frame_index >= total_frames:
                self.logger.error(f"目标帧序号 {target_frame_index} 超出视频总帧数 {total_frames}")
                return False

            # 使用CAP_PROP_POS_FRAMES定位
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_index)

            # 验证定位是否成功
            current_frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

            if current_frame_index == target_frame_index:
                self.logger.info(f"成功定位到帧序号 {target_frame_index}")
                return True
            else:
                self.logger.warning(f"定位帧序号不匹配: 目标={target_frame_index}, 实际={current_frame_index}")
                # 尝试读取帧验证
                ret, frame = cap.read()
                if ret:
                    self.logger.info(f"虽然帧序号不匹配，但成功读取帧，继续检测")
                    return True
                return False

        except Exception as e:
            self.logger.error(f"OpenCV定位失败: {e}")
            return False

    def get_current_frame_id(self, video_capture: Any, video_source: str = None) -> Optional[Any]:
        """
        获取当前帧ID

        Args:
            video_capture: 视频捕获对象
            video_source: 视频源类型（'local_video' 或 'rtsp_stream'），None则自动检测

        Returns:
            Optional[Any]: 当前帧ID
                - 本地视频：帧序号（int）
                - RTSP流：SCR时间戳（int或float）
                - 失败返回None
        """
        try:
            # 自动检测视频源类型
            if video_source is None:
                video_source = self.detect_video_source_type(video_capture)

            if video_source == 'local_video':
                # 本地视频：返回帧序号
                if hasattr(video_capture, 'cap') and isinstance(video_capture.cap, cv2.VideoCapture):
                    return int(video_capture.cap.get(cv2.CAP_PROP_POS_FRAMES))
                elif isinstance(video_capture, cv2.VideoCapture):
                    return int(video_capture.get(cv2.CAP_PROP_POS_FRAMES))
                elif hasattr(video_capture, 'get_current_frame_index'):
                    return video_capture.get_current_frame_index()
                else:
                    return None

            elif video_source == 'rtsp_stream':
                # RTSP流：返回SCR时间戳
                if hasattr(video_capture, 'get_current_scr_timestamp'):
                    return video_capture.get_current_scr_timestamp()
                else:
                    self.logger.warning("视频捕获器不支持获取SCR时间戳")
                    return None

            else:
                return None

        except Exception as e:
            self.logger.error(f"获取当前帧ID失败: {e}")
            return None

    def validate_frame_id(self, video_capture: Any, frame_id: Any, video_source: str = None) -> bool:
        """
        验证帧ID是否有效

        Args:
            video_capture: 视频捕获对象
            frame_id: 要验证的帧ID
            video_source: 视频源类型（'local_video' 或 'rtsp_stream'），None则自动检测

        Returns:
            bool: 帧ID是否有效
        """
        try:
            # 自动检测视频源类型
            if video_source is None:
                video_source = self.detect_video_source_type(video_capture)

            if video_source == 'local_video':
                # 本地视频：验证帧序号
                frame_index = int(frame_id)
                if frame_index < 0:
                    return False

                # 获取视频总帧数
                if hasattr(video_capture, 'cap') and isinstance(video_capture.cap, cv2.VideoCapture):
                    total_frames = int(video_capture.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                elif isinstance(video_capture, cv2.VideoCapture):
                    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                else:
                    # 无法获取总帧数，假设有效
                    return True

                if total_frames > 0:
                    return frame_index < total_frames

                return True

            elif video_source == 'rtsp_stream':
                # RTSP流：验证SCR时间戳（假设时间戳总是有效的）
                return True

            else:
                return False

        except Exception as e:
            self.logger.error(f"验证帧ID失败: {e}")
            return False


def parse_frame_id_from_command(command_data: dict) -> Optional[int]:
    """
    从start_detection命令中解析frame_id

    Args:
        command_data: 命令数据字典

    Returns:
        Optional[int]: 帧ID，如果不存在或无效则返回None
    """
    try:
        frame_id = command_data.get('frame_id')

        if frame_id is None:
            return None

        # 转换为整数
        frame_id = int(frame_id)

        if frame_id < 0:
            logging.warning(f"无效的frame_id: {frame_id}，必须 >= 0")
            return None

        return frame_id

    except (ValueError, TypeError) as e:
        logging.warning(f"解析frame_id失败: {e}")
        return None


# 全局帧ID识别器实例
_frame_id_identifier = None


def get_frame_id_identifier() -> FrameIdIdentifier:
    """获取全局帧ID识别器实例"""
    global _frame_id_identifier
    if _frame_id_identifier is None:
        _frame_id_identifier = FrameIdIdentifier()
    return _frame_id_identifier
