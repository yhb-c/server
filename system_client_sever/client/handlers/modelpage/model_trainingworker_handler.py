# -*- coding: utf-8 -*-

"""
训练工作线程

处理模型训练的后台线程
"""

import os
import yaml
import json
import struct
import hashlib
from pathlib import Path
from qtpy import QtCore

# 尝试导入 pyqtSignal，如果失败则使用 Signal
try:
    from PyQt5.QtCore import pyqtSignal
except ImportError:
    try:
        from PyQt6.QtCore import pyqtSignal
    except ImportError:
        # 如果都失败，使用 QtCore.Signal
        from qtpy.QtCore import Signal as pyqtSignal

from qtpy.QtCore import QThread

# 导入统一的路径管理函数
try:
    from ...database.config import get_project_root, get_temp_models_dir, get_train_dir
except (ImportError, ValueError):
    try:
        from database.config import get_project_root, get_temp_models_dir, get_train_dir
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from database.config import get_project_root, get_temp_models_dir, get_train_dir

# 导入模型转换工具
try:
    from .tools.convert_pt_to_dat import FileConverter as PtToDatConverter
except (ImportError, ValueError):
    try:
        from handlers.modelpage.tools.convert_pt_to_dat import FileConverter as PtToDatConverter
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from handlers.modelpage.tools.convert_pt_to_dat import FileConverter as PtToDatConverter

MODEL_FILE_SIGNATURE = b'LDS_MODEL_FILE'
MODEL_FILE_VERSION = 1
MODEL_ENCRYPTION_KEY = "liquid_detection_system_2024"


