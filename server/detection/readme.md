服务端线程管理架构
核心类：DetectionTaskManager
线程相关属性：

detection_threads: Dict[str, threading.Thread] - 每个通道一个检测线程
stop_events: Dict[str, threading.Event] - 每个通道一个停止事件
关键方法：

start_task(channel_id) (第118-184行)

创建 threading.Thread 运行 _detection_worker
每个通道独立线程：name=f"detection_{channel_id}"
线程启动后状态设为 'running'
_detection_worker(channel_id, stop_event) (第216-281行) - 检测工作线程


while not stop_event.is_set():
    ret, frame = video_capture.read()  # 获取视频帧
    detection_result = detection_engine.detect(frame, channel_id=channel_id)  # 调用检测引擎
    result_callback(channel_id, detection_result)  # 回调结果
    time.sleep(0.033)  # 约30FPS
stop_task(channel_id) (第186-214行)

设置 stop_event.set() 通知线程停止
thread.join(timeout=5.0) 等待线程结束
清理资源
线程特点：

每个通道一个独立线程（多通道并发）
使用 threading.Event 优雅停止
帧率控制：time.sleep(0.033) 约30FPS
检测引擎在线程中调用：detection_engine.detect(frame, channel_id=channel_id)