# -*- coding: utf-8 -*-

"""
检测结果接收线程（客户端版本）

职责：
1. 通过WebSocket从服务器接收检测结果
2. 将检测结果放入检测结果队列
3. 更新最新检测结果（供显示线程和曲线绘制使用）

注意：客户端不再进行本地检测，所有检测由服务器完成
"""

import time
import queue
from typing import Callable, Optional


class DetectionThread:
    """检测结果接收线程类（客户端只接收服务器结果）"""

    @staticmethod
    def run(context, frame_rate: float, detection_model=None,
            on_detection_mission_result: Optional[Callable] = None,
            batch_size: int = 4, use_batch: bool = True):
        """检测结果接收线程主循环

        Args:
            context: ChannelThreadContext 实例
            frame_rate: 检测帧率（保留参数，用于兼容性）
            detection_model: 检测模型对象（客户端不使用，保留参数）
            on_detection_mission_result: 检测结果回调函数 callback(channel_id, mission_result)
            batch_size: 批处理大小（客户端不使用，保留参数）
            use_batch: 是否启用批处理模式（客户端不使用，保留参数）
        """
        channel_id = context.channel_id

        print(f"[{channel_id}] 检测结果接收线程启动（客户端模式）")
        print(f"  - 从服务器接收检测结果")
        print(f"  - WebSocket地址: ws://192.168.0.121:8085")

        # TODO: 初始化WebSocket连接到服务器
        # ws_client = DetectionThread._connect_to_server(channel_id)
        # if ws_client is None:
        #     print(f"[{channel_id}] 无法连接到服务器")
        #     return

        frame_interval = 1.0 / frame_rate if frame_rate > 0 else 0.05

        while context.channel_detect_status:
            try:
                frame_start_time = time.time()

                # TODO: 从WebSocket接收服务器的检测结果
                # detection_mission_result = ws_client.receive()

                # 临时：模拟接收（实际应从WebSocket接收）
                detection_mission_result = None

                if detection_mission_result is not None:
                    context.detection_count += 1

                    # 放入检测结果队列（供曲线绘制使用）
                    try:
                        if context.detection_mission_results.full():
                            context.detection_mission_results.get_nowait()  # 丢弃旧结果
                        context.detection_mission_results.put_nowait(detection_mission_result)
                    except:
                        pass

                    # 放入存储数据队列（供存储线程使用，独立队列）
                    if 'liquid_line_positions' in detection_mission_result:
                        try:
                            if context.storage_data.full():
                                context.storage_data.get_nowait()  # 丢弃旧数据
                            context.storage_data.put_nowait(detection_mission_result)
                        except:
                            pass

                    # 更新最新检测结果（供显示线程使用）
                    with context.detection_lock:
                        context.latest_detection = detection_mission_result

                    # 调用检测结果回调
                    if on_detection_mission_result:
                        try:
                            on_detection_mission_result(channel_id, detection_mission_result)
                        except Exception as e:
                            pass  # 静默处理回调错误

                # 帧率控制
                elapsed = time.time() - frame_start_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    time.sleep(0.01)  # 没有数据时短暂休眠

            except Exception as e:
                print(f"[{channel_id}] 接收检测结果异常: {e}")
                time.sleep(0.1)

    @staticmethod
    def _connect_to_server(channel_id: str):
        """连接到服务器WebSocket

        Args:
            channel_id: 通道ID

        Returns:
            WebSocket客户端对象，失败返回None
        """
        try:
            # TODO: 实现WebSocket连接
            # import websocket
            # ws_url = f"ws://192.168.0.121:8085/detection/{channel_id}"
            # ws_client = websocket.create_connection(ws_url)
            # return ws_client

            print(f"[{channel_id}] TODO: 实现WebSocket连接到服务器")
            return None

        except Exception as e:
            print(f"[{channel_id}] 连接服务器失败: {e}")
            return None
