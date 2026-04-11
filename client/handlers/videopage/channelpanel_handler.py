# -*- coding: utf-8 -*-

"""
通道相关的信号槽处理方法

包含所有与通道操作相关的回调函数
以及通道配置文件的读写操作
"""

import os
import re
import threading
import queue
import time
import yaml
import logging
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy.QtCore import Qt, QFileSystemWatcher

# 导入新的线程管理器
try:
    from .thread_manager.thread_manager import ChannelThreadManager
except ImportError:
    try:
        from thread_manager.thread_manager import ChannelThreadManager
    except ImportError:
        try:
            from client.handlers.videopage.thread_manager.thread_manager import ChannelThreadManager
        except ImportError:
            ChannelThreadManager = None

try:
    from ...database.config import get_project_root
except ImportError:
    try:
        from database.config import get_project_root
    except ImportError:
        from database.config import get_project_root

# 导入远程配置管理器
try:
    from utils.config import RemoteConfigManager
except ImportError:
    try:
        from client.utils.config import RemoteConfigManager
    except ImportError:
        RemoteConfigManager = None


class VideoDisplaySignal(QtCore.QObject):
    """视频显示信号类，用于跨线程更新UI
    
    这是一个独立的 QObject，用于在子线程和主线程之间传递信号。
    信号连接使用 QueuedConnection，确保槽函数在主线程中执行。
    """
    # 信号：(channel_id, overlay_data)
    update_display = QtCore.Signal(str, object)
    
    def __init__(self, handler, parent=None):
        super().__init__(parent)
        self._handler = handler
    
    @QtCore.Slot(str, object)
    def on_update_display(self, channel_id, overlay_data):
        """槽函数：在主线程中更新UI"""
        if self._handler:
            self._handler._updateVideoDisplayUI(channel_id, overlay_data)


