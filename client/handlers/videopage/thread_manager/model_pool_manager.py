# -*- coding: utf-8 -*-

"""
模型池管理器 - 全局检测线程架构核心组件

职责：
1. 扫描配置文件识别唯一模型路径
2. 实现模型常驻显存加载和管理
3. 建立通道到模型的映射关系
4. 提供模型切换和批量推理接口
5. 监控GPU显存使用和异常处理

设计原则：
- 模型一旦加载到GPU显存，在整个应用生命周期内保持常驻
- 多个通道共享相同模型时，只在显存中保留一个实例
- 通过模型池索引切换当前活跃模型，而非重新加载
- 实时监控GPU显存使用情况，防止内存溢出
"""

import os
import yaml
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import cv2
import numpy as np
from qtpy.QtCore import QThread, Signal


class ModelLoadingThread(QThread):
    """模型加载后台线程
    
    在后台线程中加载模型，避免阻塞UI主线程
    """
    # 信号定义
    progress_updated = Signal(int, str, str, int)  # (current, model_id, step, sub_progress)
    loading_completed = Signal(bool, dict)  # (success, loaded_models)
    loading_error = Signal(str)  # (error_message)
    
    def __init__(self, unique_models: Dict[str, str], manager):
        """
        初始化加载线程
        
        Args:
            unique_models: {model_id: model_path} 需要加载的模型
            manager: ModelPoolManager实例，用于访问配置和方法
        """
        super().__init__()
        self.unique_models = unique_models
        self.manager = manager
        self.loaded_models = {}  # {model_id: detection_engine}
        self.is_cancelled = False
    
    def run(self):
        """线程执行函数"""
        try:
            total_models = len(self.unique_models)
            print(f"[后台加载线程] 开始加载 {total_models} 个模型...")
            
            success_count = 0
            for idx, (model_id, model_path) in enumerate(self.unique_models.items(), 1):
                if self.is_cancelled:
                    print(f"[后台加载线程] 加载被取消")
                    break
                
                # 发送进度更新信号
                try:
                    self.progress_updated.emit(idx, model_id, "准备加载模型...", 0)
                except Exception as signal_err:
                    print(f"[后台加载线程] 信号发送失败: {signal_err}")
                
                print(f"[后台加载线程] 正在加载模型 {idx}/{total_models}: {model_id}")
                start_time = time.time()
                
                try:
                    detection_engine = self._load_single_model_internal(model_id, model_path, idx)
                except Exception as load_err:
                    print(f"[后台加载线程] 加载模型时发生未捕获异常: {load_err}")
                    import traceback
                    traceback.print_exc()
                    detection_engine = None
                
                load_time = time.time() - start_time
                
                if detection_engine:
                    self.loaded_models[model_id] = detection_engine
                    success_count += 1
                    print(f"[后台加载线程] 模型 {model_id} 加载成功，耗时 {load_time:.2f}s")
                else:
                    print(f"[后台加载线程] 模型 {model_id} 加载失败")
            
            # 发送完成信号
            success = success_count > 0
            print(f"[后台加载线程] 加载完成，成功 {success_count}/{total_models}")
            
            try:
                self.loading_completed.emit(success, self.loaded_models)
            except Exception as signal_err:
                print(f"[后台加载线程] 完成信号发送失败: {signal_err}")
            
        except Exception as e:
            error_msg = f"模型加载异常: {str(e)}"
            print(f"[后台加载线程] {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                self.loading_error.emit(error_msg)
            except Exception as signal_err:
                print(f"[后台加载线程] 错误信号发送失败: {signal_err}")
    
    def _load_single_model_internal(self, model_id: str, model_path: str, current_idx: int):
        """内部方法：通过服务端API加载单个模型
        
        Args:
            model_id: 模型ID
            model_path: 模型文件路径
            current_idx: 当前模型序号
            
        Returns:
            服务端模型标识对象，失败返回None
        """
        try:
            # 步骤1: 连接服务端 (0-20%)
            self.progress_updated.emit(current_idx, model_id, "连接服务端...", 0)
            
            # 导入远程配置管理器
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                try:
                    from utils.config import RemoteConfigManager
                except ImportError:
                    RemoteConfigManager = None
                    
            if not RemoteConfigManager:
                print("❌ [后台加载线程] 远程配置管理器不可用")
                return None
                
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                print(f"❌ [后台加载线程] SSH连接不可用")
                return None
            
            self.progress_updated.emit(current_idx, model_id, "服务端连接成功", 20)
            
            # 步骤2: 在服务端加载模型 (20-80%)
            self.progress_updated.emit(current_idx, model_id, "正在服务端加载模型...", 25)
            
            # 构建服务端模型加载命令
            load_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
try:
    from detection import LiquidDetectionEngine
    
    # 创建检测引擎实例
    engine = LiquidDetectionEngine(
        model_path='{model_path}',
        device='{self.manager.device}',
        batch_size={self.manager.batch_size}
    )
    
    print('SUCCESS: 服务端模型加载成功')
    print(f'MODEL_ID: {model_id}')
    print(f'MODEL_PATH: {model_path}')
    
except Exception as e:
    print(f'ERROR: 服务端模型加载失败: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
            
            result = ssh_manager.execute_remote_command(load_cmd)
            
            if not result['success'] or 'SUCCESS: 服务端模型加载成功' not in result['stdout']:
                error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                print(f"❌ [后台加载线程] 服务端模型加载失败: {error_msg}")
                return None
            
            self.progress_updated.emit(current_idx, model_id, "服务端模型加载完成", 80)
            
            # 步骤3: 创建客户端模型标识对象 (80-100%)
            self.progress_updated.emit(current_idx, model_id, "创建模型标识...", 85)
            
            # 创建服务端模型标识对象
            class ServerModelProxy:
                def __init__(self, model_id, model_path, device, batch_size):
                    self.model_id = model_id
                    self.model_path = model_path
                    self.device = device
                    self.batch_size = batch_size
                    self.is_server_model = True
                    
                def detect(self, frames, **kwargs):
                    """通过服务端API执行检测（占位方法）"""
                    # 实际检测会通过WebSocket或API调用服务端
                    return None
                    
                def configure(self, *args, **kwargs):
                    """配置模型（占位方法）"""
                    # 实际配置会通过服务端API进行
                    return True
            
            server_model = ServerModelProxy(model_id, model_path, self.manager.device, self.manager.batch_size)
            
            self.progress_updated.emit(current_idx, model_id, "模型标识创建完成", 100)
            
            print(f"✅ [后台加载线程] 服务端模型 {model_id} 加载成功")
            return server_model
            
        except Exception as e:
            print(f"❌ [后台加载线程] 加载模型失败 {model_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cancel(self):
        """取消加载"""
        self.is_cancelled = True


class ModelPoolManager:
    """模型池管理器
    
    管理所有检测模型的加载、切换和生命周期
    """
    
    def __init__(self):
        """初始化模型池管理器"""
        # ========== 模型池核心数据 ==========
        self.model_pool: Dict[str, Any] = {}           # {model_id: detection_engine}
        self.channel_model_mapping: Dict[str, str] = {} # {channel_id: model_id}
        self.model_usage_count: Dict[str, int] = {}     # {model_id: usage_count}
        
        # ========== 模型路径映射 ==========
        self.model_path_to_id: Dict[str, str] = {}      # {model_path: model_id}
        self.model_id_to_path: Dict[str, str] = {}      # {model_id: model_path}
        
        # ========== 当前状态 ==========
        self.current_model_id: Optional[str] = None     # 当前活跃的模型ID
        self.is_initialized = False                      # 是否已初始化
        
        # ========== 线程安全 ==========
        self._lock = threading.RLock()                   # 可重入锁
        
        # ========== 性能监控 ==========
        self.stats = {
            'total_models_loaded': 0,
            'model_switches': 0,
            'total_inferences': 0,
            'gpu_memory_usage': 0.0,
            'model_load_times': {},
            'switch_times': []
        }
        
        # ========== 配置参数 ==========
        self.device = 'cuda'                             # GPU设备
        self.batch_size = 4                              # 默认批大小
        self.enable_memory_monitoring = True             # 内存监控开关
        
        # ========== UI进度条 ==========
        self.progress_dialog: Optional[Any] = None       # 进度条对话框
        
        # ========== 配置缓存（避免每帧读取YAML）==========
        self._annotation_config_cache: Dict[str, Dict] = {}  # {channel_id: annotation_config}
        self._config_cache_loaded = False                     # 缓存是否已加载
        
        
    
    def initialize(self, config_file_path: Optional[str] = None) -> bool:
        """初始化模型池
        
        Args:
            config_file_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            bool: 初始化是否成功
        """
        with self._lock:
            if self.is_initialized:
                return True
            
            try:
                
                # 1. 加载配置文件
                config = self._load_config(config_file_path)
                if not config:
                    return False
                
                # 2. 扫描和识别唯一模型
                unique_models = self._scan_unique_models(config)
                if not unique_models:
                    print("❌ [模型池管理器] 未找到任何模型配置")
                    return False
                
                # 3. 建立通道到模型的映射（必须在模型加载前完成）
                self._build_channel_mapping(config)
                
                # 4. 加载所有唯一模型到显存
                success = self._load_all_models(unique_models)
                if not success:
                    print("❌ [模型池管理器] 模型加载失败")
                    return False
                
                # 5. 初始化性能监控
                self._initialize_monitoring()
                
                # 6. 预加载所有通道的标注配置到缓存
                self.preload_all_annotation_configs()
                
                self.is_initialized = True

                self._print_model_summary()
                
                return True
                
            except Exception as e:
                print(f"❌ [模型池管理器] 初始化失败: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    def _load_config(self, config_file_path: Optional[str] = None) -> Optional[Dict]:
        """加载配置文件"""
        try:
            if config_file_path is None:
                # 使用默认配置文件路径
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # 从 handlers/videopage/thread_manager 向上3层到项目根目录
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                config_file_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
                
            
            if not os.path.exists(config_file_path):
                print(f"❌ [模型池管理器] 配置文件不存在: {config_file_path}")
                return None
            
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 读取全局配置
            self.device = config.get('default_device', 'cuda') if config.get('gpu_enabled', True) else 'cpu'
            self.batch_size = config.get('default_batch_size', 4)
            
            return config
            
        except Exception as e:
            print(f"❌ [模型池管理器] 配置加载失败: {e}")
            return None
    
    def _scan_unique_models(self, config: Dict) -> Dict[str, str]:
        """扫描配置文件，识别所有唯一的模型路径
        
        Args:
            config: 配置字典
            
        Returns:
            Dict[str, str]: {model_id: model_path} 唯一模型映射
        """
        try:
            unique_models = {}
            model_path_counter = {}
            
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            
            # 扫描标准通道的模型路径配置（严格限制为 channelX_model_path 格式）
            for key, value in config.items():
                # 严格匹配 channelX_model_path 格式，其中 X 是数字
                if key.startswith('channel') and key.endswith('_model_path'):
                    # 提取通道ID并验证格式
                    channel_part = key.replace('_model_path', '')
                    if channel_part.startswith('channel') and channel_part[7:].isdigit():
                        channel_id = channel_part
                        model_path = value
                    else:
                        continue
                    
                    # 转换为绝对路径
                    if not os.path.isabs(model_path):
                        model_path = model_path.replace('/', os.sep).replace('\\', os.sep)
                        model_path = os.path.join(project_root, model_path)
                    
                    model_path = os.path.normpath(model_path)
                    
                    # 检查模型文件是否存在
                    if not os.path.exists(model_path):
                        continue
                    
                    # 统计相同路径的模型
                    if model_path not in model_path_counter:
                        model_path_counter[model_path] = []
                    model_path_counter[model_path].append(channel_id)
            
            # 为每个唯一路径生成模型ID
            for model_path, channels in model_path_counter.items():
                # 从路径中提取模型标识符（如 "3", "4", "5"）
                path_parts = model_path.split(os.sep)
                model_identifier = None
                
                for part in reversed(path_parts):
                    if part.isdigit():
                        model_identifier = part
                        break
                
                if model_identifier:
                    model_id = f"model_{model_identifier}"
                else:
                    # 如果无法提取标识符，使用文件名
                    model_id = f"model_{os.path.splitext(os.path.basename(model_path))[0]}"
                
                unique_models[model_id] = model_path
                self.model_path_to_id[model_path] = model_id
                self.model_id_to_path[model_id] = model_path
                
            return unique_models
            
        except Exception as e:
            return {}
    
    def _load_all_models(self, unique_models: Dict[str, str]) -> bool:
        """加载所有唯一模型到显存（使用后台线程）
        
        Args:
            unique_models: {model_id: model_path} 唯一模型映射
            
        Returns:
            bool: 是否全部加载成功
        """
        try:
            total_models = len(unique_models)
            
            # 初始化加载状态
            self._loading_success = False
            self._loading_finished = False
            
            # 创建进度条对话框
            self._create_progress_dialog(total_models)
            
            # 创建后台加载线程
            self.loading_thread = ModelLoadingThread(unique_models, self)
            
            # 连接信号
            self.loading_thread.progress_updated.connect(self._on_loading_progress)
            self.loading_thread.loading_completed.connect(self._on_loading_completed)
            self.loading_thread.loading_error.connect(self._on_loading_error)
            
            # 启动后台线程
            self.loading_thread.start()
            
            # 使用事件循环等待线程完成（不阻塞UI）
            from qtpy.QtWidgets import QApplication
            while not self._loading_finished:
                QApplication.processEvents()
                self.loading_thread.wait(50)  # 等待50ms
                if self.loading_thread.isFinished():
                    break
            
            # 确保所有信号处理完成
            QApplication.processEvents()
            
            # 返回加载结果
            return self._loading_success
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._close_progress_dialog(False)
            return False
    
    def _on_loading_progress(self, current: int, model_id: str, step: str, sub_progress: int):
        """处理加载进度更新信号
        
        Args:
            current: 当前模型序号
            model_id: 模型ID
            step: 当前步骤
            sub_progress: 子进度
        """
        self._update_progress_dialog(current, model_id, step, sub_progress)
    
    def _on_loading_completed(self, success: bool, loaded_models: dict):
        """处理加载完成信号
        
        Args:
            success: 是否成功
            loaded_models: 已加载的模型字典
        """
        
        # 将加载的模型添加到模型池
        for model_id, detection_engine in loaded_models.items():
            self.model_pool[model_id] = detection_engine
            self.model_usage_count[model_id] = 0
        
        self.stats['total_models_loaded'] = len(loaded_models)
        self._loading_success = success and len(loaded_models) > 0
        self._loading_finished = True  # 标记加载完成
        
            
        # 关闭进度条对话框
        self._close_progress_dialog(self._loading_success)
    
    def _on_loading_error(self, error_msg: str):
        """处理加载错误信号
        
        Args:
            error_msg: 错误信息
        """
        self._loading_success = False
        self._loading_finished = True  # 标记加载完成（即使失败）
        self._close_progress_dialog(False)
    
    def _create_progress_dialog(self, total_models: int):
        """创建进度条对话框
        
        Args:
            total_models: 总模型数
        """
        try:
            from .model_loading_progress import ModelLoadingProgressDialog
            
            # 尝试获取主窗口作为父窗口
            parent = None
            try:
                from qtpy.QtWidgets import QApplication
                app = QApplication.instance()
                if app and app.topLevelWidgets():
                    parent = app.topLevelWidgets()[0]
            except:
                pass
            
            self.progress_dialog = ModelLoadingProgressDialog(parent, total_models)
            self.progress_dialog.show()
            
            
        except Exception as e:
            print(f"⚠️ [模型池管理器] 创建进度条对话框失败: {e}")
            self.progress_dialog = None
    
    def _update_progress_dialog(self, current: int, model_id: str, step: str = "", sub_progress: int = 0):
        """更新进度条对话框
        
        Args:
            current: 当前进度（1-based）
            model_id: 模型ID
            step: 当前步骤描述
            sub_progress: 子步骤进度（0-100）
        """
        if self.progress_dialog:
            try:
                self.progress_dialog.update_progress(current, model_id, step, sub_progress)
            except Exception as e:
                import traceback
                traceback.print_exc()
    
    def _close_progress_dialog(self, success: bool = True):
        """关闭进度条对话框
        
        Args:
            success: 是否成功加载
        """
        if self.progress_dialog:
            try:
                if success:
                    self.progress_dialog.set_complete()
                else:
                    self.progress_dialog.set_error("部分模型加载失败")
                
                self.progress_dialog = None
                
            except Exception as e:
                import traceback
                traceback.print_exc()
    
    def _load_single_model(self, model_id: str, model_path: str, current_idx: int = 1) -> Optional[Any]:
        """通过服务端API加载单个模型
        
        Args:
            model_id: 模型ID
            model_path: 模型文件路径
            current_idx: 当前模型序号（用于进度报告）
            
        Returns:
            服务端模型标识对象，失败返回None
        """
        try:
            # 步骤1: 连接服务端 (0-20%)
            self._update_progress_dialog(current_idx, model_id, "连接服务端...", 0)
            
            # 导入远程配置管理器
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                try:
                    from utils.config import RemoteConfigManager
                except ImportError:
                    RemoteConfigManager = None
                    
            if not RemoteConfigManager:
                print(f"❌ [模型池管理器] 远程配置管理器不可用")
                return None
                
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                print(f"❌ [模型池管理器] SSH连接不可用")
                return None
            
            self._update_progress_dialog(current_idx, model_id, "服务端连接成功", 20)
            
            # 步骤2: 在服务端加载模型 (20-60%)
            self._update_progress_dialog(current_idx, model_id, "正在服务端加载模型...", 25)
            
            # 构建服务端模型加载命令
            load_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
try:
    from detection import LiquidDetectionEngine
    
    # 创建检测引擎实例
    engine = LiquidDetectionEngine(
        model_path='{model_path}',
        device='{self.device}',
        batch_size={self.batch_size}
    )
    
    print('SUCCESS: 服务端模型加载成功')
    print(f'MODEL_ID: {model_id}')
    print(f'MODEL_PATH: {model_path}')
    
except Exception as e:
    print(f'ERROR: 服务端模型加载失败: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
            
            result = ssh_manager.execute_remote_command(load_cmd)
            
            if not result['success'] or 'SUCCESS: 服务端模型加载成功' not in result['stdout']:
                error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                print(f"❌ [模型池管理器] 服务端模型加载失败: {error_msg}")
                return None
            
            self._update_progress_dialog(current_idx, model_id, "服务端模型加载完成", 60)
            
            # 步骤3: 读取标注配置 (60-75%)
            self._update_progress_dialog(current_idx, model_id, "正在读取标注配置文件...", 65)
            annotation_config = self._load_annotation_config_for_model(model_id)
            if not annotation_config:
                print(f"❌ [模型池管理器] 无法读取标注配置: {model_id}")
                return None
            self._update_progress_dialog(current_idx, model_id, "标注配置文件读取完成", 75)
            
            # 步骤4: 创建服务端模型代理对象 (75-95%)
            self._update_progress_dialog(current_idx, model_id, "正在创建模型代理...", 80)
            
            # 创建服务端模型标识对象
            class ServerModelProxy:
                def __init__(self, model_id, model_path, device, batch_size, annotation_config):
                    self.model_id = model_id
                    self.model_path = model_path
                    self.device = device
                    self.batch_size = batch_size
                    self.annotation_config = annotation_config
                    self.is_server_model = True
                    
                def detect(self, frames, **kwargs):
                    """通过服务端API执行检测（占位方法）"""
                    # 实际检测会通过WebSocket或API调用服务端
                    return None
                    
                def configure(self, *args, **kwargs):
                    """配置模型（占位方法）"""
                    # 实际配置会通过服务端API进行
                    return True
            
            server_model = ServerModelProxy(model_id, model_path, self.device, self.batch_size, annotation_config)
            
            self._update_progress_dialog(current_idx, model_id, "模型代理创建完成", 95)
            
            # 步骤5: 完成 (95-100%)
            self._update_progress_dialog(current_idx, model_id, "服务端模型就绪，等待检测任务", 100)
            
            print(f"✅ [模型池管理器] 服务端模型 {model_id} 加载成功")
            return server_model
            
        except Exception as e:
            print(f"❌ [模型池管理器] 加载模型失败 {model_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _load_annotation_config_for_model(self, model_id: str) -> Optional[Dict]:
        """为模型加载标注配置
        
        Args:
            model_id: 模型ID
            
        Returns:
            标注配置字典，失败返回None
        """
        try:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            
            # 读取标注数据
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if not os.path.exists(annotation_file):
                return None
            
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation_config = yaml.safe_load(f)
            
            # 找到使用此模型的第一个通道的配置
            for channel_id, mapped_model_id in self.channel_model_mapping.items():
                if mapped_model_id == model_id and channel_id in annotation_config:
                    annotation_data = annotation_config[channel_id]
                    
                    # 读取区域高度数据
                    channel_config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
                    actual_heights = []
                    
                    if os.path.exists(channel_config_file):
                        with open(channel_config_file, 'r', encoding='utf-8') as f:
                            channel_config = yaml.safe_load(f)
                        
                        if channel_config and channel_id in channel_config:
                            area_heights = channel_config[channel_id].get('general', {}).get('area_heights', {})
                            num_boxes = len(annotation_data.get('boxes', []))
                            
                            # 提取区域高度
                            for i in range(num_boxes):
                                area_key = f'area_{i+1}'
                                height_str = area_heights.get(area_key, '20mm')
                                
                                # 解析高度字符串
                                import re
                                height_match = re.search(r'([\d.]+)\s*(mm|cm)?', str(height_str))
                                if height_match:
                                    height_value = float(height_match.group(1))
                                    unit = height_match.group(2) if height_match.group(2) else 'mm'
                                    
                                    if unit == 'cm':
                                        height_mm = height_value * 10.0
                                    else:
                                        height_mm = height_value
                                    
                                    actual_heights.append(height_mm)
                                else:
                                    actual_heights.append(20.0)
                    
                    # 如果没有读取到高度数据，使用默认值
                    if not actual_heights:
                        num_boxes = len(annotation_data.get('boxes', []))
                        actual_heights = [20.0] * num_boxes
                    
                    # 添加actual_heights到配置中
                    annotation_data['actual_heights'] = actual_heights
                    
                    return annotation_data
            
            return None
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _configure_annotation_data(self, engine: Any, annotation_config: Dict) -> bool:
        """配置标注数据到检测引擎
        
        Args:
            engine: 检测引擎实例
            annotation_config: 标注配置字典
        
        Returns:
            bool: 配置是否成功
        """
        try:
            # 提取标注数据
            boxes = annotation_config.get('boxes', [])
            fixed_bottoms = annotation_config.get('fixed_bottoms', [])
            fixed_tops = annotation_config.get('fixed_tops', [])
            actual_heights = annotation_config.get('actual_heights', [])
            
            # 从标注结果读取初始状态（detect_initstatus）
            # areas配置中包含init_status字段：0=默认, 1=满, 2=空
            annotation_initstatus = []
            areas = annotation_config.get('areas', {})
            print(f"[DEBUG-Pool] 读取areas配置: {areas}")
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                area_info = areas.get(area_key, {})
                init_status = area_info.get('init_status', 0)
                annotation_initstatus.append(init_status)
                print(f"[DEBUG-Pool] {area_key}: init_status={init_status}")
            
            print(f"[DEBUG-Pool] annotation_initstatus列表: {annotation_initstatus}")
            
            # 如果没有实际高度数据，使用默认值
            if not actual_heights:
                actual_heights = [20.0] * len(boxes)
            
            # 调用引擎的configure方法（传递annotation_initstatus）
            engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights, annotation_initstatus)
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _build_channel_mapping(self, config: Dict):
        """建立通道到模型的映射关系
        
        Args:
            config: 配置字典
        """
        try:
            for key, value in config.items():
                # 严格匹配 channelX_model_path 格式，其中 X 是数字
                if key.startswith('channel') and key.endswith('_model_path'):
                    # 提取通道ID并验证格式
                    channel_part = key.replace('_model_path', '')
                    if channel_part.startswith('channel') and channel_part[7:].isdigit():
                        channel_id = channel_part
                        model_path = value
                    else:
                        continue
                    
                    # 转换为绝对路径
                    if not os.path.isabs(model_path):
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        model_path = model_path.replace('/', os.sep).replace('\\', os.sep)
                        model_path = os.path.join(project_root, model_path)
                    
                    model_path = os.path.normpath(model_path)
                    
                    # 查找对应的模型ID
                    model_id = self.model_path_to_id.get(model_path)
                    if model_id:
                        self.channel_model_mapping[channel_id] = model_id
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _initialize_monitoring(self):
        """初始化性能监控"""
        try:
            if self.enable_memory_monitoring and self.device.startswith('cuda'):
                # 尝试获取GPU内存使用情况
                try:
                    import torch
                    if torch.cuda.is_available():
                        self.stats['gpu_memory_usage'] = torch.cuda.memory_allocated() / 1024**3  # GB
                except ImportError:
                    pass
                except Exception:
                    pass
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _print_model_summary(self):
        """打印模型池摘要信息"""
        pass
        
        for model_id, model_path in self.model_id_to_path.items():
            if model_id in self.model_pool:
                # 找到使用此模型的通道
                channels = [ch for ch, mid in self.channel_model_mapping.items() if mid == model_id]
                load_time = self.stats['model_load_times'].get(model_id, 0)
    
    def get_model_for_channel(self, channel_id: str) -> Optional[Any]:
        """获取指定通道的检测模型
        
        Args:
            channel_id: 通道ID
            
        Returns:
            检测引擎实例，失败返回None
        """
        with self._lock:
            if not self.is_initialized:
                return None
            
            model_id = self.channel_model_mapping.get(channel_id)
            if not model_id:
                return None
            
            model = self.model_pool.get(model_id)
            if not model:
                return None
            
            # 更新使用计数
            self.model_usage_count[model_id] += 1
            
            # 记录模型切换（如果切换了模型）
            if self.current_model_id != model_id:
                self.current_model_id = model_id
                self.stats['model_switches'] += 1
            
            return model
    
    def get_channel_annotation_config(self, channel_id: str) -> Optional[Dict]:
        """获取指定通道的标注配置（使用缓存，避免每帧读取YAML）
        
        Args:
            channel_id: 通道ID
            
        Returns:
            标注配置字典，失败返回None
        """
        # 🔥 优先从缓存获取
        if channel_id in self._annotation_config_cache:
            return self._annotation_config_cache[channel_id].copy()
        
        try:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            
            # 读取标注数据
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if not os.path.exists(annotation_file):
                return None
            
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation_config = yaml.safe_load(f)
            
            if not annotation_config or channel_id not in annotation_config:
                return None
            
            annotation_data = annotation_config[channel_id].copy()
            
            # 读取区域高度数据
            channel_config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            actual_heights = []
            
            if os.path.exists(channel_config_file):
                with open(channel_config_file, 'r', encoding='utf-8') as f:
                    channel_config = yaml.safe_load(f)
                
                if channel_config and channel_id in channel_config:
                    area_heights = channel_config[channel_id].get('general', {}).get('area_heights', {})
                    num_boxes = len(annotation_data.get('boxes', []))
                    
                    # 提取区域高度
                    import re
                    for i in range(num_boxes):
                        area_key = f'area_{i+1}'
                        height_str = area_heights.get(area_key, '20mm')
                        
                        # 解析高度字符串
                        height_match = re.search(r'([\d.]+)\s*(mm|cm)?', str(height_str))
                        if height_match:
                            height_value = float(height_match.group(1))
                            unit = height_match.group(2) if height_match.group(2) else 'mm'
                            
                            if unit == 'cm':
                                height_mm = height_value * 10.0
                            else:
                                height_mm = height_value
                            
                            actual_heights.append(height_mm)
                        else:
                            actual_heights.append(20.0)
            
            # 如果没有读取到高度数据，使用默认值
            if not actual_heights:
                num_boxes = len(annotation_data.get('boxes', []))
                actual_heights = [20.0] * num_boxes
            
            # 添加actual_heights到配置中
            annotation_data['actual_heights'] = actual_heights
            
            # 🔥 存入缓存
            self._annotation_config_cache[channel_id] = annotation_data
            
            return annotation_data.copy()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def preload_all_annotation_configs(self):
        """预加载所有通道的标注配置到缓存
        
        在初始化时调用，避免检测时首次读取YAML的延迟
        """
        try:
            for channel_id in self.channel_model_mapping.keys():
                if channel_id not in self._annotation_config_cache:
                    self.get_channel_annotation_config(channel_id)
            
            self._config_cache_loaded = True
            print(f"📦 [模型池管理器] 已预加载 {len(self._annotation_config_cache)} 个通道的标注配置")
            
        except Exception as e:
            print(f"⚠️ [模型池管理器] 预加载标注配置失败: {e}")
    
    def invalidate_annotation_cache(self, channel_id: str = None):
        """使标注配置缓存失效（配置文件更新时调用）
        
        Args:
            channel_id: 指定通道ID，为None则清空所有缓存
        """
        if channel_id:
            self._annotation_config_cache.pop(channel_id, None)
            print(f"🔄 [模型池管理器] 通道 {channel_id} 标注配置缓存已清除")
        else:
            self._annotation_config_cache.clear()
            self._config_cache_loaded = False
            print(f"🔄 [模型池管理器] 所有标注配置缓存已清除")
    
    def process_batches(self, scheduled_batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理批量推理请求
        
        支持两种输入格式：
        1. roi_frames: ROI区域的RGB图像列表（优化后的数据流）
        2. frame: 完整帧RGB图像（兼容旧逻辑）
        
        Args:
            scheduled_batches: 调度后的批次列表
            
        Returns:
            推理结果列表
        """
        with self._lock:
            if not self.is_initialized:
                return []
            
            results = []
            
            try:
                for batch in scheduled_batches:
                    model_id = batch.get('model_id')
                    frames = batch.get('frames', [])
                    
                    if not model_id or not frames:
                        continue
                    
                    # 获取对应的模型
                    model = self.model_pool.get(model_id)
                    if not model:
                        continue
                    
                    # 切换到目标模型
                    if self.current_model_id != model_id:
                        switch_start = time.time()
                        self.current_model_id = model_id
                        self.stats['model_switches'] += 1
                        switch_time = time.time() - switch_start
                        self.stats['switch_times'].append(switch_time)
                    
                    # 批量推理
                    batch_results = []
                    for frame_data in frames:
                        channel_id = frame_data.get('channel_id')
                        
                        # 优先使用roi_frames（优化后的数据流）
                        roi_frames = frame_data.get('roi_frames')
                        frame = frame_data.get('frame')
                        
                        # 从缓存获取通道特定的标注配置
                        annotation_config = self.get_channel_annotation_config(channel_id)
                        if annotation_config:
                            annotation_config['channel_id'] = channel_id
                        
                        if roi_frames is not None:
                            # ROI模式：直接传入裁剪好的ROI图像列表
                            detection_result = model.detect(roi_frames, annotation_config=annotation_config, channel_id=channel_id)
                        elif frame is not None:
                            # 完整帧模式：传入完整帧，由detect内部裁剪ROI
                            detection_result = model.detect(frame, annotation_config=annotation_config, channel_id=channel_id)
                        else:
                            continue
                        
                        if detection_result:
                            # 记录模型分割FPS
                            try:
                                from utils.debug_logger import get_debug_logger
                                get_debug_logger().record_detection_frame(channel_id)
                            except:
                                pass
                            batch_results.append({
                                'channel_id': channel_id,
                                'result': detection_result
                            })
                    
                    results.extend(batch_results)
                    self.stats['total_inferences'] += len(batch_results)
                
                return results
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return []
    
    
    def cleanup(self):
        """清理模型池资源"""
        with self._lock:
            try:
                # 清理所有模型
                for model_id, model in self.model_pool.items():
                    try:
                        # 如果模型有cleanup方法，调用它
                        if hasattr(model, 'cleanup'):
                            model.cleanup()
                    except Exception:
                        pass
                
                # 清空所有数据结构
                self.model_pool.clear()
                self.channel_model_mapping.clear()
                self.model_usage_count.clear()
                self.model_path_to_id.clear()
                self.model_id_to_path.clear()
                
                self.current_model_id = None
                self.is_initialized = False
                
            except Exception as e:
                import traceback
                traceback.print_exc()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        with self._lock:
            stats = self.stats.copy()
            stats['model_count'] = len(self.model_pool)
            stats['channel_count'] = len(self.channel_model_mapping)
            stats['current_model'] = self.current_model_id
            
            # 计算平均切换时间
            if self.stats['switch_times']:
                stats['average_switch_time'] = sum(self.stats['switch_times']) / len(self.stats['switch_times'])
            else:
                stats['average_switch_time'] = 0.0
            
            return stats
