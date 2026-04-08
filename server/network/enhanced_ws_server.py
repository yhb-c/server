# 增强的WebSocket服务器模块
#
# 职责说明：
# 1. 管理WebSocket客户端连接和断开
# 2. 接收并处理客户端命令（订阅、加载模型、配置通道、启动/停止检测等）
# 3. 管理通道订阅关系
# 4. 推送检测结果和状态更新到订阅的客户端（唯一的推送出口）
# 5. 集成DetectionService处理检测业务逻辑
#
# 注意：所有检测结果和状态更新都通过本模块的broadcast_to_channel方法推送

import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Set, Optional
import threading
import os
import sys

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from detection_service import DetectionService


class EnhancedWebSocketServer:
    """
    增强的WebSocket服务器
    
    职责：
    - 处理客户端WebSocket连接
    - 接收和处理客户端命令
    - 管理液位检测服务
    - 推送检测结果到客户端
    """
    
    def __init__(self, host='0.0.0.0', port=8085):
        """
        初始化增强的WebSocket服务器
        
        Args:
            host: 监听地址
            port: 监听端口
        """
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.server = None
        
        # 客户端连接字典 {websocket: {'channels': set(), 'client_info': dict}}
        self.clients: Dict = {}
        
        # 通道订阅字典 {channel_id: set(websockets)}
        self.channel_subscribers: Dict[str, Set] = {}
        
        # 液位检测服务
        self.detection_service = DetectionService(websocket_server=self)
        
        # 服务器统计信息
        self.server_stats = {
            'start_time': None,
            'total_connections': 0,
            'active_connections': 0,
            'total_commands': 0,
            'total_broadcasts': 0
        }
    
    async def start(self):
        """启动WebSocket服务器"""
        try:
            self.server_stats['start_time'] = datetime.now().isoformat()

            # 设置检测服务的事件循环
            self.detection_service.event_loop = asyncio.get_running_loop()
            self.logger.info("已设置检测服务的事件循环")

            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=None,  # 禁用自动ping
                ping_timeout=None    # 禁用ping超时
            )

            self.logger.info(f"增强WebSocket服务器启动成功: ws://{self.host}:{self.port}")

            # 保持服务器运行
            await self.server.wait_closed()
            
        except Exception as e:
            self.logger.error(f"WebSocket服务器启动失败: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket服务器"""
        try:
            self.logger.info("正在停止WebSocket服务器...")
            
            # 停止所有检测
            self.detection_service.cleanup()
            
            # 关闭服务器
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            self.logger.info("WebSocket服务器已停止")
            
        except Exception as e:
            self.logger.error(f"停止WebSocket服务器失败: {e}")
    
    async def _handle_client(self, websocket):
        """
        处理客户端连接
        
        Args:
            websocket: WebSocket连接
        """
        client_addr = websocket.remote_address
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        
        self.logger.info(f"客户端连接: {client_id}")
        
        # 注册客户端
        self.clients[websocket] = {
            'channels': set(),
            'client_info': {
                'id': client_id,
                'connect_time': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat()
            }
        }
        
        self.server_stats['total_connections'] += 1
        self.server_stats['active_connections'] += 1
        
        try:
            # 发送欢迎消息
            await websocket.send(json.dumps({
                'type': 'welcome',
                'message': '连接成功',
                'server_time': datetime.now().isoformat(),
                'client_id': client_id
            }))
            
            # 处理客户端消息
            async for message in websocket:
                try:
                    # 更新活动时间
                    self.clients[websocket]['client_info']['last_activity'] = datetime.now().isoformat()
                    
                    # 解析消息
                    data = json.loads(message)
                    self.server_stats['total_commands'] += 1
                    
                    # 处理命令
                    await self._handle_command(websocket, data)
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"[{client_id}] 无法解析消息: {message[:100]}...")
                    await self._send_error_response(websocket, "消息格式错误", str(e))
                    
                except Exception as e:
                    self.logger.error(f"[{client_id}] 处理消息异常: {e}")
                    await self._send_error_response(websocket, "处理消息失败", str(e))
                    
        except websockets.exceptions.ConnectionClosed as e:
            self.logger.info(f"[{client_id}] 客户端正常断开 - 原因: {e.code} {e.reason}")
            import traceback
            self.logger.debug(f"[{client_id}] 断开堆栈:\n{traceback.format_exc()}")
        except Exception as e:
            self.logger.error(f"[{client_id}] 客户端连接异常: {e}")
            import traceback
            self.logger.error(f"[{client_id}] 异常堆栈:\n{traceback.format_exc()}")
        finally:
            # 注销客户端
            self.logger.info(f"[{client_id}] 开始注销客户端，当前订阅通道: {list(self.clients[websocket]['channels']) if websocket in self.clients else '无'}")
            self._unregister_client(websocket)
            self.server_stats['active_connections'] -= 1
            self.logger.info(f"[{client_id}] 客户端连接结束，活跃连接数: {self.server_stats['active_connections']}")
    
    async def _handle_command(self, websocket, data: dict):
        """
        处理客户端命令

        Args:
            websocket: WebSocket连接
            data: 命令数据
        """
        # 兼容两种消息格式：command 和 type
        command = data.get('command') or data.get('type')
        channel_id = data.get('channel_id')
        client_id = self.clients[websocket]['client_info']['id']

        self.logger.info(f"[{client_id}] === 收到命令 ===")
        self.logger.info(f"[{client_id}] 命令: {command}")
        self.logger.info(f"[{client_id}] 通道: {channel_id}")
        self.logger.info(f"[{client_id}] 数据: {data}")

        try:
            if command == 'subscribe':
                # 订阅通道
                self.logger.info(f"[{client_id}] 处理订阅命令")
                await self._handle_subscribe(websocket, channel_id)

            elif command == 'unsubscribe':
                # 取消订阅通道
                self.logger.info(f"[{client_id}] 处理取消订阅命令")
                await self._handle_unsubscribe(websocket, channel_id)

            elif command == 'load_model':
                # 加载检测模型
                self.logger.info(f"[{client_id}] 处理模型加载命令")
                await self._handle_load_model(websocket, data)

            elif command == 'configure_channel':
                # 配置通道
                self.logger.info(f"[{client_id}] 处理通道配置命令")
                await self._handle_configure_channel(websocket, data)

            elif command == 'start_detection':
                # 启动检测
                self.logger.info(f"[{client_id}] 处理启动检测命令")
                await self._handle_start_detection(websocket, channel_id)

            elif command == 'start_all':
                # 启动所有通道检测
                self.logger.info(f"[{client_id}] 处理启动所有通道检测命令")
                await self._handle_start_all(websocket)

            elif command == 'stop_detection':
                # 停止检测
                self.logger.info(f"[{client_id}] 处理停止检测命令")
                await self._handle_stop_detection(websocket, channel_id)

            elif command == 'stop_all':
                # 停止所有通道检测
                self.logger.info(f"[{client_id}] 处理停止所有通道检测命令")
                await self._handle_stop_all(websocket)

            elif command == 'get_status':
                # 获取状态
                self.logger.info(f"[{client_id}] 处理状态查询命令")
                await self._handle_get_status(websocket, channel_id)

            elif command == 'ping':
                # 心跳检测
                self.logger.info(f"[{client_id}] 处理ping命令")
                await self._handle_ping(websocket)

            elif command == 'heartbeat':
                # 心跳消息（客户端定期发送）
                self.logger.debug(f"[{client_id}] 收到心跳消息")
                # 不需要响应，只记录日志

            elif command == 'client_init':
                # 客户端初始化消息
                self.logger.info(f"[{client_id}] 客户端初始化")
                # 不需要响应，只记录日志

            else:
                self.logger.warning(f"[{client_id}] 未知命令: {command}")
                await self._send_error_response(websocket, "未知命令", f"不支持的命令: {command}")

            self.logger.info(f"[{client_id}] 命令 {command} 处理完成")
                
        except Exception as e:
            self.logger.error(f"[{client_id}] 处理命令 {command} 异常: {e}")
            import traceback
            self.logger.error(f"[{client_id}] 异常详情:\n{traceback.format_exc()}")
            await self._send_error_response(websocket, "命令处理失败", str(e))
    
    async def _handle_subscribe(self, websocket, channel_id: str):
        """处理订阅命令"""
        if not channel_id:
            await self._send_error_response(websocket, "订阅失败", "通道ID不能为空")
            return
        
        self._subscribe_channel(websocket, channel_id)
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'subscribe',
            'channel_id': channel_id,
            'success': True,
            'message': f'已订阅通道 {channel_id}',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def _handle_unsubscribe(self, websocket, channel_id: str):
        """处理取消订阅命令"""
        if not channel_id:
            await self._send_error_response(websocket, "取消订阅失败", "通道ID不能为空")
            return
        
        self._unsubscribe_channel(websocket, channel_id)
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'unsubscribe',
            'channel_id': channel_id,
            'success': True,
            'message': f'已取消订阅通道 {channel_id}',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def _handle_load_model(self, websocket, data: dict):
        """处理加载模型命令"""
        client_id = self.clients[websocket]['client_info']['id']
        channel_id = data.get('channel_id')
        model_path = data.get('model_path')
        device = data.get('device', 'cuda')
        
        self.logger.info(f"[{client_id}] === 收到加载模型命令 ===")
        self.logger.info(f"[{client_id}] 通道ID: {channel_id}")
        self.logger.info(f"[{client_id}] 模型路径: {model_path}")
        self.logger.info(f"[{client_id}] 设备类型: {device}")
        
        if not channel_id or not model_path:
            error_msg = "通道ID和模型路径不能为空"
            self.logger.error(f"[{client_id}] 参数验证失败: {error_msg}")
            await self._send_error_response(websocket, "加载模型失败", error_msg)
            return
        
        try:
            # 执行模型加载
            self.logger.info(f"[{client_id}] 开始执行模型加载...")
            success = self.detection_service.load_model(channel_id, model_path, device)
            self.logger.info(f"[{client_id}] 模型加载结果: {success}")
            
            # 发送响应
            response = {
                'type': 'command_response',
                'command': 'load_model',
                'channel_id': channel_id,
                'success': success,
                'message': f'模型加载{"成功" if success else "失败"}',
                'model_path': model_path,
                'device': device,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"[{client_id}] 发送模型加载响应: {success}")
            await websocket.send(json.dumps(response))
            
        except Exception as e:
            error_msg = f"模型加载异常: {str(e)}"
            self.logger.error(f"[{client_id}] {error_msg}")
            import traceback
            self.logger.error(f"[{client_id}] 异常详情:\n{traceback.format_exc()}")
            
            # 发送错误响应
            await self._send_error_response(websocket, "加载模型失败", error_msg)
    
    async def _handle_configure_channel(self, websocket, data: dict):
        """处理配置通道命令"""
        channel_id = data.get('channel_id')
        config = data.get('config', {})
        
        if not channel_id:
            await self._send_error_response(websocket, "配置通道失败", "通道ID不能为空")
            return
        
        # 执行通道配置
        success = self.detection_service.configure_channel(channel_id, config)
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'configure_channel',
            'channel_id': channel_id,
            'success': success,
            'message': f'通道配置{"成功" if success else "失败"}',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def _handle_start_detection(self, websocket, channel_id: str):
        """处理启动检测命令"""
        client_id = self.clients[websocket]['client_info']['id']
        self.logger.info(f"[{client_id}] 收到启动检测命令: 通道{channel_id}")

        if not channel_id:
            self.logger.error(f"[{client_id}] 启动检测失败: 通道ID为空")
            await self._send_error_response(websocket, "启动检测失败", "通道ID不能为空")
            return

        # 检查客户端是否已订阅该通道，如果没有则自动订阅
        if channel_id not in self.clients[websocket]['channels']:
            self.logger.info(f"[{client_id}] 客户端未订阅通道{channel_id}，自动订阅")
            self._subscribe_channel(websocket, channel_id)

        self.logger.info(f"[{client_id}] 开始执行启动检测: 通道{channel_id}")

        # 执行启动检测
        success = self.detection_service.start_detection(channel_id)

        self.logger.info(f"[{client_id}] 启动检测结果: 通道{channel_id}, 成功={success}")
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'start_detection',
            'channel_id': channel_id,
            'success': success,
            'message': f'检测{"启动成功" if success else "启动失败"}',
            'timestamp': datetime.now().isoformat()
        }))
        
        # 如果启动成功，广播状态变化
        if success:
            self.logger.info(f"[{client_id}] 广播检测启动状态: 通道{channel_id}")
            await self.broadcast_to_channel(channel_id, {
                'type': 'detection_status',
                'channel_id': channel_id,
                'status': 'started',
                'message': '检测已启动',
                'timestamp': datetime.now().isoformat()
            })
        else:
            self.logger.error(f"[{client_id}] 检测启动失败: 通道{channel_id}")

    async def _handle_start_all(self, websocket):
        """处理启动所有通道检测命令"""
        client_id = self.clients[websocket]['client_info']['id']
        self.logger.info(f"[{client_id}] 收到启动所有通道检测命令")

        # 获取所有通道ID
        all_channels = list(self.detection_service.channel_status.keys())
        self.logger.info(f"[{client_id}] 找到 {len(all_channels)} 个通道: {all_channels}")

        # 统计结果
        success_count = 0
        failed_channels = []
        results = {}

        # 遍历所有通道并启动检测
        for channel_id in all_channels:
            try:
                self.logger.info(f"[{client_id}] 正在处理通道: {channel_id}")

                # 检查客户端是否已订阅该通道，如果没有则自动订阅
                if channel_id not in self.clients[websocket]['channels']:
                    self.logger.info(f"[{client_id}] 客户端未订阅通道{channel_id}，自动订阅")
                    self._subscribe_channel(websocket, channel_id)

                # 获取通道状态
                channel_state = self.detection_service.channel_status[channel_id]

                # 步骤1: 加载模型（如果未加载）
                if not channel_state['model_loaded']:
                    model_path = channel_state.get('config_model_path')
                    if not model_path:
                        self.logger.error(f"[{client_id}] 通道 {channel_id} 配置中没有模型路径")
                        failed_channels.append(channel_id)
                        results[channel_id] = {'success': False, 'message': '配置中没有模型路径'}
                        continue

                    self.logger.info(f"[{client_id}] 通道 {channel_id} 开始加载模型: {model_path}")
                    load_success = self.detection_service.load_model(channel_id, model_path, 'cuda')

                    if not load_success:
                        self.logger.error(f"[{client_id}] 通道 {channel_id} 模型加载失败")
                        failed_channels.append(channel_id)
                        results[channel_id] = {'success': False, 'message': '模型加载失败'}
                        continue

                    self.logger.info(f"[{client_id}] 通道 {channel_id} 模型加载成功")

                # 步骤2: 配置通道（如果未配置）
                if not channel_state['configured']:
                    self.logger.info(f"[{client_id}] 通道 {channel_id} 开始配置")

                    # 从annotation_result.yaml加载ROI配置
                    import yaml
                    import os
                    annotation_file = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'database', 'config', 'annotation_result.yaml'
                    )

                    annotation_config = {}
                    if os.path.exists(annotation_file):
                        try:
                            with open(annotation_file, 'r', encoding='utf-8') as f:
                                all_annotations = yaml.safe_load(f)
                                if channel_id in all_annotations:
                                    annotation_config = all_annotations[channel_id]
                                    self.logger.info(f"[{client_id}] 通道 {channel_id} 加载ROI配置成功: {annotation_config.get('annotation_count', 0)}个区域")
                                else:
                                    self.logger.warning(f"[{client_id}] 通道 {channel_id} 在annotation_result.yaml中未找到配置")
                        except Exception as e:
                            self.logger.error(f"[{client_id}] 通道 {channel_id} 加载ROI配置失败: {e}")
                    else:
                        self.logger.warning(f"[{client_id}] annotation_result.yaml文件不存在: {annotation_file}")

                    # 构建完整配置
                    config = {
                        'detection_config': {
                            'confidence_threshold': 0.5,
                            'iou_threshold': 0.45
                        },
                        'annotation_config': annotation_config  # 添加ROI配置
                    }

                    config_success = self.detection_service.configure_channel(channel_id, config)

                    if not config_success:
                        self.logger.error(f"[{client_id}] 通道 {channel_id} 配置失败")
                        failed_channels.append(channel_id)
                        results[channel_id] = {'success': False, 'message': '通道配置失败'}
                        continue

                    self.logger.info(f"[{client_id}] 通道 {channel_id} 配置成功")

                # 步骤3: 启动检测
                self.logger.info(f"[{client_id}] 通道 {channel_id} 开始启动检测")
                success = self.detection_service.start_detection(channel_id)

                if success:
                    success_count += 1
                    results[channel_id] = {'success': True, 'message': '启动成功'}
                    self.logger.info(f"[{client_id}] 通道 {channel_id} 启动成功")

                    # 广播状态变化
                    await self.broadcast_to_channel(channel_id, {
                        'type': 'detection_status',
                        'channel_id': channel_id,
                        'status': 'started',
                        'message': '检测已启动',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    failed_channels.append(channel_id)
                    results[channel_id] = {'success': False, 'message': '启动失败'}
                    self.logger.error(f"[{client_id}] 通道 {channel_id} 启动失败")

            except Exception as e:
                failed_channels.append(channel_id)
                results[channel_id] = {'success': False, 'message': str(e)}
                self.logger.error(f"[{client_id}] 通道 {channel_id} 处理异常: {e}")
                import traceback
                self.logger.error(f"[{client_id}] 异常详情:\n{traceback.format_exc()}")

        # 发送汇总响应
        response = {
            'type': 'command_response',
            'command': 'start_all',
            'success': success_count > 0,
            'message': f'成功启动 {success_count}/{len(all_channels)} 个通道',
            'total_channels': len(all_channels),
            'success_count': success_count,
            'failed_count': len(failed_channels),
            'failed_channels': failed_channels,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }

        self.logger.info(f"[{client_id}] 启动所有通道完成: 成功{success_count}个, 失败{len(failed_channels)}个")
        await websocket.send(json.dumps(response))

    async def _handle_stop_detection(self, websocket, channel_id: str):
        """处理停止检测命令"""
        if not channel_id:
            await self._send_error_response(websocket, "停止检测失败", "通道ID不能为空")
            return
        
        # 执行停止检测
        success = self.detection_service.stop_detection(channel_id)
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'stop_detection',
            'channel_id': channel_id,
            'success': success,
            'message': f'检测{"停止成功" if success else "停止失败"}',
            'timestamp': datetime.now().isoformat()
        }))
        
        # 如果停止成功，广播状态变化
        if success:
            await self.broadcast_to_channel(channel_id, {
                'type': 'detection_status',
                'channel_id': channel_id,
                'status': 'stopped',
                'message': '检测已停止',
                'timestamp': datetime.now().isoformat()
            })

    async def _handle_stop_all(self, websocket):
        """处理停止所有通道检测命令"""
        client_id = self.clients[websocket]['client_info']['id']
        self.logger.info(f"[{client_id}] 收到停止所有通道检测命令")

        # 获取所有通道ID
        all_channels = list(self.detection_service.channel_status.keys())
        self.logger.info(f"[{client_id}] 找到 {len(all_channels)} 个通道: {all_channels}")

        # 统计结果
        success_count = 0
        failed_channels = []
        results = {}

        # 遍历所有通道并停止检测
        for channel_id in all_channels:
            try:
                self.logger.info(f"[{client_id}] 正在停止通道: {channel_id}")

                # 停止检测
                success = self.detection_service.stop_detection(channel_id)

                if success:
                    success_count += 1
                    results[channel_id] = {'success': True, 'message': '停止成功'}
                    self.logger.info(f"[{client_id}] 通道 {channel_id} 停止成功")

                    # 广播状态变化
                    await self.broadcast_to_channel(channel_id, {
                        'type': 'detection_status',
                        'channel_id': channel_id,
                        'status': 'stopped',
                        'message': '检测已停止',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    failed_channels.append(channel_id)
                    results[channel_id] = {'success': False, 'message': '停止失败'}
                    self.logger.error(f"[{client_id}] 通道 {channel_id} 停止失败")

            except Exception as e:
                failed_channels.append(channel_id)
                results[channel_id] = {'success': False, 'message': str(e)}
                self.logger.error(f"[{client_id}] 通道 {channel_id} 停止异常: {e}")

        # 发送汇总响应
        response = {
            'type': 'command_response',
            'command': 'stop_all',
            'success': success_count > 0,
            'message': f'成功停止 {success_count}/{len(all_channels)} 个通道',
            'total_channels': len(all_channels),
            'success_count': success_count,
            'failed_count': len(failed_channels),
            'failed_channels': failed_channels,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }

        self.logger.info(f"[{client_id}] 停止所有通道完成: 成功{success_count}个, 失败{len(failed_channels)}个")
        await websocket.send(json.dumps(response))

    async def _handle_get_status(self, websocket, channel_id: Optional[str]):
        """处理获取状态命令"""
        if channel_id:
            # 获取指定通道状态
            status = self.detection_service.get_detection_status(channel_id)
        else:
            # 获取所有通道状态
            status = self.detection_service.get_all_status()
        
        await websocket.send(json.dumps({
            'type': 'command_response',
            'command': 'get_status',
            'channel_id': channel_id,
            'success': True,
            'data': status,
            'server_stats': self.server_stats,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def _handle_ping(self, websocket):
        """处理心跳检测命令"""
        await websocket.send(json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def _send_error_response(self, websocket, error_type: str, error_message: str):
        """发送错误响应"""
        try:
            await websocket.send(json.dumps({
                'type': 'error',
                'error_type': error_type,
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
            }))
        except:
            pass  # 忽略发送失败
    
    def _subscribe_channel(self, websocket, channel_id: str):
        """订阅通道"""
        if channel_id not in self.channel_subscribers:
            self.channel_subscribers[channel_id] = set()

        self.channel_subscribers[channel_id].add(websocket)
        self.clients[websocket]['channels'].add(channel_id)

        client_id = self.clients[websocket]['client_info']['id']
        self.logger.info(f"[{client_id}] 订阅通道: {channel_id}，当前订阅者数量: {len(self.channel_subscribers[channel_id])}")
    
    def _unsubscribe_channel(self, websocket, channel_id: str):
        """取消订阅通道"""
        if channel_id in self.channel_subscribers:
            self.channel_subscribers[channel_id].discard(websocket)

        if websocket in self.clients:
            self.clients[websocket]['channels'].discard(channel_id)

        client_id = self.clients[websocket]['client_info']['id'] if websocket in self.clients else 'unknown'
        remaining_subscribers = len(self.channel_subscribers.get(channel_id, set()))
        self.logger.info(f"[{client_id}] 取消订阅通道: {channel_id}，剩余订阅者数量: {remaining_subscribers}")

        # 检查该通道是否还有订阅者，如果没有则自动停止检测
        if channel_id in self.channel_subscribers and len(self.channel_subscribers[channel_id]) == 0:
            self.logger.info(f"[{client_id}] 通道 {channel_id} 无订阅者，自动停止检测")
            # 停止检测任务
            if self.detection_service:
                try:
                    self.detection_service.stop_detection(channel_id)
                    self.logger.info(f"[{client_id}] 通道 {channel_id} 检测已自动停止")
                except Exception as e:
                    self.logger.error(f"[{client_id}] 自动停止检测失败: {e}")
    
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
        # 记录检测结果数据的关键信息（仅DEBUG级别）
        if data.get('type') == 'detection_result':
            result_data = data.get('data', {})
            self.logger.debug(f"[{channel_id}] 收到检测结果推送 - 帧号: {result_data.get('frame_count')}, "
                           f"数据字段: {list(result_data.keys())}")

        if channel_id not in self.channel_subscribers:
            self.logger.warning(f"[{channel_id}] 通道没有订阅者字典，无法推送数据")
            self.logger.warning(f"当前所有通道订阅: {list(self.channel_subscribers.keys())}")
            return

        subscribers = self.channel_subscribers[channel_id].copy()

        if not subscribers:
            self.logger.warning(f"[{channel_id}] 通道订阅者列表为空，无法推送数据")
            self.logger.debug(f"[{channel_id}] 所有通道订阅者状态: {[(ch, len(subs)) for ch, subs in self.channel_subscribers.items()]}")
            return

        # 构造消息
        try:
            message = json.dumps(data, ensure_ascii=False)
            self.server_stats['total_broadcasts'] += 1
        except Exception as e:
            self.logger.error(f"[{channel_id}] JSON序列化失败: {e}")
            self.logger.error(f"[{channel_id}] 数据类型: {data.get('type')}, 数据键: {list(data.keys())}")
            import traceback
            self.logger.error(traceback.format_exc())
            return

        # 移除已断开的连接
        disconnected = set()

        for client in subscribers:
            try:
                await client.send(message)
            except Exception as e:
                self.logger.warning(f"[{channel_id}] 发送消息到客户端失败: {e}")
                disconnected.add(client)

        # 清理断开的连接
        for client in disconnected:
            self._unsubscribe_channel(client, channel_id)
    
    def get_server_info(self) -> dict:
        """获取服务器信息"""
        return {
            'host': self.host,
            'port': self.port,
            'stats': self.server_stats,
            'active_connections': len(self.clients),
            'channels': {
                channel_id: len(subscribers)
                for channel_id, subscribers in self.channel_subscribers.items()
            },
            'detection_status': self.detection_service.get_all_status()
        }