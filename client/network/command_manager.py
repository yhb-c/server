# 网络命令管理器
# 负责管理与服务端的命令通信，分离网络连接和业务逻辑

import json
import logging
from pathlib import Path
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
log_dir = project_root / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / 'client.log'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('CommandManager')

from qtpy import QtCore
from .websocket_client import WebSocketClient

# 导入CSV写入器
try:
    from client.storage.detection_result_csv_writer import DetectionResultCSVWriter
except ImportError:
    DetectionResultCSVWriter = None
    logger.warning("无法导入CSV写入器，数据存储功能将不可用")

class NetworkCommandManager(QtCore.QObject):
    """
    网络命令管理器
    
    职责：
    - 管理WebSocket连接
    - 提供简单的命令发送接口
    - 处理连接状态管理
    - 转发服务端响应
    """
    
    # 信号定义
    connectionStatusChanged = QtCore.Signal(bool, str)  # 连接状态变化
    detectionResultReceived = QtCore.Signal(dict)       # 检测结果接收
    commandResponseReceived = QtCore.Signal(str, dict)  # 命令响应接收
    liquidHeightReceived = QtCore.Signal(str, list)     # 液位高度数据接收 (channel_id, heights)
    
    def __init__(self, server_url='ws://192.168.0.121:8085', parent=None, enable_csv_storage=True, csv_save_dir=None):
        """
        初始化网络命令管理器

        Args:
            server_url: 服务器WebSocket地址
            parent: 父对象
            enable_csv_storage: 是否启用CSV存储（默认True）
            csv_save_dir: CSV保存目录（默认 D:\\system_client_sever\\client\\result）
        """
        super().__init__(parent)

        self.server_url = server_url
        self.ws_client = None
        self.is_connected = False

        # CSV存储
        self.enable_csv_storage = enable_csv_storage
        self.csv_writer = None

        logger.info("========== CSV初始化 ==========")
        logger.info(f"enable_csv_storage: {enable_csv_storage}")
        logger.info(f"DetectionResultCSVWriter available: {DetectionResultCSVWriter is not None}")

        if enable_csv_storage and DetectionResultCSVWriter:
            try:
                logger.info("正在初始化CSV写入器...")
                if csv_save_dir:
                    logger.info(f"使用指定目录: {csv_save_dir}")
                    self.csv_writer = DetectionResultCSVWriter(csv_save_dir)
                else:
                    logger.info("使用默认目录")
                    self.csv_writer = DetectionResultCSVWriter()
                logger.info(f"CSV存储已启用，csv_writer={self.csv_writer}")
            except Exception as e:
                logger.error(f"CSV写入器初始化失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            if not enable_csv_storage:
                logger.info("CSV存储已禁用")
            if not DetectionResultCSVWriter:
                logger.error("DetectionResultCSVWriter未导入")

        logger.info(f"CSV初始化完成，csv_writer={self.csv_writer}")
        logger.info("========================================\n")

        self._init_websocket()
    
    def _init_websocket(self):
        """初始化WebSocket客户端"""
        try:
            print(f"[CommandManager] ========== Initialize WebSocket ==========")
            self.ws_client = WebSocketClient(self.server_url, self)

            # 连接WebSocket信号
            print(f"[CommandManager] Connecting connection_status signal...")
            self.ws_client.connection_status.connect(self._on_connection_status)
            print(f"[CommandManager] [OK] connection_status signal connected")

            print(f"[CommandManager] Connecting detection_result signal...")
            self.ws_client.detection_result.connect(self._on_detection_result)
            print(f"[CommandManager] [OK] detection_result signal connected")

            print(f"[CommandManager] WebSocket client initialized: {self.server_url}")
            print(f"[CommandManager] ==========================================\n")

        except Exception as e:
            print(f"[CommandManager] WebSocket initialization failed: {e}")
            import traceback
            print(f"[CommandManager] Exception traceback: {traceback.format_exc()}")
            self.ws_client = None
    
    def start_connection(self):
        """启动WebSocket连接"""
        if self.ws_client:
            self.ws_client.start()
            return True
        return False
    
    def stop_connection(self):
        """停止WebSocket连接"""
        if self.ws_client:
            self.ws_client.stop()
            self.is_connected = False
    
    def send_detection_command(self, channel_id, action='start_detection'):
        """
        发送检测命令
        
        Args:
            channel_id: 通道ID
            action: 动作类型 ('start_detection', 'stop_detection')
            
        Returns:
            bool: 发送是否成功
        """
        print(f"[CommandManager] === 发送检测命令 ===")
        print(f"[CommandManager] 通道ID: {channel_id}")
        print(f"[CommandManager] 动作: {action}")
        
        if not self.ws_client:
            print(f"[CommandManager] 错误: WebSocket客户端未初始化")
            return False
        
        if not self.is_connected:
            print(f"[CommandManager] 警告: WebSocket未连接，尝试重新连接...")
            self.ws_client.force_reconnect()
            
            # 等待连接建立
            import time
            for i in range(20):  # 最多等待2秒
                time.sleep(0.1)
                if self.is_connected:
                    print(f"[CommandManager] 重连成功")
                    break
            else:
                print(f"[CommandManager] 错误: 重连失败，无法发送命令")
                return False

        # 发送命令
        print(f"[CommandManager] Sending WebSocket command...")
        success = self.ws_client.send_command(action, channel_id=channel_id)

        if success:
            print(f"[CommandManager] [OK] Detection command sent: {action}, channel: {channel_id}")
        else:
            print(f"[CommandManager] [FAIL] Detection command failed: {action}, channel: {channel_id}")

        return success
    
    def send_model_load_command(self, channel_id, model_path, device='cuda'):
        """
        发送模型加载命令
        
        Args:
            channel_id: 通道ID
            model_path: 模型路径
            device: 设备类型
            
        Returns:
            bool: 发送是否成功
        """
        if not self.ws_client or not self.is_connected:
            print(f"[CommandManager] WebSocket未连接，无法发送模型加载命令")
            return False
        
        success = self.ws_client.send_command(
            'load_model',
            channel_id=channel_id,
            model_path=model_path,
            device=device,
            purpose='detection'
        )
        
        if success:
            print(f"[CommandManager] 模型加载命令发送成功: {model_path}")
        else:
            print(f"[CommandManager] 模型加载命令发送失败: {model_path}")
        
        return success
    
    def send_annotation_command(self, channel_id, frame_data, conf_threshold=0.5):
        """
        发送自动标注命令
        
        Args:
            channel_id: 通道ID
            frame_data: 图像数据（base64编码）
            conf_threshold: 置信度阈值
            
        Returns:
            bool: 发送是否成功
        """
        if not self.ws_client or not self.is_connected:
            print(f"[CommandManager] WebSocket未连接，无法发送标注命令")
            return False
        
        success = self.ws_client.send_command(
            'auto_annotation',
            channel_id=channel_id,
            frame_data=frame_data,
            conf_threshold=conf_threshold,
            min_area=50,
            padding=10
        )
        
        if success:
            print(f"[CommandManager] 自动标注命令发送成功")
        else:
            print(f"[CommandManager] 自动标注命令发送失败")
        
        return success
    
    def send_configure_channel_command(self, channel_id, config):
        """
        发送配置通道命令
        
        Args:
            channel_id: 通道ID
            config: 配置参数字典
                - rtsp_url: RTSP流地址
                - boxes: 检测区域框 [(cx, cy, size), ...]
                - fixed_bottoms: 底部线条 [y1, y2, ...]
                - fixed_tops: 顶部线条 [y1, y2, ...]
                - actual_heights: 实际高度 [h1, h2, ...] (毫米)
                - annotation_initstatus: 初始状态 [0, 1, 2, ...]
                
        Returns:
            bool: 发送是否成功
        """
        if not self.ws_client or not self.is_connected:
            print(f"[CommandManager] WebSocket未连接，无法发送配置通道命令")
            return False
        
        success = self.ws_client.send_command(
            'configure_channel',
            channel_id=channel_id,
            config=config
        )
        
        if success:
            print(f"[CommandManager] 配置通道命令发送成功: {channel_id}")
        else:
            print(f"[CommandManager] 配置通道命令发送失败: {channel_id}")
        
        return success
    
    def send_subscribe_command(self, channel_id):
        """
        发送订阅通道命令
        
        Args:
            channel_id: 通道ID
            
        Returns:
            bool: 发送是否成功
        """
        if not self.ws_client or not self.is_connected:
            print(f"[CommandManager] WebSocket未连接，无法发送订阅命令")
            return False
        
        success = self.ws_client.send_command(
            'subscribe',
            channel_id=channel_id
        )
        
        if success:
            print(f"[CommandManager] 订阅通道命令发送成功: {channel_id}")
        else:
            print(f"[CommandManager] 订阅通道命令发送失败: {channel_id}")
        
        return success
    
    def force_reconnect(self):
        """强制重新连接"""
        if self.ws_client:
            self.ws_client.force_reconnect()

    # ========== CSV存储管理 ==========

    def enable_csv_storage_for_channel(self, channel_id: str):
        """
        为指定通道启用CSV存储

        Args:
            channel_id: 通道ID
        """
        if self.csv_writer:
            print(f"[CommandManager] 通道 {channel_id} CSV存储已启用")
        else:
            print(f"[CommandManager] CSV写入器未初始化")

    def disable_csv_storage(self):
        """禁用CSV存储"""
        self.enable_csv_storage = False
        print(f"[CommandManager] CSV存储已禁用")

    def get_csv_filepath(self, channel_id: str):
        """
        获取指定通道的CSV文件路径

        Args:
            channel_id: 通道ID

        Returns:
            Path: CSV文件路径
        """
        if self.csv_writer:
            return self.csv_writer.get_filepath(channel_id)
        return None

    def close_csv_files(self):
        """关闭所有CSV文件"""
        if self.csv_writer:
            self.csv_writer.close_all()
            print(f"[CommandManager] 所有CSV文件已关闭")
    
    def _on_connection_status(self, is_connected, message):
        """WebSocket连接状态变化处理"""
        self.is_connected = is_connected
        print(f"[CommandManager] 连接状态变化: {'已连接' if is_connected else '未连接'} - {message}")
        
        # 转发连接状态信号
        self.connectionStatusChanged.emit(is_connected, message)
    
    def _on_detection_result(self, data):
        """检测结果处理"""
        if data.get('type') != 'detection_result':
            return

        channel_id = data.get('channel_id')
        data_obj = data.get('data', {})
        liquid_line_positions = data_obj.get('liquid_line_positions', {})

        logger.debug(f"收到检测结果 - 通道: {channel_id}")

        # 从 liquid_line_positions 提取 heights 用于CSV存储
        heights = []
        if isinstance(liquid_line_positions, dict):
            for key in sorted(liquid_line_positions.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                position_data = liquid_line_positions[key]
                if isinstance(position_data, dict):
                    height_mm = position_data.get('height_mm', 0)
                    heights.append(height_mm)

        logger.debug(f"提取液位高度 - 通道: {channel_id}, 液位数: {len(heights)}, heights: {heights}")

        if channel_id and heights:
            # 发送液位高度数据信号
            self.liquidHeightReceived.emit(channel_id, heights)

            # 保存到CSV文件
            if self.csv_writer:
                try:
                    timestamp = data.get('timestamp')
                    logger.info(f"准备保存CSV - 通道: {channel_id}, 液位数: {len(heights)}")
                    self.csv_writer.write_detection_result(channel_id, heights, timestamp)
                    logger.info(f"CSV保存成功 - 通道: {channel_id}, 液位数: {len(heights)}")
                except Exception as e:
                    logger.error(f"CSV保存失败 - 通道: {channel_id}, 错误: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning(f"CSV写入器未初始化，无法保存数据 - 通道: {channel_id}")
        else:
            if not channel_id:
                logger.warning("检测结果缺少channel_id")
            if not heights:
                logger.warning(f"检测结果无液位数据 - 通道: {channel_id}")

        # 将heights添加到data中，方便system_window使用
        data['heights'] = heights

        # 转发检测结果信号
        self.detectionResultReceived.emit(data)