# -*- coding: utf-8 -*-
"""
WebSocket客户端 - 接收服务端推送的检测结果
"""

import asyncio
import websockets
import json
import logging
import threading
from qtpy import QtCore


class WebSocketClient(QtCore.QObject):
    """WebSocket客户端"""
    
    # 信号：接收到检测结果
    detection_result = QtCore.Signal(dict)
    
    # 信号：接收到视频帧
    video_frame = QtCore.Signal(bytes, int, int, int)  # (jpeg_data, width, height, channel_id)
    
    # 信号：连接状态变化
    connection_status = QtCore.Signal(bool, str)  # (is_connected, message)
    
    def __init__(self, ws_url='ws://192.168.0.127:8085', parent=None):
        """
        初始化WebSocket客户端
        
        Args:
            ws_url: WebSocket服务器地址
            parent: 父对象
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.ws_url = ws_url
        
        self.is_running = False
        self.websocket = None
        self.loop = None
        self.thread = None
        self._is_connected = False  # 独立的连接状态标志
    
    def start(self):
        """启动WebSocket客户端"""
        if self.is_running:
            self.logger.warning("WebSocket客户端已在运行")
            return
        
        self.is_running = True
        
        # 在新线程中运行asyncio事件循环
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        self.logger.info(f"WebSocket客户端启动: {self.ws_url}")
    
    def stop(self):
        """停止WebSocket客户端"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止事件循环
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # 等待线程结束
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        
        self.logger.info("WebSocket客户端已停止")
    
    def _run_loop(self):
        """在新线程中运行asyncio事件循环"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 运行WebSocket连接
            self.loop.run_until_complete(self._connect())
            
        except Exception as e:
            self.logger.error(f"WebSocket事件循环异常: {e}")
        finally:
            if self.loop:
                self.loop.close()
    
    async def _connect(self):
        """连接WebSocket服务器"""
        retry_count = 0
        max_retries = 5
        
        while self.is_running and retry_count < max_retries:
            try:
                self.logger.info(f"正在连接WebSocket服务器: {self.ws_url}")
                
                async with websockets.connect(self.ws_url) as websocket:
                    self.websocket = websocket
                    self._is_connected = True  # 设置连接状态
                    retry_count = 0  # 重置重试计数
                    
                    # 发送连接成功信号
                    self.connection_status.emit(True, "已连接")
                    self.logger.info("WebSocket连接成功")
                    
                    # 接收消息循环
                    async for message in websocket:
                        if not self.is_running:
                            break
                        
                        try:
                            # 解析JSON数据
                            data = json.loads(message)
                            
                            # 根据消息类型分发
                            msg_type = data.get('type', 'detection')
                            
                            if msg_type == 'video_frame':
                                # 视频帧数据
                                frame_hex = data.get('frame', '')
                                width = data.get('width', 0)
                                height = data.get('height', 0)
                                channel_id = data.get('channel_id', 1)
                                
                                # 十六进制转字节
                                jpeg_data = bytes.fromhex(frame_hex)
                                
                                # 发送视频帧信号
                                self.video_frame.emit(jpeg_data, width, height, channel_id)
                                
                            else:
                                # 检测结果数据
                                self.detection_result.emit(data)
                            
                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON解析失败: {e}")
                        except Exception as e:
                            self.logger.error(f"处理消息异常: {e}")
                
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket连接关闭")
                self._is_connected = False  # 清除连接状态
                self.connection_status.emit(False, "连接关闭")
                
            except Exception as e:
                retry_count += 1
                self._is_connected = False  # 清除连接状态
                self.logger.error(f"WebSocket连接失败 ({retry_count}/{max_retries}): {e}")
                self.connection_status.emit(False, f"连接失败: {str(e)}")
                
                if retry_count < max_retries and self.is_running:
                    # 等待后重试
                    await asyncio.sleep(3)
            
            finally:
                self.websocket = None
                self._is_connected = False  # 清除连接状态
        
        if retry_count >= max_retries:
            self.logger.error("WebSocket连接失败次数过多，停止重试")
            self.connection_status.emit(False, "连接失败")
    
    def is_connected(self):
        """检查是否已连接"""
        return self._is_connected and self.is_running
    
    def send_command(self, command, **kwargs):
        """
        发送命令到服务端
        
        Args:
            command: 命令名称 ('start_detection', 'stop_detection')
            **kwargs: 额外参数
        """
        if not self.is_connected():
            self.logger.warning("WebSocket未连接，无法发送命令")
            return False
        
        try:
            # 构造命令数据
            data = {
                'command': command,
                **kwargs
            }
            
            # 在事件循环中发送
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps(data)),
                    self.loop
                )
                self.logger.info(f"发送命令: {command}")
                return True
            else:
                self.logger.warning("事件循环未运行")
                return False
                
        except Exception as e:
            self.logger.error(f"发送命令异常: {e}")
            return False
