# -*- coding: utf-8 -*-
"""
WebSocket客户端
"""

import logging
import json
import asyncio
from qtpy.QtCore import QObject, Signal, QThread
import websockets


class WebSocketClient(QObject):
    """WebSocket客户端"""
    
    # 信号定义
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, ws_url):
        """
        初始化WebSocket客户端
        
        Args:
            ws_url: WebSocket服务器URL
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.ws_url = ws_url
        self.ws = None
        self.is_connected = False
        self.loop = None
        self.thread = None
    
    def connect(self):
        """连接到WebSocket服务器"""
        self.logger.info(f"连接WebSocket: {self.ws_url}")
        
        # 在新线程中运行asyncio事件循环
        self.thread = QThread()
        self.thread.run = self._run_loop
        self.thread.start()
    
    def _run_loop(self):
        """运行asyncio事件循环"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._connect_loop())
        except Exception as e:
            self.logger.error(f"WebSocket循环异常: {e}")
        finally:
            self.loop.close()
    
    async def _connect_loop(self):
        """连接循环 - 支持自动重连"""
        while True:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.ws = websocket
                    self.is_connected = True
                    self.connected.emit()
                    self.logger.info("WebSocket连接成功")
                    
                    # 接收消息循环
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            self.message_received.emit(data)
                        except json.JSONDecodeError as e:
                            self.logger.error(f"解析消息失败: {e}")
            
            except Exception as e:
                self.logger.error(f"WebSocket连接失败: {e}")
                self.is_connected = False
                self.disconnected.emit()
                
                # 等待5秒后重连
                await asyncio.sleep(5)
                self.logger.info("尝试重新连接...")
    
    def disconnect(self):
        """断开WebSocket连接"""
        if self.loop:
            self.loop.stop()
        
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        
        self.is_connected = False
        self.disconnected.emit()
    
    async def send(self, data):
        """
        发送数据
        
        Args:
            data: 要发送的数据(字典)
        """
        if not self.is_connected or not self.ws:
            self.logger.warning("WebSocket未连接")
            return
        
        try:
            message = json.dumps(data)
            await self.ws.send(message)
        except Exception as e:
            self.logger.error(f"发送数据失败: {e}")
