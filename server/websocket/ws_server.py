# -*- coding: utf-8 -*-
"""
WebSocket服务器 - 支持多通道推送
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Set


class WebSocketServer:
    """WebSocket服务器 - 支持多通道"""
    
    def __init__(self, host='0.0.0.0', port=8085, channel_manager=None):
        """
        初始化WebSocket服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            channel_manager: 通道管理器实例
        """
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.channel_manager = channel_manager
        self.server = None
        
        # 客户端连接字典 {websocket: {'channels': set()}}
        self.clients: Dict = {}
        
        # 通道订阅字典 {channel_id: set(websockets)}
        self.channel_subscribers: Dict[str, Set] = {}
    
    async def start(self):
        """启动WebSocket服务器"""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        self.logger.info(f"WebSocket服务器启动: ws://{self.host}:{self.port}")
    
    async def _handle_client(self, websocket):
        """
        处理客户端连接
        
        Args:
            websocket: WebSocket连接
        """
        client_addr = websocket.remote_address
        self.logger.info(f"客户端连接: {client_addr}")
        
        # 注册客户端
        self.clients[websocket] = {'channels': set()}
        
        try:
            async for message in websocket:
                # 接收客户端消息（命令）
                try:
                    data = json.loads(message)
                    await self._handle_command(websocket, data)
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析消息: {message}")
                except Exception as e:
                    self.logger.error(f"处理消息异常: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # 注销客户端
            self._unregister_client(websocket)
            self.logger.info(f"客户端断开: {client_addr}")
    
    async def _handle_command(self, websocket, data: dict):
        """
        处理客户端命令
        
        Args:
            websocket: WebSocket连接
            data: 命令数据
        """
        command = data.get('command')
        channel_id = data.get('channel_id')
        
        if command == 'subscribe':
            # 订阅通道
            self._subscribe_channel(websocket, channel_id)
            await websocket.send(json.dumps({
                'type': 'command_response',
                'command': 'subscribe',
                'channel_id': channel_id,
                'success': True,
                'message': f'已订阅通道 {channel_id}'
            }))
            
        elif command == 'unsubscribe':
            # 取消订阅通道
            self._unsubscribe_channel(websocket, channel_id)
            await websocket.send(json.dumps({
                'type': 'command_response',
                'command': 'unsubscribe',
                'channel_id': channel_id,
                'success': True,
                'message': f'已取消订阅通道 {channel_id}'
            }))
            
        elif command == 'start_detection':
            # 启动检测
            if self.channel_manager:
                success = self.channel_manager.send_command(channel_id, {
                    'type': 'start_detection'
                })
                await websocket.send(json.dumps({
                    'type': 'command_response',
                    'command': 'start_detection',
                    'channel_id': channel_id,
                    'success': success,
                    'message': '检测已启动' if success else '启动失败'
                }))
                self.logger.info(f"收到命令: 启动检测 - {channel_id}")
        
        elif command == 'stop_detection':
            # 停止检测
            if self.channel_manager:
                success = self.channel_manager.send_command(channel_id, {
                    'type': 'stop_detection'
                })
                await websocket.send(json.dumps({
                    'type': 'command_response',
                    'command': 'stop_detection',
                    'channel_id': channel_id,
                    'success': success,
                    'message': '检测已停止' if success else '停止失败'
                }))
                self.logger.info(f"收到命令: 停止检测 - {channel_id}")
        
        else:
            self.logger.debug(f"收到未知命令: {command}")
    
    def _subscribe_channel(self, websocket, channel_id: str):
        """订阅通道"""
        if channel_id not in self.channel_subscribers:
            self.channel_subscribers[channel_id] = set()
        
        self.channel_subscribers[channel_id].add(websocket)
        self.clients[websocket]['channels'].add(channel_id)
        
        self.logger.info(f"客户端订阅通道: {channel_id}")
    
    def _unsubscribe_channel(self, websocket, channel_id: str):
        """取消订阅通道"""
        if channel_id in self.channel_subscribers:
            self.channel_subscribers[channel_id].discard(websocket)
        
        if websocket in self.clients:
            self.clients[websocket]['channels'].discard(channel_id)
        
        self.logger.info(f"客户端取消订阅通道: {channel_id}")
    
    def _unregister_client(self, websocket):
        """注销客户端"""
        if websocket not in self.clients:
            return
        
        # 取消所有订阅
        channels = self.clients[websocket]['channels'].copy()
        for channel_id in channels:
            self._unsubscribe_channel(websocket, channel_id)
        
        # 删除客户端
        del self.clients[websocket]
    
    async def broadcast_to_channel(self, channel_id: str, data: dict):
        """
        推送数据到订阅该通道的所有客户端
        
        Args:
            channel_id: 通道ID
            data: 要发送的数据
        """
        if channel_id not in self.channel_subscribers:
            return
        
        subscribers = self.channel_subscribers[channel_id].copy()
        if not subscribers:
            return
        
        # 构造消息
        message = json.dumps(data, ensure_ascii=False)
        
        # 移除已断开的连接
        disconnected = set()
        
        for client in subscribers:
            try:
                await client.send(message)
            except:
                disconnected.add(client)
        
        # 清理断开的连接
        for client in disconnected:
            self._unsubscribe_channel(client, channel_id)
    
    def get_client_count(self) -> int:
        """获取连接的客户端数量"""
        return len(self.clients)
    
    def get_channel_subscriber_count(self, channel_id: str) -> int:
        """获取通道订阅者数量"""
        return len(self.channel_subscribers.get(channel_id, set()))