class ChannelPanelHandler:
    """
    通道面板处理器 (Mixin类)
    
    对应组件：widgets/videopage/channelpanel.py (ChannelPanel)
    
    处理通道面板的所有信号：
    - channelSelected: 通道被选中
    - channelConnected: 打开通道
    - channelDisconnected: 断开通道
    - channelAdded: 添加新通道
    - channelRemoved: 移除通道
    - channelEdited: 通道设置
    
    架构设计：
    - 捕获线程：从通道抓取画面 -> frame_buffer
    - 显示线程：从frame_buffer复制读取 -> 显示到UI
    
    注意：此类需要混入 QObject 子类（如 QMainWindow）以支持信号
    """
    
    
    def _initChannelResources(self):
        """初始化通道相关资源（在MainWindow的__init__中调用）"""
        # 初始化logger
        self.logger = logging.getLogger('client')

        # 存储活动的通道捕获对象 {channel_id: HKcapture}
        self._channel_captures = {}
        
        #  正在连接的通道集合（防止重复连接）
        self._channels_connecting = set()
        
        # 通道ID到面板的映射 {channel_id: ChannelPanel}
        self._channel_panels_map = {}
        
        # 全屏放大窗口映射 {channel_id: AmplifyWindow}
        self._amplify_windows = {}
        # 全屏放大窗口处理器映射 {channel_id: AmplifyWindowHandler}
        self._amplify_handlers = {}
        
        # 检测引擎字典 {channel_id: detection_engine}
        self._detection_engines = {}
        
        # 液位线位置数据缓存 {channel_id: {area_idx: position_data}}
        self._liquid_line_positions = {}
        
        # 🔥 创建视频显示信号对象（用于跨线程更新UI）
        # 使用 QApplication.instance() 作为父对象，防止被垃圾回收
        app = QtWidgets.QApplication.instance()
        self._video_display_signal = VideoDisplaySignal(self, app)
        # 信号连接到自身的槽函数，使用 QueuedConnection 确保在主线程执行
        self._video_display_signal.update_display.connect(
            self._video_display_signal.on_update_display, 
            QtCore.Qt.QueuedConnection
        )
        self._liquid_line_locks = {}
        
        # frame_buffer映射 {channel_id: queue.Queue} - 用于兼容旧代码
        self._frame_buffers = {}
        
        # 初始化新的线程管理器
        self.thread_manager = ChannelThreadManager()
        # 设置主窗口引用，以便访问 current_mission
        self.thread_manager.main_window = self
        # 设置应用配置，以便获取编译模式
        if hasattr(self, '_config'):
            self.thread_manager.config = self._config
        
        # 🔥 初始化远程配置管理器
        self._remote_config_manager = RemoteConfigManager()
        
        # 🔥 曲线更新回调现在由 CurvePanelHandler.connectCurvePanel() 负责设置
        
        # 🔥 初始化配置文件监控器
        self._initConfigFileWatcher()
        
        # 从配置文件加载帧率设置
        self._loadFrameRateConfig()
        
        # 🔥 WebSocket客户端现在由系统窗口统一管理，不在这里初始化
        # self._initWebSocketClient()
    
    def initializeChannelPanels(self, channel_panels):
        """初始化通道面板数据（在app.py中调用）
        
        Args:
            channel_panels: 通道面板列表
        """
        for i, panel in enumerate(channel_panels):
            channel_id = f"channel{i+1}"
            
            # 立即建立映射（无论通道是否打开，都能找到面板）
            self._channel_panels_map[channel_id] = panel
            
            # 临时方案：直接添加通道数据，不依赖配置文件
            channel_data = {
                'name': f'通道{i+1}',
                'type': 'rtsp',
                'url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
                'status': 'disconnected',
                'resolution': '1920x1080'
            }
            panel.addChannel(channel_id, channel_data)
            self.logger.debug(f"[DEBUG] 已添加通道数据: {channel_id} -> {channel_data}")
    
    def _connectChannelPanelSignals(self, panel):
        """
        打开通道面板的信号（在初始化面板后调用）
        
        Args:
            panel: ChannelPanel 实例
        """
        # 打开通道信号
        if hasattr(panel, 'channelConnected'):
            panel.channelConnected.connect(self.onChannelConnected)
        
        if hasattr(panel, 'channelDisconnected'):
            panel.channelDisconnected.connect(self.onChannelDisconnected)
        
        if hasattr(panel, 'channelEdited'):
            panel.channelEdited.connect(self.onChannelEdited)
        
        if hasattr(panel, 'amplifyClicked'):
            panel.amplifyClicked.connect(self.onAmplifyClicked)
        
        # 连接名称更改信号
        if hasattr(panel, 'channelNameChanged'):
            panel.channelNameChanged.connect(self.onChannelNameChanged)
    
    def _loadFrameRateConfig(self):
        """从配置文件加载帧率设置"""
        try:
            config = self._config
            
            # 读取各线程帧率配置
            self._capture_fps = config.get('capture_frame_rate', 25)
            self._display_fps = config.get('display_frame_rate', 25)
            self._detection_fps = config.get('detection_frame_rate', 25)
            self._save_fps = config.get('save_data_rate', 25)
            self._crop_fps = config.get('crop_frame_rate', 25)
            
            pass
            
        except Exception as e:
            pass
            # 使用默认帧率
            self._capture_fps = 25
            self._display_fps = 25
            self._detection_fps = 25
            self._save_fps = 25
            self._crop_fps = 25
    
    def _initWebSocketClient(self):
        """初始化WebSocket客户端（已废弃 - 现在由系统窗口统一管理）"""
        # WebSocket客户端现在在系统窗口级别统一初始化和管理
        # 所有handler通过self.ws_client访问（因为handler是Mixin到SystemWindow中的）
        pass
        
        # 以下代码已废弃，保留作为参考
        # try:
        #     from utils.ws_client import WebSocketClient
        #     
        #     # 创建WebSocket客户端
        #     ws_url = 'ws://192.168.0.127:8085'
        #     self.ws_client = WebSocketClient(ws_url, self)
        #     
        #     # 连接信号
        #     self.ws_client.detection_result.connect(self._onDetectionResult)
        #     self.ws_client.connection_status.connect(self._onWebSocketStatus)
        #     self.ws_client.video_frame.connect(self._onVideoFrame)
        #     
        #     # 不自动启动，等待用户点击连接按钮
        #     # self.ws_client.start()
        #     
        #     print(f"[WebSocket] 客户端已初始化: {ws_url}")
        #     
        # except Exception as e:
        #     print(f"[WebSocket] 初始化失败: {e}")
        #     import traceback
        #     traceback.print_exc()
        #     self.ws_client = None
    
    @QtCore.Slot(bytes, int, int, int)
    def _onVideoFrame(self, jpeg_data, width, height, channel_id):
        """处理视频帧
        
        Args:
            jpeg_data: JPEG图像数据
            width: 图像宽度
            height: 图像高度
            channel_id: 通道ID
        """
        try:
            channel_id_str = f"channel{channel_id}"
            
            # 获取通道面板
            panel = self._channel_panels_map.get(channel_id_str)
            if not panel:
                return
            
            # 调试：检查JPEG数据
            if not hasattr(self, '_jpeg_decode_debug_logged'):
                self.logger.debug(f"[视频帧调试] JPEG数据大小: {len(jpeg_data)} bytes")
                self.logger.debug(f"[视频帧调试] 图像尺寸: {width}x{height}")
                self._jpeg_decode_debug_logged = True
            
            # JPEG解码为QPixmap
            from qtpy import QtGui
            pixmap = QtGui.QPixmap()
            success = pixmap.loadFromData(jpeg_data, 'JPEG')
            
            if not success or pixmap.isNull():
                self.logger.debug(f"[视频帧] JPEG解码失败")
                return
            
            # 调试：检查QPixmap
            if not hasattr(self, '_pixmap_debug_logged'):
                self.logger.debug(f"[视频帧调试] QPixmap尺寸: {pixmap.width()}x{pixmap.height()}")
                self.logger.debug(f"[视频帧调试] QPixmap格式: {pixmap.depth()} bits")
                self._pixmap_debug_logged = True
            
            # 显示到面板
            if hasattr(panel, 'displayFrame'):
                panel.displayFrame(pixmap)
            
        except Exception as e:
            self.logger.debug(f"[视频帧] 处理异常: {e}")
            import traceback
            traceback.print_exc()
    
    @QtCore.Slot(dict)
    def _onDetectionResult(self, data):
        """处理检测结果
        
        Args:
            data: 检测结果数据
                {
                    'channel_id': int,
                    'liquid_level': float,
                    'confidence': float,
                    'timestamp': str,
                    'status': str
                }
        """
        try:
            channel_id_num = data.get('channel_id', 1)
            channel_id = f"channel{channel_id_num}"
            
            liquid_level = data.get('liquid_level', 0)
            confidence = data.get('confidence', 0)
            timestamp = data.get('timestamp', '')

            # 更新通道面板显示
            panel = self._channel_panels_map.get(channel_id)
            if panel:
                # 更新液位数据到InfoOverlay
                # 这里可以扩展为显示液位线
                # 暂时只打印日志
                pass
            
        except Exception as e:
            self.logger.error(f"[检测结果] 处理异常: {e}")
            import traceback
            traceback.print_exc()
    
    @QtCore.Slot(bool, str)
    def _onWebSocketStatus(self, is_connected, message):
        """处理WebSocket连接状态变化
        
        Args:
            is_connected: 是否已连接
            message: 状态消息
        """
        try:
            if is_connected:
                self.logger.debug(f"[WebSocket] 连接成功: {message}")
                self.statusBar().showMessage(f"推理服务已连接")
            else:
                self.logger.debug(f"[WebSocket] 连接断开: {message}")
                self.statusBar().showMessage(f"推理服务未连接")
                
        except Exception as e:
            self.logger.debug(f"[WebSocket] 状态处理异常: {e}")
    
    def setDetectionEngine(self, channel_id, detection_engine):
        """
        为指定通道设置检测引擎
        
        Args:
            channel_id: 通道ID
            detection_engine: 检测引擎对象，需要有 detect(frame) 方法
                             返回格式：{'liquid_line_positions': {area_idx: position_data}}
        
        Returns:
            bool: 设置成功返回True
        """
        try:
            if not detection_engine:
                pass
                return False
            
            if not hasattr(detection_engine, 'detect'):
                pass
                return False
            
            self._detection_engines[channel_id] = detection_engine
            pass
            
            # 如果检测线程已在运行，重新启动以使用新引擎
            if channel_id in self._channel_detect_statuss and self._channel_detect_statuss[channel_id]:
                pass
            
            return True
            
        except Exception as e:
            pass
            return False
    
    def removeDetectionEngine(self, channel_id):
        """
        移除指定通道的检测引擎
        
        Args:
            channel_id: 通道ID
        
        Returns:
            bool: 移除成功返回True
        """
        try:
            if channel_id in self._detection_engines:
                del self._detection_engines[channel_id]
                pass
                return True
            else:
                pass
                return False
                
        except Exception as e:
            pass
            return False
    
    def getChannelDisplayName(self, channel_id, channel_number):
        """
        获取通道显示名称（业务逻辑）
        
        Args:
            channel_id: 通道ID，如 'channel1'
            channel_number: 通道编号，如 1, 2, 3, 4
            
        Returns:
            str: 显示名称，优先使用配置的 name，为空则使用 "通道X"
        """
        try:
            # 从配置读取该通道
            channel_config = self._config.get(channel_id, {})
            channel_name = channel_config.get('name', '').strip()
            
            # 如果 name 存在且不为空，使用 name；否则使用 "通道X"
            if channel_name:
                return channel_name
            else:
                return f"通道{channel_number}"
        except Exception as e:
            pass
            return f"通道{channel_number}"
    
    def onChannelNameChanged(self, channel_id, new_name):
        """
        处理通道名称更改（业务逻辑）
        
        Args:
            channel_id: 通道ID，如 'channel1'
            new_name: 新的通道名称
        """
        try:
            pass
            
            # 更新配置
            if channel_id in self._config:
                self._config[channel_id]['name'] = new_name
                pass
            else:
                pass
                return
            
            # 保存到配置文件
            success = self._saveChannelNameToConfig(channel_id, new_name)
            
            if success:
                self.statusBar().showMessage(
                    self.tr(" 通道名称已更新: {} -> {}").format(channel_id, new_name)
                )
            else:
                self.statusBar().showMessage(
                    self.tr(" 保存通道名称失败")
                )
                
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
    
    def _saveChannelNameToConfig(self, channel_id, new_name):
        """
        保存通道名称到服务端配置文件
        
        Args:
            channel_id: 通道ID
            new_name: 新名称
            
        Returns:
            bool: 保存是否成功
        """
        try:
            self.logger.debug(f"[DEBUG] 保存通道{channel_id}名称到服务端: {new_name}")
            
            # 获取当前配置
            current_config = {}
            try:
                current_config = self._remote_config_manager.load_channel_config()
            except Exception as e:
                self.logger.debug(f"[DEBUG] 加载当前配置失败，使用空配置: {e}")
                current_config = {}
            
            # 确保 channels 部分存在
            if 'channels' not in current_config:
                current_config['channels'] = {}
            
            # 提取通道编号
            channel_num = int(channel_id.replace('channel', '')) if 'channel' in channel_id else int(channel_id)
            
            # 更新通道名称
            if channel_num not in current_config['channels']:
                current_config['channels'][channel_num] = {
                    'channel_id': channel_num,
                    'name': new_name,
                    'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'  # 默认地址
                }
            else:
                current_config['channels'][channel_num]['name'] = new_name
            
            # 同时更新根级别的通道配置（兼容性）
            if channel_id not in current_config:
                current_config[channel_id] = {}
            current_config[channel_id]['name'] = new_name
            
            # 保存到服务端
            success = self._remote_config_manager.save_channel_config(current_config)
            
            if success:
                self.logger.debug(f"[DEBUG] 通道{channel_id}名称已成功保存到服务端")
                # 更新内存中的配置
                if hasattr(self, '_config'):
                    if self._config is None:
                        self._config = {}
                    if channel_id in self._config:
                        self._config[channel_id]['name'] = new_name
                return True
            else:
                self.logger.debug(f"[ERROR] 保存通道{channel_id}名称到服务端失败")
                return False
            
        except Exception as e:
            self.logger.debug(f"[ERROR] 保存通道{channel_id}名称异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def onChannelSelected(self, channel_data):
        """通道被选中"""
        channel_name = channel_data.get('name', '')
        self.statusBar().showMessage(self.tr("选中通道: {}").format(channel_name))
    
    def onChannelConnected(self, channel_id):
        """打开通道"""
        self.logger.debug(f"[DEBUG] onChannelConnected被调用: {channel_id}")
        self.statusBar().showMessage(self.tr("正在打开通道: {}").format(channel_id))
        
        # 找到发送信号的通道面板（映射已在初始化时建立）
        sender = self.sender()
        self.logger.debug(f"[DEBUG] sender: {sender}")
        
        # 关键修复：如果通道已经连接或正在连接，不要重复连接
        if channel_id in self._channel_captures:
            self.logger.debug(f"[DEBUG] {channel_id} 已经连接")
            return
        
        if channel_id in self._channels_connecting:
            self.logger.debug(f"[DEBUG] {channel_id} 正在连接中")
            return
        
        # 立即标记为正在连接（防止重复调用）
        self._channels_connecting.add(channel_id)
        self.logger.debug(f"[DEBUG] {channel_id} 标记为正在连接")
        
        # 映射已在 initializeChannelPanels 中建立，这里不需要再建立
        # 但为了兼容性，如果映射不存在则建立（某些特殊情况）
        if sender and hasattr(sender, 'displayFrame'):
            if channel_id not in self._channel_panels_map:
                self._channel_panels_map[channel_id] = sender
        
        # 从系统窗口读取通道配置（RTSP地址和本地视频文件）
        channel_config = {}

        # 获取通道编号
        channel_number = channel_id.replace('channel', '') if 'channel' in channel_id else '1'

        # 尝试从系统窗口获取RTSP地址和本地视频文件路径
        if hasattr(self, 'channelAddressInputs') and channel_number in self.channelAddressInputs:
            rtsp_address = self.channelAddressInputs[channel_number].text().strip()
            if rtsp_address and rtsp_address != 'username:password@ip:port/stream':
                channel_config['address'] = rtsp_address
                self.logger.debug(f"[DEBUG] 使用RTSP地址: {rtsp_address}")

        # 如果没有有效的RTSP地址，尝试使用本地视频文件
        if 'address' not in channel_config:
            if hasattr(self, 'channelVideoFileInputs') and channel_number in self.channelVideoFileInputs:
                video_file = self.channelVideoFileInputs[channel_number].text().strip()
                if video_file and video_file != '选择本地视频文件路径':
                    channel_config['address'] = video_file
                    self.logger.debug(f"[DEBUG] 使用本地视频文件: {video_file}")

        # 如果既没有RTSP地址也没有本地视频文件，无法连接
        if 'address' not in channel_config:
            self.logger.debug(f"[DEBUG] {channel_id} 没有配置RTSP地址或本地视频文件，无法连接")
            self._channels_connecting.discard(channel_id)
            return

        self.logger.debug(f"[DEBUG] 最终使用配置: {channel_config}")
        
        # 读取并设置通道名称到面板（调用业务逻辑方法）
        # 从 channel_id (如 'channel1') 提取通道编号
        channel_number = channel_id.replace('channel', '') if 'channel' in channel_id else '?'
        channel_name = f"通道{channel_number}"
        self.logger.debug(f"[DEBUG] 通道名称: {channel_name}")
        
        panel = self._channel_panels_map.get(channel_id)
        if panel and hasattr(panel, 'setChannelName'):
            panel.setChannelName(channel_name)
        
        # 关键修复：在主线程中预先获取面板引用
        # 不再需要HWND，使用Qt渲染模式
        panel = self._channel_panels_map.get(channel_id)
        if panel:
            self.logger.debug(f"[DEBUG] 主线程获取 {channel_id} 面板引用")

            # 设置面板为Qt渲染模式（不使用HWND）
            if hasattr(panel, 'setHwndRenderMode'):
                panel.setHwndRenderMode(False)
                self.logger.debug(f"[DEBUG] 主线程设置 {channel_id} Qt渲染模式")

        # 切换到视频监控页面
        self.showVideoPage()

        # 在后台线程中打开通道（避免阻塞UI）
        # 不再传递HWND参数
        thread = threading.Thread(
            target=self._connectChannelThread,
            args=(channel_id, channel_config, None),
            daemon=True
        )
        thread.start()
        self.logger.debug(f"[DEBUG] 后台线程已启动")
    
    def _loadTaskInfoToPanel(self, channel_id, panel):
        """
        从全局变量 current_mission 同步任务信息到通道面板
        
        🔥 关键修复：如果 current_mission 为空或为"None"，但面板上已有有效的任务信息，
        则保留面板上的任务信息，不重置为None（避免打开通道时覆盖用户已选中的任务）
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            panel: 通道面板实例
        """
        try:
            if not panel or not hasattr(panel, 'setTaskInfo'):
                return
            
            # 从全局变量 current_mission 读取任务路径
            current_mission_path = None
            if hasattr(self, 'current_mission'):
                current_mission_path = self.current_mission
            
            # 从路径中提取文件夹名称
            task_folder_name = self._extractTaskFolderName(current_mission_path)
            
            # 设置任务信息到面板
            if task_folder_name:
                # current_mission 中有任务路径，提取文件夹名称并显示
                mission_selected_channels = self._getMissionSelectedChannelIds(task_folder_name)
                if mission_selected_channels and channel_id not in mission_selected_channels:
                    if hasattr(panel, 'setTaskInfo'):
                        panel.setTaskInfo(None)
                    return
                
                panel.setTaskInfo(task_folder_name)
            else:
                # current_mission 中没有任务信息
                # 关键修复：检查面板上是否已有有效的任务信息
                if hasattr(panel, 'getTaskInfo'):
                    current_task_name = panel.getTaskInfo()
                    if current_task_name:
                        # 面板上已有有效的任务信息，保留它（不重置为None）
                        return
                
                # 面板上也没有任务信息，才设置为None
                panel.setTaskInfo(None)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _extractTaskFolderName(self, mission_path):
        """
        从任务路径中提取文件夹名称
        
        Args:
            mission_path: 任务文件夹完整路径，如 "D:\\...\\mission_result\\1_1" 或 "1_1"
        
        Returns:
            str: 文件夹名称（如 "1_1"），如果路径无效则返回None
        """
        if not mission_path or mission_path == "None" or mission_path.lower() == "none":
            return None
        
        try:
            import os
            # 如果是路径，提取最后一级文件夹名称
            if os.path.sep in str(mission_path) or '/' in str(mission_path):
                folder_name = os.path.basename(os.path.normpath(mission_path))
            else:
                # 如果已经是文件夹名称，直接返回
                folder_name = str(mission_path).strip()
            
            # 如果文件夹名称为空或为"None"，返回None
            if not folder_name or folder_name.lower() == "none":
                return None
            
            return folder_name
            
        except Exception as e:
            return None
    
    def syncTaskInfoToAllPanels(self):
        """
        同步任务信息到所有通道面板（从current_mission读取）
        
        当current_mission更新时，调用此方法同步所有通道面板的任务信息显示
        """
        try:
            if not hasattr(self, '_channel_panels_map'):
                return
            
            # 从current_mission提取文件夹名称
            current_mission_path = None
            if hasattr(self, 'current_mission'):
                current_mission_path = self.current_mission
            
            task_folder_name = self._extractTaskFolderName(current_mission_path)
            mission_selected_channels = self._getMissionSelectedChannelIds(task_folder_name) if task_folder_name else set()
            
            # 遍历所有通道面板，同步任务信息
            for channel_id, panel in self._channel_panels_map.items():
                if panel and hasattr(panel, 'setTaskInfo'):
                    if task_folder_name:
                        if mission_selected_channels:
                            if channel_id in mission_selected_channels:
                                panel.setTaskInfo(task_folder_name)
                            else:
                                panel.setTaskInfo(None)
                        else:
                            panel.setTaskInfo(task_folder_name)
                    else:
                        # 如果current_mission为空，检查面板上是否已有任务信息
                        if hasattr(panel, 'getTaskInfo'):
                            current_task_name = panel.getTaskInfo()
                            if not current_task_name:
                                # 面板上也没有任务信息，才设置为None
                                panel.setTaskInfo(None)
                        else:
                            panel.setTaskInfo(None)
                
                # 🔥 同步debug标签显示（显示完整的current_mission值）
                if panel and hasattr(panel, 'setCurrentMission'):
                    # print(f"[DEBUG] 同步debug标签到 {channel_id}: current_mission_path = {current_mission_path}")
                    panel.setCurrentMission(current_mission_path)
                            
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _getMissionSelectedChannelIds(self, task_folder_name):
        """
        根据任务配置文件获取需要同步的通道ID集合
        
        Args:
            task_folder_name: 任务文件夹名称（如 '1_1'）
        
        Returns:
            set: 需要同步的通道ID集合（如 {'channel1', 'channel2'}）
        """
        if not task_folder_name:
            return set()
        
        cache = getattr(self, '_mission_selected_channels_cache', None)
        if cache and cache.get('folder') == task_folder_name:
            return cache.get('channels', set())
        
        channel_ids = set()
        try:
            project_root = get_project_root()
            mission_config_dir = os.path.join(project_root, 'database', 'config', 'mission')
            mission_result_dir = os.path.join(project_root, 'database', 'mission_result', task_folder_name)
            
            candidate_files = [
                os.path.join(mission_config_dir, f"{task_folder_name}.yaml"),
                os.path.join(mission_result_dir, f"{task_folder_name}.yaml")
            ]
            
            for file_path in candidate_files:
                if not file_path or not os.path.exists(file_path):
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                selected_channels = config.get('selected_channels', [])
                if selected_channels:
                    for channel_key in selected_channels:
                        channel_id = self._normalizeMissionChannelKey(channel_key)
                        if channel_id:
                            channel_ids.add(channel_id)
                    break
        except Exception as e:
            pass
        
        self._mission_selected_channels_cache = {
            'folder': task_folder_name,
            'channels': channel_ids
        }
        return channel_ids

    @staticmethod
    def _normalizeMissionChannelKey(channel_key):
        """
        将任务配置中的通道标识转换为channelX格式
        """
        if channel_key is None:
            return None
        
        if isinstance(channel_key, int):
            return f"channel{channel_key}"
        
        channel_str = str(channel_key).strip()
        if not channel_str:
            return None
        
        if channel_str.startswith('channel') and channel_str[7:].isdigit():
            return channel_str
        
        # 支持新格式：'通道1', '通道2'（推荐）
        if channel_str.startswith('通道'):
            # 移除'通道'前缀，获取数字部分
            suffix = channel_str.replace('通道', '').strip()
            # 如果包含下划线（旧格式'通道_1'），去掉下划线
            suffix = suffix.replace('_', '').strip()
            if suffix.isdigit():
                return f"channel{suffix}"
        
        return None
    
    def _getChannelConfigFromFile(self, channel_id):
        """从服务端配置文件读取单个通道配置"""
        try:
            self.logger.debug(f"[DEBUG] 从服务端读取通道{channel_id}配置")
            
            # 使用远程配置管理器获取通道信息
            channel_info = self._remote_config_manager.get_channel_info(int(channel_id.replace('channel', '')))
            
            if channel_info:
                self.logger.debug(f"[DEBUG] 成功获取通道{channel_id}配置: {channel_info}")
                return channel_info
            
            # 如果没有找到，尝试从内存配置读取
            if hasattr(self, '_config') and self._config:
                config = self._config
                
                # 查找对应通道的配置（新格式：channel1, channel2, ...）
                channel_config = config.get(channel_id)
                
                if channel_config and isinstance(channel_config, dict):
                    self.logger.debug(f"[DEBUG] 从内存配置获取通道{channel_id}配置")
                    return channel_config
            
            self.logger.debug(f"[DEBUG] 未找到通道{channel_id}配置，返回None")
            return None
            
        except Exception as e:
            self.logger.debug(f"[ERROR] 读取通道{channel_id}配置失败: {e}")
            return None
    
    def loadAllChannelConfig(self):
        """
        从服务端配置文件加载所有通道配置
        
        Returns:
            dict: 通道配置数据，格式：
            {
                'channels': {
                    1: {'channel_id': 1, 'name': '前门通道', 'address': 'rtsp://...'},
                    2: {'channel_id': 2, 'name': '后门通道', 'address': 'rtsp://...'},
                    ...
                },
                'address_list': '前门通道: rtsp://...\n后门通道: rtsp://...'
            }
        """
        try:
            self.logger.debug("[DEBUG] 开始从服务端加载通道配置")
            
            # 使用远程配置管理器加载配置
            channel_config = self._remote_config_manager.load_channel_config()
            default_config = self._remote_config_manager.load_default_config()
            
            # 解析通道配置
            channels = {}
            address_list = []
            
            # 首先尝试从 channel_config.yaml 的 channels 部分读取
            if 'channels' in channel_config:
                config_channels = channel_config['channels']
                for channel_id, channel_data in config_channels.items():
                    if isinstance(channel_data, dict):
                        name = channel_data.get('name', f'通道{channel_id}')
                        address = channel_data.get('address', '')
                        
                        if address:  # 只有当地址非空时才添加
                            channels[int(channel_id)] = {
                                'channel_id': int(channel_id),
                                'name': name,
                                'address': address
                            }
                            address_list.append(f"{name}: {address}")
                            self.logger.debug(f"[DEBUG] 从channels配置加载通道{channel_id}: {name} -> {address}")
            
            # 如果 channels 部分没有数据，尝试从 default_config.yaml 读取
            if not channels and default_config:
                for i in range(1, 9):  # 支持8个通道
                    channel_key = f'channel{i}'
                    if channel_key in default_config:
                        channel_data = default_config[channel_key]
                        name = channel_data.get('name', f'通道{i}')
                        address = channel_data.get('address', '')
                        
                        if address:  # 只有当地址非空时才添加
                            channels[i] = {
                                'channel_id': i,
                                'name': name,
                                'address': address
                            }
                            address_list.append(f"{name}: {address}")
                            self.logger.debug(f"[DEBUG] 从default_config加载通道{i}: {name} -> {address}")
            
            # 如果还是没有数据，尝试从 channel_config.yaml 的根级别读取
            if not channels:
                for i in range(1, 9):  # 支持8个通道
                    channel_key = f'channel{i}'
                    if channel_key in channel_config:
                        channel_data = channel_config[channel_key]
                        if isinstance(channel_data, dict) and 'general' in channel_data:
                            # 这种格式需要从其他地方获取地址信息
                            name = f'通道{i}'
                            # 尝试从 channels 部分获取地址
                            if 'channels' in channel_config and i in channel_config['channels']:
                                address = channel_config['channels'][i].get('address', '')
                                name = channel_config['channels'][i].get('name', name)
                            else:
                                address = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'  # 默认地址
                            
                            channels[i] = {
                                'channel_id': i,
                                'name': name,
                                'address': address
                            }
                            address_list.append(f"{name}: {address}")
                            self.logger.debug(f"[DEBUG] 从channel配置加载通道{i}: {name} -> {address}")
            
            # 获取地址列表（如果配置中有的话）
            config_address_list = channel_config.get('address_list', '') or default_config.get('address_list', '')
            if config_address_list:
                address_list_str = config_address_list
            else:
                address_list_str = '\n'.join(address_list)
            
            self.logger.debug(f"[DEBUG] 成功加载{len(channels)}个通道配置")
            
            # 更新内存中的配置
            self._config = {**default_config, **channel_config}
            
            return {
                'channels': channels,
                'address_list': address_list_str
            }
        
        except Exception as e:
            self.logger.debug(f"[ERROR] 加载远程通道配置失败: {e}")
            # 返回备用配置
            return {
                'channels': {
                    1: {'channel_id': 1, 'name': '通道1', 'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'},
                    2: {'channel_id': 2, 'name': '通道2', 'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'},
                    3: {'channel_id': 3, 'name': '通道3', 'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'},
                    4: {'channel_id': 4, 'name': '通道4', 'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'}
                },
                'address_list': '通道1: rtsp://admin:cei345678@192.168.0.27:8000/stream1\n通道2: rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            }
    
    def saveChannelConfig(self, channel_data):
        """
        保存通道配置到服务端
        
        Args:
            channel_data: 通道数据字典，格式：
            {
                'channels': {
                    1: {'channel_id': 1, 'name': '...', 'address': '...'},
                    ...
                },
                'address_list': '...'
            }
        
        Returns:
            bool: 保存是否成功
        """
        try:
            self.logger.debug(f"[DEBUG] 开始保存通道配置到服务端: {channel_data}")
            
            # 获取当前完整配置
            current_config = {}
            
            # 先尝试加载当前的配置
            try:
                current_config = self._remote_config_manager.load_channel_config()
            except Exception as e:
                self.logger.debug(f"[DEBUG] 加载当前配置失败，使用空配置: {e}")
                current_config = {}
            
            channels = channel_data.get('channels', {})
            address_list = channel_data.get('address_list', '')
            
            # 确保 channels 部分存在
            if 'channels' not in current_config:
                current_config['channels'] = {}
            
            # 更新通道配置
            for i in range(1, 9):  # 支持8个通道
                channel_key = f'channel{i}'
                if i in channels:
                    # 更新已有通道
                    current_config['channels'][i] = {
                        'channel_id': i,
                        'name': channels[i]['name'],
                        'address': channels[i]['address']
                    }
                    
                    # 同时更新根级别的通道配置（兼容性）
                    if channel_key not in current_config:
                        current_config[channel_key] = {}
                    current_config[channel_key]['name'] = channels[i]['name']
                    current_config[channel_key]['address'] = channels[i]['address']
                else:
                    # 保持未配置通道的现有配置
                    if i not in current_config['channels']:
                        current_config['channels'][i] = {
                            'channel_id': i,
                            'name': f'通道{i}',
                            'address': ''
                        }
            
            # 更新地址列表
            current_config['address_list'] = address_list
            
            # 保存到服务端
            success = self._remote_config_manager.save_channel_config(current_config)
            
            if success:
                self.logger.debug("[DEBUG] 通道配置已成功保存到服务端")
                # 更新内存中的配置
                self._config = current_config
                return True
            else:
                self.logger.debug("[ERROR] 保存通道配置到服务端失败")
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("保存失败"),
                    self.tr("保存通道配置到服务端失败")
                )
                return False
        
        except Exception as e:
            self.logger.debug(f"[ERROR] 保存通道配置异常: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("保存失败"),
                self.tr(f"保存通道配置失败: {str(e)}")
            )
            return False
    
    def _connectChannelThread(self, channel_id, channel_config, hwnd=None):
        """在后台线程中打开通道（直接连接RTSP相机）

        Args:
            channel_id: 通道ID
            channel_config: 通道配置
            hwnd: 窗口句柄（已废弃，不再使用）
        """
        try:
            self.logger.debug(f"[通道连接] {channel_id} 开始连接RTSP相机")

            # 解析RTSP地址
            rtsp_url = channel_config.get('address', '')
            username, password, ip, port = self._parseRTSP(rtsp_url)

            self.logger.debug(f"[通道连接] RTSP解析结果: {ip}:{port}, 用户: {username}")

            # 导入HKcapture
            import sys
            import os
            from pathlib import Path

            # 添加HK_SDK路径
            current_dir = Path(__file__).parent
            hk_sdk_path = current_dir / "HK_SDK"
            sys.path.insert(0, str(hk_sdk_path))

            from HKcapture import HKcapture

            # 创建HKcapture对象（不再设置HWND）
            cap = HKcapture(
                source=rtsp_url,
                username=username,
                password=password,
                port=port,
                channel=1,
                fps=25,
                debug=True
            )

            # 不再设置HWND，使用纯CPU解码模式
            self.logger.debug(f"[通道连接] 使用纯CPU解码模式（无渲染）")

            # 打开相机连接
            if not cap.open():
                raise Exception("无法打开相机连接")

            self.logger.debug(f"[通道连接] {channel_id} 相机连接成功")
            
            # 开始捕获
            if not cap.start_capture():
                raise Exception("无法开始视频捕获")
            
            self.logger.debug(f"[通道连接] {channel_id} 视频捕获已启动")
            
            # 保存捕获对象
            self._channel_captures[channel_id] = cap
            
            # 移除连接中标记
            self._channels_connecting.discard(channel_id)
            
            # 启动视频显示
            self._startVideoStream(channel_id, hwnd)
            
            # 更新UI状态（在主线程中执行）
            QtCore.QTimer.singleShot(0, lambda: self._updateChannelConnectedUI(channel_id))
            
            self.logger.debug(f"[通道连接] {channel_id} 连接完成")
            
        except Exception as e:
            self.logger.debug(f"[通道连接] {channel_id} 连接失败: {e}")
            import traceback
            traceback.print_exc()
            self._channels_connecting.discard(channel_id)
            QtCore.QTimer.singleShot(0, lambda: self._showConnectionError(channel_id, str(e)))
    
    def _parseRTSP(self, rtsp_url):
        """
        解析RTSP URL
        
        Returns:
            tuple: (username, password, ip)
        """
        try:
            # RTSP格式: rtsp://[username:password@]ip:port/path
            # 或者纯IP地址
            
            # 检查是否为纯IP
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if re.match(ip_pattern, rtsp_url):
                return None, None, rtsp_url, 8000
            
            # 检查是否为USB设备（如 "0"）
            if rtsp_url.isdigit():
                return None, None, None, 8000
            
            # 解析完整RTSP URL（支持密码中包含@符号）
            if rtsp_url.startswith('rtsp://'):
                url_part = rtsp_url[7:]  # 去掉 "rtsp://"

                
                # 找到最后一个 @ 符号（IP地址前的那个）
                last_at_index = url_part.rfind('@')

                
                if last_at_index != -1:
                    # 有认证信息
                    credentials_part = url_part[:last_at_index]
                    host_part = url_part[last_at_index + 1:]

                    
                    # 分离用户名和密码（第一个:分隔）
                    first_colon = credentials_part.find(':')

                    
                    if first_colon != -1:
                        username = credentials_part[:first_colon]
                        password = credentials_part[first_colon + 1:]

                        # URL解码密码
                        from urllib.parse import unquote
                        password = unquote(password)

                    else:
                        username = credentials_part
                        password = None
                else:
                    # 没有认证信息
                    username = None
                    password = None
                    host_part = url_part
                
                # 提取IP和端口
                colon_idx = host_part.find(':')
                slash_idx = host_part.find('/')
                
                if colon_idx != -1:
                    ip = host_part[:colon_idx]
                    # 提取端口
                    if slash_idx != -1:
                        port_str = host_part[colon_idx + 1:slash_idx]
                    else:
                        port_str = host_part[colon_idx + 1:]
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 8000
                else:
                    if slash_idx != -1:
                        ip = host_part[:slash_idx]
                    else:
                        ip = host_part
                    port = 8000
                

                
                return username, password, ip, port
            
            return None, None, None, 8000
            
        except Exception as e:
            return None, None, None, 8000
    
    def _updateChannelConnectedUI(self, channel_id):
        """更新通道连接UI状态（在主线程中执行）"""
        try:
            panel = self._channel_panels_map.get(channel_id)
            if panel:
                # 隐藏"未打开通道"提示
                if hasattr(panel, '_overlayLabel'):
                    panel._overlayLabel.hide()

                # 更新面板状态
                if hasattr(panel, 'setConnected'):
                    panel.setConnected(True)

            # 更新状态栏
            self.statusBar().showMessage(f"通道 {channel_id} 已连接")

            self.logger.debug(f"[UI更新] {channel_id} 连接状态已更新")

            # 如果预览窗口当前没有显示任何通道，自动切换到刚打开的通道
            if hasattr(self, '_current_preview_channel_id') and self._current_preview_channel_id is None:
                self.logger.debug(f"[UI更新] 预览窗口为空，自动切换到 {channel_id}")
                # 延迟100ms执行切换，确保视频流已经稳定
                QtCore.QTimer.singleShot(100, lambda: self._onSmallPanelClicked(channel_id))

        except Exception as e:
            self.logger.debug(f"[UI更新] {channel_id} 更新失败: {e}")

        try:
            # 更新通道面板状态
            panel = self._channel_panels_map.get(channel_id)
            if panel:
                panel.updateChannelStatus(channel_id, 'connected')
                panel.setConnected(True)

            self.statusBar().showMessage(
                self.tr(" 通道已连接: {} - 视频流已启动").format(channel_id)
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    
    
    def _showConnectionError(self, channel_id, error_msg):
        """显示连接错误（线程安全）- 使用 QTimer.singleShot"""
        # 使用 lambda 捕获参数值
        QtCore.QTimer.singleShot(0, lambda: self._showConnectionErrorUI(channel_id, error_msg))
    
    def _showConnectionErrorUI(self, channel_id, error_msg):
        """在主线程中显示连接错误"""
        try:
            QtWidgets.QMessageBox.critical(
                self,
                self.tr("连接失败"),
                self.tr("通道 {} 连接失败:\n{}").format(channel_id, error_msg)
            )
            self.statusBar().showMessage(
                self.tr(" 通道连接失败: {}").format(channel_id)
            )
        except Exception as e:
            pass
    
    def onChannelDisconnected(self, channel_id):
        """断开通道"""
        self.statusBar().showMessage(self.tr("正在断开通道: {}").format(channel_id))
        
        try:
            # 停止帧存储线程（已禁用）
            # if hasattr(self, '_storage_flags'):
            #     self._storage_flags[channel_id] = False
            
            # 停止显示线程
            if hasattr(self, '_display_flags'):
                self._display_flags[channel_id] = False
            
            # 释放捕获对象
            if channel_id in self._channel_captures:
                cap = self._channel_captures[channel_id]
                if cap and hasattr(cap, 'stop_capture'):
                    cap.stop_capture()
                if cap and hasattr(cap, 'release'):
                    cap.release()
                del self._channel_captures[channel_id]
                self.logger.debug(f"[通道断开] {channel_id} 捕获对象已释放")
            
            # 清理帧缓冲
            if hasattr(self, '_frame_buffers') and channel_id in self._frame_buffers:
                del self._frame_buffers[channel_id]
            
            # 清理thread_manager上下文
            if hasattr(self, 'thread_manager') and self.thread_manager:
                self.thread_manager.remove_channel_context(channel_id)
            
            # 更新面板UI
            panel = self._channel_panels_map.get(channel_id)
            if panel:
                # 显示"未打开通道"提示
                if hasattr(panel, '_overlayLabel'):
                    panel._overlayLabel.show()
                    panel._overlayLabel.setText("未打开通道")

                # 更新面板状态
                if hasattr(panel, 'setConnected'):
                    panel.setConnected(False)

                # 清空显示
                if hasattr(panel, 'clearDisplay'):
                    panel.clearDisplay()

                # 更新通道状态
                if hasattr(panel, 'updateChannelStatus'):
                    panel.updateChannelStatus(channel_id, 'disconnected')

            # 如果断开的是当前预览窗口显示的通道，需要处理预览窗口
            if hasattr(self, '_current_preview_channel_id') and self._current_preview_channel_id == channel_id:
                self.logger.debug(f"[通道断开] 当前预览通道 {channel_id} 已断开，尝试切换到其他通道")
                # 清空当前预览通道标记
                self._current_preview_channel_id = None

                # 尝试切换到其他已连接的通道
                if hasattr(self, '_channel_captures') and self._channel_captures:
                    # 找到第一个已连接的通道
                    for other_channel_id in self._channel_captures.keys():
                        if other_channel_id != channel_id:
                            self.logger.debug(f"[通道断开] 切换预览窗口到 {other_channel_id}")
                            QtCore.QTimer.singleShot(100, lambda cid=other_channel_id: self._onSmallPanelClicked(cid))
                            break
                else:
                    # 没有其他通道，清空预览窗口
                    if hasattr(self, 'previewPanel'):
                        self.previewPanel.clearDisplay()
                        self.previewPanel.setConnected(False)
                        self.logger.debug(f"[通道断开] 预览窗口已清空")

            self.statusBar().showMessage(f"通道 {channel_id} 已断开")
            
        except Exception as e:
            self.logger.debug(f"[通道断开] {channel_id} 断开异常: {e}")
            import traceback
            traceback.print_exc()
        
        # 清理连接中标记
        self._channels_connecting.discard(channel_id)
    
    def onChannelManage(self):
        """
        处理通道管理对话框
        
        1. 从配置文件加载当前配置
        2. 打开对话框让用户编辑
        3. 保存更新后的配置到文件
        """
        from widgets.videopage.rtsp_dialogue import RtspDialog
        
        # 从配置文件加载当前通道配置
        channel_data = self.loadAllChannelConfig()
        
        # 打开通道管理对话框
        dialog = RtspDialog(self, channel_data)
        mission_result = dialog.exec_()
        
        if mission_result == QtWidgets.QDialog.Accepted:
            # 获取用户编辑后的数据
            new_channel_data = dialog.getChannelData()
            
            # 保存到配置文件
            if self.saveChannelConfig(new_channel_data):
                self.statusBar().showMessage(
                    self.tr(" 通道配置已保存")
                )
                
                # 打印配置详情（可选）
                channels = new_channel_data.get('channels', {})
                for ch_id, ch_data in channels.items():
                    pass
            else:
                self.statusBar().showMessage(
                    self.tr(" 通道配置保存失败")
                )
        else:
            pass
            self.statusBar().showMessage(self.tr("通道管理已取消"))
    
    def onChannelAdded(self, channel_data):
        """添加新通道"""
        from widgets.videopage.rtsp_dialogue import RtspDialog
        
        # 打开RTSP配置对话框
        dialog = RtspDialog(self)
        if dialog.exec_():
            channel_data = dialog.getChannelData()
            
            # 生成通道ID
            import uuid
            channel_id = str(uuid.uuid4())[:8]
            
            # 添加到通道面板
            channel_data['status'] = 'disconnected'
            self.channelPanel.addChannel(channel_id, channel_data)
            
            self.statusBar().showMessage(
                self.tr("已添加通道: {}").format(channel_data['name'])
            )
    
    def onChannelRemoved(self, channel_id):
        """通道被移除"""
        # 如果通道正在运行任务，先停止任务
        running_missions = self._getMissionsUsingChannel(channel_id)
        if running_missions:
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tr("确认删除"),
                self.tr("该通道正在被 {} 个任务使用，确定删除吗？").format(len(running_missions)),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
        
        self.statusBar().showMessage(self.tr("通道已移除: {}").format(channel_id))
    
    def _handleRefreshModelListForDialog(self, panel):
        """处理对话框中的刷新模型列表请求"""
        pass
        
        # 获取嵌入的模型设置widget
        if hasattr(panel, 'model_setting_widget'):
            model_widget = panel.model_setting_widget
            
            # 调用模型设置handler的刷新方法（混入自 ModelSettingHandler）
            if hasattr(self, '_handleRefreshModelList'):
                pass
                self._handleRefreshModelList(model_widget)
            else:
                pass
                pass
        else:
            pass
    
    def onChannelEdited(self, channel_id, channel_data):
        """通道设置 - 打开常规设置对话框"""
        # 获取通道名称和任务信息
        channel_name = channel_data.get('name', channel_id)
        task_info = {
            'task_id': channel_data.get('task_id', ''),
            'task_name': channel_data.get('task_name', ''),
        }
        
        # 🔥 打开对话框前隐藏所有通道的 InfoOverlay（避免遮挡设置界面）
        self._hideAllChannelOverlays()
        
        try:
            # 使用 showGeneralSetDialog 方法打开对话框（包含自动加载配置和信号连接的逻辑）
            dialog = self.showGeneralSetDialog(
                channel_name=channel_name,
                channel_id=channel_id,  # 传递通道ID
                task_info=task_info
            )
            
            # showGeneralSetDialog 内部已经完成了信号连接和配置加载
            pass
            
            #  刷新模型列表（确保初始加载时能看到模型列表）
            panel = dialog.getPanel()
            if panel and hasattr(panel, 'model_setting_widget'):
                QtCore.QTimer.singleShot(100, lambda: self._handleRefreshModelListForDialog(panel))
            
            # 如果有现有配置，加载到对话框
            if hasattr(self, '_loadChannelSettings'):
                settings = self._loadChannelSettings(channel_id)
                if settings:
                    dialog.setSettings(settings)
            
            mission_result = dialog.exec_()
            
            if mission_result == QtWidgets.QDialog.Accepted:
                # 获取用户设置的配置
                settings = dialog.getSettings()
                
                # 保存配置
                if hasattr(self, '_saveChannelSettings'):
                    self._saveChannelSettings(channel_id, settings)
                
                self.statusBar().showMessage(
                    self.tr(" {} 设置已保存").format(channel_name)
                )
                
                pass
            else:
                pass
                self.statusBar().showMessage(self.tr("设置已取消"))
        
        finally:
            # 🔥 对话框关闭后恢复显示所有通道的 InfoOverlay
            self._showAllChannelOverlays()
    
    def _getMissionsUsingChannel(self, channel_id):
        """获取使用指定通道的任务列表"""
        missions = []
        # TODO: 实现从missionPanel获取使用该通道的任务
        return missions
    
    def _hideAllChannelOverlays(self):
        """隐藏所有通道的 InfoOverlay（打开对话框前调用）"""
        try:
            if hasattr(self, '_channel_panels_map'):
                for channel_id, panel in self._channel_panels_map.items():
                    if panel and hasattr(panel, 'hideOverlay'):
                        panel.hideOverlay()
        except Exception as e:
            self.logger.debug(f"[WARNING] 隐藏 overlay 失败: {e}")
    
    def _showAllChannelOverlays(self):
        """显示所有通道的 InfoOverlay（对话框关闭后调用）"""
        try:
            if hasattr(self, '_channel_panels_map'):
                for channel_id, panel in self._channel_panels_map.items():
                    if panel and hasattr(panel, 'showOverlay'):
                        # 只显示已连接通道的 overlay
                        if hasattr(panel, '_is_connected') and panel._is_connected:
                            panel.showOverlay()
        except Exception as e:
            self.logger.debug(f"[WARNING] 显示 overlay 失败: {e}")
    
    def _loadChannelSettings(self, channel_id):
        """
        加载通道设置（从 channel_config.yaml）
        
        Args:
            channel_id: 通道ID（如 'channel1'）
        
        Returns:
            dict: 通道设置字典，如果没有返回None
        """
        try:
            import os
            import yaml
            
            #  使用项目根目录的动态路径
            # 从当前文件向上2级：handlers/videopage/ -> handlers/ -> 项目根
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            
            # channel_config.yaml 路径
            config_file = os.path.join(project_root, 'database', 'config', 'channel_config.yaml')
            
            if not os.path.exists(config_file):
                return None
            
            # 加载配置
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            # 获取该通道的配置
            if channel_key not in config:
                return None

            channel_settings = config[channel_key]
            return channel_settings
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _saveChannelSettings(self, channel_id, settings):
        """
        保存通道设置（到 channel_config.yaml）
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            settings: 设置字典，格式：{'general': {...}, 'model': {...}, 'logic': {...}}
        
        Returns:
            bool: 保存是否成功
        """
        try:
            import os
            import yaml
            
            #  使用项目根目录的动态路径
            # 从当前文件向上2级：handlers/videopage/ -> handlers/ -> 项目根
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            
            # channel_config.yaml 路径
            config_file = os.path.join(project_root, 'database', 'config', 'channel_config.yaml')
            
            # 读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # 更新该通道的配置
            config[channel_id] = settings
            
            # 保存回配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("保存失败"),
                self.tr("保存通道配置失败: {}").format(str(e))
            )
            return False
    
    def _startVideoStream(self, channel_id, hwnd=None):
        """启动视频流显示（使用Qt渲染模式）

        Args:
            channel_id: 通道ID
            hwnd: 窗口句柄（已废弃，不再使用）
        """
        self.logger.debug(f"[视频流] {channel_id} 开始启动视频显示（Qt渲染模式）")

        if channel_id not in self._channel_captures:
            self.logger.debug(f"[视频流] {channel_id} 不在 _channel_captures 中")
            return

        cap = self._channel_captures[channel_id]
        self.logger.debug(f"[视频流] 获取到 capture 对象: {cap}")

        # 启动Qt显示线程
        self._startQtVideoDisplay(channel_id)
    
    def _startFrameStorageThread(self, channel_id):
        """启动帧数据存储线程（供标注功能使用）
        
        Args:
            channel_id: 通道ID
        """
        try:
            # 初始化thread_manager上下文（如果还没有）
            if hasattr(self, 'thread_manager') and self.thread_manager:
                context = self.thread_manager.get_channel_context(channel_id)
                if not context:
                    # 创建通道上下文
                    context = self.thread_manager.create_channel_context(channel_id)
                    self.logger.debug(f"[帧存储] {channel_id} 创建了新的通道上下文")
                else:
                    self.logger.debug(f"[帧存储] {channel_id} 使用现有通道上下文")
            
            # 创建帧缓冲队列（兼容旧代码）
            if not hasattr(self, '_frame_buffers'):
                self._frame_buffers = {}
            if not hasattr(self, '_storage_flags'):
                self._storage_flags = {}
                
            self._frame_buffers[channel_id] = queue.Queue(maxsize=10)
            
            # 启动帧存储线程
            self._storage_flags[channel_id] = True
            storage_thread = threading.Thread(
                target=self._frameStorageLoop,
                args=(channel_id,),
                daemon=True
            )
            storage_thread.start()
            
            self.logger.debug(f"[帧存储] {channel_id} 帧存储线程已启动")
            
        except Exception as e:
            self.logger.debug(f"[帧存储] {channel_id} 帧存储线程启动失败: {e}")
    
    def _frameStorageLoop(self, channel_id):
        """帧存储循环线程（专门为标注功能提供帧数据）
        
        Args:
            channel_id: 通道ID
        """
        self.logger.debug(f"[帧存储] {channel_id} 开始运行")
        
        frame_count = 0
        last_frame_time = time.time()
        
        while self._storage_flags.get(channel_id, False):
            try:
                cap = self._channel_captures.get(channel_id)
                if not cap:
                    time.sleep(0.1)
                    continue
                
                # 读取最新帧
                frame = None
                if hasattr(cap, 'read_latest'):
                    ret, frame = cap.read_latest()
                    if not ret:
                        frame = None
                elif hasattr(cap, 'get_frame'):
                    frame = cap.get_frame()
                elif hasattr(cap, 'read'):
                    ret, frame = cap.read()
                    if not ret:
                        frame = None
                
                if frame is not None:
                    frame_count += 1
                    current_time = time.time()
                    
                    # 每5秒统计一次帧率
                    if current_time - last_frame_time >= 5.0:
                        fps = frame_count / (current_time - last_frame_time)
                        self.logger.debug(f"[帧存储] {channel_id} 存储帧率: {fps:.1f} fps")
                        frame_count = 0
                        last_frame_time = current_time
                    
                    # 存储到thread_manager上下文
                    if hasattr(self, 'thread_manager') and self.thread_manager:
                        context = self.thread_manager.get_channel_context(channel_id)
                        if context and hasattr(context, 'frame_lock'):
                            with context.frame_lock:
                                context.latest_frame = frame.copy()
                    
                    # 存储到frame_buffer（兼容旧代码）
                    buffer = self._frame_buffers.get(channel_id)
                    if buffer:
                        try:
                            # 如果队列满了，丢弃最旧的帧
                            if buffer.full():
                                try:
                                    buffer.get_nowait()
                                except queue.Empty:
                                    pass
                            buffer.put_nowait(frame.copy())
                        except queue.Full:
                            pass
                    
                    # 控制存储频率（10fps，减少CPU占用）
                    time.sleep(0.1)
                else:
                    # 没有新帧，短暂等待
                    time.sleep(0.05)
                    
            except Exception as e:
                self.logger.debug(f"[帧存储] {channel_id} 异常: {e}")
                time.sleep(0.1)
        
        self.logger.debug(f"[帧存储] {channel_id} 已停止")
    
    def _startQtVideoDisplay(self, channel_id):
        """启动Qt视频显示线程
        
        Args:
            channel_id: 通道ID
        """
        try:
            # 创建帧缓冲队列
            if not hasattr(self, '_frame_buffers'):
                self._frame_buffers = {}
            if not hasattr(self, '_display_flags'):
                self._display_flags = {}
                
            self._frame_buffers[channel_id] = queue.Queue(maxsize=10)
            
            # 启动显示线程
            self._display_flags[channel_id] = True
            display_thread = threading.Thread(
                target=self._qtDisplayLoop,
                args=(channel_id,),
                daemon=True
            )
            display_thread.start()
            
            self.logger.debug(f"[视频流] {channel_id} Qt显示线程已启动")
            
        except Exception as e:
            self.logger.debug(f"[视频流] {channel_id} Qt显示线程启动失败: {e}")
    
    def _qtDisplayLoop(self, channel_id):
        """Qt视频显示循环线程
        
        Args:
            channel_id: 通道ID
        """
        self.logger.debug(f"[Qt显示] {channel_id} 开始运行")
        
        frame_count = 0
        last_frame_time = time.time()
        
        while self._display_flags.get(channel_id, False):
            try:
                cap = self._channel_captures.get(channel_id)
                if not cap:
                    time.sleep(0.1)
                    continue
                
                # 读取最新帧
                ret, frame = cap.read_latest()
                
                if ret and frame is not None:
                    frame_count += 1
                    current_time = time.time()
                    
                    # 每秒统计一次帧率
                    if current_time - last_frame_time >= 1.0:
                        fps = frame_count / (current_time - last_frame_time)
                        self.logger.debug(f"[Qt显示] {channel_id} 帧率: {fps:.1f} fps")
                        frame_count = 0
                        last_frame_time = current_time
                    
                    # 更新视频显示
                    self._updateVideoDisplay(channel_id, frame)
                    
                    # 控制帧率（25fps）
                    time.sleep(0.04)
                else:
                    # 没有新帧，短暂等待
                    time.sleep(0.01)
                    
            except Exception as e:
                self.logger.debug(f"[Qt显示] {channel_id} 异常: {e}")
                time.sleep(0.1)
        
        self.logger.debug(f"[Qt显示] {channel_id} 已停止")
        
                

    
    def _handleDetectionmission_result(self, channel_id, mission_result):
        """处理检测结果回调"""
        try:
            # 检测结果已经通过 liquid_line_positions 传递给显示线程
            # 这里可以添加额外的处理逻辑，比如记录日志、触发报警等
            if mission_result and mission_result.get('success'):
                liquid_positions = mission_result.get('liquid_line_positions', {})
                pass
        except Exception as e:
            pass
    
    @staticmethod
    def handleDetectionmission_result(mission_result):
        """处理检测结果回调（静态方法，保留兼容性）"""
        # 这里可以处理检测结果，比如更新液位线位置等
        pass
    
    def _handleThreadError(self, channel_id, error):
        """处理线程错误回调"""
        # 这里可以处理错误，比如显示错误信息、重连等
        pass
    
    def _stopVideoStream(self, channel_id):
        """停止视频流（使用新的线程管理器）"""
        pass
        
        try:
            # 使用新的线程管理器停止通道线程
            success = self.thread_manager.stop_channel_threads(channel_id)
            
            if success:
                pass
            else:
                pass
                
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
    
    def _captureLoop(self, channel_id, cap):
        """
        捕获线程循环 - 只负责从通道抓取画面到缓存池
        
        策略：快速轮询 + 基于配置帧率的智能等待
        - 海康SDK通过回调按通道帧率接收帧
        - cap.read() 是非阻塞的，返回最新可用帧
        - 使用基于配置帧率的轮询间隔，避免CPU空转
        
        Args:
            channel_id: 通道ID
            cap: HKcapture对象
        """
        pass
        pass
        
        # 根据配置的帧率计算轮询间隔（帧间隔的1/4，确保不丢帧）
        frame_interval = 1.0 / self._capture_fps if self._capture_fps > 0 else 0.04
        poll_interval = frame_interval / 4.0  # 轮询频率是帧率的4倍
        
        pass
        frame_count = 0
        
        while self._capture_flags.get(channel_id, False):
            try:
                # 从通道读取最新帧（对于海康威视，会清空内部队列只取最新帧）
                # 注意：SDK会按照通道配置的帧率自动返回帧
                ret, frame = cap.read_latest()
                
                if ret and frame is not None:
                    frame_count += 1
                    
                    # 将帧放入缓存池（非阻塞）
                    try:
                        buffer = self._frame_buffers.get(channel_id)
                        if buffer:
                            # 如果队列满了，丢弃最旧的帧
                            if buffer.full():
                                try:
                                    buffer.get_nowait()  # 丢弃旧帧
                                except queue.Empty:
                                    pass
                            
                            # 放入新帧
                            buffer.put_nowait(frame.copy())
                            
                            # 每100帧打印一次统计
                            if frame_count % 100 == 0:
                                pass
                    except queue.Full:
                        # 队列满，跳过这一帧
                        pass
                else:
                    # 没有新帧，使用基于配置帧率的轮询间隔等待
                    # 避免CPU空转，同时保持对新帧的响应性
                    time.sleep(poll_interval)
                    
            except Exception as e:
                pass
                # 只在异常时暂停，避免错误循环
                time.sleep(0.1)
        
        pass
    
    def _displayLoop(self, channel_id):
        """
        显示线程循环 - 从frame_buffer读取画面进行显示
        
        Args:
            channel_id: 通道ID
        """
        display_count = 0
        
        # 计算帧间隔（根据配置的显示帧率）
        frame_interval = 1.0 / self._display_fps if self._display_fps > 0 else 0.033
        
        last_display_time = time.time()
        
        while self._display_flags.get(channel_id, False):
            try:
                buffer = self._frame_buffers.get(channel_id)
                if not buffer:
                    time.sleep(0.01)
                    continue
                
                # 从缓存池获取帧（只取最新帧，丢弃中间的旧帧）
                try:
                    # 清空队列，只保留最新帧
                    frame = None
                    frames_skipped = 0
                    while not buffer.empty():
                        try:
                            frame = buffer.get_nowait()
                            if frame is not None:
                                frames_skipped += 1
                        except queue.Empty:
                            break
                    
                    # 如果队列为空，等待新帧
                    if frame is None:
                        frame = buffer.get(timeout=0.1)
                    
                    display_count += 1
                    
                    # 获取液位线位置数据并绘制（如果检测线程有输出）
                    liquid_positions = self._getLiquidLinePositions(channel_id)
                    if liquid_positions:
                        frame = self._drawLiquidLines(frame, liquid_positions)
                    
                    # 使用Qt信号线程安全地更新UI
                    self._updateVideoDisplay(channel_id, frame)
                    
                    # 控制显示帧率（使用配置的帧率）
                    current_time = time.time()
                    elapsed = current_time - last_display_time
                    sleep_time = frame_interval - elapsed
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                    last_display_time = time.time()
                    
                except queue.Empty:
                    # 缓存池为空，等待新帧
                    continue
                    
            except Exception as e:
                time.sleep(0.1)
    
    def _detectionLoop(self, channel_id):
        """
        检测线程循环 - 从frame_buffer读取帧并执行液位检测
        
        职责：
        1. 从frame_buffer复制读取原始帧
        2. 使用检测引擎进行液位检测推理
        3. 输出液位线位置数据
        4. 供显示线程绘制液位线
        
        Args:
            channel_id: 通道ID
        """
        print(f" 检测线程启动: {channel_id}")
        print(f"   检测帧率: {self._detection_fps} fps")
        
        # 根据配置的检测帧率计算间隔
        detection_interval = 1.0 / self._detection_fps if self._detection_fps > 0 else 0.1
        print(f"   检测间隔: {detection_interval:.4f}s")
        
        frame_count = 0
        detection_count = 0
        success_count = 0
        fail_count = 0
        
        # 等待检测引擎就绪（最多等待10秒）
        max_wait = 10
        wait_count = 0
        while wait_count < max_wait * 10:
            if channel_id in self._detection_engines:
                detection_engine = self._detection_engines[channel_id]
                if detection_engine and hasattr(detection_engine, 'detect'):
                    print(f" {channel_id} 检测引擎已就绪")
                    break
            time.sleep(0.1)
            wait_count += 1
        else:
            print(f" {channel_id} 检测引擎未就绪，检测线程将只读取帧不执行检测")
        
        while self._channel_detect_statuss.get(channel_id, False):
            try:
                loop_start_time = time.time()
                
                # 从frame_buffer获取帧副本（只读复制）
                buffer = self._frame_buffers.get(channel_id)
                if not buffer:
                    time.sleep(0.1)
                    continue
                
                try:
                    # 非阻塞获取，避免检测线程等待
                    frame = buffer.get(timeout=0.05)
                except queue.Empty:
                    # 缓存池为空，继续下一次循环
                    time.sleep(detection_interval / 2)
                    continue
                
                frame_count += 1
                
                # 执行检测（如果检测引擎可用）
                if channel_id in self._detection_engines:
                    detection_engine = self._detection_engines[channel_id]
                    
                    try:
                        # 调用检测引擎的detect方法（传入channel_id用于多通道状态隔离）
                        detection_mission_result = detection_engine.detect(frame.copy(), channel_id=channel_id)
                        
                        # 处理检测结果
                        if detection_mission_result and 'liquid_line_positions' in detection_mission_result:
                            # 存储液位线位置数据（线程安全）
                            if channel_id not in self._liquid_line_locks:
                                self._liquid_line_locks[channel_id] = threading.Lock()
                            
                            with self._liquid_line_locks[channel_id]:
                                self._liquid_line_positions[channel_id] = detection_mission_result['liquid_line_positions'].copy()
                            
                            detection_count += 1
                            success_count += 1
                            
                            # 每100次成功检测打印一次统计
                            if success_count % 100 == 0:
                                print(f" {channel_id} 检测成功 {success_count} 次，失败 {fail_count} 次")
                        else:
                            fail_count += 1
                            
                    except Exception as e:
                        print(f" {channel_id} 检测推理错误: {e}")
                        fail_count += 1
                
                # 帧率控制：基于配置的检测帧率
                elapsed = time.time() - loop_start_time
                sleep_time = max(0, detection_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f" {channel_id} 检测线程错误: {e}")
                time.sleep(0.1)
        
        print(f" 检测线程停止: {channel_id}")
        print(f"   总帧数: {frame_count}, 检测次数: {detection_count}")
        print(f"   成功: {success_count}, 失败: {fail_count}")
    
    def _getLiquidLinePositions(self, channel_id):
        """
        获取并清空液位线位置数据（供显示线程使用）

        Args:
            channel_id: 通道ID

        Returns:
            dict: 液位线位置数据，格式：{area_idx: position_data}
        """
        if channel_id not in self._liquid_line_locks:
            return {}

        with self._liquid_line_locks[channel_id]:
            positions = self._liquid_line_positions.get(channel_id, {})
            # 复制后清空，确保每次只绘制最新的检测结果
            self._liquid_line_positions[channel_id] = {}
            return positions.copy()
    
    def _drawLiquidLines(self, frame, liquid_positions):
        """
        在帧上绘制液位线

        Args:
            frame: 输入帧
            liquid_positions: 液位线位置数据，格式：{area_idx: position_data}

        Returns:
            绘制后的帧
        """
        import cv2
        import numpy as np

        if not liquid_positions:
            return frame


        # 复制帧以避免修改原始数据
        display_frame = frame.copy()

        # 遍历每个ROI的液位线数据
        for area_idx, position_data in liquid_positions.items():
            try:
                left = position_data.get('left', 0)
                right = position_data.get('right', 0)
                # 兼容两种字段名：'y' 和 'y_absolute'
                y_absolute = position_data.get('y', position_data.get('y_absolute', 0))
                height_mm = position_data.get('height_mm', 0)


                # 绘制红色液位线
                cv2.line(display_frame, (int(left), int(y_absolute)),
                        (int(right), int(y_absolute)), (0, 0, 255), 2)

                # 四舍五入高度值
                height_mm = int(np.round(height_mm, 0))
                text = f"{height_mm}mm"

                # 绘制绿色高度文字
                cv2.putText(display_frame, text, (int(left) + 5, int(y_absolute) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


            except Exception as e:
                continue

        return display_frame
    
    def _updateVideoDisplay(self, channel_id, frame_or_data):
        """
        更新视频显示（线程安全）
        
        通过 Qt 信号机制将数据传递到主线程处理。
        
        Args:
            channel_id: 通道ID
            frame_or_data: 
                - HWND模式：dict，包含液位线数据 {'liquid_positions': {...}, 'is_new_data': bool, ...}
                - Qt模式：numpy.ndarray，视频帧
        """
        try:
            # 直接通过信号发射，Qt 会自动在主线程中调用槽函数
            if hasattr(self, '_video_display_signal') and self._video_display_signal:
                self._video_display_signal.update_display.emit(channel_id, frame_or_data)
        except Exception as e:
            self.logger.debug(f"[ERROR] _updateVideoDisplay 异常: {e}")
    
    def _updateVideoDisplayUI(self, channel_id, frame_or_data):
        """
        在主线程中更新视频显示

        使用节流机制，每200ms最多更新一次 InfoOverlay，避免频繁重绘。

        Args:
            channel_id: 通道ID
            frame_or_data:
                - HWND模式：dict，包含液位线数据
                - Qt模式：numpy.ndarray，视频帧
        """
        try:
            panel = self._channel_panels_map.get(channel_id)
            if not panel:
                return

            # 判断是 HWND 模式还是 Qt 模式
            if isinstance(frame_or_data, dict):
                # HWND模式：缓存液位线数据，使用节流更新
                liquid_positions = frame_or_data.get('liquid_positions', {})
                is_new_data = frame_or_data.get('is_new_data', True)
                video_width = frame_or_data.get('video_width', 0)
                video_height = frame_or_data.get('video_height', 0)

                # 缓存最新数据
                if not hasattr(self, '_liquid_line_cache'):
                    self._liquid_line_cache = {}
                self._liquid_line_cache[channel_id] = {
                    'liquid_positions': liquid_positions,
                    'is_new_data': is_new_data,
                    'video_width': video_width,
                    'video_height': video_height
                }

                # 节流：每200ms最多更新一次
                import time
                if not hasattr(self, '_last_overlay_update'):
                    self._last_overlay_update = {}

                current_time = time.time()
                last_update = self._last_overlay_update.get(channel_id, 0)

                if current_time - last_update >= 0.2:  # 200ms
                    self._last_overlay_update[channel_id] = current_time
                    if hasattr(panel, 'updateLiquidLines'):
                        panel.updateLiquidLines(liquid_positions, is_new_data, video_width, video_height)

                    # 如果当前通道正在预览窗口显示，同步更新预览窗口的液位线
                    if hasattr(self, '_current_preview_channel_id') and self._current_preview_channel_id == channel_id:
                        if hasattr(self, 'previewPanel') and hasattr(self.previewPanel, 'updateLiquidLines'):
                            self.previewPanel.updateLiquidLines(liquid_positions, is_new_data, video_width, video_height)
            else:
                # Qt模式：显示视频帧
                if hasattr(panel, 'displayFrame'):
                    panel.displayFrame(frame_or_data)

                # 如果当前通道正在预览窗口显示，同步更新预览窗口的画面
                if hasattr(self, '_current_preview_channel_id') and self._current_preview_channel_id == channel_id:
                    if hasattr(self, 'previewPanel') and hasattr(self.previewPanel, 'displayFrame'):
                        self.previewPanel.displayFrame(frame_or_data)

                # 同步更新放大窗口
                self._updateAmplifyWindows(channel_id, frame_or_data)
        except Exception as e:
            self.logger.debug(f"[ERROR] 更新视频显示失败: {e}")
    
    
    def _releaseChannel(self, channel_id):
        """释放通道资源"""
        if channel_id in self._channel_captures:
            try:
                cap = self._channel_captures[channel_id]
                cap.release()
                del self._channel_captures[channel_id]
                print(f" 通道资源已释放: {channel_id}")
            except Exception as e:
                print(f" 释放通道资源失败: {e}")
        
        # 清理标志（兼容旧代码，检查属性是否存在）
        if hasattr(self, '_capture_flags') and channel_id in self._capture_flags:
            del self._capture_flags[channel_id]
        
        if hasattr(self, '_display_flags') and channel_id in self._display_flags:
            del self._display_flags[channel_id]
    
    def getFrameBuffer(self, channel_id):
        """
        获取指定通道的frame_buffer
        
        外部组件可以通过这个方法访问frame_buffer
        
        Args:
            channel_id: 通道ID
        
        Returns:
            queue.Queue: 帧缓存队列，如果不存在返回None
        """
        return self._frame_buffers.get(channel_id)
    
    def getLatestFrame(self, channel_id):
        """
        获取指定通道的最新一帧（非阻塞，供标注功能使用）
        
        此方法用于标注功能等需要获取最新帧但不消费frame_buffer的场景。
        使用非消费式读取，不影响检测线程。
        
        Args:
            channel_id: 通道ID
        
        Returns:
            numpy.ndarray: 图像帧的副本，如果没有返回None
        """
        # 从线程管理器的 latest_frame 获取（非消费式读取）
        # 这样标注功能可以随时获取最新帧，而不会影响frame_buffer
        context = self.thread_manager.get_channel_context(channel_id)
        if context:
            with context.frame_lock:
                if context.latest_frame is not None:
                    # 返回副本，避免标注修改影响显示线程
                    return context.latest_frame.copy()
        
        # 兼容旧代码：如果新架构没数据，尝试从旧的frame_buffer获取
        buffer = self._frame_buffers.get(channel_id)
        if not buffer:
            return None
        
        # 获取最新帧（丢弃中间的旧帧）
        frame = None
        while not buffer.empty():
            try:
                frame = buffer.get_nowait()
            except queue.Empty:
                break
        
        return frame.copy() if frame is not None else None
    
    def onAmplifyClicked(self, channel_id):
        """
        处理放大按钮点击事件
        
        Args:
            channel_id: 通道ID
        """
        try:
            pass
            
            # 检查是否已经有全屏窗口
            if channel_id in self._amplify_windows:
                # 如果窗口已存在，将其置于前台
                window = self._amplify_windows[channel_id]
                if window.isVisible():
                    window.raise_()
                    window.activateWindow()
                    return
                else:
                    # 窗口已关闭，从映射中移除
                    del self._amplify_windows[channel_id]
            
            #  获取通道名称（从配置或使用channel_id）
            channel_name = channel_id
            if hasattr(self, '_config') and channel_id in self._config:
                channel_name = self._config[channel_id].get('name', channel_id)
            
            # 创建全屏窗口
            from widgets.videopage.amplify_window import AmplifyWindow
            from handlers.videopage.amplify_window_handler import AmplifyWindowHandler
            
            amplify_window = AmplifyWindow(
                channel_id=channel_id,
                channel_name=channel_name,
                parent=self
            )
            
            # 创建业务逻辑处理器
            amplify_handler = AmplifyWindowHandler(amplify_window)
            
            # 连接窗口关闭信号
            amplify_window.windowClosed.connect(self.onAmplifyWindowClosed)
            
            # 存储窗口和处理器引用
            self._amplify_windows[channel_id] = amplify_window
            self._amplify_handlers[channel_id] = amplify_handler
            
            # 显示窗口
            amplify_window.show()
            
            #  放大窗口现在通过 _updateVideoDisplayUI 同步更新，无需单独的同步线程
            # if channel_id in self._channel_captures:
            #     self._startAmplifyFrameSync(channel_id)
                
        except Exception as e:
            print(f" 创建全屏窗口失败: {e}")
            import traceback
            traceback.print_exc()
    
    def onAmplifyWindowClosed(self, channel_id):
        """
        处理全屏窗口关闭事件
        
        Args:
            channel_id: 通道ID
        """
        try:
            # 从映射中移除窗口和处理器
            if channel_id in self._amplify_windows:
                del self._amplify_windows[channel_id]
            if channel_id in self._amplify_handlers:
                del self._amplify_handlers[channel_id]
                
            # 停止帧同步
            self._stopAmplifyFrameSync(channel_id)
            
        except Exception as e:
            print(f" 处理全屏窗口关闭失败: {e}")
    
    def _startAmplifyFrameSync(self, channel_id):
        """
        开始全屏窗口的帧同步
        
        Args:
            channel_id: 通道ID
        """
        try:
            if channel_id not in self._amplify_windows:
                return
            
            amplify_window = self._amplify_windows[channel_id]
            
            # 检查是否已经有同步线程
            if hasattr(self, '_amplify_sync_flags'):
                if channel_id in self._amplify_sync_flags and self._amplify_sync_flags[channel_id]:
                    return
            
            # 初始化同步标志
            if not hasattr(self, '_amplify_sync_flags'):
                self._amplify_sync_flags = {}
            self._amplify_sync_flags[channel_id] = True
            
            # 启动帧同步线程
            import threading
            sync_thread = threading.Thread(
                target=self._amplifyFrameSyncLoop,
                args=(channel_id,),
                daemon=True
            )
            sync_thread.start()
            
        except Exception as e:
            print(f" 启动全屏帧同步失败: {e}")
    
    def _stopAmplifyFrameSync(self, channel_id):
        """
        停止全屏窗口的帧同步
        
        Args:
            channel_id: 通道ID
        """
        try:
            if hasattr(self, '_amplify_sync_flags'):
                if channel_id in self._amplify_sync_flags:
                    self._amplify_sync_flags[channel_id] = False
            
        except Exception as e:
            print(f" 停止全屏帧同步失败: {e}")
    
    def _amplifyFrameSyncLoop(self, channel_id):
        """
        全屏窗口帧同步循环
        
        Args:
            channel_id: 通道ID
        """
        frame_count = 0
        last_sync_time = time.time()
        
        while self._amplify_sync_flags.get(channel_id, False):
            try:
                # 从frame_buffer获取最新帧
                buffer = self._frame_buffers.get(channel_id)
                if not buffer:
                    time.sleep(0.01)
                    continue
                
                # 获取最新帧（丢弃旧帧）
                frame = None
                while not buffer.empty():
                    try:
                        frame = buffer.get_nowait()
                    except queue.Empty:
                        break
                
                if frame is not None:
                    # 发送帧到全屏窗口
                    amplify_window = self._amplify_windows.get(channel_id)
                    amplify_handler = self._amplify_handlers.get(channel_id)
                    
                    if amplify_window and amplify_window.isVisible() and amplify_handler:
                        # 使用处理器处理帧
                        processed_frame = amplify_handler.processFrame(frame)
                        
                        # 使用Qt的信号槽机制确保线程安全
                        # 创建局部变量避免lambda捕获问题
                        current_frame = processed_frame.copy() if processed_frame is not None else frame.copy()
                        QtCore.QTimer.singleShot(0, lambda f=current_frame: amplify_window.displayFrame(f))
                    
                    frame_count += 1
                    
                    # 计算FPS
                    current_time = time.time()
                    if frame_count % 30 == 0:  # 每30帧计算一次FPS
                        fps = 30 / (current_time - last_sync_time)
                        last_sync_time = current_time
                    
                else:
                    # 没有新帧，短暂等待
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f" {channel_id} 全屏帧同步错误: {e}")
                time.sleep(0.1)
    
    def _updateAmplifyWindows(self, channel_id, frame):
        """
        更新所有全屏窗口的显示
        
        Args:
            channel_id: 通道ID
            frame: 视频帧（已经包含液位线等绘制内容）
        """
        try:
            # 获取放大窗口和处理器
            amplify_window = self._amplify_windows.get(channel_id)
            amplify_handler = self._amplify_handlers.get(channel_id)
            
            if amplify_window and amplify_window.isVisible():
                #  如果有处理器，先进行数字变焦等处理
                if amplify_handler:
                    processed_frame = amplify_handler.processFrame(frame)
                    amplify_window.displayFrame(processed_frame)
                else:
                    # 没有处理器，直接显示
                    amplify_window.displayFrame(frame)
                
        except Exception as e:
            print(f"更新全屏窗口失败: {e}")
    
    def _initConfigFileWatcher(self):
        """初始化配置文件监控器"""
        try:
            # 临时禁用配置文件监控器以解决 QWidget 创建顺序问题
            return
            
            # 获取配置文件路径
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return
            
            # 创建文件系统监控器
            self._config_watcher = QFileSystemWatcher()
            self._config_watcher.addPath(config_path)
            
            # 连接文件变化信号
            self._config_watcher.fileChanged.connect(self._onConfigFileChanged)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _onConfigFileChanged(self, path):
        """配置文件变化时的回调"""
        try:
            # 延迟一小段时间，确保文件写入完成
            # 修复：检查 QApplication 是否存在
            if QtWidgets.QApplication.instance() is not None:
                QtCore.QTimer.singleShot(100, self._reloadChannelConfig)
            else:
                # 如果没有 QApplication，直接调用重载函数
                self._reloadChannelConfig()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _reloadChannelConfig(self):
        """重新从服务端加载通道配置"""
        try:
            self.logger.debug("[DEBUG] 开始从服务端重新加载通道配置")
            
            # 刷新远程配置缓存
            self._remote_config_manager.refresh_config_cache()
            
            # 重新加载配置
            channel_config = self._remote_config_manager.load_channel_config()
            default_config = self._remote_config_manager.load_default_config()
            
            # 合并配置
            self._config = {**default_config, **channel_config}
            
            self.logger.debug("[DEBUG] 成功从服务端重新加载配置")
            
            # 更新每个通道面板的名称显示
            for i in range(1, 9):  # 支持8个通道
                channel_id = f'channel{i}'
                
                # 获取通道面板
                panel = self._channel_panels_map.get(channel_id)
                if not panel:
                    continue
                
                # 从配置中获取通道名称
                channel_name = f'通道{i}'
                
                # 尝试从不同的配置源获取名称
                if 'channels' in channel_config and i in channel_config['channels']:
                    channel_name = channel_config['channels'][i].get('name', f'通道{i}')
                elif channel_id in default_config:
                    channel_name = default_config[channel_id].get('name', f'通道{i}')
                elif channel_id in channel_config:
                    channel_name = channel_config[channel_id].get('name', f'通道{i}')
                
                # 更新面板显示的名称
                if hasattr(panel, 'setChannelName'):
                    panel.setChannelName(channel_name)
                    self.logger.debug(f"[DEBUG] 更新通道{i}名称为: {channel_name}")
            
            self.logger.debug("[DEBUG] 通道配置重新加载完成")
            
        except Exception as e:
            self.logger.debug(f"[ERROR] 重新加载通道配置失败: {e}")
            import traceback
            traceback.print_exc()
    
    def updateMissionLabelByVar(self, channel_num, text):
        """
        通过变量名更新通道任务标签的显示内容
        
        使用方法：
            self.updateMissionLabelByVar(1, "1_1")  # 更新通道1的任务标签
            self.updateMissionLabelByVar(2, "2_3")  # 更新通道2的任务标签
        
        或者直接通过变量赋值：
            self.channel1mission.setText("1_1")
            self.channel2mission.setText("2_3")
        
        Args:
            channel_num: 通道编号（1-4）
            text: 要显示的文本内容
        """
        try:
            if not 1 <= channel_num <= 4:
                return
            
            # 获取对应的任务标签变量
            mission_var_name = f'channel{channel_num}mission'
            
            if not hasattr(self, mission_var_name):
                return
            
            mission_label = getattr(self, mission_var_name)
            
            # 更新标签文本
            mission_label.setText(str(text))
            mission_label.adjustSize()
            
            # 如果面板有定位方法，重新定位标签
            channel_id = f'channel{channel_num}'
            panel = self._channel_panels_map.get(channel_id)
            if panel and hasattr(panel, '_positionTaskLabel'):
                panel._positionTaskLabel()

        except Exception as e:
            import traceback
            traceback.print_exc()

    def _onWebSocketDetectionResult(self, data):
        """
        接收WebSocket推送的检测结果并更新液位线显示

        Args:
            data: 检测结果数据
        """
        try:
            # 提取通道ID
            channel_id = data.get('channel_id')
            if not channel_id:
                return

            # 提取检测结果数据
            data_obj = data.get('data', {})
            liquid_line_positions = data_obj.get('liquid_line_positions', {})

            if not liquid_line_positions:
                return

            # 转换key从字符串到整数
            converted_positions = {}
            for key, value in liquid_line_positions.items():
                try:
                    int_key = int(key)
                    converted_positions[int_key] = value
                except (ValueError, TypeError):
                    converted_positions[key] = value

            # 更新液位线位置数据（线程安全）- 用于非HWND模式
            if channel_id not in self._liquid_line_locks:
                import threading
                self._liquid_line_locks[channel_id] = threading.Lock()

            with self._liquid_line_locks[channel_id]:
                self._liquid_line_positions[channel_id] = converted_positions.copy()

            # 直接更新ChannelPanel的液位线显示（用于HWND模式）
            panel = self._channel_panels_map.get(channel_id)
            if panel:

                # 获取视频尺寸（从通道配置或默认值）
                video_width = 1920  # 默认值，可以从配置读取
                video_height = 1080

                # 尝试从通道配置获取实际尺寸
                if hasattr(self, '_channel_configs') and channel_id in self._channel_configs:
                    config = self._channel_configs[channel_id]
                    video_width = config.get('width', 1920)
                    video_height = config.get('height', 1080)

                # 调用ChannelPanel的updateLiquidLines方法
                panel.updateLiquidLines(
                    liquid_positions=converted_positions,
                    is_new_data=True,
                    video_width=video_width,
                    video_height=video_height
                )

        except Exception as e:
            self.logger.error(f"[UI-Draw] ERROR: {e}")
            import traceback
            traceback.print_exc()
