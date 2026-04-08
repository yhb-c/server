import cv2
import threading
import time
import os
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入日志工具
from server.utils.logger import get_logger

# 导入HKcapture类 - 使用服务端的海康SDK
try:
    # 服务端使用自己的海康SDK模块
    from video.hik_capture import HikSDK, PlayM4SDK
    HKcapture = None  # 服务端暂时不使用HKcapture类
except ImportError as e:
    logger = get_logger('server')
    logger.error(f"导入海康SDK失败: {e}")
    HikSDK = None
    PlayM4SDK = None
    HKcapture = None

class VideoRecorder:
    def __init__(self, rtsp_url, save_path, camera_id):
        self.rtsp_url = rtsp_url
        self.save_path = save_path
        self.camera_id = camera_id
        self.cap = None
        self.writer = None
        self.is_recording = False
        self.thread = None
        self.file_start_time = None
        self.logger = get_logger('server')

    def start_recording(self):
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        self.is_recording = True
        self.thread = threading.Thread(target=self._record_loop)
        self.thread.start()
        self.logger.info(f"相机{self.camera_id}开始录制: {self.rtsp_url}")

    def stop_recording(self):
        self.is_recording = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.stop_capture()
            self.cap.release()
        if self.writer:
            self.writer.release()
        self.logger.info(f"相机{self.camera_id}停止录制")

    def _record_loop(self):
        # 使用HKcapture类初始化
        self.cap = HKcapture(source=self.rtsp_url, fps=25)
        
        # 打开连接
        if not self.cap.open():
            self.logger.error(f"无法打开相机{self.camera_id}: {self.rtsp_url}")
            return
        
        # 开始捕获
        if not self.cap.start_capture():
            self.logger.error(f"无法开始捕获相机{self.camera_id}: {self.rtsp_url}")
            return
        
        # 获取视频属性
        width, height = self.cap.get_frame_size()
        fps = self.cap.get_fps()
        
        if width == 0 or height == 0:
            # 如果无法获取尺寸，尝试读取一帧来获取
            time.sleep(2)  # 等待数据开始流入
            ret, frame = self.cap.read()
            if ret and frame is not None:
                height, width = frame.shape[:2]
            else:
                width, height = 1920, 1080  # 默认尺寸
        
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # AVI格式
        
        self.file_start_time = datetime.now()
        self._create_new_writer(fourcc, fps, width, height)

        # 用于计算实际帧率
        frame_count = 0
        start_time = time.time()
        actual_fps = fps  # 初始使用配置的fps

        while self.is_recording:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.writer.write(frame)
                frame_count += 1
                
                # 每30帧重新计算一次实际帧率
                if frame_count % 30 == 0:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        calculated_fps = frame_count / elapsed_time
                        # 使用移动平均来平滑帧率变化
                        actual_fps = (actual_fps * 0.8 + calculated_fps * 0.2)
                        
                        # 如果实际帧率与写入帧率差异较大，重新创建writer
                        if abs(actual_fps - fps) > 2:  # 差异超过2fps
                            self.logger.info(f"相机{self.camera_id} 检测到帧率变化: {fps:.1f} -> {actual_fps:.1f}")
                            self.writer.release()
                            fps = max(1, int(actual_fps))  # 确保fps至少为1
                            self._create_new_writer(fourcc, fps, width, height)
            else:
                time.sleep(0.01)  # 短暂等待，减少CPU占用

            # 检查是否需要切换新文件（5分钟）
            if datetime.now() - self.file_start_time >= timedelta(minutes=5):
                self.writer.release()
                self.file_start_time = datetime.now()
                self._create_new_writer(fourcc, fps, width, height)
                frame_count = 0  # 重置帧计数
                start_time = time.time()

        if self.writer:
            self.writer.release()
        self.cap.stop_capture()
        self.cap.release()

    def _create_new_writer(self, fourcc, fps, width, height):
        timestamp = self.file_start_time.strftime('%Y%m%d_%H%M%S')
        filename = f"{self.save_path}/camera_{self.camera_id}_{timestamp}.avi"
        self.writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        self.logger.info(f"创建新视频文件: {filename}")


def main():
    logger = get_logger('server')
    # 相机配置（最多支持4个）
    cameras = [
        {
            'rtsp_url': 'rtsp://admin:123456aA@@192.168.8.225:8000/stream1',
            'save_path': r'D:\record\通道1',
            'id': 1
        },
        {
            'rtsp_url': 'rtsp://admin:123456aA@@192.168.8.215:8000/stream1',
            'save_path': r'D:\record\通道2',
            'id': 2
        },
        {
            'rtsp_url': 'rtsp://admin:123456aA@@192.168.8.228:8000/stream1',
            'save_path': r'D:\record\通道3',
            'id': 3
        },
        # 第四个相机可在此添加
        # {
        #     'rtsp_url': 'rtsp://...',
        #     'save_path': r'D:\record\通道4',
        #     'id': 4
        # }
    ]

    # 创建录制器
    recorders = []
    for cam in cameras:
        recorder = VideoRecorder(cam['rtsp_url'], cam['save_path'], cam['id'])
        recorders.append(recorder)

    # 启动录制
    for recorder in recorders:
        recorder.start_recording()

    try:
        # 持续运行，可添加停止逻辑
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
    logger.info("收到停止信号，正在停止录制...")
        for recorder in recorders:
            recorder.stop_recording()

if __name__ == '__main__':
    main()