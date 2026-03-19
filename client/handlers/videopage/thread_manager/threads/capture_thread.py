# -*- coding: utf-8 -*-

"""
捕获线程

职责：
1. 使用HKcapture类从视频流中抓取画面
2. 放入frame_buffer（供显示和检测使用）
3. 复制一份到原始帧队列（供存储使用）

注意：
- 捕获线程帧率由外部SDK决定，系统不做设置
- 使用队列满时丢弃旧帧的策略，避免阻塞
"""

import time
import queue
from typing import Callable, Optional


class CaptureThread:
    """捕获线程类"""
    
    @staticmethod
    def run(context, capture_source, on_frame_captured: Optional[Callable] = None):
        """捕获线程主循环
        
        Args:
            context: ChannelThreadContext 实例
            capture_source: 视频捕获对象（HKcapture或cv2.VideoCapture）
            on_frame_captured: 帧捕获回调函数 callback(channel_id, frame)
        """
        channel_id = context.channel_id
        
        while context.capture_flag:
            try:
                # 读取帧（帧率由SDK控制）
                ret, frame = capture_source.read()
                
                if ret and frame is not None:
                    context.capture_count += 1
                    
                    #  更新最新帧（供显示线程非消费性读取）- 不复制，直接使用
                    with context.frame_lock:
                        context.latest_frame = frame
                    
                    # 放入frame_buffer（供检测线程使用）- 直接使用，无需复制
                    # 原因：HKcapture.read()内部已复制，每次返回新对象，且检测线程只读不改
                    if context.detection_enabled:
                        try:
                            if context.frame_buffer.full():
                                context.frame_buffer.get_nowait()  # 丢弃旧帧
                            context.frame_buffer.put_nowait(frame)  #  优化：直接使用，减少1次复制
                        except:
                            pass
                    
                    # 调用回调
                    if on_frame_captured:
                        on_frame_captured(channel_id, frame)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                time.sleep(0.1)

