# WebSocket客户端模块
# 用于与服务端通信，获取液位检测数据

import json
import time
import threading
import logging
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from qtpy import QtCore, QtWebSockets, QtNetwork
from qtpy import sip

# 配置日志
logger = logging.getLogger('WebSocketClient')


class WebSocketClient(QtCore.QObject):
    """WebSocket客户端，用于与服务端通信"""
    
    # 信号定义
    connection_status = QtCore.Signal(bool, str)  # 连接状态变化
    detection_result = QtCore.Signal(dict)        # 检测结果
    video_frame = QtCore.Signal(bytes, int, int, int)  # 视频帧数据
    
    def __init__(self, url, parent=None):
        """初始化WebSocket客户端
        
        Args:
            url: WebSocket服务器地址
            parent: 父对象
        """
        super().__init__(parent)

        self.url = url
        self.websocket = None
        self.is_running = False
        self.reconnect_timer = QtCore.QTimer()
        self.reconnect_timer.timeout.connect(self._reconnect)
        self.reconnect_interval = 5000  # 5秒重连间隔

        # 心跳定时器
        self.heartbeat_timer = QtCore.QTimer()
        self.heartbeat_timer.timeout.connect(self.sendHeartbeat)
        self.heartbeat_interval = 30000  # 30秒心跳间隔

        # print(f"[WebSocket] 客户端初始化: {url}")
    
    def start(self):
        """启动WebSocket连接"""
        if self.is_running:
            # print("[WebSocket] 客户端已在运行")
            return

        try:
            # print(f"[WebSocket] 准备连接到: {self.url}")
            self.websocket = QtWebSockets.QWebSocket()
            
            # 禁用代理，避免代理相关的连接问题
            no_proxy = QtNetwork.QNetworkProxy(QtNetwork.QNetworkProxy.NoProxy)
            self.websocket.setProxy(no_proxy)
            # print(f"[WebSocket] QWebSocket对象创建成功，已禁用代理")

            # 连接信号
            # print(f"[WebSocket] 连接信号...")
            self.websocket.connected.connect(self._onConnected)
            # print(f"[WebSocket] [OK] connected信号已连接")

            self.websocket.disconnected.connect(self._onDisconnected)
            # print(f"[WebSocket] [OK] disconnected信号已连接")

            self.websocket.textMessageReceived.connect(self._onTextMessage)
            # print(f"[WebSocket] [OK] textMessageReceived信号已连接")
            logger.info("textMessageReceived信号已连接到_onTextMessage")

            self.websocket.binaryMessageReceived.connect(self._onBinaryMessage)
            # print(f"[WebSocket] [OK] binaryMessageReceived信号已连接")

            self.websocket.error.connect(self._onError)
            # print(f"[WebSocket] [OK] error信号已连接")

            # print(f"[WebSocket] 所有信号连接完成")

            # 开始连接
            self.websocket.open(QtCore.QUrl(self.url))
            self.is_running = True

            # print(f"[WebSocket] 开始连接: {self.url}")
            # print(f"[WebSocket] 当前状态: {self.websocket.state()}")

        except Exception as e:
            import traceback
            # print(f"[WebSocket] 启动失败: {e}")
            # print(f"[WebSocket] 详细错误:\n{traceback.format_exc()}")
            self.connection_status.emit(False, f"启动失败: {str(e)}")
    
    def stop(self):
        """停止WebSocket连接"""
        if not self.is_running:
            return

        try:
            self.is_running = False

            # 安全停止定时器
            try:
                if self.reconnect_timer and not sip.isdeleted(self.reconnect_timer):
                    self.reconnect_timer.stop()
            except Exception as e:
                logger.warning(f"停止重连定时器时出错: {e}")

            try:
                if self.heartbeat_timer and not sip.isdeleted(self.heartbeat_timer):
                    self.heartbeat_timer.stop()
            except Exception as e:
                logger.warning(f"停止心跳定时器时出错: {e}")

            if self.websocket:
                self.websocket.close()
                self.websocket = None

        except Exception as e:
            pass

    def _onConnected(self):
        """连接成功回调"""
        # print("[WebSocket] 连接成功")
        try:
            if self.reconnect_timer and not sip.isdeleted(self.reconnect_timer):
                self.reconnect_timer.stop()
        except Exception as e:
            logger.warning(f"停止重连定时器时出错: {e}")

        # 启动心跳定时器
        try:
            if self.heartbeat_timer and not sip.isdeleted(self.heartbeat_timer):
                self.heartbeat_timer.start(self.heartbeat_interval)
                # print(f"[WebSocket] 心跳定时器已启动，间隔: {self.heartbeat_interval}ms")
        except Exception as e:
            logger.warning(f"启动心跳定时器时出错: {e}")

        self.connection_status.emit(True, "连接成功")

        # 发送初始化消息
        self._sendMessage({
            'type': 'client_init',
            'client_type': 'liquid_detection_client',
            'timestamp': time.time()
        })
    
    def _onDisconnected(self):
        """连接断开回调"""
        # print("[WebSocket] ========== 连接断开 ==========")
        # print(f"[WebSocket] 断开时间: {time.time()}")
        # print(f"[WebSocket] is_running状态: {self.is_running}")

        # 获取断开原因
        if self.websocket:
            pass

        # 打印调用堆栈
        import traceback

        # 停止心跳定时器 - 添加安全检查
        try:
            if self.heartbeat_timer and not sip.isdeleted(self.heartbeat_timer):
                self.heartbeat_timer.stop()
        except Exception as e:
            logger.warning(f"停止心跳定时器时出错: {e}")

        self.connection_status.emit(False, "连接断开")

        # 如果还在运行状态，启动重连
        if self.is_running:
            # 添加安全检查，确保reconnect_timer未被删除
            try:
                if self.reconnect_timer and not sip.isdeleted(self.reconnect_timer):
                    self.reconnect_timer.start(self.reconnect_interval)
            except Exception as e:
                logger.warning(f"启动重连定时器时出错: {e}")
        else:
            pass

    def _onTextMessage(self, message):
        """接收文本消息回调

        Args:
            message: 文本消息
        """
        try:
            # logger.debug(f"收到文本消息，长度: {len(message)}")
            data = json.loads(message)
            message_type = data.get('type', '')
            # logger.debug(f"消息类型: {message_type}")

            if message_type == 'detection_result':
                # 液位检测结果
                channel_id = data.get('channel_id', 'unknown')
                logger.info(f"[WebSocket] 接收检测结果 - 通道: {channel_id}")
                self.detection_result.emit(data)

            elif message_type == 'server_status':
                # 服务器状态消息
                # logger.debug(f"服务器状态: {data.get('message', '')}")
                # print(f"[WebSocket] Server status: {data.get('message', '')}")
                pass

            elif message_type == 'error':
                # 错误消息
                error_type = data.get('error_type', '')
                error_message = data.get('error_message', data.get('message', ''))
                logger.warning(f"服务器错误: {error_type} - {error_message}")
                print(f"[WebSocket] Server error: {error_type} - {error_message}")

            elif message_type == 'command_response':
                # 命令响应消息
                # logger.debug(f"命令响应: {data.get('command', '')} - {data.get('message', '')}")
                # print(f"[WebSocket] Command response: {data.get('command', '')} - {data.get('message', '')}")
                pass

            elif message_type == 'detection_status':
                # 检测状态消息
                # logger.debug(f"检测状态: {data.get('status', '')}")
                # print(f"[WebSocket] Detection status: {data.get('status', '')}")
                pass

            elif message_type == 'welcome':
                # 欢迎消息
                logger.info("已连接到服务器")
                # print(f"[WebSocket] Connected to server")

            else:
                # 忽略status_update等高频消息，避免日志爆炸
                if message_type not in ['status_update', 'heartbeat']:
                    logger.warning(f"未知消息类型: {message_type}")
                # print(f"[WebSocket] Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            # print(f"[WebSocket] JSON parse failed: {e}")
        except Exception as e:
            logger.error(f"消息处理错误: {e}")
            # print(f"[WebSocket] Message processing error: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _onBinaryMessage(self, data):
        """接收二进制消息回调
        
        Args:
            data: 二进制数据
        """
        try:
            # 解析二进制数据头部（假设前16字节为头部信息）
            if len(data) < 16:
                return
            
            # 简单的二进制协议：
            # 前4字节：消息类型（int）
            # 接下来4字节：宽度（int）
            # 接下来4字节：高度（int）
            # 接下来4字节：通道ID（int）
            # 剩余数据：图像数据
            
            import struct
            header = struct.unpack('!IIII', data[:16])
            msg_type, width, height, channel_id = header
            
            if msg_type == 1:  # 视频帧数据
                jpeg_data = data[16:]
                self.video_frame.emit(jpeg_data, width, height, channel_id)
            
        except Exception as e:
            pass

    def _onError(self, error):
        """连接错误回调

        Args:
            error: 错误类型
        """
        # 解析错误类型
        error_names = {
            0: "ConnectionRefusedError - 连接被拒绝",
            1: "RemoteHostClosedError - 远程主机关闭连接",
            2: "HostNotFoundError - 主机未找到",
            3: "SocketAccessError - Socket访问错误",
            4: "SocketResourceError - Socket资源错误",
            5: "SocketTimeoutError - Socket超时",
            6: "DatagramTooLargeError - 数据包过大",
            7: "NetworkError - 网络错误",
            8: "AddressInUseError - 地址已被使用",
            9: "SocketAddressNotAvailableError - Socket地址不可用",
            10: "UnsupportedSocketOperationError - 不支持的Socket操作",
            11: "UnfinishedSocketOperationError - 未完成的Socket操作",
            12: "ProxyAuthenticationRequiredError - 代理认证需要",
            13: "SslHandshakeFailedError - SSL握手失败",
            14: "ProxyConnectionRefusedError - 代理连接被拒绝",
            15: "ProxyConnectionClosedError - 代理连接关闭",
            16: "ProxyConnectionTimeoutError - 代理连接超时",
            17: "ProxyNotFoundError - 代理未找到",
            18: "ProxyProtocolError - 代理协议错误",
            19: "OperationError - 操作错误",
            20: "SslInternalError - SSL内部错误",
            21: "SslInvalidUserDataError - SSL无效用户数据",
            22: "TemporaryError - 临时错误",
            99: "UnknownSocketError - 未知Socket错误"
        }

        error_name = error_names.get(error, f"未知错误({error})")
        error_msg = f"WebSocket错误: {error} - {error_name}"
        # print(f"[WebSocket] ========== 发生错误 ==========")
        # print(f"[WebSocket] {error_msg}")
        # print(f"[WebSocket] 尝试连接的URL: {self.url}")
        # print(f"[WebSocket] 当前状态: {self.websocket.state() if self.websocket else 'None'}")
        # print(f"[WebSocket] 错误字符串: {self.websocket.errorString() if self.websocket else 'None'}")

        # 打印调用堆栈
        import traceback
        # print(f"[WebSocket] 错误调用堆栈:\n{''.join(traceback.format_stack())}")
        self.connection_status.emit(False, error_msg)
    
    def _reconnect(self):
        """重连逻辑"""
        if not self.is_running:
            # print("[WebSocket] 重连取消: is_running=False")
            return

        # print(f"[WebSocket] 尝试重连到: {self.url}")

        if self.websocket:
            # print(f"[WebSocket] 关闭旧连接，当前状态: {self.websocket.state()}")
            self.websocket.close()

        # 重新创建连接
        self.websocket = QtWebSockets.QWebSocket()
        
        # 禁用代理，避免代理相关的连接问题
        no_proxy = QtNetwork.QNetworkProxy(QtNetwork.QNetworkProxy.NoProxy)
        self.websocket.setProxy(no_proxy)
        # print(f"[WebSocket] 创建新的QWebSocket对象，已禁用代理")

        # 重新连接信号
        self.websocket.connected.connect(self._onConnected)
        self.websocket.disconnected.connect(self._onDisconnected)
        self.websocket.textMessageReceived.connect(self._onTextMessage)
        self.websocket.binaryMessageReceived.connect(self._onBinaryMessage)
        self.websocket.error.connect(self._onError)
        # print(f"[WebSocket] 信号重新连接完成")

        # 开始连接
        # print(f"[WebSocket] 调用open()开始连接...")
        self.websocket.open(QtCore.QUrl(self.url))
        # print(f"[WebSocket] open()调用完成，当前状态: {self.websocket.state()}")
    
    def _sendMessage(self, data):
        """发送消息
        
        Args:
            data: 要发送的数据（字典）
        """
        try:
            if self.websocket and self.is_connected():
                message = json.dumps(data)
                self.websocket.sendTextMessage(message)
            else:
                pass

        except Exception as e:
            pass

    def is_connected(self):
        """检查WebSocket是否已连接
        
        Returns:
            bool: 连接状态
        """
        try:
            if self.websocket is None:
                # print(f"[WebSocket] is_connected: websocket为None")
                return False
            
            # 检查WebSocket状态 - 使用数值比较（ConnectedState = 3）
            state = self.websocket.state()
            connected_state = 3  # QAbstractSocket.ConnectedState
            is_conn = state == connected_state
            
            # print(f"[WebSocket] is_connected: state={state}, ConnectedState={connected_state}, result={is_conn}")
            return is_conn
        except Exception as e:
            # print(f"[WebSocket] 检查连接状态异常: {e}")
            return False
    
    def send_command(self, command, **kwargs):
        """发送命令到服务端

        Args:
            command: 命令类型
            **kwargs: 命令参数

        Returns:
            bool: 发送是否成功
        """
        try:
            import time  # 在函数开头导入time模块
            
            # 如果未连接，尝试重新连接
            if not self.is_connected():
                # print(f"[WebSocket] 未连接，尝试重新连接后发送命令: {command}")
                self._reconnect()

                # 等待一小段时间让连接建立
                for i in range(10):  # 最多等待1秒
                    time.sleep(0.1)
                    if self.is_connected():
                        break

                if not self.is_connected():
                    # print(f"[WebSocket] 重连失败，无法发送命令: {command}")
                    return False

            # 服务端期望的命令格式：直接在根级别包含command字段
            command_data = {
                'command': command,
                'timestamp': time.time(),
                **kwargs
            }

            self._sendMessage(command_data)
            # print(f"[WebSocket] 发送命令成功: {command}, 数据: {command_data}")
            return True

        except Exception as e:
            # print(f"[WebSocket] 发送命令失败: {e}")
            return False
    
    def force_reconnect(self):
        """强制重新连接"""
        # print("[WebSocket] 强制重新连接...")
        if self.websocket:
            self.websocket.close()
        self._reconnect()
    
    def sendDetectionRequest(self, channel_id, roi_data=None):
        """发送检测请求
        
        Args:
            channel_id: 通道ID
            roi_data: ROI区域数据（可选）
        """
        request_data = {
            'type': 'detection_request',
            'channel_id': channel_id,
            'timestamp': time.time()
        }
        
        if roi_data:
            request_data['roi_data'] = roi_data
        
        self._sendMessage(request_data)
        # print(f"[WebSocket] 发送检测请求: {channel_id}")
    
    def sendHeartbeat(self):
        """发送心跳包"""
        heartbeat_data = {
            'type': 'heartbeat',
            'timestamp': time.time()
        }
        self._sendMessage(heartbeat_data)


# 使用示例
if __name__ == "__main__":
    import sys
    from qtpy import QtWidgets
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建WebSocket客户端
    ws_client = WebSocketClient('ws://192.168.0.121:8085')
    
    # 连接信号
    def on_connection_status(is_connected, message):
        pass

    def on_detection_result(data):
        pass
    
    ws_client.connection_status.connect(on_connection_status)
    ws_client.detection_result.connect(on_detection_result)
    
    # 启动客户端
    ws_client.start()
    
    # print("WebSocket客户端测试启动")
    # print("按Ctrl+C退出")
    
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        # print("正在退出...")
        ws_client.stop()
        app.quit()