class TrainingWorker(QThread):
    """训练工作线程"""
    
    # 信号定义
    log_output = pyqtSignal(str)  # 日志输出信号
    training_finished = pyqtSignal(bool)  # 训练完成信号
    training_progress = pyqtSignal(int, dict)  # 训练进度信号 (epoch, loss_dict)
    
    def __init__(self, training_params):
        super().__init__()
        self.training_params = training_params
        self.is_running = True
        self.training_actually_started = False  # 标记训练是否已经真正开始（第一个epoch开始）
        self.train_config = None
        
        #  调试信息：显示传入的训练参数
        print(f"\n [TrainingWorker初始化] 接收到的训练参数:")
        for key, value in training_params.items():
            print(f"  {key}: {value}")
        print(f" [TrainingWorker初始化] base_model路径: {training_params.get('base_model', 'None')}")
        print(f" [TrainingWorker初始化] base_model文件存在: {os.path.exists(training_params.get('base_model', '')) if training_params.get('base_model') else False}")
        
        self.training_report = {
            "status": "init",
            "start_time": None,
            "end_time": None,
            "exp_name": training_params.get("exp_name"),
            "params": training_params,
            "device": training_params.get("device"),
            "weights_dir": None,
            "converted_dat_files": [],
            "error": None,
        }
        # 加载训练配置
        self._loadTrainingConfig()
    
    def _loadTrainingConfig(self):
        """加载训练配置"""
        try:
            import os
            import json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(current_dir, "..", "..", "database", "config", "train_configs")
            config_file_path = os.path.join(config_dir, "default_config.json")
            
            if not os.path.exists(config_file_path):
                # 尝试使用项目根目录
                try:
                    from database.config import get_project_root
                    project_root = get_project_root()
                    config_file_path = os.path.join(project_root, "database", "config", "train_configs", "default_config.json")
                except:
                    pass
            
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    self.train_config = json.load(f)
            else:
                self.train_config = None
        except Exception as e:
            self.train_config = None
    
    def _decode_dat_model(self, dat_path):
        """
        将加密的 .dat 模型解密为临时 .pt 文件（使用系统临时目录）
        
        Args:
            dat_path (str): .dat 模型路径
        
        Returns:
            str: 解密后的 .pt 模型路径
        """
        dat_path = Path(dat_path)
        if not dat_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {dat_path}")
        
        # 检查文件签名，判断是否为加密文件
        with open(dat_path, 'rb') as f:
            signature = f.read(len(MODEL_FILE_SIGNATURE))
            
            # 如果签名不匹配，说明这是一个直接重命名的 .pt 文件
            if signature != MODEL_FILE_SIGNATURE:
                print(f"[警告] {dat_path.name} 不是加密的 .dat 文件，将直接作为 .pt 文件使用")
                # 直接返回原路径，YOLO 可以直接加载
                return str(dat_path)
            
            # 继续解密流程
            version = struct.unpack('<I', f.read(4))[0]
            if version != MODEL_FILE_VERSION:
                raise ValueError(f"不支持的模型文件版本: {version}")
            
            filename_len = struct.unpack('<I', f.read(4))[0]
            _ = f.read(filename_len)  # 原始文件名，当前不使用
            
            data_len = struct.unpack('<Q', f.read(8))[0]
            encrypted_data = f.read(data_len)
        
        # 解密数据
        key_hash = hashlib.sha256(MODEL_ENCRYPTION_KEY.encode('utf-8')).digest()
        decrypted = bytearray(len(encrypted_data))
        key_len = len(key_hash)
        for idx, byte in enumerate(encrypted_data):
            decrypted[idx] = byte ^ key_hash[idx % key_len]
        decrypted = bytes(decrypted)
        
        # 使用系统临时文件（自动管理，训练结束后会在finally块中删除）
        import tempfile
        temp_fd, temp_model_path = tempfile.mkstemp(suffix='.pt', prefix='yolo_train_')
        try:
            # 关闭文件描述符
            os.close(temp_fd)
            # 写入解密数据
            with open(temp_model_path, 'wb') as f:
                f.write(decrypted)
            return temp_model_path
        except Exception as e:
            # 如果出错，清理临时文件
            try:
                os.remove(temp_model_path)
            except:
                pass
            raise e
    
    def _validateTrainingDataInThread(self, save_liquid_data_path):
        """
        在线程中验证训练数据（简化版，避免UI操作）
        
        Returns:
            tuple: (是否有效, 消息)
        """
        try:
            if not os.path.exists(save_liquid_data_path):
                return False, f"数据集配置文件不存在: {save_liquid_data_path}"
            
            if not save_liquid_data_path.endswith('.yaml'):
                return False, "数据集配置文件必须是 .yaml 格式"
            
            # 读取配置
            with open(save_liquid_data_path, 'r', encoding='utf-8') as f:
                data_config = yaml.safe_load(f)
            
            if not data_config:
                return False, "数据集配置文件为空"
            
            # 获取data.yaml所在目录
            data_yaml_dir = os.path.dirname(os.path.abspath(save_liquid_data_path))
            
            train_dir = data_config.get('train', '')
            val_dir = data_config.get('val', '')
            
            if not train_dir:
                return False, "训练集路径为空"
            
            if not val_dir:
                return False, "验证集路径为空"
            
            # 如果是相对路径，转换为相对于data.yaml的绝对路径
            if not os.path.isabs(train_dir):
                train_dir = os.path.join(data_yaml_dir, train_dir)
            
            if not os.path.isabs(val_dir):
                val_dir = os.path.join(data_yaml_dir, val_dir)
            
            if not os.path.exists(train_dir):
                return False, f"训练集路径不存在: {train_dir}"
            
            if not os.path.exists(val_dir):
                return False, f"验证集路径不存在: {val_dir}"
            
            # 检查是否有图片文件
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
            
            train_count = sum(1 for f in os.listdir(train_dir) 
                            if any(f.lower().endswith(ext) for ext in image_extensions))
            val_count = sum(1 for f in os.listdir(val_dir) 
                          if any(f.lower().endswith(ext) for ext in image_extensions))
            
            if train_count == 0:
                return False, f"训练集目录为空: {train_dir}"
            
            if val_count == 0:
                return False, f"验证集目录为空: {val_dir}"
            
            return True, f"数据集验证通过 (训练: {train_count} 张, 验证: {val_count} 张)"
            
        except Exception as e:
            return False, f"验证过程出错: {str(e)}"
        
    def run(self):
        """执行训练"""
        # 初始化变量（确保finally块能访问）
        original_stdout = None
        original_stderr = None
        temp_model_path = None
        
        try:
            import os
            import sys
            import io
            import logging
            
            # 根据训练设备设置环境变量
            device = self.training_params.get('device', 'cpu')
            if device.lower() == 'cpu':
                os.environ["CUDA_VISIBLE_DEVICES"] = '-1'  # 强制使用 CPU
            else:
                # GPU 设备：支持 '0', '0,1' 等格式
                os.environ["CUDA_VISIBLE_DEVICES"] = device
            
            # 优化环境变量设置
            os.environ['YOLO_VERBOSE'] = 'True'  # 允许显示训练进度
            os.environ['ULTRALYTICS_AUTODOWNLOAD'] = 'False'  # 禁用自动下载
            os.environ['ULTRALYTICS_DATASETS_DIR'] = os.path.join(os.getcwd(), 'database', 'dataset')
            
            # 设置日志级别以支持进度条显示
            import logging
            logging.getLogger('ultralytics').setLevel(logging.INFO)
            logging.getLogger('yolov8').setLevel(logging.INFO)
            
            # 确保进度条能正常显示
            os.environ['TERM'] = 'xterm-256color'  # 支持颜色和进度条
            
            # 先导入YOLO，但不立即设置离线模式
            # 离线模式会在验证模型文件存在后设置
            from ultralytics import YOLO
            
            # 创建日志捕获类（同步终端和UI，只显示原生进度条，单行实时更新，每轮换行）
            class LogCapture:
                """捕获训练进度，同步显示到终端和UI（与终端完全一致）
                
                - 训练过程中：单行实时更新进度条（缓存进度条，只发送最新的）
                - 每轮完成（100%）：保留该行并换行，下一轮从新行开始
                """
                def __init__(self, signal, original_stream, log_file_path=None):
                    self.signal = signal
                    self.original = original_stream
                    self.buffer = ""
                    self._log_file_path = log_file_path
                    self._is_progress_line = False  # 标记当前是否是进度条行
                    self._cached_progress = None  # 缓存最新的进度条行
                    self._last_epoch = None  # 记录上一个 epoch
                
                def write(self, text):
                    import re
                    
                    # 始终写入终端（保证终端显示完整）
                    if self.original:
                        try:
                            self.original.write(text)
                            self.original.flush()
                        except:
                            pass
                    
                    # 同步写入到日志文件（追加）
                    if self._log_file_path:
                        try:
                            with open(self._log_file_path, "a", encoding="utf-8", errors="ignore") as lf:
                                lf.write(text)
                        except:
                            pass
                    
                    # 处理文本：清理ANSI代码并发送到UI
                    
                    # 移除ANSI转义序列（颜色代码等）
                    clean_text = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)
                    
                    # 过滤掉YOLO自动打印的验证指标行（包含mAP等）
                    # 这些行通常包含：Epoch, GPU_mem, box_loss, cls_loss, dfl_loss, Instances, Size, mAP50, mAP50-95等
                    # 示例：Epoch    GPU_mem   box_loss   cls_loss   dfl_loss  Instances       Size
                    #       1/100      3.72G      1.173      1.920      1.506         29        640
                    if re.search(r'(Epoch\s+GPU_mem|metrics/mAP|val/box_loss|val/cls_loss|val/dfl_loss|mAP50|mAP50-95)', clean_text, re.IGNORECASE):
                        # 跳过这些验证指标行，不发送到UI
                        return
                    
                    # 检查是否包含回车符（进度条通常使用\r来覆盖同一行）
                    has_carriage_return = '\r' in text
                    
                    # 移除回车符，但记住这是进度条行
                    if has_carriage_return:
                        clean_text = re.sub(r'\r', '', clean_text)
                        self._is_progress_line = True
                    
                    # 如果有换行符，说明进度条行结束
                    if '\n' in clean_text:
                        self._is_progress_line = False
                    
                    # 先检查是否需要过滤（扫描信息、调试日志等）
                    # 只过滤明确不需要的信息
                    skip_patterns = [
                        'scanning',  # 数据集扫描信息
                        'labels.cache',  # 缓存文件信息
                        'duplicate',  # 重复标签信息
                        'warning:',  # 警告信息
                        '[trainingpage]',  # UI 调试日志
                        '[应用]',  # 应用调试日志
                    ]
                    should_skip = False
                    for pattern in skip_patterns:
                        if pattern in clean_text.lower():
                            should_skip = True
                            break
                    
                    if should_skip:
                        return  # 跳过这条信息
                    
                    # 再检查是否是训练进度条行（优先级最高，不过滤）
                    # 训练进度条格式：epoch/batch 显存 损失值... 进度条 速度
                    # 例如：1/100 3.72G 1.173 1.92 1.506 1.253 29 640: 4% ──────────── 109/2901
                    # 关键特征：包含 epoch/batch、显存(G)、多个损失值、百分比
                    is_progress_bar = (
                        # 最准确的特征：包含 epoch/batch 格式、显存信息(G)、百分比和进度符号
                        (not '\n' in clean_text and 
                         re.search(r'\d+/\d+', clean_text) is not None and
                         re.search(r'\d+\.?\d*G', clean_text) is not None and
                         '%' in clean_text and
                         ('|' in clean_text or '━' in clean_text or '─' in clean_text))
                    )
                    
                    # 发送所有有效文本到UI，包括训练信息和进度条
                    if clean_text.strip():
                        
                        # 发送进度条或普通文本到UI
                        if is_progress_bar:
                            try:
                                # 检查是否达到100%（一轮完成）
                                is_complete = '100%' in clean_text
                                
                                # 提取当前 epoch 号（格式：1/100, 2/100 等）
                                epoch_match = re.search(r'(\d+)/(\d+)', clean_text)
                                current_epoch = int(epoch_match.group(1)) if epoch_match else None
                                
                                # 使用特殊标记来标识进度条
                                if is_complete:
                                    # 如果达到100%，标记为完成，UI会保留这一行并换行
                                    marked_text = "__PROGRESS_BAR_COMPLETE__" + clean_text
                                    self.signal.emit(marked_text)
                                    self._cached_progress = None  # 清空缓存
                                    self._last_epoch = current_epoch  # 更新 epoch 记录
                                else:
                                    # 关键修复：实时发送进度条，而不是缓存
                                    # 这样用户可以看到实时的训练进度
                                    marked_text = "__PROGRESS_BAR__" + clean_text
                                    self.signal.emit(marked_text)  # 立即发送，不缓存
                                    self._cached_progress = marked_text  # 保留缓存备用
                            except Exception as e:
                                # 如果处理进度条出错，作为普通文本发送
                                self.signal.emit(clean_text)
                        else:
                            # 发送之前缓存的进度条（如果有的话）
                            if self._cached_progress:
                                self.signal.emit(self._cached_progress)
                                self._cached_progress = None
                            
                            # 发送普通训练信息到UI
                            self.signal.emit(clean_text)
                
                def flush(self):
                    # 刷新终端
                    if self.original:
                        try:
                            self.original.flush()
                        except:
                            pass
                    
                    # 如果缓冲区有内容，尝试发送到UI
                    if self.buffer and self.buffer.strip():
                        try:
                            import re
                            clean_text = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', self.buffer)
                            clean_text = re.sub(r'\r', '', clean_text)
                            
                            if clean_text.strip():
                                self.signal.emit(clean_text)
                                self.buffer = ""
                        except:
                            pass
            
            # 保存原始stdout/stderr
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            
            # 预先准备日志目录与日志文件
            try:
                train_root_for_log = get_train_dir()
                exp_name_for_log = self.training_params.get('exp_name', 'training_experiment')
                exp_dir_for_log = os.path.join(train_root_for_log, "runs", "train", exp_name_for_log)
                os.makedirs(exp_dir_for_log, exist_ok=True)
                log_file_path = os.path.join(exp_dir_for_log, "training_ui.log")
                # 记录到报告（存绝对路径）
                self.training_report["weights_dir"] = os.path.abspath(os.path.join(exp_dir_for_log, "weights"))
            except Exception:
                log_file_path = None
            
            # 重定向stdout和stderr（附带文件记录）
            sys.stdout = LogCapture(self.log_output, sys.__stdout__, log_file_path)
            sys.stderr = LogCapture(self.log_output, sys.__stderr__, log_file_path)
            
            # 输出训练开始信息（简化版，不打印详细参数）
            self.log_output.emit("=" * 70 + "\n")
            self.log_output.emit("开始升级模型\n")
            self.log_output.emit("=" * 70 + "\n\n")
            # 报告：开始时间
            import time as _time_mod
            self.training_report["status"] = "running"
            self.training_report["start_time"] = _time_mod.time()
            
            # 验证数据集（在训练线程中再次验证，确保数据可用）
            self.log_output.emit("正在验证数据集...\n")
            try:
                validation_result, validation_msg = self._validateTrainingDataInThread(self.training_params['save_liquid_data_path'])
                if not validation_result:
                    self.log_output.emit(f"[ERROR] 数据集验证失败: {validation_msg}\n")
                    self.log_output.emit("=" * 60 + "\n")
                    self.training_finished.emit(False)
                    return
                else:
                    self.log_output.emit(f"{validation_msg}\n\n")
            except Exception as e:
                self.log_output.emit(f"[WARNING] 数据集验证过程出错: {str(e)}\n")
                self.log_output.emit("继续尝试训练...\n\n")
            
            # 处理模型文件
            model_path = self.training_params['base_model']
            temp_model_path = None
            
            if model_path.endswith('.dat'):
                self.log_output.emit("正在处理.dat模型文件...\n")
                try:
                    decoded_path = self._decode_dat_model(model_path)
                    model_path = decoded_path
                    temp_model_path = decoded_path
                    self.log_output.emit("模型处理完成\n")
                except Exception as decode_error:
                    self.log_output.emit(f"[ERROR] 模型处理失败: {decode_error}\n")
                    self.training_finished.emit(False)
                    return
            
            # 检查停止标志
            if not self.is_running:
                self.log_output.emit("[WARNING] 训练在开始前被停止\n")
                return
            
            # 加载模型
            self.log_output.emit("正在加载模型...\n")
            
            try:
                #  详细调试信息
                # self.log_output.emit(f" [训练工作线程] 模型路径: {model_path}\n")
                # self.log_output.emit(f" [训练工作线程] 模型路径类型: {type(model_path)}\n")
                # self.log_output.emit(f" [训练工作线程] 文件是否存在: {os.path.exists(model_path)}\n")
                
                if os.path.exists(model_path):
                    file_size = os.path.getsize(model_path)
                    self.log_output.emit(f" [训练工作线程] 文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)\n")
                
                # 在加载模型前验证文件存在，并设置离线模式
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"模型文件不存在: {model_path}")
                
                # 验证通过后，设置离线模式防止ultralytics尝试下载其他模型
                os.environ['YOLO_OFFLINE'] = '1'
                os.environ['ULTRALYTICS_OFFLINE'] = 'True'
                
                model = YOLO(model_path)
                self.log_output.emit("模型加载成功\n\n")
            except Exception as model_error:
                self.log_output.emit(f"[ERROR] 模型加载失败: {str(model_error)}\n")
                raise model_error
            
            # 创建训练回调
            import time
            epoch_start_time = [0]  # 使用列表以便在闭包中修改
            
            def on_train_start(trainer):
                """训练开始回调 - 只输出到终端，不发送到UI"""
                # 标记训练已经真正开始
                self.training_actually_started = True
                # 记录开始时间
                epoch_start_time[0] = time.time()
                # 不发送任何格式化消息到UI，让LogCapture直接捕获原生输出
            
            def on_train_batch_end(trainer):
                """训练批次结束回调 - 检查停止标志但不立即停止"""
                if not self.is_running:
                    # 只显示提示信息，不设置stop_training标志
                    # 让训练继续到epoch结束
                    if not hasattr(trainer, '_stop_message_shown'):
                        print("\n用户请求停止训练...")
                        print("请稍候，等待当前训练轮次完成...")
                        trainer._stop_message_shown = True
            
            def on_train_epoch_end(trainer):
                """训练周期结束回调 - 检查停止标志，在epoch完成后优雅停止"""
                # 获取当前轮次信息
                epoch = trainer.epoch + 1
                total_epochs = trainer.epochs
                
                # 如果用户请求停止，在当前epoch完成后停止
                if not self.is_running:
                    print(f"\n当前轮次 {epoch}/{total_epochs} 已完成")
                    print("用户请求停止训练，正在退出...")
                    trainer.stop_training = True
                    if hasattr(trainer, 'model'):
                        trainer.model.training = False
                    # 抛出异常来终止训练，但此时当前epoch已完成
                    raise KeyboardInterrupt("用户停止训练")
                
                # 重置计时器
                current_time = time.time()
                epoch_start_time[0] = current_time
                
                # 只发送进度信号，不发送格式化消息到UI
                # 让LogCapture直接捕获原生输出
                try:
                    loss_dict = {}
                    if hasattr(trainer, 'metrics'):
                        if hasattr(trainer.metrics, 'box_loss'):
                            loss_dict['box_loss'] = float(trainer.metrics.box_loss)
                        if hasattr(trainer.metrics, 'cls_loss'):
                            loss_dict['cls_loss'] = float(trainer.metrics.cls_loss)
                    self.training_progress.emit(epoch, loss_dict)
                except Exception as e:
                    pass
            
            # 添加回调
            try:
                model.add_callback("on_train_start", on_train_start)
                model.add_callback("on_train_batch_end", on_train_batch_end)
                model.add_callback("on_train_epoch_end", on_train_epoch_end)
            except Exception as e:
                self.log_output.emit(f"回调添加失败: {str(e)}\n")
            
            # 最后一次检查停止标志
            if not self.is_running:
                self.log_output.emit("[WARNING] 训练在开始前被停止\n")
                return
            
            self.log_output.emit("开始升级模型...\n")
            self.log_output.emit("=" * 60 + "\n")
            
            # 检查并调整batch size（防止GPU OOM）
            batch_size = self.training_params['batch']
            device_str = self.training_params['device']
            imgsz = self.training_params['imgsz']
            original_batch_size = batch_size  # 保存原始batch size
            
            # 如果使用GPU，检查显存和batch size
            if device_str.lower() not in ['cpu', '-1']:
                self.log_output.emit(f"检测到GPU训练（设备: {device_str}）\n")
                
                # 尝试获取GPU信息
                try:
                    import torch
                    import gc
                    if torch.cuda.is_available():
                        gpu_id = int(device_str) if device_str.isdigit() else 0
                        gpu_name = torch.cuda.get_device_name(gpu_id)
                        total_memory = torch.cuda.get_device_properties(gpu_id).total_memory / (1024**3)  # GB
                        
                        self.log_output.emit(f"GPU型号: {gpu_name}\n")
                        self.log_output.emit(f"总显存: {total_memory:.2f} GB\n")
                        
                        # 彻底清理显存
                        gc.collect()
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        
                        # 获取当前可用显存
                        try:
                            allocated = torch.cuda.memory_allocated(gpu_id) / (1024**3)
                            reserved = torch.cuda.memory_reserved(gpu_id) / (1024**3)
                            free_memory = total_memory - reserved
                            
                            self.log_output.emit(f"当前已分配: {allocated:.2f} GB\n")
                            self.log_output.emit(f"当前保留: {reserved:.2f} GB\n")
                            self.log_output.emit(f"可用显存: {free_memory:.2f} GB\n\n")
                            
                            # 根据显存大小和图像尺寸给出batch size建议
                            if total_memory < 6:  # 6GB以下
                                recommended_batch = 4
                                recommended_imgsz = 512
                            elif total_memory < 12:  # 6-12GB
                                recommended_batch = 8
                                recommended_imgsz = 640
                            else:  # 12GB以上
                                recommended_batch = 16
                                recommended_imgsz = 640
                            
                            # 根据图像尺寸调整建议
                            if imgsz > 640:
                                recommended_batch = max(4, recommended_batch // 2)
                            elif imgsz > 512:
                                recommended_batch = max(4, int(recommended_batch * 0.75))
                            
                            # 如果可用显存不足，进一步降低建议
                            if free_memory < 3.0:
                                recommended_batch = max(2, recommended_batch // 2)
                            
                            # 检查当前设置是否合理，如果超出建议值则自动调整
                            if batch_size > recommended_batch:
                                self.log_output.emit(f"警告: 当前batch={batch_size}可能超出显存容量\n")
                                self.log_output.emit(f"自动调整: batch={batch_size} -> {recommended_batch}\n")
                                batch_size = recommended_batch
                                self.log_output.emit(f"建议配置: batch≤{recommended_batch}, imgsz≤{recommended_imgsz}\n\n")
                            elif free_memory < 2.0:  # 可用显存少于2GB
                                self.log_output.emit(f"警告: 可用显存不足 ({free_memory:.2f} GB)\n")
                                # 自动降低batch size
                                if batch_size > 4:
                                    new_batch = max(2, batch_size // 2)
                                    self.log_output.emit(f"自动调整: batch={batch_size} -> {new_batch}\n")
                                    batch_size = new_batch
                                self.log_output.emit(f"建议: 关闭其他程序释放显存，或进一步减小batch size\n\n")
                        except:
                            pass
                except Exception as e:
                    self.log_output.emit(f"无法获取GPU详细信息: {str(e)}\n")
                    # 通用建议和自动调整
                    if batch_size > 8:
                        self.log_output.emit(f"警告: batch={batch_size} 可能导致显存不足\n")
                        new_batch = max(4, batch_size // 2)
                        self.log_output.emit(f"自动调整: batch={batch_size} -> {new_batch}\n")
                        batch_size = new_batch
                        self.log_output.emit(f"建议: 使用batch≤8以避免OOM错误\n\n")
            
            # 开始训练（支持自动重试和batch size调整）
            max_retries = 3
            retry_count = 0
            training_success = False
            
            while retry_count < max_retries and not training_success:
                try:
                    # 从配置文件读取AMP设置，如果没有则默认启用（节省显存）
                    amp_enabled = True  # 默认启用AMP
                    if self.train_config and 'device_config' in self.train_config:
                        amp_enabled = self.train_config['device_config'].get('amp', True)
                    # 如果使用CPU，强制关闭AMP（CPU不支持AMP）
                    if device_str.lower() in ['cpu', '-1']:
                        amp_enabled = False
                    
                    # 如果是重试，清理显存
                    if retry_count > 0:
                        self.log_output.emit(f"\n第 {retry_count} 次重试训练...\n")
                        try:
                            import torch
                            import gc
                            gc.collect()
                            torch.cuda.empty_cache()
                            torch.cuda.synchronize()
                            self.log_output.emit("已清理GPU显存缓存\n")
                        except:
                            pass
                    
                    self.log_output.emit(f"批次大小: {batch_size}\n")
                    self.log_output.emit(f"训练设备: {device_str}\n")
                    self.log_output.emit(f"模型名称: {self.training_params['exp_name']}\n\n")
                    
                    # 优化workers参数，避免多线程死锁
                    workers = min(self.training_params['workers'], 2)  # 限制最大workers数量
                    if device_str.lower() in ['cpu', '-1']:
                        workers = 0  # CPU模式下禁用多线程数据加载
                    
                    # 获取下一个可用的模型ID并创建目录
                    project_root = get_project_root()
                    detection_model_dir = os.path.join(project_root, 'database', 'model', 'detection_model')
                    os.makedirs(detection_model_dir, exist_ok=True)
                    
                    # 查找下一个可用的数字ID
                    existing_dirs = []
                    for item in os.listdir(detection_model_dir):
                        item_path = os.path.join(detection_model_dir, item)
                        if os.path.isdir(item_path) and item.isdigit():
                            existing_dirs.append(int(item))
                    
                    next_id = max(existing_dirs) + 1 if existing_dirs else 1
                    model_output_dir = os.path.join(detection_model_dir, str(next_id))
                    
                    # 预先设置目录结构
                    # YOLO会在project目录下创建train子目录，train下有weights子目录
                    train_dir = os.path.join(model_output_dir, "train")
                    weights_dir = os.path.join(train_dir, "weights")
                    self.training_report["weights_dir"] = weights_dir
                    self.training_report["model_output_dir"] = model_output_dir  # 保存模型输出目录
                    
                    # 设置training_results目录用于存放训练结果文件
                    training_results_dir = os.path.join(model_output_dir, "training_results")
                    self.training_report["training_results_dir"] = training_results_dir
                    
                    self.log_output.emit(f"模型将直接保存到: {model_output_dir}\n")
                    self.log_output.emit(f"  - .dat文件: {weights_dir}\n")
                    self.log_output.emit(f"  - 训练结果: {training_results_dir}\n")
                    
                    # 开始训练
                    try:
                        mission_results = model.train(
                            data=self.training_params['save_liquid_data_path'],
                            imgsz=self.training_params['imgsz'],
                            epochs=self.training_params['epochs'],
                            batch=batch_size,
                            workers=workers,
                            device=device_str,
                            optimizer=self.training_params['optimizer'],
                            close_mosaic=self.training_params['close_mosaic'],
                            resume=self.training_params['resume'],
                            project=model_output_dir,
                            name='',  # 空名称，直接使用project目录
                            single_cls=self.training_params['single_cls'],
                            cache=False,
                            pretrained=self.training_params['pretrained'],
                            verbose=True,  # 启用原生进度条显示
                            save_period=-1,  # -1表示只保存best和last，不保存每个epoch
                            amp=amp_enabled,
                            plots=True,
                            exist_ok=True,
                            patience=100
                        )
                        
                    except KeyboardInterrupt:
                        # 用户停止训练，这是正常的停止操作
                        self.log_output.emit("\n训练已按用户要求停止\n")
                        # 等待YOLO完成当前epoch并保存模型
                        import time
                        self.log_output.emit("等待当前epoch完成并保存模型...\n")
                        time.sleep(2)  # 给YOLO时间完成保存
                        training_success = True  # 标记为成功，因为这是用户主动停止
                        
                        # 获取实际保存目录并转换模型
                        try:
                            save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
                            
                            if save_dir:
                                save_dir_abs = os.path.abspath(str(save_dir))
                                weights_dir = os.path.abspath(os.path.join(save_dir_abs, "weights"))
                                self.training_report["weights_dir"] = weights_dir
                                
                                # 立即转换PT文件为DAT格式并删除PT文件
                                self.log_output.emit(f"\n[调试] ========== 准备调用转换和删除方法 ==========\n")
                                self.log_output.emit(f"[调试] 调用位置: 训练完成 - 正常路径\n")
                                self.log_output.emit(f"[调试] Weights目录: {weights_dir}\n")
                                self._convertPtToDatAndCleanup(weights_dir)
                                self.log_output.emit(f"[调试] 转换和删除方法调用完成\n")
                                
                                # 整理训练结果文件
                                self._organizeTrainingResults(save_dir_abs)
                            else:
                                # 备用方案：使用预设的model_output_dir
                                self.log_output.emit("\n[WARNING] 无法从trainer获取保存目录，使用预设目录\n")
                                if 'model_output_dir' in locals():
                                    # 查找实际的weights目录（可能在train子目录下）
                                    possible_weights_dirs = [
                                        os.path.join(model_output_dir, "train", "weights"),
                                        os.path.join(model_output_dir, "weights")
                                    ]
                                    for possible_dir in possible_weights_dirs:
                                        if os.path.exists(possible_dir):
                                            weights_dir = possible_dir
                                            self.training_report["weights_dir"] = weights_dir
                                            self.log_output.emit(f"\n[调试] ========== 准备调用转换和删除方法 ==========\n")
                                            self.log_output.emit(f"[调试] 调用位置: 训练完成 - 备用路径\n")
                                            self.log_output.emit(f"[调试] Weights目录: {weights_dir}\n")
                                            self._convertPtToDatAndCleanup(weights_dir)
                                            self.log_output.emit(f"[调试] 转换和删除方法调用完成\n")
                                            break
                                    else:
                                        self.log_output.emit(f"[ERROR] 未找到权重目录，跳过转换\n")
                                else:
                                    self.log_output.emit(f"[ERROR] model_output_dir 未定义，跳过转换\n")
                        except Exception as convert_err:
                            self.log_output.emit(f"\n[ERROR] 转换过程出错: {convert_err}\n")
                            import traceback
                            self.log_output.emit(traceback.format_exc())
                        
                        break  # 跳出重试循环
                        
                    except Exception as e:
                        # 如果训练失败，尝试备用方法
                        self.log_output.emit(f"训练启动失败: {str(e)}\n")
                        self.log_output.emit("尝试备用方法...\n")
                        try:
                            mission_results = model.train(
                                data=self.training_params['save_liquid_data_path'],
                                epochs=self.training_params['epochs'],
                                batch=max(1, batch_size // 2),
                                device=device_str,
                                workers=0,
                                verbose=True,
                                save_period=1  # 每个epoch都保存模型
                            )
                        except KeyboardInterrupt:
                            # 备用方法中用户也停止了训练
                            self.log_output.emit("\n训练已按用户要求停止\n")
                            # 等待YOLO完成当前epoch并保存模型
                            import time
                            self.log_output.emit("等待当前epoch完成并保存模型...\n")
                            time.sleep(2)  # 给YOLO时间完成保存
                            training_success = True
                            
                            # 获取实际保存目录并转换模型
                            try:
                                save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
                                
                                if save_dir:
                                    save_dir_abs = os.path.abspath(str(save_dir))
                                    weights_dir = os.path.abspath(os.path.join(save_dir_abs, "weights"))
                                    self.training_report["weights_dir"] = weights_dir
                                    
                                    # 立即转换PT文件为DAT格式并删除PT文件
                                    self.log_output.emit(f"\n[调试] ========== 准备调用转换和删除方法 ==========\n")
                                    self.log_output.emit(f"[调试] 调用位置: 继续训练完成 - 正常路径\n")
                                    self.log_output.emit(f"[调试] Weights目录: {weights_dir}\n")
                                    self._convertPtToDatAndCleanup(weights_dir)
                                    self.log_output.emit(f"[调试] 转换和删除方法调用完成\n")
                                    
                                    # 整理训练结果文件
                                    self._organizeTrainingResults(save_dir_abs)
                                else:
                                    # 备用方案：使用预设的model_output_dir
                                    self.log_output.emit("\n[WARNING] 无法从trainer获取保存目录，使用预设目录\n")
                                    if 'model_output_dir' in locals():
                                        # 查找实际的weights目录（可能在train子目录下）
                                        possible_weights_dirs = [
                                            os.path.join(model_output_dir, "train", "weights"),
                                            os.path.join(model_output_dir, "weights")
                                        ]
                                        for possible_dir in possible_weights_dirs:
                                            if os.path.exists(possible_dir):
                                                weights_dir = possible_dir
                                                self.training_report["weights_dir"] = weights_dir
                                                self.log_output.emit(f"\n[调试] ========== 准备调用转换和删除方法 ==========\n")
                                                self.log_output.emit(f"[调试] 调用位置: 继续训练完成 - 备用路径\n")
                                                self.log_output.emit(f"[调试] Weights目录: {weights_dir}\n")
                                                self._convertPtToDatAndCleanup(weights_dir)
                                                self.log_output.emit(f"[调试] 转换和删除方法调用完成\n")
                                                break
                                        else:
                                            self.log_output.emit(f"[ERROR] 未找到权重目录，跳过转换\n")
                                    else:
                                        self.log_output.emit(f"[ERROR] model_output_dir 未定义，跳过转换\n")
                            except Exception as convert_err:
                                self.log_output.emit(f"\n[ERROR] 转换过程出错: {convert_err}\n")
                                import traceback
                                self.log_output.emit(traceback.format_exc())
                            
                            break
                    
                    # 训练成功
                    training_success = True
                    # 保存基本结果路径到报告
                    try:
                        # Ultralytics 会把保存目录置于 model.trainer.save_dir
                        save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
                        if save_dir:
                            save_dir_abs = os.path.abspath(str(save_dir))
                            weights_dir = os.path.abspath(os.path.join(save_dir_abs, "weights"))
                            self.training_report["weights_dir"] = weights_dir
                            
                            # 立即转换PT文件为DAT格式并删除PT文件
                            self.log_output.emit(f"\n[调试] ========== 准备调用转换和删除方法 ==========\n")
                            self.log_output.emit(f"[调试] 调用位置: 用户停止训练\n")
                            self.log_output.emit(f"[调试] Weights目录: {weights_dir}\n")
                            self._convertPtToDatAndCleanup(weights_dir)
                            self.log_output.emit(f"[调试] 转换和删除方法调用完成\n")
                            
                            # 整理训练结果文件：将train目录下的其他文件移动到training_results目录
                            self._organizeTrainingResults(save_dir_abs)
                        else:
                            self.log_output.emit("\n[WARNING] 无法获取模型保存目录，跳过转换\n")
                    except Exception as convert_err:
                        self.log_output.emit(f"\n[ERROR] 转换过程出错: {convert_err}\n")
                        import traceback
                        self.log_output.emit(traceback.format_exc())
                    break  # 跳出重试循环
                    
                except RuntimeError as runtime_error:
                    error_msg = str(runtime_error)
                    
                    # 检查是否是CUDA OOM错误
                    if 'out of memory' in error_msg.lower() or 'cuda' in error_msg.lower():
                        # 如果是OOM错误且还有重试机会，自动降低batch size重试
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            # 降低batch size
                            if batch_size > 1:
                                new_batch = max(1, batch_size // 2)
                                self.log_output.emit(f"\n" + "="*70 + "\n")
                                self.log_output.emit(f"GPU显存不足（OOM）错误！\n\n")
                                self.log_output.emit(f"自动降低batch size: {batch_size} -> {new_batch}\n")
                                self.log_output.emit(f"准备重试训练（第 {retry_count}/{max_retries-1} 次）...\n")
                                self.log_output.emit("="*70 + "\n\n")
                                batch_size = new_batch
                                continue  # 重试
                            else:
                                # batch size已经是1，无法再降低
                                self.log_output.emit(f"\n" + "="*70 + "\n")
                                self.log_output.emit(f"GPU显存不足（OOM）错误！\n\n")
                                self.log_output.emit(f"batch size已经是1，无法继续降低\n")
                                self.log_output.emit(f"请尝试：\n")
                                self.log_output.emit(f"   1. 减小图像尺寸（当前: {imgsz}）\n")
                                self.log_output.emit(f"   2. 关闭数据缓存\n")
                                self.log_output.emit(f"   3. 减少workers数量（当前: {self.training_params['workers']}）\n")
                                self.log_output.emit(f"   4. 关闭其他占用GPU的程序\n")
                                self.log_output.emit("="*70 + "\n")
                                self.training_finished.emit(False)
                                raise runtime_error
                        else:
                            # 重试次数用完，输出详细错误信息并抛出异常
                            self.log_output.emit(f"\n" + "="*70 + "\n")
                            self.log_output.emit(f"GPU显存不足（OOM）错误！\n\n")
                            self.log_output.emit(f"已重试 {max_retries-1} 次，仍无法解决显存问题\n")
                            raise runtime_error
                    else:
                        # 其他运行时错误，直接抛出
                        raise runtime_error
                        
                except KeyboardInterrupt as kb_error:
                    # 用户停止训练的异常
                    self.log_output.emit(f"\n" + "="*60 + "\n")
                    self.log_output.emit("训练已按用户要求停止\n")
                    self.log_output.emit("="*60 + "\n")
                    
                    # 强制保存当前模型
                    try:
                        self.log_output.emit("正在保存当前训练进度...\n")
                        weights_dir = self.training_report.get("weights_dir")
                        if weights_dir and os.path.exists(weights_dir):
                            last_pt = os.path.join(weights_dir, "last.pt")
                            
                            # 方法1：直接保存模型权重（不依赖results.csv）
                            saved = False
                            if hasattr(model, 'save'):
                                try:
                                    model.save(last_pt)
                                    saved = True
                                    self.log_output.emit(f"✓ 模型已保存到: {last_pt}\n")
                                except Exception as save_error:
                                    self.log_output.emit(f"⚠ model.save()失败: {save_error}，尝试备用方法...\n")
                            
                            # 方法2：备用方法 - 保存checkpoint
                            if not saved and hasattr(model, 'trainer') and model.trainer:
                                try:
                                    import torch
                                    ckpt = {
                                        'epoch': model.trainer.epoch if hasattr(model.trainer, 'epoch') else 0,
                                        'model': model.model.state_dict() if hasattr(model, 'model') else model.state_dict(),
                                    }
                                    torch.save(ckpt, last_pt)
                                    saved = True
                                    self.log_output.emit(f"✓ checkpoint已保存到: {last_pt}\n")
                                except Exception as ckpt_error:
                                    self.log_output.emit(f"⚠ checkpoint保存失败: {ckpt_error}\n")
                            
                            if not saved:
                                self.log_output.emit("⚠ 所有保存方法均失败\n")
                            else:
                                # 保存成功后，立即转换为DAT并删除PT
                                self.log_output.emit("\n[调试] ========== 保存检查点后转换并删除PT ==========\n")
                                self.log_output.emit(f"[调试] 检查点已保存，开始转换为DAT格式...\n")
                                self._convertPtToDatAndCleanup(weights_dir)
                                self.log_output.emit(f"[调试] 检查点转换和删除完成\n")
                        else:
                            self.log_output.emit(f"⚠ 权重目录不存在: {weights_dir}\n")
                    except Exception as save_error:
                        self.log_output.emit(f"⚠ 保存模型失败: {save_error}\n")
                    
                    self.training_report["status"] = "stopped_by_user"
                    
                    # 标记为用户手动停止
                    self._is_user_stopped = True
                    
                    # 用户主动停止发送 False，但在 _onTrainingFinished 中会根据 _is_user_stopped 判断是否进入继续模式
                    self.training_finished.emit(False)
                    return  # 直接返回，不继续执行
                    
                except Exception as train_error:
                    # 其他异常，直接抛出
                    raise train_error
            
            # 如果训练成功，继续后续处理
            if training_success:
                # 训练完成
                if self.is_running:
                    self.log_output.emit("\n" + "="*60 + "\n")
                    self.log_output.emit(" 训练正常完成！\n")
                    self.log_output.emit("="*60 + "\n")
                    # 标记报告
                    self.training_report["status"] = "success"
                    # 尝试转换pt->dat后，将列表加入报告
                    try:
                        if self.training_params.get('exp_name'):
                            # 这里不能直接访问外层 Handler 的方法，仅标记占位；实际转换在 _onTrainingFinished 中执行
                            # 因此我们在报告里预留字段，稍后 _onTrainingFinished 会覆盖写入最终报告
                            self.training_report.setdefault("converted_dat_files", [])
                    except Exception:
                        pass
                    self.training_finished.emit(True)
                else:
                    # 用户停止训练（is_running=False）
                    self.log_output.emit("\n" + "="*60 + "\n")
                    self.log_output.emit("训练已按用户要求停止\n")
                    self.log_output.emit("="*60 + "\n")
                    
                    # 强制保存当前模型
                    try:
                        self.log_output.emit("正在保存当前训练进度...\n")
                        weights_dir = self.training_report.get("weights_dir")
                        if weights_dir and os.path.exists(weights_dir):
                            last_pt = os.path.join(weights_dir, "last.pt")
                            
                            # 方法1：直接保存模型权重（不依赖results.csv）
                            saved = False
                            if hasattr(model, 'save'):
                                try:
                                    model.save(last_pt)
                                    saved = True
                                    self.log_output.emit(f"✓ 模型已保存到: {last_pt}\n")
                                except Exception as save_error:
                                    self.log_output.emit(f"⚠ model.save()失败: {save_error}，尝试备用方法...\n")
                            
                            # 方法2：备用方法 - 保存checkpoint
                            if not saved and hasattr(model, 'trainer') and model.trainer:
                                try:
                                    import torch
                                    ckpt = {
                                        'epoch': model.trainer.epoch if hasattr(model.trainer, 'epoch') else 0,
                                        'model': model.model.state_dict() if hasattr(model, 'model') else model.state_dict(),
                                    }
                                    torch.save(ckpt, last_pt)
                                    saved = True
                                    self.log_output.emit(f"✓ checkpoint已保存到: {last_pt}\n")
                                except Exception as ckpt_error:
                                    self.log_output.emit(f"⚠ checkpoint保存失败: {ckpt_error}\n")
                            
                            if not saved:
                                self.log_output.emit("⚠ 所有保存方法均失败\n")
                            else:
                                # 保存成功后，立即转换为DAT并删除PT
                                self.log_output.emit("\n[调试] ========== 保存检查点后转换并删除PT ==========\n")
                                self.log_output.emit(f"[调试] 检查点已保存，开始转换为DAT格式...\n")
                                self._convertPtToDatAndCleanup(weights_dir)
                                self.log_output.emit(f"[调试] 检查点转换和删除完成\n")
                        else:
                            self.log_output.emit(f"⚠ 权重目录不存在: {weights_dir}\n")
                    except Exception as save_error:
                        self.log_output.emit(f"⚠ 保存模型失败: {save_error}\n")
                    
                    self.training_report["status"] = "stopped_by_user"
                    self._is_user_stopped = True
                    # 用户主动停止发送 False，但在 _onTrainingFinished 中会根据 _is_user_stopped 判断是否进入继续模式
                    self.training_finished.emit(False)
                
        except KeyboardInterrupt as kb_error:
            # 用户停止训练的异常（最外层捕获）
            self.log_output.emit(f"\n" + "="*60 + "\n")
            self.log_output.emit("训练已按用户要求停止\n")
            self.log_output.emit("="*60 + "\n")
            
            # 强制保存当前模型
            try:
                self.log_output.emit("正在保存当前训练进度...\n")
                if 'model' in locals():
                    weights_dir = self.training_report.get("weights_dir")
                    if weights_dir and os.path.exists(weights_dir):
                        last_pt = os.path.join(weights_dir, "last.pt")
                        
                        # 方法1：直接保存模型权重（不依赖results.csv）
                        saved = False
                        if hasattr(model, 'save'):
                            try:
                                model.save(last_pt)
                                saved = True
                                self.log_output.emit(f"✓ 模型已保存到: {last_pt}\n")
                            except Exception as save_error:
                                self.log_output.emit(f"⚠ model.save()失败: {save_error}，尝试备用方法...\n")
                        
                        # 方法2：备用方法 - 保存checkpoint
                        if not saved and hasattr(model, 'trainer') and model.trainer:
                            try:
                                import torch
                                ckpt = {
                                    'epoch': model.trainer.epoch if hasattr(model.trainer, 'epoch') else 0,
                                    'model': model.model.state_dict() if hasattr(model, 'model') else model.state_dict(),
                                }
                                torch.save(ckpt, last_pt)
                                saved = True
                                self.log_output.emit(f"✓ checkpoint已保存到: {last_pt}\n")
                            except Exception as ckpt_error:
                                self.log_output.emit(f"⚠ checkpoint保存失败: {ckpt_error}\n")
                        
                        if not saved:
                            self.log_output.emit("⚠ 所有保存方法均失败\n")
                        else:
                            # 保存成功后，立即转换为DAT并删除PT
                            self.log_output.emit("\n[调试] ========== 保存检查点后转换并删除PT ==========\n")
                            self.log_output.emit(f"[调试] 检查点已保存，开始转换为DAT格式...\n")
                            self._convertPtToDatAndCleanup(weights_dir)
                            self.log_output.emit(f"[调试] 检查点转换和删除完成\n")
                    else:
                        self.log_output.emit(f"⚠ 权重目录不存在: {weights_dir}\n")
                else:
                    self.log_output.emit("⚠ model对象不存在，无法保存\n")
            except Exception as save_error:
                self.log_output.emit(f"⚠ 保存模型失败: {save_error}\n")
            
            self.training_report["status"] = "stopped_by_user"
            
            # 标记为用户手动停止，确保按钮状态正确切换
            self._is_user_stopped = True
            
            # 用户主动停止发送 False，但在 _onTrainingFinished 中会根据 _is_user_stopped 判断是否进入继续模式
            self.training_finished.emit(False)
            
        except Exception as e:
            error_msg = str(e)
            self.log_output.emit(f"\n" + "="*60 + "\n")
            self.log_output.emit(f" 升级失败: {error_msg}\n")
            self.log_output.emit("="*60 + "\n")
            
            # 检查常见错误
            error_lower = error_msg.lower()
            
            if 'dataset' in error_lower or 'images not found' in error_lower or 'missing path' in error_lower:
                self.log_output.emit(f"\n 数据集路径错误！\n")
                self.log_output.emit(f" 请检查 data.yaml 中的 train 和 val 路径是否正确。\n")
                self.log_output.emit(f" 确保路径下存在图片文件。\n")
            
            if 'file not found' in error_lower or 'no such file' in error_lower:
                self.log_output.emit(f"\n 文件未找到错误！\n")
                self.log_output.emit(f" 请检查数据集路径是否正确。\n")
            
            # 输出详细错误信息
            import traceback
            full_traceback = traceback.format_exc()
            self.log_output.emit(f"\n详细错误信息：\n{full_traceback}\n")
            
            # 标记报告
            self.training_report["status"] = "failed"
            self.training_report["error"] = error_msg
            self.training_finished.emit(False)
        finally:
            # 记录结束时间并落盘报告
            import time as _time_mod2, json as _json_mod2
            self.training_report["end_time"] = _time_mod2.time()
            # 写入 report 到模型输出目录
            try:
                model_output_dir = self.training_report.get("model_output_dir")
                if model_output_dir and os.path.exists(model_output_dir):
                    report_path = os.path.join(model_output_dir, "training_report.json")
                    with open(report_path, "w", encoding="utf-8") as rf:
                        _json_mod2.dump(self.training_report, rf, ensure_ascii=False, indent=2)
                    self.log_output.emit(f"训练报告已保存: {report_path}\n")
            except Exception as e:
                self.log_output.emit(f"[警告] 保存训练报告失败: {e}\n")
            # 恢复原始stdout/stderr
            import sys
            if original_stdout is not None and original_stderr is not None:
                try:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                except Exception as e:
                    pass
            
            # 清理临时文件
            if temp_model_path:
                import os
                if os.path.exists(temp_model_path):
                    try:
                        os.remove(temp_model_path)
                    except Exception as e:
                        pass
    
    def _convertPtToDatAndCleanup(self, weights_dir):
        """
        转换PT文件为DAT格式并删除原始PT文件
        
        Args:
            weights_dir: 权重目录路径
        """
        self.log_output.emit("\n" + "="*70 + "\n")
        self.log_output.emit("[调试-Worker] _convertPtToDatAndCleanup 方法被调用\n")
        self.log_output.emit(f"[调试-Worker] 权重目录: {weights_dir}\n")
        self.log_output.emit("="*70 + "\n")
        
        try:
            if not os.path.exists(weights_dir):
                self.log_output.emit("[调试-Worker] 权重目录不存在，退出\n")
                return
            
            self.log_output.emit("[调试-Worker] 正在创建PT到DAT转换器...\n")
            # 创建转换器
            converter = PtToDatConverter(key=MODEL_ENCRYPTION_KEY)
            self.log_output.emit("[调试-Worker] 转换器创建成功\n")
            
            # 查找所有.pt文件
            pt_files = []
            self.log_output.emit("[调试-Worker] 开始扫描PT文件...\n")
            for filename in os.listdir(weights_dir):
                if filename.endswith('.pt'):
                    pt_file_path = os.path.join(weights_dir, filename)
                    pt_files.append(pt_file_path)
                    self.log_output.emit(f"[调试-Worker] 发现PT文件: {filename}\n")
            
            if not pt_files:
                self.log_output.emit("[调试-Worker] 未发现PT文件，退出\n")
                return
            
            self.log_output.emit(f"[调试-Worker] 共发现 {len(pt_files)} 个PT文件\n")
            
            # 转换每个.pt文件
            converted_files = []
            self.log_output.emit("\n[调试-Worker] 开始转换PT文件...\n")
            for pt_file in pt_files:
                try:
                    filename = os.path.basename(pt_file)
                    self.log_output.emit(f"\n[调试-Worker] 处理文件: {filename}\n")
                    
                    # 生成输出文件名（使用.dat扩展名）
                    exp_name = self.training_params.get('exp_name', '')
                    base_name = os.path.splitext(filename)[0]
                    self.log_output.emit(f"[调试-Worker] 实验名称: {exp_name}\n")
                    self.log_output.emit(f"[调试-Worker] 基础名称: {base_name}\n")
                    
                    if exp_name:
                        # 例如: best.pt -> best.template_1234.dat
                        output_filename = f"{base_name}.{exp_name}.dat"
                    else:
                        # 例如: best.pt -> best.dat
                        output_filename = f"{base_name}.dat"
                    
                    output_path = os.path.join(weights_dir, output_filename)
                    self.log_output.emit(f"[调试-Worker] 输出路径: {output_filename}\n")
                    
                    # 执行转换
                    self.log_output.emit(f"[调试-Worker] 开始转换 {filename}...\n")
                    converted_path = converter.convert_file(pt_file, output_path)
                    converted_files.append(converted_path)
                    self.log_output.emit(f"[调试-Worker] ✓ 转换成功: {output_filename}\n")
                    
                    # 删除原始.pt文件（增强版：重试机制）
                    self.log_output.emit(f"\n[调试-Worker] ========== 开始删除PT文件 ==========\n")
                    self.log_output.emit(f"[调试-Worker] 目标文件: {pt_file}\n")
                    import time
                    import gc
                    
                    # 先等待确保转换完成
                    self.log_output.emit(f"[调试-Worker] 等待0.5秒确保转换完成...\n")
                    time.sleep(0.5)
                    
                    # 强制垃圾回收，释放可能的文件句柄
                    self.log_output.emit(f"[调试-Worker] 执行垃圾回收...\n")
                    gc.collect()
                    time.sleep(0.3)
                    
                    deleted = False
                    last_error = None
                    
                    self.log_output.emit(f"[调试-Worker] 开始10次删除重试...\n")
                    for attempt in range(10):  # 增加到10次重试
                        self.log_output.emit(f"[调试-Worker]   第 {attempt+1}/10 次删除尝试...\n")
                        try:
                            if os.path.exists(pt_file):
                                self.log_output.emit(f"[调试-Worker]   文件存在，尝试删除...\n")
                                os.remove(pt_file)
                                deleted = True
                                self.log_output.emit(f"[调试-Worker]   ✓✓✓ 删除成功！\n")
                                self.log_output.emit(f"[转换] 已删除原始文件: {filename}\n")
                                break
                            else:
                                # 文件已不存在
                                self.log_output.emit(f"[调试-Worker]   文件不存在（可能已被删除）\n")
                                deleted = True
                                break
                        except Exception as del_error:
                            last_error = str(del_error)
                            self.log_output.emit(f"[调试-Worker]   ✗ 删除失败: {last_error}\n")
                            if attempt < 9:
                                # 每次重试前强制垃圾回收
                                self.log_output.emit(f"[调试-Worker]   执行垃圾回收并等待0.5秒...\n")
                                gc.collect()
                                time.sleep(0.5)  # 增加等待时间到0.5秒
                            else:
                                # 最后一次失败，输出错误日志
                                self.log_output.emit(f"\n[警告] ========== 删除失败 ==========\n")
                                self.log_output.emit(f"[警告] 无法删除PT文件: {filename}\n")
                                self.log_output.emit(f"  错误: {last_error}\n")
                                self.log_output.emit(f"  路径: {pt_file}\n")
                                self.log_output.emit(f"  请手动删除该文件\n")
                                self.log_output.emit(f"[警告] ====================================\n")
                    
                    if not deleted:
                        self.log_output.emit(f"[调试-Worker] ========== PT文件删除失败 ==========\n")
                        # 记录删除失败的文件
                        if "failed_deletions" not in self.training_report:
                            self.training_report["failed_deletions"] = []
                        self.training_report["failed_deletions"].append({
                            "file": pt_file,
                            "error": last_error
                        })
                    else:
                        self.log_output.emit(f"[调试-Worker] ========== PT文件删除成功 ==========\n")
                    
                except Exception as convert_error:
                    self.log_output.emit(f"[调试-Worker] ✗ 转换异常: {str(convert_error)}\n")
                    import traceback
                    self.log_output.emit(f"[调试-Worker] 详细错误:\n{traceback.format_exc()}\n")
                    continue
            
            # 更新训练报告
            self.training_report["converted_dat_files"] = converted_files
            self.log_output.emit(f"\n[调试-Worker] _convertPtToDatAndCleanup 执行完成\n")
            self.log_output.emit(f"[调试-Worker] 共转换 {len(converted_files)} 个文件\n")
            self.log_output.emit("="*70 + "\n\n")
            
        except Exception as e:
            self.log_output.emit(f"\n[调试-Worker] ✗✗✗ _convertPtToDatAndCleanup 发生异常: {str(e)}\n")
            import traceback
            self.log_output.emit(f"[调试-Worker] 详细错误:\n{traceback.format_exc()}\n")
            self.log_output.emit("="*70 + "\n\n")
    
    def _organizeTrainingResults(self, train_dir):
        """
        整理训练结果文件：将train目录下的文件（除weights）移动到training_results目录
        
        Args:
            train_dir: train目录路径（例如：database/model/detection_model/6/train）
        """
        try:
            import shutil
            
            # 获取training_results目录路径
            training_results_dir = self.training_report.get("training_results_dir")
            if not training_results_dir:
                self.log_output.emit("\n[WARNING] training_results_dir未设置，跳过文件整理\n")
                return
            
            # 创建training_results目录
            os.makedirs(training_results_dir, exist_ok=True)
            
            self.log_output.emit(f"\n正在整理训练结果文件...\n")
            self.log_output.emit(f"  源目录: {train_dir}\n")
            self.log_output.emit(f"  目标目录: {training_results_dir}\n")
            
            # 遍历train目录下的所有文件和子目录
            moved_count = 0
            for item in os.listdir(train_dir):
                if item == 'weights':
                    # 跳过weights目录，.dat文件保留在train/weights中
                    continue
                
                source_path = os.path.join(train_dir, item)
                target_path = os.path.join(training_results_dir, item)
                
                try:
                    if os.path.isfile(source_path):
                        # 移动文件
                        shutil.move(source_path, target_path)
                        self.log_output.emit(f"  移动文件: {item}\n")
                        moved_count += 1
                    elif os.path.isdir(source_path):
                        # 移动目录（如plots目录）
                        if os.path.exists(target_path):
                            shutil.rmtree(target_path)
                        shutil.move(source_path, target_path)
                        self.log_output.emit(f"  移动目录: {item}/\n")
                        moved_count += 1
                except Exception as move_error:
                    self.log_output.emit(f"  [WARNING] 移动失败 {item}: {move_error}\n")
            
            self.log_output.emit(f"文件整理完成，共移动 {moved_count} 项\n")
            self.log_output.emit(f"  - .dat文件位置: {os.path.join(train_dir, 'weights')}\n")
            self.log_output.emit(f"  - 训练结果位置: {training_results_dir}\n\n")
            
        except Exception as e:
            self.log_output.emit(f"\n[ERROR] 整理训练结果文件失败: {e}\n")
            import traceback
            self.log_output.emit(traceback.format_exc())
    
    def stop_training(self):
        """停止训练"""
        self.is_running = False
    
    def has_training_started(self):
        """检查训练是否已经真正开始"""
        return self.training_actually_started
