# -*- coding: utf-8 -*-
"""
RTSP视频流捕获
"""

import cv2
import logging
import threading
from queue import Queue


class RTSPCapture:
    """RTSP视频流捕获器"""
    
    def __init__(self, rtsp_url, channel_id):
        """
        初始化RTSP捕获器
        
        Args:
            rtsp_url: RTSP流地址
            channel_id: 通道ID
        """
        self.logger = logging.getLogger(__name__)
        self.rtsp_url = rtsp_url
        self.channel_id = channel_id
        
        self.cap = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=30)
        self.capture_thread = None
    
    def start(self):
        """启动视频流捕获"""
        if self.is_running:
            self.logger.warning(f"通道{self.channel_id}已在运行")
            return False
        
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            
            if not self.cap.isOpened():
                self.logger.error(f"无法打开RTSP流: {self.rtsp_url}")
                return False
            
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            self.logger.info(f"通道{self.channel_id}视频流启动成功")
            return True
        
        except Exception as e:
            self.logger.error(f"启动视频流失败: {e}")
            return False
    
    def stop(self):
        """停止视频流捕获"""
        self.is_running = False
        
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        
        if self.cap:
            self.cap.release()
        
        self.logger.info(f"通道{self.channel_id}视频流已停止")
    
    def _capture_loop(self):
        """视频捕获循环"""
        while self.is_running:
            ret, frame = self.cap.read()
            
            if not ret:
                self.logger.warning(f"通道{self.channel_id}读取帧失败")
                break
            
            # 如果队列满,丢弃旧帧
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            
            self.frame_queue.put(frame)
    
    def get_frame(self):
        """
        获取最新帧
        
        Returns:
            numpy.array: 视频帧,如果没有则返回None
        """
        try:
            return self.frame_queue.get(timeout=1)
        except:
            return None
    
    def is_alive(self):
        """检查视频流是否存活"""
        return self.is_running and self.cap and self.cap.isOpened()
