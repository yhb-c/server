# -*- coding: utf-8 -*-

"""
模型训练处理器

处理模型训练相关的所有功能
"""

import os
import yaml
import json
import threading
import tempfile
import struct
import hashlib
from pathlib import Path
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import QtGui

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
    from ...config import get_project_root, get_temp_models_dir, get_train_dir
except (ImportError, ValueError):
    try:
        from client.config import get_project_root, get_temp_models_dir, get_train_dir
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from client.config import get_project_root, get_temp_models_dir, get_train_dir

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

# 导入 TrainingWorker 类
try:
    from .model_trainingworker_handler import TrainingWorker
except (ImportError, ValueError):
    try:
        from handlers.modelpage.model_trainingworker_handler import TrainingWorker
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from handlers.modelpage.model_trainingworker_handler import TrainingWorker

# 导入 ModelTestHandler 类
try:
    from .model_test_handler import ModelTestHandler
except (ImportError, ValueError):
    try:
        from handlers.modelpage.model_test_handler import ModelTestHandler
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from handlers.modelpage.model_test_handler import ModelTestHandler

# 导入全局字体管理器
try:
    from ...widgets.style_manager import FontManager
except (ImportError, ValueError):
    try:
        from widgets.style_manager import FontManager
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from widgets.style_manager import FontManager

MODEL_FILE_SIGNATURE = b'LDS_MODEL_FILE'
MODEL_FILE_VERSION = 1
MODEL_ENCRYPTION_KEY = "liquid_detection_system_2024"




class ModelTrainingHandler(ModelTestHandler):
    """
    模型训练处理器
    
    处理模型训练相关的所有功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型训练处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self.main_window = None
        self.training_worker = None
        self.training_active = False
        self.current_exp_name = None
        self.temp_trained_models = []
        self.train_config = None
        self._is_user_stopped = False  # 标记用户是否手动停止训练
        self.annotation_engine = None  # 标注引擎
        self.annotation_widget = None  # 标注界面组件
        self.test_detection_window = None  # 测试检测窗口
        
        # 加载训练配置
        self._loadTrainingConfig()

        # 初始化.pt -> .dat 转换器
        try:
            self.file_converter = PtToDatConverter()
        except Exception as e:
            self.file_converter = None
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self.main_window = main_window
    
    def _loadTrainingConfig(self):
        """加载训练配置"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(current_dir, "..", "..", "database", "config", "train_configs")
            self.config_file_path = os.path.join(config_dir, "default_config.json")
            
            if not os.path.exists(self.config_file_path):
                self.train_config = None
                return
            
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                self.train_config = json.load(f)
            
        except Exception as e:
            self.train_config = None
    
    def _onStartTraining(self, training_params):
        """开始训练"""
        try:
            # 验证参数
            if not training_params.get('base_model'):
                QtWidgets.QMessageBox.critical(self.main_window, "参数错误", "未找到可用的基础模型文件")
                return False
            
            if not training_params.get('save_liquid_data_path'):
                QtWidgets.QMessageBox.critical(self.main_window, "参数错误", "未选择数据集文件夹，请至少添加一个数据集文件夹")
                return False
            
            if not training_params.get('exp_name'):
                QtWidgets.QMessageBox.critical(self.main_window, "参数错误", "请输入模型名称")
                return False
            
            # 检查CUDA可用性
            device = training_params.get('device', '0')
            if device != 'cpu':
                try:
                    import torch
                    if not torch.cuda.is_available():
                        # CUDA不可用，提示用户
                        from utils.message_box_utils import showQuestion
                        use_cpu = showQuestion(
                            self.main_window,
                            "CUDA不可用",
                            "检测到系统没有可用的CUDA/GPU。\n\n"
                            "可能原因：\n"
                            "1. 未安装NVIDIA显卡驱动\n"
                            "2. 未安装CUDA toolkit\n"
                            "3. PyTorch是CPU版本\n\n"
                            "是否使用CPU进行训练？\n"
                            "（CPU训练速度较慢，建议先安装CUDA）"
                        )
                        if use_cpu:
                            training_params['device'] = 'cpu'
                            self._appendLog("\n已切换到CPU训练模式\n")
                        else:
                            return False
                except ImportError:
                    pass
            
            # 验证文件是否存在
            base_model = training_params['base_model']
            save_liquid_data_path = training_params['save_liquid_data_path']
            
            if not os.path.exists(base_model):
                QtWidgets.QMessageBox.critical(self.main_window, "文件错误", 
                    f"基础模型文件不存在\n文件路径: {base_model}\n请检查文件路径是否正确,或重新选择模型文件。")
                return False
            
            # 解析数据集文件夹列表（用分号分隔）
            dataset_folders = [f.strip() for f in save_liquid_data_path.split(';') if f.strip()]
            
            if not dataset_folders:
                QtWidgets.QMessageBox.critical(self.main_window, "参数错误", "未选择数据集文件夹，请至少添加一个数据集文件夹")
                return False
            
            # 验证每个数据集文件夹是否存在
            invalid_folders = []
            for folder in dataset_folders:
                if not os.path.exists(folder):
                    invalid_folders.append(folder)
            
            if invalid_folders:
                QtWidgets.QMessageBox.critical(
                    self.main_window, 
                    "文件夹错误", 
                    f"以下数据集文件夹不存在：\n\n" + "\n".join(invalid_folders) + 
                    "\n\n请检查文件夹路径是否正确，或重新选择数据集文件夹。"
                )
                return False
            
            # 验证数据集文件夹内容
            validation_result, validation_msg = self._validateDatasetFolders(dataset_folders)
            if not validation_result:
                QtWidgets.QMessageBox.critical(
                    self.main_window, 
                    "数据集验证失败", 
                    f"数据集验证失败：\n\n{validation_msg}\n\n请检查数据集文件夹内容。"
                )
                return False
            
            # 确认对话框
            confirm_msg = f"确定要开始升级模型吗？\n\n"
            confirm_msg += f"基础模型: {os.path.basename(base_model)}\n"
            confirm_msg += f"数据集文件夹数量: {len(dataset_folders)}\n"
            for i, folder in enumerate(dataset_folders, 1):
                confirm_msg += f"  {i}. {os.path.basename(folder)}\n"
            confirm_msg += f"图像尺寸: {training_params['imgsz']}\n"
            confirm_msg += f"训练轮数: {training_params['epochs']}\n"
            confirm_msg += f"批次大小: {training_params['batch']}\n"
            confirm_msg += f"模型名称: {training_params['exp_name']}"
            
            # 创建对话框并设置model图标
            msg_box = QtWidgets.QMessageBox(self.main_window)
            msg_box.setWindowTitle("确认升级")
            msg_box.setText(confirm_msg)
            msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
            
            # 设置窗口左上角图标为 model.png
            try:
                project_root = get_project_root()
                model_icon_path = os.path.join(project_root, 'resources', 'icons', 'model.png')
                if os.path.exists(model_icon_path):
                    msg_box.setWindowIcon(QtGui.QIcon(model_icon_path))
            except Exception as e:
                pass
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
            
            # 设置中文按钮文本
            yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
            no_btn = msg_box.button(QtWidgets.QMessageBox.No)
            if yes_btn:
                yes_btn.setText("是")
            if no_btn:
                no_btn.setText("否")
            
            reply = msg_box.exec_()
            
            if reply == QtWidgets.QMessageBox.Yes:
                return self._startTrainingWorker(training_params)
            
            return False
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"启动训练失败: {str(e)}")
            return False
    
    def _startTrainingWorker(self, training_params):
        """启动训练工作线程"""
        try:
            # 检查是否已有训练在进行中
            if self.training_active and self.training_worker:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "提示", 
                    "训练正在进行中，请先停止当前训练"
                )
                return False
            
            # 禁止自动下载yolo11模型
            os.environ['YOLO_AUTODOWNLOAD'] = '0'
            os.environ['YOLO_OFFLINE'] = '1'
            
            # 重置用户停止标记
            self._is_user_stopped = False
            self._is_stopping = False  # 标记训练是否正在停止中
            
            # 如果面板处于"继续训练"模式，切换回"停止升级"模式
            if hasattr(self, 'training_panel'):
                if hasattr(self.training_panel, '_is_training_stopped') and self.training_panel._is_training_stopped:
                    if hasattr(self.training_panel, 'switchToStopMode'):
                        self.training_panel.switchToStopMode()
            
            # 清空日志
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_log_text'):
                self.training_panel.train_log_text.clear()
            
            # 处理多数据集文件夹合并
            dataset_folders = [f.strip() for f in training_params['save_liquid_data_path'].split(';') if f.strip()]
            if len(dataset_folders) > 1:
                self._appendLog("检测到多个数据集文件夹，正在合并...\n")
                merged_data_yaml = self._mergeMultipleDatasets(dataset_folders, training_params['exp_name'])
                if merged_data_yaml:
                    training_params['save_liquid_data_path'] = merged_data_yaml
                    self._appendLog(f"数据集合并完成: {merged_data_yaml}\n")
                else:
                    QtWidgets.QMessageBox.critical(self.main_window, "错误", "数据集合并失败")
                    return False
            elif len(dataset_folders) == 1:
                # 单个数据集文件夹，需要创建data.yaml文件
                single_folder = dataset_folders[0]
                data_yaml_path = self._createDataYamlForSingleFolder(single_folder, training_params['exp_name'])
                if data_yaml_path:
                    training_params['save_liquid_data_path'] = data_yaml_path
                    self._appendLog(f"已为单个数据集创建配置文件: {data_yaml_path}\n")
                else:
                    QtWidgets.QMessageBox.critical(self.main_window, "错误", "创建数据集配置文件失败")
                    return False
            
            # 禁用笔记保存和提交按钮（训练开始时）
            self._disableNotesButtons()
            
            # 更新UI状态
            if hasattr(self, 'training_panel'):
                if hasattr(self.training_panel, 'train_status_label'):
                    self.training_panel.train_status_label.setText("正在训练...")
                    self.training_panel.train_status_label.setStyleSheet("""
                        QLabel {
                            color: #ffffff;
                            background-color: #28a745;
                            border: 1px solid #28a745;
                            border-radius: 4px;
                            padding: 10px;
                            min-height: 40px;
                        }
                    """)
                    FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                
                if hasattr(self.training_panel, 'start_train_btn'):
                    self.training_panel.start_train_btn.setEnabled(False)
                if hasattr(self.training_panel, 'stop_train_btn'):
                    self.training_panel.stop_train_btn.setEnabled(True)
            
            # 创建并启动训练线程
            self.training_worker = TrainingWorker(training_params)
            # 直接连接信号到训练面板的 appendLog 方法，使用队列连接确保线程安全和实时同步
            if hasattr(self.training_panel, 'appendLog'):
                self.training_worker.log_output.connect(
                    self.training_panel.appendLog,
                    QtCore.Qt.QueuedConnection  # 确保线程安全
                )
            else:
                # 备用方案：通过 _appendLog 转发
                self.training_worker.log_output.connect(
                    self._appendLog,
                    QtCore.Qt.QueuedConnection
                )
            self.training_worker.training_finished.connect(
                self._onTrainingFinished,
                QtCore.Qt.QueuedConnection
            )
            self.training_worker.training_progress.connect(
                self._onTrainingProgress,
                QtCore.Qt.QueuedConnection
            )
            
            self.training_active = True
            self.current_exp_name = training_params['exp_name']
            
            self.training_worker.start()
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"启动训练线程失败: {str(e)}")
            self._appendLog(f"\n 启动训练失败: {str(e)}\n")
            return False
    
    def _onStopTraining(self):
        """停止训练 - 根据训练状态采用不同策略"""
        # 检查是否已经在停止过程中
        if getattr(self, '_is_stopping', False):
            self._appendLog("\n[提示] 训练正在停止中，请耐心等待...\n")
            return True
        
        if self.training_worker and self.training_active:
            # 检查训练是否已经真正开始
            training_started = self.training_worker.has_training_started()
            
            # 设置停止标记，防止重复触发
            self._is_stopping = True
            self._is_user_stopped = True  # 标记为用户手动停止
            self.training_worker.stop_training()  # 设置 is_running = False
            
            if not training_started:
                # 训练还未真正开始（仍在初始化阶段），直接取消训练
                self._appendLog("\n" + "="*70 + "\n")
                self._appendLog("训练尚未开始，正在取消训练...\n")
                self._appendLog("="*70 + "\n")
                
                # 更新状态标签
                if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                    self.training_panel.train_status_label.setText("正在取消训练...")
                    self.training_panel.train_status_label.setStyleSheet("""
                        QLabel {
                            color: #ffffff;
                            background-color: #dc3545;
                            border: 1px solid #dc3545;
                            border-radius: 4px;
                            padding: 10px;
                            min-height: 40px;
                        }
                    """)
                    FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                
                # 强制终止训练线程（因为训练还未开始，可以安全终止）
                if self.training_worker:
                    self.training_worker.terminate()
                    self.training_worker.wait(3000)  # 等待最多3秒
                    if self.training_worker.isRunning():
                        self.training_worker.kill()  # 强制杀死线程
                
                # 直接调用训练完成回调，恢复UI状态
                self._onTrainingFinished(False)
                
            else:
                # 训练已经开始，优雅停止（完成当前epoch后停止）
                self._appendLog("\n" + "="*70 + "\n")
                self._appendLog("用户请求停止训练\n")
                self._appendLog("正在完成当前训练轮次...\n")
                self._appendLog("（请勿关闭程序，等待当前epoch完成）\n")
                self._appendLog("="*70 + "\n")
                
                # 更新状态标签
                if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                    self.training_panel.train_status_label.setText("正在停止训练...")
                    self.training_panel.train_status_label.setStyleSheet("""
                        QLabel {
                            color: #ffffff;
                            background-color: #ffc107;
                            border: 1px solid #ffc107;
                            border-radius: 4px;
                            padding: 10px;
                            min-height: 40px;
                        }
                    """)
                    FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                
                # 禁用所有训练相关按钮，防止重复点击和冲突
                if hasattr(self, 'training_panel'):
                    if hasattr(self.training_panel, 'stop_train_btn'):
                        self.training_panel.stop_train_btn.setEnabled(False)
                    if hasattr(self.training_panel, 'start_train_btn'):
                        self.training_panel.start_train_btn.setEnabled(False)
                
                # 不立刻终止线程，让YOLO在epoch结束时自动停止
                # 线程会在 _onTrainingFinished 中被清理
            
            return True
        else:
            QtWidgets.QMessageBox.information(self.main_window, "提示", "当前没有正在进行的训练")
            return False
    
    def _onTrainingFinished(self, success):
        """训练完成回调"""
        try:
            # 重置停止标记
            self._is_stopping = False
            self.training_active = False
            
            if success:
                self._appendLog("\n" + "="*70 + "\n")
                self._appendLog(" 模型升级成功完成！\n")
                self._appendLog("="*70 + "\n")
                
                # 获取weights目录和转换结果
                weights_dir = None
                converted_files = []
                if self.training_worker and hasattr(self.training_worker, "training_report"):
                    weights_dir = self.training_worker.training_report.get("weights_dir")
                    converted_files = self.training_worker.training_report.get("converted_dat_files", [])
                
                # 显示转换结果（转换已在TrainingWorker中完成）
                if converted_files:
                    self._appendLog(f"\n 模型已转换为dat格式: {len(converted_files)}个文件\n")
                    for f in converted_files:
                        self._appendLog(f"   - {os.path.basename(f)}\n")
                
                # 保存训练日志到training_results目录
                training_results_dir = None
                if self.training_worker and hasattr(self.training_worker, "training_report"):
                    training_results_dir = self.training_worker.training_report.get("training_results_dir")
                
                if training_results_dir and os.path.exists(training_results_dir):
                    self._appendLog("\n 正在保存训练日志...\n")
                    log_file = self._saveTrainingLogToWeightsDir(self.current_exp_name, training_results_dir)
                    if log_file:
                        self._appendLog(f" 训练日志已保存: {os.path.basename(log_file)}\n")
                    else:
                        self._appendLog(" [WARNING] 训练日志保存失败\n")
                    
                    # 将转换结果写入 training_report.json
                    try:
                        report_path = None
                        if weights_dir:
                            # weights_dir 保持绝对路径
                            resolved_weights_dir = weights_dir
                            if not os.path.isabs(resolved_weights_dir):
                                resolved_weights_dir = os.path.abspath(resolved_weights_dir)
                            exp_dir_for_report = os.path.dirname(resolved_weights_dir)
                            if exp_dir_for_report:
                                report_path = os.path.join(exp_dir_for_report, "training_report.json")
                        if not report_path and self.current_exp_name:
                            train_root_for_report = get_train_dir()
                            exp_dir_for_report = os.path.join(train_root_for_report, "runs", "train", self.current_exp_name)
                            report_path = os.path.join(exp_dir_for_report, "training_report.json")
                        if report_path and os.path.exists(report_path):
                            import json as _json_mod3
                            with open(report_path, "r", encoding="utf-8") as rf:
                                report_obj = _json_mod3.load(rf)
                            report_obj["converted_dat_files"] = converted_files
                            with open(report_path, "w", encoding="utf-8") as wf:
                                _json_mod3.dump(report_obj, wf, ensure_ascii=False, indent=2)
                    except Exception as _:
                        pass
                
                # 更新状态标签
                if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                    self.training_panel.train_status_label.setText("升级成功完成")
                    self.training_panel.train_status_label.setStyleSheet("""
                        QLabel {
                            color: #ffffff;
                            background-color: #28a745;
                            border: 1px solid #28a745;
                            border-radius: 4px;
                            padding: 10px;
                            min-height: 40px;
                        }
                    """)
                    FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                
                # 自动将新模型添加到模型集配置
                try:
                    self._addTrainedModelToModelSet(converted_files, weights_dir)
                except Exception as add_error:
                    self._appendLog(f"[WARNING] 添加到模型集失败: {str(add_error)}\n")
                
                # 刷新模型集管理页面
                try:
                    self._refreshModelSetPage()
                except Exception as refresh_error:
                    pass
                
                try:
                    self._refreshModelTestPage()
                except Exception as test_refresh_error:
                    pass
                
                # 修复：使用非阻塞式通知，避免卡住UI
                self._appendLog("\n" + "="*70 + "\n")
                self._appendLog(" 训练完成通知\n")
                self._appendLog("="*70 + "\n")
                self._appendLog("模型升级已完成！\n")
                self._appendLog("新模型已保存到detection_model目录\n")
                self._appendLog("新模型已自动添加到模型集管理\n")
                self._appendLog("请切换到【模型集管理】页面查看新模型\n")
                self._appendLog("="*70 + "\n")
                
                # 启用笔记保存和提交按钮（训练完成后允许继续编辑笔记）
                self._enableNotesButtons()
                
                # 使用定时器延迟显示消息框，避免阻塞训练线程的清理
                QtCore.QTimer.singleShot(500, lambda: QtWidgets.QMessageBox.information(
                    self.main_window, 
                    "升级完成", 
                    "模型升级已完成！\n新模型已保存到detection_model目录\n并自动添加到模型集管理。"
                ))
            else:
                # 检查是否为用户手动停止
                is_user_stopped = getattr(self, '_is_user_stopped', False)
                
                # 检查训练是否已经真正开始
                training_started = False
                if self.training_worker:
                    training_started = self.training_worker.has_training_started()
                
                if is_user_stopped and training_started:
                    self._appendLog("\n" + "="*70 + "\n")
                    self._appendLog("训练已暂停\n")
                    self._appendLog("="*70 + "\n")
                    
                    # 获取weights目录和转换结果（转换已在TrainingWorker中完成）
                    converted_files = []
                    weights_dir = None
                    if self.training_worker and hasattr(self.training_worker, "training_report"):
                        weights_dir = self.training_worker.training_report.get("weights_dir")
                        converted_files = self.training_worker.training_report.get("converted_dat_files", [])
                    
                    # 显示转换结果
                    if converted_files:
                        self._appendLog(f"\n模型已转换为dat格式: {len(converted_files)}个文件\n")
                        for f in converted_files:
                            self._appendLog(f"   - {os.path.basename(f)}\n")
                    
                    # 保存训练日志到training_results目录
                    training_results_dir = None
                    if self.training_worker and hasattr(self.training_worker, "training_report"):
                        training_results_dir = self.training_worker.training_report.get("training_results_dir")
                    
                    if training_results_dir and os.path.exists(training_results_dir):
                        self._appendLog("\n正在保存训练日志...\n")
                        log_file = self._saveTrainingLogToWeightsDir(self.current_exp_name, training_results_dir)
                        if log_file:
                            self._appendLog(f"训练日志已保存: {os.path.basename(log_file)}\n")
                        else:
                            self._appendLog("[WARNING] 训练日志保存失败\n")
                    
                    # 用户停止训练时也要同步模型到模型集
                    self._appendLog("\n正在将模型同步到模型集管理...\n")
                    self._addTrainedModelToModelSet(converted_files, weights_dir)
                    
                    # 刷新模型集管理页面
                    self._refreshModelSetPage()
                    
                    self._refreshModelTestPage()
                    
                    # 获取 last.dat 路径（转换后应该是 dat 文件）
                    last_checkpoint_path = None
                    if self.current_exp_name and weights_dir:
                        last_dat_path = os.path.join(weights_dir, "last.dat")
                        last_pt_path = os.path.join(weights_dir, "last.pt")
                        
                        if os.path.exists(last_dat_path):
                            last_checkpoint_path = last_dat_path
                        elif os.path.exists(last_pt_path):
                            last_checkpoint_path = last_pt_path
                        
                        if last_checkpoint_path:
                            self._appendLog(f"\n训练进度已保存至: {last_checkpoint_path}\n")
                            self._appendLog("可点击【继续训练】按钮从此处恢复训练\n")
                        else:
                            self._appendLog("\n未找到可用的训练进度文件\n")
                    
                    # 更新状态标签
                    if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                        self.training_panel.train_status_label.setText("训练已暂停")
                        self.training_panel.train_status_label.setStyleSheet("""
                            QLabel {
                                color: #ffffff;
                                background-color: #ffc107;
                                border: 1px solid #ffc107;
                                border-radius: 4px;
                                padding: 10px;
                                min-height: 40px;
                            }
                        """)
                        FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                    
                    # 切换按钮状态为继续训练模式
                    if hasattr(self, 'training_panel'):
                        if hasattr(self.training_panel, 'start_train_btn'):
                            self.training_panel.start_train_btn.setEnabled(False)  # 禁用开始训练按钮
                        
                        # 将停止训练按钮切换为继续训练按钮
                        if hasattr(self.training_panel, 'stop_train_btn') and hasattr(self.training_panel, 'switchToContinueMode'):
                            # 使用训练面板的方法切换到继续训练模式
                            self.training_panel.switchToContinueMode(last_checkpoint_path)
                        elif hasattr(self.training_panel, 'stop_train_btn'):
                            # 如果没有switchToContinueMode方法，手动设置
                            self.training_panel.stop_train_btn.setText("继续训练")
                            self.training_panel.stop_train_btn.setEnabled(True)
                            self.training_panel._is_training_stopped = True
                            self.training_panel._last_checkpoint_path = last_checkpoint_path
                    
                    # 重置标记
                    self._is_user_stopped = False
                    self._is_stopping = False
                elif is_user_stopped and not training_started:
                    # 训练被取消（未真正开始），恢复初始状态
                    self._appendLog("\n" + "="*70 + "\n")
                    self._appendLog("训练已取消\n")
                    self._appendLog("="*70 + "\n")
                    
                    # 更新状态标签
                    if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                        self.training_panel.train_status_label.setText("训练已取消")
                        self.training_panel.train_status_label.setStyleSheet("""
                            QLabel {
                                color: #ffffff;
                                background-color: #6c757d;
                                border: 1px solid #6c757d;
                                border-radius: 4px;
                                padding: 10px;
                                min-height: 40px;
                            }
                        """)
                        FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                    
                    # 恢复按钮状态（允许重新开始训练）
                    if hasattr(self, 'training_panel'):
                        if hasattr(self.training_panel, 'start_train_btn'):
                            self.training_panel.start_train_btn.setEnabled(True)
                        if hasattr(self.training_panel, 'stop_train_btn'):
                            self.training_panel.stop_train_btn.setEnabled(False)
                            self.training_panel.stop_train_btn.setText("停止升级")  # 恢复原始文本
                    
                    # 重置标记
                    self._is_user_stopped = False
                    self._is_stopping = False
                else:
                    self._appendLog("\n" + "="*70 + "\n")
                    self._appendLog(" 升级失败\n")
                    self._appendLog("="*70 + "\n")
                    
                    # 更新状态标签
                    if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'train_status_label'):
                        self.training_panel.train_status_label.setText("升级失败")
                        self.training_panel.train_status_label.setStyleSheet("""
                            QLabel {
                                color: #ffffff;
                                background-color: #dc3545;
                                border: 1px solid #dc3545;
                                border-radius: 4px;
                                padding: 10px;
                                min-height: 40px;
                            }
                        """)
                        FontManager.applyToWidget(self.training_panel.train_status_label, weight=FontManager.WEIGHT_BOLD)
                    
                    QtWidgets.QMessageBox.warning(self.main_window, "训练失败", "训练过程中出现错误")
                    
                    # 训练失败时恢复按钮状态（允许重新开始）
                    if hasattr(self, 'training_panel'):
                        if hasattr(self.training_panel, 'start_train_btn'):
                            self.training_panel.start_train_btn.setEnabled(True)
                        if hasattr(self.training_panel, 'stop_train_btn'):
                            self.training_panel.stop_train_btn.setEnabled(False)
                            self.training_panel.stop_train_btn.setText("停止升级")
                        # 重置训练停止标记
                        self.training_panel._is_training_stopped = False
                    
                    # 重置停止标记
                    self._is_user_stopped = False
                    self._is_stopping = False
            
            # 如果是正常完成（非用户停止），恢复按钮状态
            if success and not self._is_user_stopped:
                if hasattr(self, 'training_panel'):
                    if hasattr(self.training_panel, 'start_train_btn'):
                        self.training_panel.start_train_btn.setEnabled(True)
                    if hasattr(self.training_panel, 'stop_train_btn'):
                        self.training_panel.stop_train_btn.setEnabled(False)
                        self.training_panel.stop_train_btn.setText("停止升级")
            
            # 清理训练工作线程
            if self.training_worker:
                self.training_worker.wait()
                self.training_worker = None
            
            # 清理临时文件
            self._cleanupTempFiles()
            
        except Exception as e:
            self._appendLog(f"\n 升级完成处理失败: {str(e)}\n")
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"升级完成处理失败: {str(e)}")
    
    def _onTrainingProgress(self, epoch, loss_dict):
        """训练进度回调"""
        # 这里可以更新进度条或显示loss信息
        pass
    
    def _convertPtToDatAndCleanup(self, weights_dir):
        """立即转换PT文件为DAT格式并删除PT文件"""
        self._appendLog("\n" + "="*70 + "\n")
        self._appendLog("[调试] _convertPtToDatAndCleanup 方法已启动\n")
        self._appendLog(f"[调试] 权重目录: {weights_dir}\n")
        self._appendLog("="*70 + "\n")
        
        try:
            if not self.file_converter:
                self._appendLog("[调试] 文件转换器未初始化，退出方法\n")
                return []
            
            if not os.path.exists(weights_dir):
                self._appendLog(f"[调试] 权重目录不存在，退出方法\n")
                return []
            
            converted_files = []
            pt_files_found = []
            
            # 查找所有PT文件
            self._appendLog("[调试] 开始扫描PT文件...\n")
            for file in os.listdir(weights_dir):
                if file.endswith('.pt'):
                    pt_files_found.append(file)
                    self._appendLog(f"[调试] 发现PT文件: {file}\n")
            
            if not pt_files_found:
                self._appendLog("[调试] 未发现PT文件，退出方法\n")
                return []
            
            self._appendLog(f"[调试] 共发现 {len(pt_files_found)} 个PT文件\n")
            
            # 获取模型名称用于文件重命名
            model_name = getattr(self, 'current_exp_name', 'trained_model')
            self._appendLog(f"[调试] 模型名称: {model_name}\n")
            
            # 转换每个PT文件
            self._appendLog("\n[调试] 开始转换PT文件为DAT格式...\n")
            for file in pt_files_found:
                pt_path = os.path.join(weights_dir, file)
                
                # 根据模型名称重命名DAT文件
                if file == 'best.pt':
                    # best.pt -> best.{model_name}
                    dat_filename = f"best.{model_name}"
                elif file == 'last.pt':
                    # last.pt -> last.{model_name}
                    dat_filename = f"last.{model_name}"
                else:
                    # 其他文件保持原名但替换扩展名
                    dat_filename = file.replace('.pt', f'.{model_name}')
                
                dat_path = os.path.join(weights_dir, dat_filename)
                
                self._appendLog(f"[调试] 转换: {file} -> {dat_filename}\n")
                
                try:
                    converted_path = self.file_converter.convert_file(pt_path, dat_path)
                    
                    if converted_path and os.path.exists(converted_path):
                        converted_files.append(converted_path)
                        self._appendLog(f"[调试] ✓ 转换成功: {dat_filename}\n")
                        
                        # 立即删除PT文件
                        self._appendLog(f"[调试] 尝试删除PT文件: {file}\n")
                        try:
                            os.remove(pt_path)
                            self._appendLog(f"[调试] ✓ PT文件已删除: {file}\n")
                        except OSError as remove_error:
                            self._appendLog(f"[调试] ✗ PT文件删除失败: {file}\n")
                            self._appendLog(f"[调试]   错误信息: {str(remove_error)}\n")
                    else:
                        self._appendLog(f"[调试] ✗ 转换失败: {dat_filename}\n")
                        
                except Exception as convert_error:
                    self._appendLog(f"[调试] ✗ 转换异常: {file}\n")
                    self._appendLog(f"[调试]   错误信息: {str(convert_error)}\n")
            
            # 强制清理任何残留的PT文件
            self._appendLog("\n[调试] 调用 _forceCleanupPtFiles 强制清理残留PT文件...\n")
            self._forceCleanupPtFiles(weights_dir)
            
            self._appendLog(f"\n[调试] _convertPtToDatAndCleanup 方法执行完成，共转换 {len(converted_files)} 个文件\n")
            self._appendLog("="*70 + "\n")
            return converted_files
            
        except Exception as e:
            self._appendLog(f"\n[调试] ✗ _convertPtToDatAndCleanup 方法发生异常: {str(e)}\n")
            import traceback
            self._appendLog(f"[调试] 详细错误:\n{traceback.format_exc()}\n")
            self._appendLog("="*70 + "\n")
            return []
    
    def _convertTrainingmission_resultsToDat(self, exp_name, weights_dir=None):
        """将训练结果的pt文件转换为dat格式"""
        try:
            if not self.file_converter:
                self._appendLog("[ERROR] 未初始化文件转换器，无法执行pt到dat的转换\n")
                return []
            
            converted_files = []
            if weights_dir:
                if not os.path.isabs(weights_dir):
                    weights_dir = os.path.abspath(weights_dir)
                weights_dir = os.path.normpath(weights_dir)
            else:
                train_root = get_train_dir()
                weights_dir = os.path.join(train_root, "runs", "train", exp_name, "weights")
            
            if not os.path.exists(weights_dir):
                self._appendLog(f"[ERROR] 训练结果目录不存在: {weights_dir}\n")
                return converted_files
            
            # 查找pt文件并转换
            for file in os.listdir(weights_dir):
                if file.endswith('.pt'):
                    pt_path = os.path.join(weights_dir, file)
                    dat_path = pt_path.replace('.pt', '.dat')
                    
                    try:
                        converted_path = self.file_converter.convert_file(pt_path, dat_path)
                        if converted_path and os.path.exists(converted_path):
                            converted_files.append(converted_path)
                            try:
                                os.remove(pt_path)
                            except OSError as remove_error:
                                self._appendLog(f"[WARNING] 无法删除原始pt文件 {pt_path}: {remove_error}\n")
                        else:
                            self._appendLog(f"[WARNING] 转换后未找到dat文件: {dat_path}\n")
                    except Exception as convert_error:
                        self._appendLog(f"[ERROR] 转换文件失败 {pt_path}: {convert_error}\n")
            
            return converted_files
            
        except Exception as e:
            self._appendLog(f"[ERROR] 训练结果转换失败: {e}\n")
            return []
    
    def _cleanupTempFiles(self):
        """清理临时文件"""
        try:
            for temp_file in self.temp_trained_models:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            self.temp_trained_models.clear()
            
        except Exception as e:
            pass
    
    def _forceCleanupPtFiles(self, weights_dir):
        """强制清理指定目录下的所有PT文件（带重试机制）"""
        self._appendLog("\n" + "-"*70 + "\n")
        self._appendLog("[调试] _forceCleanupPtFiles 方法已启动\n")
        self._appendLog(f"[调试] 权重目录: {weights_dir}\n")
        self._appendLog("-"*70 + "\n")
        
        try:
            if not os.path.exists(weights_dir):
                self._appendLog("[调试] 权重目录不存在，退出方法\n")
                return
            
            import time
            import gc
            
            pt_files = []
            self._appendLog("[调试] 开始扫描残留的PT文件...\n")
            for file in os.listdir(weights_dir):
                if file.endswith('.pt'):
                    pt_files.append((file, os.path.join(weights_dir, file)))
                    self._appendLog(f"[调试] 发现残留PT文件: {file}\n")
            
            if not pt_files:
                self._appendLog("[调试] 未发现残留PT文件，退出方法\n")
                self._appendLog("-"*70 + "\n")
                return
            
            self._appendLog(f"[调试] 共发现 {len(pt_files)} 个残留PT文件，开始强制清理...\n")
            self._appendLog("[调试] 执行垃圾回收释放文件句柄...\n")
            
            # 强制垃圾回收，释放可能的文件句柄
            gc.collect()
            time.sleep(1.0)  # 增加初始等待时间
            
            success_count = 0
            fail_count = 0
            
            for filename, pt_file in pt_files:
                self._appendLog(f"\n[调试] 处理文件: {filename}\n")
                deleted = False
                last_error = None
                
                for attempt in range(10):  # 增加到10次重试
                    self._appendLog(f"[调试]   尝试删除 (第{attempt+1}/10次)...\n")
                    try:
                        if os.path.exists(pt_file):
                            os.remove(pt_file)
                            deleted = True
                            self._appendLog(f"[调试]   ✓ 删除成功\n")
                            break
                        else:
                            self._appendLog(f"[调试]   文件不存在（可能已被删除）\n")
                            deleted = True
                            break
                    except OSError as e:
                        last_error = str(e)
                        self._appendLog(f"[调试]   ✗ 删除失败: {last_error}\n")
                        if attempt < 9:
                            # 每次重试前强制垃圾回收
                            gc.collect()
                            self._appendLog(f"[调试]   等待0.5秒后重试...\n")
                            time.sleep(0.5)  # 等待0.5秒后重试
                
                if deleted:
                    success_count += 1
                    self._appendLog(f"[清理] ✓ 已删除PT文件: {filename}\n")
                    # 再次等待确保文件系统同步
                    time.sleep(0.2)
                else:
                    fail_count += 1
                    self._appendLog(f"[警告] ✗ 无法删除PT文件: {filename}\n")
                    self._appendLog(f"  原因: {last_error}\n")
                    self._appendLog(f"  文件路径: {pt_file}\n")
                    self._appendLog(f"  请手动删除此文件\n")
            
            self._appendLog(f"\n[调试] _forceCleanupPtFiles 执行完成\n")
            self._appendLog(f"[调试]   成功: {success_count} 个\n")
            self._appendLog(f"[调试]   失败: {fail_count} 个\n")
            self._appendLog("-"*70 + "\n")
                        
        except Exception as e:
            self._appendLog(f"\n[调试] ✗ _forceCleanupPtFiles 方法发生异常: {str(e)}\n")
            import traceback
            self._appendLog(f"[调试] 详细错误:\n{traceback.format_exc()}\n")
            self._appendLog("-"*70 + "\n")
    
    def _saveTrainingLogToWeightsDir(self, exp_name, weights_dir=None):
        """
        将训练日志保存到weights目录下
        
        Args:
            exp_name: 实验名称
            weights_dir: weights目录路径，如果为None则自动构建
        
        Returns:
            str: 保存的日志文件路径，失败返回None
        """
        try:
            # 确定weights目录
            if weights_dir:
                if not os.path.isabs(weights_dir):
                    weights_dir = os.path.abspath(weights_dir)
                weights_dir = os.path.normpath(weights_dir)
            else:
                train_root = get_train_dir()
                weights_dir = os.path.join(train_root, "runs", "train", exp_name, "weights")
            
            if not os.path.exists(weights_dir):
                return None
            
            # 获取训练日志内容
            log_content = ""
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'log_display'):
                log_content = self.training_panel.log_display.toPlainText()
            
            if not log_content:
                return None
            
            # 生成日志文件名：training_log_[模型名称].txt
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"training_log_{exp_name}_{timestamp}.txt"
            log_filepath = os.path.join(weights_dir, log_filename)
            
            # 保存日志文件
            with open(log_filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"训练日志 - {exp_name}\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                f.write(log_content)
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("日志结束\n")
                f.write("=" * 80 + "\n")
            
            return log_filepath
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _appendLog(self, message):
        """追加日志到训练面板（线程安全，防止递归）"""
        try:
            # 直接调用训练面板的 appendLog 方法（线程安全）
            if hasattr(self, 'training_panel') and self.training_panel:
                if hasattr(self.training_panel, 'appendLog'):
                    # 使用 Qt 的信号机制确保线程安全
                    QtCore.QMetaObject.invokeMethod(
                        self.training_panel,
                        "appendLog",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, message)
                    )
                elif hasattr(self.training_panel, 'train_log_text'):
                    # 备用方案：直接操作文本框（但可能不够线程安全）
                    QtCore.QMetaObject.invokeMethod(
                        self.training_panel.train_log_text,
                        "insertPlainText",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, message)
                    )
        except Exception as e:
            # 静默处理错误，避免递归
            import sys
            if hasattr(sys, '__stderr__'):
                try:
                    sys.__stderr__.write(f"[ERROR] 输出日志失败: {e}\n")
                    sys.__stderr__.flush()
                except:
                    pass
    
    def connectToTrainingPanel(self, training_panel):
        """
        连接到训练面板
        
        Args:
            training_panel: 训练面板实例（如TestModelPage）
        """
        self.training_panel = training_panel
        
        # 连接训练面板的信号到处理器
        if hasattr(training_panel, 'startTrainingClicked'):
            training_panel.startTrainingClicked.connect(self._handleStartTraining)
        
        if hasattr(training_panel, 'stopTrainingClicked'):
            training_panel.stopTrainingClicked.connect(self._handleStopTraining)
        
        if hasattr(training_panel, 'continueTrainingClicked'):
            training_panel.continueTrainingClicked.connect(self._handleContinueTraining)
        
        # 连接测试相关按钮（使用父类 ModelTestHandler 的方法）
        self.connectTestButtons(training_panel)
        
        # 初始化UI组件的默认值
        self._initializeTrainingPanelDefaults(training_panel)
    
    def _initializeTrainingPanelDefaults(self, training_panel):
        """初始化训练面板的默认值"""
        try:
            # 基础模型现在通过下拉菜单从模型集管理页面加载，不需要手动设置
            # 下拉菜单会在页面显示时自动加载并选择默认模型
            
            # 数据集现在通过文件夹列表管理，可以手动添加默认数据集文件夹
            if hasattr(training_panel, 'dataset_folders_list'):
                project_root = get_project_root()
                default_dataset_folder = os.path.join(project_root, 'database', 'dataset')
                if os.path.exists(default_dataset_folder) and os.path.isdir(default_dataset_folder):
                    # 添加默认数据集文件夹（如果列表为空）
                    if training_panel.dataset_folders_list.count() == 0:
                        training_panel.dataset_folders_list.addItem(default_dataset_folder)
                        if hasattr(training_panel, '_updateDatasetPath'):
                            training_panel._updateDatasetPath()
            
            # 设置默认模型名称
            if hasattr(training_panel, 'exp_name_edit'):
                if not training_panel.exp_name_edit.text():
                    training_panel.exp_name_edit.setText('training_experiment')
            
        except Exception as e:
            pass
    
    def _handleStartTraining(self):
        """处理开始训练按钮点击"""
        try:
            # 从训练面板获取参数
            if not hasattr(self, 'training_panel'):
                QtWidgets.QMessageBox.warning(self.main_window, "错误", "训练面板未连接")
                return
            
            # 获取训练参数
            training_params = self._getTrainingParamsFromPanel()
            
            # 开始训练
            self._onStartTraining(training_params)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"启动训练失败: {str(e)}")
    
    def _handleStopTraining(self):
        """处理停止训练按钮点击"""
        self._onStopTraining()
    
    def _handleContinueTraining(self):
        """处理继续训练按钮点击"""
        try:
            # 从训练面板获取参数
            if not hasattr(self, 'training_panel'):
                QtWidgets.QMessageBox.warning(self.main_window, "错误", "训练面板未连接")
                return
            
            # 获取上次训练的路径
            checkpoint_path = getattr(self.training_panel, '_last_training_path', None)
            
            # 验证保存的检查点路径是否仍然有效
            if checkpoint_path and os.path.exists(checkpoint_path):
                # 找到了有效的检查点，询问用户是否使用
                exp_name = os.path.basename(os.path.dirname(os.path.dirname(checkpoint_path)))
                # 创建无图标的对话框
                msg_box = QtWidgets.QMessageBox(self.main_window)
                msg_box.setWindowTitle("继续训练")
                msg_box.setText(f"找到上次训练的检查点:\n\n实验名称: {exp_name}\n检查点: {os.path.basename(checkpoint_path)}\n\n是否继续训练？\n\n（点击'否'可以选择其他检查点）")
                msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
                msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
                
                # 设置中文按钮文本
                yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
                no_btn = msg_box.button(QtWidgets.QMessageBox.No)
                if yes_btn:
                    yes_btn.setText("是")
                if no_btn:
                    no_btn.setText("否")
                
                reply = msg_box.exec_()
                
                if reply != QtWidgets.QMessageBox.Yes:
                    checkpoint_path = None  # 用户选择不使用，继续搜索其他检查点
            
            if not checkpoint_path:
                # 如果没有保存的路径或用户选择不使用，搜索可用的训练检查点
                train_root = os.path.normpath(get_train_dir())
                runs_train_dir = os.path.join(train_root, "runs", "train")
                
                # 首先尝试查找当前界面输入的模型名称对应的检查点
                training_params = self._getTrainingParamsFromPanel()
                current_exp_name = training_params.get('exp_name', '')
                
                if current_exp_name:
                    current_weights_dir = os.path.join(runs_train_dir, current_exp_name, "weights")
                    for checkpoint_file in ["last.dat", "last.pt"]:
                        candidate_path = os.path.join(current_weights_dir, checkpoint_file)
                        if os.path.exists(candidate_path):
                            checkpoint_path = candidate_path
                            self._appendLog(f"找到当前模型名称对应的检查点: {checkpoint_path}\n")
                            break
                
                # 如果当前模型名称没有对应的检查点，搜索所有可用的检查点
                if not checkpoint_path:
                    if not os.path.exists(runs_train_dir):
                        QtWidgets.QMessageBox.warning(
                            self.main_window,
                            "错误",
                            f"未找到训练目录\n\n路径: {runs_train_dir}\n\n请先完成至少一次训练。"
                        )
                        return
                    
                    # 搜索所有包含检查点文件的训练目录
                    available_checkpoints = []
                    try:
                        for item in os.listdir(runs_train_dir):
                            item_path = os.path.join(runs_train_dir, item)
                            if os.path.isdir(item_path):
                                weights_dir = os.path.join(item_path, "weights")
                                if os.path.exists(weights_dir):
                                    # 查找 last.pt 或 last.dat
                                    for checkpoint_file in ["last.pt", "last.dat"]:
                                        checkpoint_full_path = os.path.join(weights_dir, checkpoint_file)
                                        if os.path.exists(checkpoint_full_path):
                                            # 获取修改时间
                                            mtime = os.path.getmtime(checkpoint_full_path)
                                            available_checkpoints.append({
                                                'path': checkpoint_full_path,
                                                'exp_name': item,
                                                'mtime': mtime
                                            })
                                            break  # 找到一个就够了
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self.main_window,
                            "错误",
                            f"搜索训练检查点时出错: {str(e)}"
                        )
                        return
                    
                    if not available_checkpoints:
                        QtWidgets.QMessageBox.warning(
                            self.main_window,
                            "错误",
                            f"未找到任何训练检查点文件\n\n"
                            f"搜索目录: {runs_train_dir}\n\n"
                            f"请确保之前的训练已完成并保存了检查点文件（last.pt 或 last.dat）。"
                        )
                        return
                    
                    # 按修改时间排序，最新的在前
                    available_checkpoints.sort(key=lambda x: x['mtime'], reverse=True)
                    
                    # 如果只有一个检查点，直接使用
                    if len(available_checkpoints) == 1:
                        checkpoint_path = available_checkpoints[0]['path']
                        exp_name = available_checkpoints[0]['exp_name']
                        
                        # 询问用户是否继续
                        # 创建无图标的对话框
                        msg_box = QtWidgets.QMessageBox(self.main_window)
                        msg_box.setWindowTitle("继续训练")
                        msg_box.setText(f"找到训练检查点:\n\n实验名称: {exp_name}\n检查点: {os.path.basename(checkpoint_path)}\n\n是否继续训练？")
                        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
                        msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
                        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                        msg_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
                        
                        # 设置中文按钮文本
                        yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
                        no_btn = msg_box.button(QtWidgets.QMessageBox.No)
                        if yes_btn:
                            yes_btn.setText("是")
                        if no_btn:
                            no_btn.setText("否")
                        
                        reply = msg_box.exec_()
                        
                        if reply != QtWidgets.QMessageBox.Yes:
                            return
                    else:
                        # 多个检查点，让用户选择
                        items = []
                        for cp in available_checkpoints:
                            import time
                            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cp['mtime']))
                            items.append(f"{cp['exp_name']} ({time_str})")
                        
                        item, ok = QtWidgets.QInputDialog.getItem(
                            self.main_window,
                            "选择训练检查点",
                            f"找到 {len(available_checkpoints)} 个训练检查点，请选择要继续的训练:",
                            items,
                            0,
                            False
                        )
                        
                        if not ok:
                            return
                        
                        # 获取选中的检查点
                        selected_index = items.index(item)
                        checkpoint_path = available_checkpoints[selected_index]['path']
            
            # 获取训练参数
            training_params = self._getTrainingParamsFromPanel()
            
            # 不使用resume模式，而是从检查点开始新的训练
            # 这样可以避免"nothing to resume"的错误
            training_params['resume'] = False
            training_params['base_model'] = checkpoint_path
            
            # 询问用户要继续训练多少个epoch
            current_epochs = training_params['epochs']
            
            # 创建输入对话框让用户选择继续训练的epoch数
            additional_epochs, ok = QtWidgets.QInputDialog.getInt(
                self.main_window,
                "继续训练",
                f"请输入要继续训练的轮数:\n\n当前模型已完成: {current_epochs} 轮\n建议继续训练:",
                current_epochs,  # 默认值
                1,  # 最小值
                1000,  # 最大值
                1   # 步长
            )
            
            if not ok:
                self._appendLog("用户取消了继续训练\n")
                return
                
            training_params['epochs'] = additional_epochs
            
            self._appendLog("\n" + "="*70 + "\n")
            self._appendLog(f"继续训练\n")
            self._appendLog(f"   从检查点开始: {checkpoint_path}\n")
            self._appendLog(f"   额外训练轮数: {additional_epochs}\n")
            self._appendLog("="*70 + "\n")
            
            # 开始训练
            self._onStartTraining(training_params)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"继续训练失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _getTrainingParamsFromPanel(self):
        """从训练面板获取训练参数"""
        if not hasattr(self, 'training_panel'):
            return {}
        
        panel = self.training_panel
        
        # 获取所有训练参数
        # 获取设备选择
        device_text = getattr(panel, 'device_combo', None) and panel.device_combo.currentText() or 'GPU'
        # 将"GPU"转换为"0"（使用第一块GPU），"CPU"转换为"cpu"
        if device_text == 'GPU':
            device_value = '0'
        elif device_text == 'CPU':
            device_value = 'cpu'
        else:
            device_value = device_text
        
        training_params = {
            'base_model': getattr(panel, 'base_model_combo', None) and panel.base_model_combo.currentData() or '',
            'save_liquid_data_path': getattr(panel, 'save_liquid_data_path_edit', None) and panel.save_liquid_data_path_edit.text() or '',
            'imgsz': getattr(panel, 'imgsz_spin', None) and panel.imgsz_spin.value() or 640,
            'epochs': getattr(panel, 'epochs_spin', None) and panel.epochs_spin.value() or 100,
            'batch': getattr(panel, 'batch_spin', None) and panel.batch_spin.value() or 16,
            'workers': getattr(panel, 'workers_spin', None) and panel.workers_spin.value() or 8,
            'device': device_value,
            'optimizer': getattr(panel, 'optimizer_combo', None) and panel.optimizer_combo.currentText() or 'SGD',
            'close_mosaic': getattr(panel, 'close_mosaic_spin', None) and panel.close_mosaic_spin.value() or 10,
            'exp_name': getattr(panel, 'exp_name_edit', None) and panel.exp_name_edit.text() or '',
            'resume': getattr(panel, 'resume_check', None) and panel.resume_check.isChecked() or False,
            'cache': getattr(panel, 'cache_check', None) and panel.cache_check.isChecked() or False,
            'single_cls': getattr(panel, 'single_cls_check', None) and panel.single_cls_check.isChecked() or False,
            'pretrained': False
        }
        
        # 验证并修正路径
        training_params = self._validateAndFixPaths(training_params)
        
        return training_params
    
    def _validateAndFixPaths(self, training_params):
        """验证并修正训练参数中的路径"""
        try:
            # 修正基础模型路径
            base_model = training_params.get('base_model', '')
            
            # 如果是相对路径，转换为绝对路径
            if base_model and not os.path.isabs(base_model):
                project_root = get_project_root()
                base_model = os.path.join(project_root, base_model)
            
            if not base_model or not os.path.exists(base_model):
                # 尝试使用配置文件中的默认路径
                if self.train_config and 'default_parameters' in self.train_config:
                    default_model = self.train_config['default_parameters'].get('base_model', '')
                    if default_model and os.path.exists(default_model):
                        training_params['base_model'] = default_model
                    else:
                        # 使用项目中可用的模型
                        project_root = get_project_root()
                        available_models = [
                            os.path.join(project_root, 'database', 'model', 'train_model', '5', 'best.dat'),
                            os.path.join(project_root, 'database', 'model', 'train_model', '2', 'best.pt'),
                            os.path.join(project_root, 'database', 'model', 'train_model')
                        ]
                        for model_path in available_models:
                            if os.path.exists(model_path):
                                if os.path.isfile(model_path):
                                    training_params['base_model'] = model_path
                                    break
                                elif os.path.isdir(model_path):
                                    # 查找目录中的第一个模型文件
                                    for root, dirs, files in os.walk(model_path):
                                        for file in files:
                                            if file.endswith('.pt') or file.endswith('.dat'):
                                                full_path = os.path.join(root, file)
                                                training_params['base_model'] = full_path
                                                break
                                        if training_params.get('base_model'):
                                            break
                                    if training_params.get('base_model'):
                                        break
            else:
                # 路径有效，更新为绝对路径
                training_params['base_model'] = base_model
            
            # 修正数据集路径（支持多文件夹，用分号分隔）
            save_liquid_data_path = training_params.get('save_liquid_data_path', '')
            
            if save_liquid_data_path:
                # 解析多个文件夹路径
                folders = [f.strip() for f in save_liquid_data_path.split(';') if f.strip()]
                fixed_folders = []
                
                for folder in folders:
                    # 如果是相对路径，转换为绝对路径
                    if not os.path.isabs(folder):
                        project_root = get_project_root()
                        folder = os.path.join(project_root, folder)
                    
                    # 只保留存在的文件夹
                    if os.path.exists(folder) and os.path.isdir(folder):
                        fixed_folders.append(folder)
                
                # 更新为绝对路径列表
                if fixed_folders:
                    training_params['save_liquid_data_path'] = ';'.join(fixed_folders)
                else:
                    # 如果没有有效文件夹，尝试使用默认数据集文件夹
                    project_root = get_project_root()
                    default_folder = os.path.join(project_root, 'database', 'dataset')
                    if os.path.exists(default_folder) and os.path.isdir(default_folder):
                        training_params['save_liquid_data_path'] = default_folder
            else:
                # 没有指定数据集，使用默认数据集文件夹
                project_root = get_project_root()
                default_folder = os.path.join(project_root, 'database', 'dataset')
                if os.path.exists(default_folder) and os.path.isdir(default_folder):
                    training_params['save_liquid_data_path'] = default_folder
            
            return training_params
            
        except Exception as e:
            return training_params
    
    def _prepareBaseModelForTraining(self, base_model_path):
        """准备基础模型用于训练"""
        try:
            if base_model_path.endswith('.dat'):
                # 如果是.dat文件，需要转换为.pt文件
                
                # 创建临时目录
                temp_dir = tempfile.mkdtemp(prefix="liquid_training_")
                temp_model_path = Path(temp_dir) / f"train_base_{Path(base_model_path).stem}.pt"
                
                # 这里需要实现dat到pt的转换逻辑
                # 暂时返回原路径
                return str(temp_model_path)
            else:
                # 如果是.pt文件，直接使用
                return base_model_path
                
        except Exception as e:
            return base_model_path
    
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
    
    def _validateDatasetFolders(self, dataset_folders):
        """
        验证多个数据集文件夹
        
        Args:
            dataset_folders: 数据集文件夹路径列表
            
        Returns:
            tuple: (是否有效, 错误消息)
        """
        try:
            if not dataset_folders:
                return False, "数据集文件夹列表为空"
            
            # 检查每个文件夹
            total_train_images = 0
            total_val_images = 0
            total_labels = 0
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
            
            for folder in dataset_folders:
                if not os.path.exists(folder):
                    return False, f"文件夹不存在: {folder}"
                
                if not os.path.isdir(folder):
                    return False, f"路径不是文件夹: {folder}"
                
                # 智能检测数据集结构
                folder_train_images = 0
                folder_val_images = 0
                folder_labels = 0
                
                # 方案1: 标准YOLO格式 (folder/images/train, folder/images/val)
                images_train_dir = os.path.join(folder, 'images', 'train')
                images_val_dir = os.path.join(folder, 'images', 'val')
                labels_train_dir = os.path.join(folder, 'labels', 'train')
                labels_val_dir = os.path.join(folder, 'labels', 'val')
                
                if os.path.exists(images_train_dir):
                    train_count = sum(1 for f in os.listdir(images_train_dir) 
                                    if any(f.lower().endswith(ext) for ext in image_extensions))
                    folder_train_images += train_count
                    
                    if os.path.exists(images_val_dir):
                        val_count = sum(1 for f in os.listdir(images_val_dir) 
                                      if any(f.lower().endswith(ext) for ext in image_extensions))
                        folder_val_images += val_count
                    
                    if os.path.exists(labels_train_dir):
                        label_count = sum(1 for f in os.listdir(labels_train_dir) 
                                        if f.lower().endswith('.txt'))
                        folder_labels += label_count
                
                # 方案2: 如果folder本身就是images目录 (例如: dataset/train/images)
                # 检查父目录是否有train/val结构
                elif os.path.basename(folder) == 'images':
                    parent_dir = os.path.dirname(folder)
                    # 检查是否在train或val目录下
                    if os.path.basename(parent_dir) in ['train', 'val']:
                        # folder是 dataset/train/images 或 dataset/val/images
                        train_count = sum(1 for f in os.listdir(folder) 
                                        if any(f.lower().endswith(ext) for ext in image_extensions))
                        if os.path.basename(parent_dir) == 'train':
                            folder_train_images += train_count
                        else:
                            folder_val_images += train_count
                        
                        # 检查对应的labels目录 (dataset/train/labels)
                        labels_dir = os.path.join(parent_dir, 'labels')
                        if os.path.exists(labels_dir):
                            label_count = sum(1 for f in os.listdir(labels_dir) 
                                            if f.lower().endswith('.txt'))
                            folder_labels += label_count
                    else:
                        # folder是简化格式的images目录 (dataset/images)
                        train_count = sum(1 for f in os.listdir(folder) 
                                        if any(f.lower().endswith(ext) for ext in image_extensions))
                        folder_train_images += train_count
                        
                        # 检查同级labels目录
                        labels_dir = os.path.join(parent_dir, 'labels')
                        if os.path.exists(labels_dir):
                            label_count = sum(1 for f in os.listdir(labels_dir) 
                                            if f.lower().endswith('.txt'))
                            folder_labels += label_count
                
                # 方案3: 直接包含图片的文件夹（递归搜索）
                else:
                    # 先检查当前目录
                    train_count = sum(1 for f in os.listdir(folder) 
                                    if os.path.isfile(os.path.join(folder, f)) and 
                                       any(f.lower().endswith(ext) for ext in image_extensions))
                    if train_count > 0:
                        folder_train_images += train_count
                        
                        # 检查同级labels
                        label_count = sum(1 for f in os.listdir(folder) 
                                        if os.path.isfile(os.path.join(folder, f)) and 
                                           f.lower().endswith('.txt'))
                        folder_labels += label_count
                    else:
                        # 如果当前目录没有图片，递归搜索子目录（最多2层）
                        for subdir in os.listdir(folder):
                            subdir_path = os.path.join(folder, subdir)
                            if os.path.isdir(subdir_path):
                                # 检查子目录中的图片
                                sub_count = sum(1 for f in os.listdir(subdir_path) 
                                              if os.path.isfile(os.path.join(subdir_path, f)) and 
                                                 any(f.lower().endswith(ext) for ext in image_extensions))
                                if sub_count > 0:
                                    folder_train_images += sub_count
                                    
                                    # 检查子目录中的labels
                                    sub_label_count = sum(1 for f in os.listdir(subdir_path) 
                                                        if os.path.isfile(os.path.join(subdir_path, f)) and 
                                                           f.lower().endswith('.txt'))
                                    folder_labels += sub_label_count
                
                total_train_images += folder_train_images
                total_val_images += folder_val_images
                total_labels += folder_labels
            
            # 验证是否有足够的数据
            if total_train_images == 0 and total_val_images == 0:
                return False, f"所有数据集文件夹中都没有找到图片文件\n请检查文件夹路径是否正确"
            
            # 如果没有训练图片但有验证图片，将验证图片作为训练图片
            if total_train_images == 0 and total_val_images > 0:
                total_train_images = total_val_images
            
            # 返回验证结果
            msg = f"数据集验证通过\n"
            msg += f"总训练图片: {total_train_images} 张\n"
            if total_val_images > 0:
                msg += f"总验证图片: {total_val_images} 张\n"
            if total_labels > 0:
                msg += f"总标注文件: {total_labels} 个"
            
            return True, msg
            
        except Exception as e:
            return False, f"验证过程出错: {str(e)}"
    
    def _validateTrainingData(self, save_liquid_data_path):
        """验证训练数据（简化版，用于向后兼容）"""
        result, _ = self._validateTrainingDataWithDetails(save_liquid_data_path)
        return result
    
    def _validateTrainingDataWithDetails(self, save_liquid_data_path):
        """
        验证训练数据（详细版）
        
        Returns:
            tuple: (是否有效, 错误消息)
        """
        try:
            if not os.path.exists(save_liquid_data_path):
                return False, f"数据集配置文件不存在: {save_liquid_data_path}"
            
            # 检查data.yaml文件
            if not save_liquid_data_path.endswith('.yaml'):
                return False, "数据集配置文件必须是 .yaml 格式"
            
            # 读取并验证配置
            with open(save_liquid_data_path, 'r', encoding='utf-8') as f:
                data_config = yaml.safe_load(f)
            
            if not data_config:
                return False, "数据集配置文件为空或格式错误"
            
            # 检查必要的字段
            if 'train' not in data_config:
                return False, "data.yaml 中缺少 'train' 字段"
            
            if 'val' not in data_config:
                return False, "data.yaml 中缺少 'val' 字段"
            
            # 获取data.yaml所在目录
            data_yaml_dir = os.path.dirname(os.path.abspath(save_liquid_data_path))
            
            # 检查路径是否存在
            train_dir = data_config.get('train')
            val_dir = data_config.get('val')
            
            if not train_dir:
                return False, "'train' 字段为空"
            
            if not val_dir:
                return False, "'val' 字段为空"
            
            # 如果是相对路径，转换为相对于data.yaml的绝对路径
            if not os.path.isabs(train_dir):
                train_dir = os.path.join(data_yaml_dir, train_dir)
            
            if not os.path.isabs(val_dir):
                val_dir = os.path.join(data_yaml_dir, val_dir)
            
            # 检查路径是否存在
            if not os.path.exists(train_dir):
                return False, f"训练集路径不存在: {train_dir}\n请确保该目录存在并包含图片文件。"
            
            if not os.path.exists(val_dir):
                return False, f"验证集路径不存在: {val_dir}\n请确保该目录存在并包含图片文件。"
            
            # 检查路径下是否有图片文件
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
            
            train_images = []
            val_images = []
            
            # 检查训练集
            if os.path.isdir(train_dir):
                for file in os.listdir(train_dir):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        train_images.append(file)
            else:
                return False, f"训练集路径不是目录: {train_dir}"
            
            # 检查验证集
            if os.path.isdir(val_dir):
                for file in os.listdir(val_dir):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        val_images.append(file)
            else:
                return False, f"验证集路径不是目录: {val_dir}"
            
            # 检查是否有图片文件
            if len(train_images) == 0:
                return False, f"训练集目录为空: {train_dir}\n请将训练图片放入该目录。"
            
            if len(val_images) == 0:
                return False, f"验证集目录为空: {val_dir}\n请将验证图片放入该目录。"
            
            # 检查是否有标注文件（可选，但建议有）
            train_labels_dir = os.path.join(os.path.dirname(train_dir), 'labels')
            val_labels_dir = os.path.join(os.path.dirname(val_dir), 'labels')
            
            train_labels_count = 0
            val_labels_count = 0
            
            if os.path.exists(train_labels_dir):
                for file in os.listdir(train_labels_dir):
                    if file.lower().endswith('.txt'):
                        train_labels_count += 1
            
            if os.path.exists(val_labels_dir):
                for file in os.listdir(val_labels_dir):
                    if file.lower().endswith('.txt'):
                        val_labels_count += 1
            
            # 构建成功消息
            success_msg = f"数据集验证成功：\n"
            success_msg += f"  训练图片: {len(train_images)} 张\n"
            success_msg += f"  验证图片: {len(val_images)} 张\n"
            
            if train_labels_count > 0 or val_labels_count > 0:
                success_msg += f"  训练标注: {train_labels_count} 个\n"
                success_msg += f"  验证标注: {val_labels_count} 个\n"
            else:
                success_msg += f"  警告: 未找到标注文件，训练将使用无监督学习模式\n"
            
            return True, success_msg
            
        except yaml.YAMLError as e:
            return False, f"YAML 解析错误: {str(e)}"
        except Exception as e:
            import traceback
            return False, f"验证训练数据失败: {str(e)}\n{traceback.format_exc()}"
    
    def _refreshModelSetPage(self):
        """刷新模型集管理页面以显示新训练的模型"""
        try:
            # 通过主窗口访问模型集管理页面
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'modelSetPage'):
                # 调用模型集页面的刷新方法
                self.main_window.modelSetPage.loadModelsFromConfig()
                self._appendLog("\n 模型集管理页面已更新\n")
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _createAnnotationEngine(self):
        """创建标注引擎"""
        try:
            # 创建一个简单的标注引擎类
            class SimpleAnnotationEngine:
                def __init__(self):
                    self.step = 0  # 0=画框模式, 1=标记液位模式
                    self.boxes = []  # 存储ROI (cx, cy, size) 格式
                    self.bottom_points = []  # 存储底部标记点
                    self.top_points = []  # 存储顶部标记点
                
                def add_box(self, cx, cy, size):
                    """
                    添加ROI（不自动生成顶部线条和底部线条）
                    
                    Args:
                        cx: 框中心x坐标
                        cy: 框中心y坐标
                        size: 框的边长
                    """
                    self.boxes.append((cx, cy, size))
                
                def add_bottom(self, x, y):
                    """添加底部标记点"""
                    self.bottom_points.append((int(x), int(y)))
                
                def add_top(self, x, y):
                    """添加顶部标记点"""
                    self.top_points.append((int(x), int(y)))
                
                def get_mission_results(self):
                    """获取标注结果"""
                    return {
                        'boxes': self.boxes,
                        'bottom_points': self.bottom_points,
                        'top_points': self.top_points
                    }
            
            engine = SimpleAnnotationEngine()
            return engine
            
        except Exception as e:
            return None
    
    def _handleStartAnnotation(self):
        """处理开始标注按钮点击"""
        try:
            import cv2
            import numpy as np
            
            # 创建标注引擎（如果还没有的话）
            if not hasattr(self, 'annotation_engine') or not self.annotation_engine:
                self.annotation_engine = self._createAnnotationEngine()
            
            # 获取测试文件路径
            if not hasattr(self.training_panel, 'test_file_input'):
                QtWidgets.QMessageBox.warning(
                    self.training_panel,
                    "错误",
                    "无法获取测试文件输入控件"
                )
                return
            
            # 从QLineEdit获取测试文件路径（浏览选择的文件）
            test_file_path = self.training_panel.test_file_input.text().strip()
            test_file_display = os.path.basename(test_file_path) if test_file_path else ""
            
            if not test_file_path:
                QtWidgets.QMessageBox.warning(
                    self.training_panel,
                    "提示",
                    '请点击"浏览..."按钮选择测试文件'
                )
                return
            
            # 读取标注帧
            annotation_frame = None
            test_path = Path(test_file_path)
            
            # 视频格式
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
            
            if test_path.is_file():
                # 检查是否为视频文件
                if test_path.suffix.lower() in video_extensions:
                    # 读取视频的第10帧
                    cap = cv2.VideoCapture(str(test_path))
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 9)
                        ret, frame = cap.read()
                        if ret:
                            annotation_frame = frame
                        cap.release()
                    else:
                        QtWidgets.QMessageBox.warning(
                            self.training_panel,
                            "视频打开失败",
                            f"无法打开视频文件：{test_path.name}"
                        )
                
                # 检查是否为图片文件
                elif test_path.suffix.lower() in image_formats:
                    # 直接读取图片
                    try:
                        annotation_frame = cv2.imread(test_file_path)
                        if annotation_frame is None:
                            # 尝试使用不同的方法读取
                            try:
                                import numpy as np
                                from PIL import Image
                                pil_image = Image.open(test_file_path)
                                # 转换为OpenCV格式
                                if pil_image.mode == 'RGB':
                                    annotation_frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                                elif pil_image.mode == 'RGBA':
                                    annotation_frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
                                else:
                                    annotation_frame = np.array(pil_image)
                            except Exception as pil_e:
                                pass
                                
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            
            # 文件夹
            elif test_path.is_dir():
                # 读取文件夹内第一张图片
                try:
                    files = os.listdir(test_file_path)
                    
                    for file in files:
                        if any(file.lower().endswith(fmt) for fmt in image_formats):
                            first_image_path = os.path.join(test_file_path, file)
                            annotation_frame = cv2.imread(first_image_path)
                            break
                    else:
                        # 给出更友好的提示
                        QtWidgets.QMessageBox.warning(
                            self.training_panel,
                            "文件夹为空",
                            f"所选文件夹内没有图片文件！\n\n"
                            f"文件夹路径: {test_file_path}\n\n"
                            f"请确保文件夹内包含以下格式的图片：\n"
                            f"  • JPG/JPEG\n"
                            f"  • PNG\n"
                            f"  • BMP\n"
                            f"  • TIFF\n"
                            f"  • WEBP\n\n"
                            f"或者直接选择单个图片文件进行标注。"
                        )
                        return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            
            if annotation_frame is None:
                error_msg = f"无法读取标注帧\n\n调试信息:\n"
                error_msg += f"- 显示名称: {test_file_display}\n"
                error_msg += f"- 实际路径: {test_file_path}\n"
                error_msg += f"- 路径存在: {test_path.exists()}\n"
                error_msg += f"- 是文件: {test_path.is_file()}\n"
                error_msg += f"- 是文件夹: {test_path.is_dir()}\n"
                if test_path.is_file():
                    error_msg += f"- 文件扩展名: {test_path.suffix.lower()}\n"
                
                QtWidgets.QMessageBox.warning(
                    self.training_panel,
                    "错误",
                    error_msg
                )
                return
            
            # 显示标注界面
            self._showAnnotationWidget(annotation_frame)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self.training_panel,
                "错误",
                f"处理标注请求时发生错误：\n{str(e)}"
            )
    
    def _showAnnotationWidget(self, frame):
        """显示标注界面（在显示面板中嵌入）"""
        try:
            # 导入标注组件
            try:
                from ...widgets.videopage.general_set import AnnotationWidget
            except ImportError:
                from widgets.videopage.general_set import AnnotationWidget
            
            # 创建标注界面组件（不作为独立窗口）
            self.annotation_widget = AnnotationWidget(self.training_panel, self.annotation_engine)
            
            # 设置通道名称（用于生成区域默认名称）
            self.annotation_widget.setChannelName("test_model")
            
            # 连接标注引擎信号
            self.annotation_widget.annotationEngineRequested.connect(self._handleAnnotationEngineRequest)
            self.annotation_widget.frameLoadRequested.connect(self._handleFrameLoadRequest)
            self.annotation_widget.annotationDataRequested.connect(self._handleAnnotationDataRequest)
            
            # 连接标注完成信号
            def on_annotation_completed(boxes, bottoms, tops):
                # 保存标注结果到临时配置
                self._saveTestAnnotationResult(boxes, bottoms, tops,
                                               self.annotation_widget.area_names,
                                               self.annotation_widget.area_heights)
                
                # 关键修改：先关闭全屏窗口，再显示预览
                # 延迟显示预览，确保全屏窗口已关闭
                def show_preview():
                    # 切换到显示面板
                    if hasattr(self.training_panel, 'display_layout'):
                        self.training_panel.display_layout.setCurrentIndex(1)
                    # 显示预览图
                    self._showAnnotationPreview(
                        frame, boxes, bottoms, tops,
                        self.annotation_widget.area_names,
                        self.annotation_widget.area_heights
                    )
                
                QtCore.QTimer.singleShot(200, show_preview)
            
            def on_annotation_cancelled():
                # 隐藏标注界面，显示提示标签
                if hasattr(self.training_panel, 'display_layout'):
                    self.training_panel.display_layout.setCurrentIndex(0)  # 切换到提示标签
            
            self.annotation_widget.annotationCompleted.connect(on_annotation_completed)
            self.annotation_widget.annotationCancelled.connect(on_annotation_cancelled)
            
            # 加载图像到标注界面
            if self.annotation_widget.loadFrame(frame):
                # 关键修改：显示为全屏标注界面
                # 标注界面配置为全屏显示（在_initUI中已设置）
                # 这样用户可以进行全屏标注操作
                self.annotation_widget.setWindowTitle("模型测试标注 - 全屏模式")
            else:
                QtWidgets.QMessageBox.warning(
                    self.training_panel,
                    "加载失败",
                    "无法加载图像到标注界面"
                )
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self.training_panel,
                "标注界面创建失败",
                f"创建标注界面时发生错误：\n{str(e)}"
            )
    
    def _saveTestAnnotationResult(self, boxes, bottoms, tops, area_names=None, area_heights=None):
        """保存测试标注结果"""
        try:
            project_root = get_project_root()
            config_dir = os.path.join(project_root, 'database', 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            # 保存到model_test_annotation_result.yaml
            annotation_file = os.path.join(config_dir, 'model_test_annotation_result.yaml')
            
            annotation_data = {
                'test_model': {
                    'boxes': boxes,
                    'bottoms': bottoms,
                    'tops': tops,
                    'areas': {}
                }
            }
            
            # 添加区域名称和高度
            if area_names and area_heights:
                for i, (name, height) in enumerate(zip(area_names, area_heights)):
                    area_key = f'area_{i+1}'
                    annotation_data['test_model']['areas'][area_key] = {
                        'name': name,
                        'height': height
                    }
            
            with open(annotation_file, 'w', encoding='utf-8') as f:
                yaml.dump(annotation_data, f, allow_unicode=True, default_flow_style=False)
            
            pass  # 测试标注结果已保存
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass  # 保存失败
    
    def _handleAnnotationEngineRequest(self):
        """处理标注引擎请求"""
        if self.annotation_engine and self.annotation_widget:
            self.annotation_widget.setAnnotationEngine(self.annotation_engine)
    
    def _handleFrameLoadRequest(self):
        """处理帧加载请求"""
        # 这里可以添加帧加载的业务逻辑
        pass
    
    def _handleAnnotationDataRequest(self):
        """处理标注数据请求"""
        try:
            if self.annotation_engine and self.annotation_widget:
                # 从标注引擎获取实际的标注数据
                boxes = self.annotation_engine.boxes
                bottoms = self.annotation_engine.bottom_points
                tops = self.annotation_engine.top_points
                
                # 发送标注完成信号
                self.annotation_widget.showAnnotationCompleted(boxes, bottoms, tops)
            else:
                if self.annotation_widget:
                    self.annotation_widget.showAnnotationError("标注引擎未初始化")
        except Exception as e:
            import traceback
            traceback.print_exc()
            if self.annotation_widget:
                self.annotation_widget.showAnnotationError(f"获取标注数据失败: {str(e)}")
    
    def _displayAnnotationPreview(self, original_frame, boxes, bottoms, tops, area_names, area_heights):
        """显示标注预览"""
        try:
            # 切换到显示面板
            if hasattr(self.training_panel, 'display_layout'):
                self.training_panel.display_layout.setCurrentIndex(1)  # 切换到显示面板
                pass
            
            # 显示标注预览图
            self._showAnnotationPreview(original_frame, boxes, bottoms, tops, area_names, area_heights)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass
    
    def _showAnnotationPreview(self, original_frame, boxes, bottoms, tops, area_names, area_heights):
        """在显示面板中显示标注预览图"""
        try:
            import cv2
            import numpy as np
            from PyQt5 import QtGui
            from datetime import datetime
            
            # 复制原始帧
            preview_frame = original_frame.copy()
            
            # 注意：这里不绘制标注框和线，因为标注工具已经绘制过了
            # 如果需要绘制，可以在这里添加绘制代码
            
            # 转换为RGB格式
            rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
            
            # 缩放图像 - 宽度500px，高度最大350px
            target_width = 500  # 从300增加到500
            h, w = rgb_frame.shape[:2]
            scale = target_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            if new_h > 350:  # 高度最大350px（从200增加到350）
                scale = 350 / new_h
                new_w = int(new_w * scale)
                new_h = int(new_h * scale)
            
            pass
            
            rgb_frame_resized = cv2.resize(rgb_frame, (new_w, new_h))
            
            # 转换为QImage
            h, w, ch = rgb_frame_resized.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(rgb_frame_resized.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 保存到临时文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            preview_image_path = os.path.join(temp_dir, "annotation_preview.png")
            qt_image.save(preview_image_path)
            
            # 在显示面板中显示结果
            if hasattr(self.training_panel, 'display_panel'):
                current_time = datetime.now().strftime("%H:%M:%S")
                
                # 生成HTML内容
                image_path_formatted = preview_image_path.replace('\\', '/')
                
                preview_html = f"""
                <div style="font-family: Arial, sans-serif; font-size: 9pt; text-align: center;">
                    <div style="color: #0078d7; font-weight: bold; margin-bottom: 8px;">
                        标注完成 ({current_time}) - {len(boxes)}个区域
                    </div>
                    <div style="margin-bottom: 10px;">
                        <img src="file:///{image_path_formatted}" style="max-width: 100%; max-height: 370px; border: 1px solid #dee2e6; border-radius: 4px;">
                    </div>
                    <div style="font-size: 8pt; color: #666; text-align: left;">
                """
                
                for i, (cx, cy, size) in enumerate(boxes):
                    area_name = area_names[i] if i < len(area_names) else f"区域{i+1}"
                    area_height = area_heights[i] if i < len(area_heights) else "20mm"
                    preview_html += f"""
                        <div style="margin: 2px 0;"><strong>{area_name}</strong> (容器高度: {area_height})</div>
                    """
                
                preview_html += """
                    </div>
                </div>
                """
                
                self.training_panel.display_panel.setHtml(preview_html)
                
                pass
            else:
                pass
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass
            
            # 降级显示：使用纯文本HTML
            if hasattr(self.training_panel, 'display_panel'):
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                text_preview = f"""
标注完成时间: {current_time}
ROI数量: {len(boxes)}
底部标记点数量: {len(bottoms)}
顶部标记点数量: {len(tops)}

区域详细信息:
"""
                for i, (cx, cy, size) in enumerate(boxes):
                    area_name = area_names[i] if i < len(area_names) else f"区域{i+1}"
                    area_height = area_heights[i] if i < len(area_heights) else "20mm"
                    text_preview += f"- {area_name}: 中心({cx}, {cy}), 尺寸{size}px, 容器高度{area_height}\n"
                
                self.training_panel.display_panel.setPlainText(text_preview)
    
    def _updateRealtimePlayerStats(self, current_frame, total_frames, success_count, fail_count):
        """更新实时播放器统计信息（已禁用）"""
        # 统计信息控件已删除，此方法保留为空以保持兼容性
        pass


    def _showAnnotationPreview(self, original_frame, boxes, bottoms, tops, area_names, area_heights):
        """在显示面板中显示标注结果预览"""
        try:
            import cv2
            import numpy as np
            from qtpy import QtGui
            from datetime import datetime
            
            # 复制原始帧用于绘制
            preview_frame = original_frame.copy()
            
            # 绘制标注结果
            # 使用PIL绘制中文文本
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np
            
            # 转换为PIL图像
            pil_image = Image.fromarray(cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)
            
            # 尝试加载中文字体
            try:
                # Windows系统字体路径
                font_large = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)  # 微软雅黑，大字体
                font_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)  # 微软雅黑，小字体
            except:
                # 如果加载失败，使用默认字体
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            for i, (cx, cy, size) in enumerate(boxes):
                # 绘制检测框
                half = size // 2
                top = cy - half
                bottom = cy + half
                left = cx - half
                right = cx + half
                
                # 绘制检测框（黄色）
                cv2.rectangle(preview_frame, (left, top), (right, bottom), (0, 255, 255), 2)
                
                # 绘制区域名称（使用PIL支持中文）
                if i < len(area_names):
                    area_name = area_names[i]
                    draw.text((left, top - 30), area_name, font=font_large, fill=(255, 255, 0))  # 黄色
            
            # 绘制底部线条（绿色）
            for pt in bottoms:
                cv2.circle(preview_frame, pt, 5, (0, 255, 0), -1)
                draw.text((pt[0] + 10, pt[1] - 8), "底部", font=font_small, fill=(0, 255, 0))  # 绿色
            
            # 绘制顶部线条（红色）
            for pt in tops:
                cv2.circle(preview_frame, pt, 5, (0, 0, 255), -1)
                draw.text((pt[0] + 10, pt[1] - 8), "顶部", font=font_small, fill=(255, 0, 0))  # 红色
            
            # 转换回OpenCV格式
            preview_frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # 转换为RGB并缩放以适应显示面板
            rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
            
            # 调整标注预览显示尺寸 - 增大显示框以便清楚显示标注框
            target_width = 500  # 目标宽度（从300增加到500）
            h, w = rgb_frame.shape[:2]
            scale = target_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            if new_h > 350:  # 如果高度超过350，再次缩放（从200增加到350）
                scale = 350 / new_h
                new_w = int(new_w * scale)
                new_h = int(new_h * scale)
            
            pass
            
            rgb_frame_resized = cv2.resize(rgb_frame, (new_w, new_h))
            
            # 转换为QImage并保存为临时文件
            h, w, ch = rgb_frame_resized.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(rgb_frame_resized.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 保存预览图像到临时文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            preview_image_path = os.path.join(temp_dir, "annotation_preview.png")
            qt_image.save(preview_image_path)
            
            # 在显示面板中显示结果信息和图像
            if hasattr(self.training_panel, 'display_panel'):
                current_time = datetime.now().strftime("%H:%M:%S")
                
                # 构建HTML内容
                image_path_formatted = preview_image_path.replace('\\', '/')
                
                preview_html = f"""
                <div style="font-family: Arial, sans-serif; font-size: 9pt; text-align: center;">
                    <div style="color: #0078d7; font-weight: bold; margin-bottom: 8px;">
                        标注完成 ({current_time}) - {len(boxes)}个区域
                    </div>
                    <div style="margin-bottom: 10px;">
                        <img src="file:///{image_path_formatted}" style="max-width: 100%; max-height: 370px; border: 1px solid #dee2e6; border-radius: 4px;">
                    </div>
                    <div style="font-size: 8pt; color: #666; text-align: left;">
                """
                
                for i, (cx, cy, size) in enumerate(boxes):
                    area_name = area_names[i] if i < len(area_names) else f"区域{i+1}"
                    area_height = area_heights[i] if i < len(area_heights) else "20mm"
                    preview_html += f"""
                        <div style="margin: 2px 0;"><strong>{area_name}</strong> ({area_height})</div>
                    """
                
                preview_html += """
                    </div>
                </div>
                """
                
                self.training_panel.display_panel.setHtml(preview_html)
                
                pass
            else:
                pass
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass
            
            # 如果HTML显示失败，使用纯文本显示
            if hasattr(self.training_panel, 'display_panel'):
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                text_preview = f"""标注结果预览
完成时间: {current_time}
ROI数量: {len(boxes)}
底部标记点: {len(bottoms)}
顶部标记点: {len(tops)}

区域详情:
"""
                for i, (cx, cy, size) in enumerate(boxes):
                    area_name = area_names[i] if i < len(area_names) else f"区域{i+1}"
                    area_height = area_heights[i] if i < len(area_heights) else "20mm"
                    text_preview += f"- {area_name}: 中心({cx}, {cy}), 尺寸{size}px, 高度{area_height}\n"
                
                self.training_panel.display_panel.setPlainText(text_preview)
    
    def _addTrainedModelToModelSet(self, converted_files, weights_dir):
        """将训练完成的模型自动添加到模型集配置（模型已经在detection_model目录中）"""
        try:
            self._appendLog("\n正在将新模型添加到模型集...\n")
            
            # 从training_worker获取模型输出目录
            model_output_dir = None
            if self.training_worker and hasattr(self.training_worker, "training_report"):
                model_output_dir = self.training_worker.training_report.get("model_output_dir")
            
            if not model_output_dir or not os.path.exists(model_output_dir):
                self._appendLog("[WARNING] 无法获取模型输出目录\n")
                return
            
            self._appendLog(f"[同步] 模型目录: {model_output_dir}\n")
            
            # 生成模型名称
            model_name = self.current_exp_name if self.current_exp_name else "trained_model"
            
            # 在weights子目录中查找模型文件
            weights_dir = os.path.join(model_output_dir, "weights")
            search_dirs = [weights_dir, model_output_dir]  # 先在weights子目录查找，再在根目录查找
            
            best_model_path = None
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                
                # 查找best模型
                for filename in os.listdir(search_dir):
                    if filename.startswith('best.') and filename.endswith('.dat'):
                        best_model_path = os.path.join(search_dir, filename)
                        self._appendLog(f"[同步] 找到best模型: {filename} (位置: {os.path.basename(search_dir)})\n")
                        break
                
                if best_model_path:
                    break
                
                # 如果没有best，查找last模型
                for filename in os.listdir(search_dir):
                    if filename.startswith('last.') and filename.endswith('.dat'):
                        best_model_path = os.path.join(search_dir, filename)
                        self._appendLog(f"[同步] 找到last模型: {filename} (位置: {os.path.basename(search_dir)})\n")
                        break
                
                if best_model_path:
                    break
                
                # 如果还没有，查找epoch模型
                epoch_files = []
                for filename in os.listdir(search_dir):
                    if filename.startswith('epoch') and filename.endswith('.dat'):
                        epoch_files.append(filename)
                if epoch_files:
                    epoch_files.sort(reverse=True)
                    best_model_path = os.path.join(search_dir, epoch_files[0])
                    self._appendLog(f"[同步] 找到epoch模型: {epoch_files[0]} (位置: {os.path.basename(search_dir)})\n")
                    break
            
            if not best_model_path:
                self._appendLog("[WARNING] 未找到可用的模型文件\n")
                self._appendLog(f"  已搜索目录: {model_output_dir} 和 {weights_dir}\n")
                return
            
            # 获取模型文件信息
            model_size = self._getFileSize(best_model_path)
            
            # 创建模型参数
            model_params = {
                'name': model_name,
                'type': 'Detection Model',
                'path': best_model_path,
                'config_path': '',
                'description': f'训练于 {self._getCurrentTimestamp()}',
                'size': model_size,
                'classes': 1,  # 液位检测单类别
                'input': '640x640',
                'confidence': 0.5,
                'iou': 0.45,
                'device': 'CUDA:0 (GPU)',
                'batch_size': 16,
                'blur_training': 100,
                'epochs': self.training_params.get('epochs', 100) if hasattr(self, 'training_params') else 100,
                'workers': 8,
                'is_trained': True,  # 标记为训练模型
                'training_date': self._getCurrentTimestamp()
            }
            
            # 保存到模型集配置（模型已经在正确位置，不需要移动）
            self._saveModelToConfig(model_name, model_params)
            
            self._appendLog(f"新模型已添加到模型集: {model_name}\n")
            self._appendLog(f"  路径: {model_params['path']}\n")
            self._appendLog(f"  大小: {model_size}\n")
            
        except Exception as e:
            self._appendLog(f"[ERROR] 添加模型到模型集失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
    
    def _getTrainingNotes(self):
        """获取训练页面的笔记内容"""
        try:
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'getTrainingNotes'):
                notes = self.training_panel.getTrainingNotes()
                if notes:
                    self._appendLog(f"[笔记] 获取到训练笔记，长度: {len(notes)} 字符\n")
                    return notes
                else:
                    self._appendLog("[笔记] 未输入训练笔记\n")
                    return ""
            else:
                self._appendLog("[笔记] 无法获取训练页面笔记接口\n")
                return ""
        except Exception as e:
            self._appendLog(f"[ERROR] 获取训练笔记失败: {str(e)}\n")
            return ""
    
    def _clearTrainingNotes(self):
        """清空训练页面的笔记内容"""
        try:
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'clearTrainingNotes'):
                self.training_panel.clearTrainingNotes()
                self._appendLog("[笔记] 训练笔记已清空\n")
            else:
                self._appendLog("[笔记] 无法获取训练页面笔记清空接口\n")
        except Exception as e:
            self._appendLog(f"[ERROR] 清空训练笔记失败: {str(e)}\n")
    
    def _enableNotesButtons(self):
        """启用训练页面的笔记保存和提交按钮"""
        try:
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'enableNotesButtons'):
                self.training_panel.enableNotesButtons()
                self._appendLog("[笔记] 笔记保存和提交按钮已启用\n")
            else:
                self._appendLog("[笔记] 无法获取训练页面笔记按钮接口\n")
        except Exception as e:
            self._appendLog(f"[ERROR] 启用笔记按钮失败: {str(e)}\n")
    
    def _disableNotesButtons(self):
        """禁用训练页面的笔记保存和提交按钮"""
        try:
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'disableNotesButtons'):
                self.training_panel.disableNotesButtons()
                self._appendLog("[笔记] 笔记保存和提交按钮已禁用\n")
            else:
                self._appendLog("[笔记] 无法获取训练页面笔记按钮接口\n")
        except Exception as e:
            self._appendLog(f"[ERROR] 禁用笔记按钮失败: {str(e)}\n")
    
    def saveNotesToLatestModel(self, notes):
        """保存笔记到最新训练的模型目录（同时保存到模型根目录和training_results目录）"""
        try:
            if not notes or not notes.strip():
                self._appendLog("[笔记] 笔记内容为空，无需保存\n")
                QtWidgets.QMessageBox.information(self.main_window, "提示", "笔记内容为空，无需保存")
                return False
            
            # 获取最新的模型目录
            latest_model_dir = self._getLatestModelDirectory()
            if not latest_model_dir:
                self._appendLog("[ERROR] 无法找到最新的模型目录\n")
                QtWidgets.QMessageBox.warning(self.main_window, "错误", "无法找到最新的训练模型目录")
                return False
            
            model_id = os.path.basename(latest_model_dir)
            
            # 准备笔记内容（带时间戳和模型信息）
            notes_content = f"训练笔记 - 模型{model_id}\n"
            notes_content += f"保存时间: {self._getCurrentTimestamp()}\n"
            notes_content += "="*50 + "\n\n"
            notes_content += notes
            
            try:
                # 1. 保存到模型根目录（用于模型描述生成）
                notes_file_root = os.path.join(latest_model_dir, 'training_notes.txt')
                with open(notes_file_root, 'w', encoding='utf-8') as f:
                    f.write(notes_content)
                self._appendLog(f"[笔记] 笔记已保存到模型根目录: {notes_file_root}\n")
                
                # 2. 保存到training_results目录（用于训练结果归档）
                training_results_dir = os.path.join(latest_model_dir, 'training_results')
                if not os.path.exists(training_results_dir):
                    os.makedirs(training_results_dir, exist_ok=True)
                
                notes_file_results = os.path.join(training_results_dir, 'training_notes.txt')
                with open(notes_file_results, 'w', encoding='utf-8') as f:
                    f.write(notes_content)
                self._appendLog(f"[笔记] 笔记已保存到训练结果目录: {notes_file_results}\n")
                
                # 保存成功后清空笔记内容
                self._clearTrainingNotes()
                
                QtWidgets.QMessageBox.information(
                    self.main_window, 
                    "保存成功", 
                    f"训练笔记已保存到模型{model_id}文件夹:\n"
                    f"• {latest_model_dir}\\training_notes.txt\n"
                    f"• {latest_model_dir}\\training_results\\training_notes.txt\n\n"
                    f"笔记内容已清空"
                )
                return True
                
            except Exception as e:
                self._appendLog(f"[ERROR] 保存笔记文件失败: {str(e)}\n")
                QtWidgets.QMessageBox.critical(self.main_window, "保存失败", f"保存笔记文件失败:\n{str(e)}")
                return False
                
        except Exception as e:
            self._appendLog(f"[ERROR] 保存笔记到最新模型失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self.main_window, "错误", f"保存笔记失败:\n{str(e)}")
            return False
    
    def _getLatestModelDirectory(self):
        """获取最新的detection_model目录"""
        try:
            project_root = get_project_root()
            detection_model_dir = os.path.join(project_root, 'database', 'model', 'detection_model')
            
            if not os.path.exists(detection_model_dir):
                return None
            
            # 获取所有数字目录
            digit_dirs = []
            for item in os.listdir(detection_model_dir):
                item_path = os.path.join(detection_model_dir, item)
                if os.path.isdir(item_path) and item.isdigit():
                    digit_dirs.append(int(item))
            
            if not digit_dirs:
                return None
            
            # 返回最大数字的目录
            latest_id = max(digit_dirs)
            latest_dir = os.path.join(detection_model_dir, str(latest_id))
            
            self._appendLog(f"[笔记] 找到最新模型目录: detection_model/{latest_id}\n")
            return latest_dir
            
        except Exception as e:
            self._appendLog(f"[ERROR] 获取最新模型目录失败: {str(e)}\n")
            return None
    
    def _moveModelToDetectionDir(self, model_path, model_name, weights_dir, training_notes=""):
        """将训练完成的模型移动到detection_model目录"""
        try:
            import shutil
            from pathlib import Path
            
            self._appendLog(f"\n开始移动模型到detection_model目录...\n")
            
            # 获取项目根目录
            project_root = get_project_root()
            detection_model_dir = os.path.join(project_root, 'database', 'model', 'detection_model')
            
            # 确保detection_model目录存在
            os.makedirs(detection_model_dir, exist_ok=True)
            
            # 获取下一个可用的数字ID
            existing_dirs = []
            for item in os.listdir(detection_model_dir):
                item_path = os.path.join(detection_model_dir, item)
                if os.path.isdir(item_path) and item.isdigit():
                    existing_dirs.append(int(item))
            
            next_id = max(existing_dirs) + 1 if existing_dirs else 1
            target_model_dir = os.path.join(detection_model_dir, str(next_id))
            
            self._appendLog(f"  目标目录: {target_model_dir}\n")
            
            # 创建目标目录结构
            os.makedirs(target_model_dir, exist_ok=True)
            
            # 创建training_results目录用于存放训练结果文件
            training_results_dir = os.path.join(target_model_dir, 'training_results')
            os.makedirs(training_results_dir, exist_ok=True)
            
            # 处理weights目录：.dat文件保留在train/weights，其他文件不复制
            if weights_dir and os.path.exists(weights_dir):
                self._appendLog(f"  整理weights目录内容...\n")
                
                # 检查.dat文件是否已在train/weights目录中
                train_weights_dir = weights_dir  # weights_dir已经指向train/weights
                dat_files_found = False
                for filename in os.listdir(train_weights_dir):
                    if filename.endswith('.dat'):
                        dat_files_found = True
                        self._appendLog(f"    .dat文件保留在train/weights: {filename}\n")
                
                if not dat_files_found:
                    self._appendLog(f"    警告: 未找到.dat文件\n")
                
                # 复制训练目录的其他文件到training_results目录
                train_exp_dir = os.path.dirname(weights_dir)
                if os.path.exists(train_exp_dir):
                    self._appendLog(f"  移动训练结果文件到training_results...\n")
                    
                    for filename in os.listdir(train_exp_dir):
                        if filename != 'weights':  # 跳过weights目录
                            source_file = os.path.join(train_exp_dir, filename)
                            
                            if os.path.isfile(source_file):
                                # 所有非weights目录的文件都移动到training_results目录
                                target_file = os.path.join(training_results_dir, filename)
                                shutil.copy2(source_file, target_file)
                                self._appendLog(f"    移动: {filename}\n")
                            elif os.path.isdir(source_file):
                                # 如果是子目录（如plots），也复制到training_results
                                target_subdir = os.path.join(training_results_dir, filename)
                                shutil.copytree(source_file, target_subdir, dirs_exist_ok=True)
                                self._appendLog(f"    移动目录: {filename}/\n")
            
            # 保存训练笔记（如果有）
            if training_notes:
                notes_file = os.path.join(target_model_dir, 'training_notes.txt')
                try:
                    with open(notes_file, 'w', encoding='utf-8') as f:
                        # 添加时间戳和模型信息
                        f.write(f"训练笔记 - {model_name}\n")
                        f.write(f"训练时间: {self._getCurrentTimestamp()}\n")
                        f.write(f"模型ID: {next_id}\n")
                        f.write("="*50 + "\n\n")
                        f.write(training_notes)
                    self._appendLog(f"    保存训练笔记: training_notes.txt\n")
                except Exception as e:
                    self._appendLog(f"    保存训练笔记失败: {str(e)}\n")
            
            # 确定最终的模型文件路径（.dat文件保留在train/weights目录）
            model_filename = os.path.basename(model_path)
            # 模型文件应该已经在train/weights目录中
            final_model_path = model_path  # 直接使用原始路径
            
            if os.path.exists(final_model_path):
                self._appendLog(f"模型文件位置: {final_model_path}\n")
                self._appendLog(f"训练结果已整理到detection_model/{next_id}/training_results/\n")
                if training_notes:
                    self._appendLog(f"训练笔记已保存到detection_model/{next_id}/training_notes.txt\n")
                return final_model_path
            else:
                self._appendLog(f"模型文件不存在: {final_model_path}\n")
                return None
                
        except Exception as e:
            self._appendLog(f"[ERROR] 移动模型到detection_model失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
            return None
    
    def _saveModelToConfig(self, model_name, model_params):
        """保存模型配置文件（模型已经在detection_model目录中）"""
        try:
            from pathlib import Path
            import yaml
            
            self._appendLog(f"\n开始保存模型配置...\n")
            self._appendLog(f"  模型名称: {model_name}\n")
            self._appendLog(f"  模型路径: {model_params['path']}\n")
            
            # 获取模型所在目录（现在应该在detection_model/{数字ID}/weights/中）
            model_path = model_params['path']
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")
            
            # 获取weights目录
            weights_dir = os.path.dirname(model_path)
            # 获取模型ID目录（weights的父目录）
            model_dir = os.path.dirname(weights_dir)
            
            self._appendLog(f"  模型目录: {model_dir}\n")
            
            # 查找可用的模型文件
            model_files_found = []
            
            # 1. 查找best模型
            for filename in os.listdir(weights_dir):
                if filename.startswith('best.') and not filename.endswith('.pt'):
                    model_files_found.append(f"best模型: {filename}")
                    # 更新路径指向best模型
                    if 'best' in filename:
                        model_params['path'] = os.path.join(weights_dir, filename)
                    break
            
            # 2. 查找last模型
            for filename in os.listdir(weights_dir):
                if filename.startswith('last.') and not filename.endswith('.pt'):
                    model_files_found.append(f"last模型: {filename}")
                    break
            
            # 3. 查找epoch1模型
            for filename in os.listdir(weights_dir):
                if filename.startswith('epoch1.') and not filename.endswith('.pt'):
                    model_files_found.append(f"第一轮模型: {filename}")
                    break
            
            # 4. 查找训练日志
            log_files_found = []
            for filename in os.listdir(weights_dir):
                if filename.startswith('training_log_') and filename.endswith('.txt'):
                    log_files_found.append(filename)
            
            # 保存模型配置到 YAML 文件
            config_file = os.path.join(model_dir, 'config.yaml')
            self._appendLog(f"  保存配置文件: {config_file}\n")
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(model_params, f, allow_unicode=True, default_flow_style=False)
            
            # 生成模型描述文件
            model_id = os.path.basename(model_dir)
            self._generateModelDescription(model_dir, model_id, model_params)
            
            # 输出总结信息
            self._appendLog(f"\n模型配置已保存到detection_model/{model_id}/\n")
            self._appendLog(f"  找到的文件:\n")
            for info in model_files_found:
                self._appendLog(f"    - {info}\n")
            if log_files_found:
                for log_file in log_files_found:
                    self._appendLog(f"    - 训练日志: {log_file}\n")
            self._appendLog(f"    - 配置文件: config.yaml\n")
            self._appendLog(f"\n模型已成功保存到detection_model目录，可在模型集管理中查看！\n")
            
        except Exception as e:
            self._appendLog(f"[ERROR] 保存模型配置失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
            self._appendLog(f"\n完整错误信息:\n")
            self._appendLog(traceback.format_exc())
    
    def _generateModelDescription(self, model_dir, model_id, model_params):
        """生成模型描述文件"""
        try:
            import time
            from pathlib import Path
            
            # 获取模型文件信息
            model_path = model_params.get('path', '')
            model_file = Path(model_path)
            
            if os.path.exists(model_path):
                file_size_bytes = model_file.stat().st_size
                file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
                mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(model_file.stat().st_mtime))
            else:
                file_size_mb = "未知"
                mod_time = self._getCurrentTimestamp()
            
            # 获取训练参数
            epochs = model_params.get('epochs', '未知')
            batch_size = model_params.get('batch_size', '未知')
            input_size = model_params.get('input', '未知')
            device = model_params.get('device', '未知')
            
            # 读取训练结果（如果有results.csv）
            # 优先从training_results目录读取
            results_csv = os.path.join(model_dir, 'training_results', 'results.csv')
            if not os.path.exists(results_csv):
                # 备用：从模型根目录读取
                results_csv = os.path.join(model_dir, 'results.csv')
            
            final_epoch = ""
            train_loss = ""
            val_loss = ""
            if os.path.exists(results_csv):
                try:
                    import pandas as pd
                    df = pd.read_csv(results_csv)
                    if len(df) > 0:
                        last_row = df.iloc[-1]
                        final_epoch = int(last_row.get('epoch', 0))
                        train_loss = f"{last_row.get('train/box_loss', 0):.4f}"
                        val_loss = f"{last_row.get('val/box_loss', 0):.4f}"
                except:
                    pass
            
            # 读取训练笔记（如果有）
            notes_content = ""
            notes_file = os.path.join(model_dir, 'training_notes.txt')
            if os.path.exists(notes_file):
                try:
                    with open(notes_file, 'r', encoding='utf-8') as f:
                        notes_content = f"\n\n训练笔记\n{'='*50}\n{f.read()}"
                except:
                    pass
            
            # 生成精简的模型描述内容
            description_content = f"""模型{model_id} - 液位检测模型

训练参数
------------------------------
训练轮数: {epochs}
批次大小: {batch_size}
输入尺寸: {input_size}
训练设备: {device}

训练结果
------------------------------
最终Epoch: {final_epoch if final_epoch else '未知'}
训练损失: {train_loss if train_loss else '未知'}
验证损失: {val_loss if val_loss else '未知'}

模型说明
------------------------------
功能: 专门用于液位检测的深度学习模型
场景: 工业自动化液位监测

其他信息
------------------------------
训练时间: {model_params.get('training_date', mod_time)}
文件大小: {file_size_mb} MB
{notes_content}
"""
            
            # 1. 保存模型描述文件到模型根目录
            description_file_root = os.path.join(model_dir, 'model_description.txt')
            with open(description_file_root, 'w', encoding='utf-8') as f:
                f.write(description_content)
            self._appendLog(f"  模型描述文件已生成: model_description.txt\n")
            
            # 2. 同时保存到 training_results 目录（用于归档）
            training_results_dir = os.path.join(model_dir, 'training_results')
            if os.path.exists(training_results_dir):
                description_file_results = os.path.join(training_results_dir, 'model_description.txt')
                with open(description_file_results, 'w', encoding='utf-8') as f:
                    f.write(description_content)
                self._appendLog(f"  模型描述文件已复制到training_results目录\n")
            
            return description_file_root
            
        except Exception as e:
            self._appendLog(f"  生成模型描述文件失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
            return None
    
    def _refreshModelTestPage(self):
        """刷新模型测试页面的模型列表"""
        try:
            # 刷新训练页面的测试模型选项
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, '_loadTestModelOptions'):
                self.training_panel._loadTestModelOptions()
                self._appendLog("模型测试页面已更新\n")
            else:
                self._appendLog("[INFO] 模型测试页面未找到或不支持刷新\n")
        except Exception as e:
            self._appendLog(f"[ERROR] 刷新模型测试页面失败: {str(e)}\n")
            import traceback
            traceback.print_exc()
    
    def _getCurrentTimestamp(self):
        """获取当前时间戳字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _getFileSize(self, file_path):
        """获取文件大小（格式化字符串）"""
        try:
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            return "未知"
        except:
            return "未知"
    
    def _loadTestImages(self, test_file_path):
        """加载测试图像（支持单图、视频、文件夹）"""
        try:
            import cv2
            from pathlib import Path
            
            test_path = Path(test_file_path)
            images = []
            
            if test_path.is_file():
                # 视频格式
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
                image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
                
                file_ext = test_path.suffix.lower()
                pass
                
                if file_ext in video_extensions:
                    # 从视频中采样帧（每10帧取1帧，最多取50帧）
                    cap = cv2.VideoCapture(str(test_path))
                    if cap.isOpened():
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        pass
                        sample_interval = max(10, total_frames // 50)
                        
                        for i in range(0, total_frames, sample_interval):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                            ret, frame = cap.read()
                            if ret:
                                images.append(frame)
                            if len(images) >= 50:  # 最多50帧
                                break
                        cap.release()
                        
                elif file_ext in image_formats:
                    # 单张图片
                    frame = cv2.imread(str(test_path))
                    if frame is not None:
                        images.append(frame)
            
            elif test_path.is_dir():
                # 文件夹：读取所有图片（最多50张）
                image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
                
                try:
                    files_in_dir = os.listdir(test_file_path)
                    pass
                    
                    if not files_in_dir:
                        pass
                        return None
                    
                    image_files = []
                    for file in files_in_dir:
                        if any(file.lower().endswith(fmt) for fmt in image_formats):
                            image_files.append(file)
                    
                    pass
                    
                    if not image_files:
                        pass
                        return None
                    
                    # 尝试读取第一张图片
                    first_image = image_files[0]
                    first_image_path = os.path.join(test_file_path, first_image)
                    pass
                    
                    frame = cv2.imread(first_image_path)
                    if frame is not None:
                        images.append(frame)
                    else:
                        pass
                        
                except Exception as dir_error:
                    pass
            else:
                pass
            
            pass
            return images
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
            return None
    
    def _performModelTest(self, model_path, test_images, annotation_file):
        """执行模型测试"""
        try:
            import yaml
            import cv2
            import numpy as np
            
            # 加载模型（支持 .dat 和 .pt 格式）
            from ultralytics import YOLO
            
            if model_path.endswith('.dat'):
                # 解密 .dat 模型
                temp_model_path = self._decode_dat_model(model_path)
                
                # 验证解密后的模型文件存在
                if not os.path.exists(temp_model_path):
                    raise FileNotFoundError(f"解密后的模型文件不存在: {temp_model_path}")
                
                os.environ['YOLO_OFFLINE'] = '1'
                os.environ['ULTRALYTICS_OFFLINE'] = 'True'
                
                model = YOLO(temp_model_path)
            else:
                # 验证模型文件存在
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"模型文件不存在: {model_path}")
                
                os.environ['YOLO_OFFLINE'] = '1'
                os.environ['ULTRALYTICS_OFFLINE'] = 'True'
                
                (model_path)
            
            # 读取标注配置
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation_data = yaml.safe_load(f)
            
            test_data = annotation_data.get('test_model', {})
            boxes = test_data.get('boxes', [])
            areas_config = test_data.get('areas', {})
            
            # 执行推理测试
            all_detections = []
            detection_counts = []
            confidence_scores = []
            
            for idx, image in enumerate(test_images):
                # 模型推理
                results = model(image, conf=0.25, iou=0.45, verbose=False)
                
                if results and len(results) > 0:
                    result = results[0]
                    boxes_detected = result.boxes
                    
                    num_detections = len(boxes_detected) if boxes_detected is not None else 0
                    detection_counts.append(num_detections)
                    
                    # 收集置信度
                    if boxes_detected is not None and len(boxes_detected) > 0:
                        for box in boxes_detected:
                            conf = float(box.conf[0]) if hasattr(box, 'conf') else 0.0
                            confidence_scores.append(conf)
                    
                    all_detections.append({
                        'image_index': idx,
                        'detections': num_detections,
                        'boxes': boxes_detected
                    })
                else:
                    detection_counts.append(0)
                    all_detections.append({
                        'image_index': idx,
                        'detections': 0,
                        'boxes': None
                    })
            
            # 计算统计指标
            total_images = len(test_images)
            total_detections = sum(detection_counts)
            avg_detections = total_detections / total_images if total_images > 0 else 0
            avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
            min_confidence = np.min(confidence_scores) if confidence_scores else 0.0
            max_confidence = np.max(confidence_scores) if confidence_scores else 0.0
            
            # 检测率（至少检测到1个目标的图像比例）
            images_with_detections = sum(1 for count in detection_counts if count > 0)
            detection_rate = images_with_detections / total_images if total_images > 0 else 0.0
            
            test_results = {
                'total_images': total_images,
                'total_detections': total_detections,
                'avg_detections_per_image': avg_detections,
                'detection_rate': detection_rate,
                'avg_confidence': avg_confidence,
                'min_confidence': min_confidence,
                'max_confidence': max_confidence,
                'images_with_detections': images_with_detections,
                'detection_details': all_detections,
                'detection_counts': detection_counts,
                'confidence_scores': confidence_scores
            }
            
            return test_results
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
            return None
    
    
    def _displayTestSummary(self, test_results, duration, image_count):
        """在显示面板展示测试结果摘要"""
        try:
            if not hasattr(self.training_panel, 'display_panel'):
                return
            
            results = test_results
            detection_rate = results['detection_rate'] * 100
            fps = image_count / duration if duration > 0 else 0
            
            # 判断质量
            if detection_rate >= 90 and results['avg_confidence'] >= 0.7:
                quality = "优秀"
                quality_color = "green"
            elif detection_rate >= 70 and results['avg_confidence'] >= 0.5:
                quality = "良好"
                quality_color = "blue"
            elif detection_rate >= 50:
                quality = "一般"
                quality_color = "orange"
            else:
                quality = "较差"
                quality_color = "red"
            
            summary_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 10px;">
                <h3 style="color: #333; margin-top: 0;">测试结果摘要</h3>
                <div style="background: #f0f0f0; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                    <p style="margin: 5px 0;"><strong>模型质量:</strong> <span style="color: {quality_color}; font-size: 16px; font-weight: bold;">{quality}</span></p>
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #667eea; color: white;">
                        <th style="padding: 8px; text-align: left;">指标</th>
                        <th style="padding: 8px; text-align: right;">数值</th>
                    </tr>
                    <tr style="background: #f9f9f9;">
                        <td style="padding: 8px;">测试图像数</td>
                        <td style="padding: 8px; text-align: right;"><strong>{results['total_images']}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">检测率</td>
                        <td style="padding: 8px; text-align: right;"><strong>{detection_rate:.1f}%</strong></td>
                    </tr>
                    <tr style="background: #f9f9f9;">
                        <td style="padding: 8px;">平均置信度</td>
                        <td style="padding: 8px; text-align: right;"><strong>{results['avg_confidence']:.3f}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">总检测数</td>
                        <td style="padding: 8px; text-align: right;"><strong>{results['total_detections']}</strong></td>
                    </tr>
                    <tr style="background: #f9f9f9;">
                        <td style="padding: 8px;">处理速度</td>
                        <td style="padding: 8px; text-align: right;"><strong>{fps:.1f} FPS</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">总耗时</td>
                        <td style="padding: 8px; text-align: right;"><strong>{duration:.2f} 秒</strong></td>
                    </tr>
                </table>
                <div style="margin-top: 15px; padding: 10px; border-left: 4px solid #dee2e6; border-radius: 4px;">
                    <p style="margin: 0; color: #ffffff; font-size: 12px;">
                        <strong>提示:</strong> 测试已完成，结果显示在上方表格中
                    </p>
                </div>
            </div>
            """
            
            self.training_panel.display_panel.setHtml(summary_html)
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
    
    def _refreshModelSetPage(self):
        """刷新模型集管理页面"""
        try:
            # 获取主窗口的模型集页面
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'modelSetPage'):
                self.main_window.modelSetPage.loadModelsFromConfig()
            else:
                pass
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
    
    def _refreshModelTestPage(self):
        """刷新模型测试页面的模型列表"""
        try:
            # 获取主窗口的模型测试页面
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'testModelPage'):
                # 如果有模型集页面，从模型集页面加载模型
                if hasattr(self.main_window, 'modelSetPage'):
                    self.main_window.testModelPage.loadModelsFromModelSetPage(self.main_window.modelSetPage)
                else:
                    # 否则直接刷新模型测试页面
                    if hasattr(self.main_window.testModelPage, 'loadModelsFromConfig'):
                        self.main_window.testModelPage.loadModelsFromConfig()
                pass
            else:
                pass
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _getFileSize(self, file_path):
        """获取文件大小（格式化字符串）"""
        try:
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            else:
                return "未知"
        except:
            return "未知"
    
    def _mergeMultipleDatasets(self, dataset_folders, exp_name):
        """
        合并多个数据集文件夹为统一的训练配置
        
        Args:
            dataset_folders: 数据集文件夹路径列表
            exp_name: 实验名称
            
        Returns:
            str: 合并后的data.yaml文件路径，失败返回None
        """
        # 数据集结构检测函数
        def detect_dataset_structure(folder):
            """
            检测数据集的目录结构
            
            Returns:
                str: 'standard' (train/images), 'variant' (images/train), 或 'unknown'
            """
            # 检测标准YOLO格式: folder/train/images
            if os.path.exists(os.path.join(folder, 'train', 'images')):
                return 'standard'
            # 检测变体格式: folder/images/train
            elif os.path.exists(os.path.join(folder, 'images', 'train')):
                return 'variant'
            # 检测扁平结构: folder/images (单个目录)
            elif os.path.exists(os.path.join(folder, 'images')):
                return 'flat'
            else:
                return 'unknown'

        try:
            import shutil
            import tempfile
            from pathlib import Path
            
            # 创建临时合并目录
            project_root = get_project_root()
            temp_dataset_dir = os.path.join(project_root, 'database', 'temp_datasets', exp_name)
            
            # 如果目录已存在，先删除
            if os.path.exists(temp_dataset_dir):
                shutil.rmtree(temp_dataset_dir)
            
            # 创建合并后的目录结构
            merged_images_train = os.path.join(temp_dataset_dir, 'images', 'train')
            merged_images_val = os.path.join(temp_dataset_dir, 'images', 'val')
            merged_labels_train = os.path.join(temp_dataset_dir, 'labels', 'train')
            merged_labels_val = os.path.join(temp_dataset_dir, 'labels', 'val')
            
            os.makedirs(merged_images_train, exist_ok=True)
            os.makedirs(merged_images_val, exist_ok=True)
            os.makedirs(merged_labels_train, exist_ok=True)
            os.makedirs(merged_labels_val, exist_ok=True)
            
            self._appendLog(f"创建合并目录: {temp_dataset_dir}\n")
            
            # 合并所有数据集
            total_train_images = 0
            total_val_images = 0
            total_train_labels = 0
            total_val_labels = 0
            
            for i, folder in enumerate(dataset_folders):
                self._appendLog(f"正在合并数据集 {i+1}/{len(dataset_folders)}: {os.path.basename(folder)}\n")
                
                # 检查源目录结构
                # 检测当前数据集的结构
                structure = detect_dataset_structure(folder)
                self._appendLog(f"  检测到结构类型: {structure}\n")
                
                # 根据结构类型设置源路径
                if structure == 'standard':
                    # 标准YOLO格式: folder/train/images, folder/val/images
                    src_images_train = os.path.join(folder, 'train', 'images')
                    src_images_val = os.path.join(folder, 'val', 'images')
                    src_labels_train = os.path.join(folder, 'train', 'labels')
                    src_labels_val = os.path.join(folder, 'val', 'labels')
                elif structure == 'variant':
                    # 变体格式: folder/images/train, folder/images/val
                    src_images_train = os.path.join(folder, 'images', 'train')
                    src_images_val = os.path.join(folder, 'images', 'val')
                    src_labels_train = os.path.join(folder, 'labels', 'train')
                    src_labels_val = os.path.join(folder, 'labels', 'val')
                elif structure == 'flat':
                    # 扁平结构: folder/images (需要作为训练集，跳过验证集)
                    src_images_train = os.path.join(folder, 'images')
                    src_images_val = None
                    src_labels_train = os.path.join(folder, 'labels')
                    src_labels_val = None
                    self._appendLog(f"  警告: 扁平结构数据集，仅使用训练集\n")
                else:
                    self._appendLog(f"  错误: 无法识别数据集结构，跳过\n")
                    continue
                
                # 复制训练图片
                if src_images_train and os.path.exists(src_images_train):
                    for filename in os.listdir(src_images_train):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')):
                            src_file = os.path.join(src_images_train, filename)
                            # 添加前缀避免文件名冲突
                            dst_filename = f"ds{i+1}_{filename}"
                            dst_file = os.path.join(merged_images_train, dst_filename)
                            shutil.copy2(src_file, dst_file)
                            total_train_images += 1
                
                # 复制验证图片
                if src_images_val and os.path.exists(src_images_val):
                    for filename in os.listdir(src_images_val):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')):
                            src_file = os.path.join(src_images_val, filename)
                            # 添加前缀避免文件名冲突
                            dst_filename = f"ds{i+1}_{filename}"
                            dst_file = os.path.join(merged_images_val, dst_filename)
                            shutil.copy2(src_file, dst_file)
                            total_val_images += 1
                
                # 复制训练标签
                if src_labels_train and os.path.exists(src_labels_train):
                    for filename in os.listdir(src_labels_train):
                        if filename.lower().endswith('.txt'):
                            src_file = os.path.join(src_labels_train, filename)
                            # 添加前缀避免文件名冲突，保持与图片文件名对应
                            dst_filename = f"ds{i+1}_{filename}"
                            dst_file = os.path.join(merged_labels_train, dst_filename)
                            shutil.copy2(src_file, dst_file)
                            total_train_labels += 1
                
                # 复制验证标签
                if src_labels_val and os.path.exists(src_labels_val):
                    for filename in os.listdir(src_labels_val):
                        if filename.lower().endswith('.txt'):
                            src_file = os.path.join(src_labels_val, filename)
                            # 添加前缀避免文件名冲突，保持与图片文件名对应
                            dst_filename = f"ds{i+1}_{filename}"
                            dst_file = os.path.join(merged_labels_val, dst_filename)
                            shutil.copy2(src_file, dst_file)
                            total_val_labels += 1
            
            self._appendLog(f"合并完成: 训练图片 {total_train_images} 张, 验证图片 {total_val_images} 张\n")
            self._appendLog(f"合并完成: 训练标签 {total_train_labels} 个, 验证标签 {total_val_labels} 个\n")
            
            # 创建data.yaml配置文件
            data_yaml_path = os.path.join(temp_dataset_dir, 'data.yaml')
            data_config = {
                'train': os.path.join(temp_dataset_dir, 'images', 'train'),
                'val': os.path.join(temp_dataset_dir, 'images', 'val'),
                'nc': 1,  # 类别数量，液位检测通常是单类别
                'names': ['liquid_level']  # 类别名称
            }
            
            with open(data_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data_config, f, default_flow_style=False, allow_unicode=True)
            
            self._appendLog(f"创建配置文件: {data_yaml_path}\n")
            
            return data_yaml_path
            
        except Exception as e:
            self._appendLog(f"数据集合并失败: {str(e)}\n")
            import traceback
            self._appendLog(traceback.format_exc())
            return None
    
    def _createDataYamlForSingleFolder(self, dataset_folder, exp_name):
        """
        为单个数据集文件夹创建data.yaml配置文件
        
        Args:
            dataset_folder: 数据集文件夹路径
            exp_name: 实验名称
            
        Returns:
            str: data.yaml文件路径，失败返回None
        """
        try:
            self._appendLog(f"正在处理数据集目录: {dataset_folder}\n")
            
            # 检查是否已经有data.yaml文件
            existing_yaml = os.path.join(dataset_folder, 'data.yaml')
            if os.path.exists(existing_yaml):
                self._appendLog(f"使用现有配置文件: {existing_yaml}\n")
                return existing_yaml
            
            # 创建data.yaml文件路径
            data_yaml_path = os.path.join(dataset_folder, 'data.yaml')
            
            # 支持的图片格式
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
            
            # 检查目录中是否包含图片
            def has_images(folder):
                if not os.path.exists(folder) or not os.path.isdir(folder):
                    return False
                try:
                    for f in os.listdir(folder):
                        if os.path.isfile(os.path.join(folder, f)) and \
                           any(f.lower().endswith(ext) for ext in image_extensions):
                            return True
                except Exception as e:
                    self._appendLog(f"检查图片时出错: {str(e)}\n")
                    return False
                return False
            
            # 检查常见的数据集结构
            train_dir = None
            val_dir = None
            
            # 1. 检查是否是标准YOLO格式: dataset/images/train, dataset/images/val
            if os.path.exists(os.path.join(dataset_folder, 'images', 'train')):
                train_dir = os.path.join(dataset_folder, 'images', 'train')
                val_dir = os.path.join(dataset_folder, 'images', 'val')
                self._appendLog("检测到标准YOLO数据集结构\n")
            # 2. 检查是否直接包含图片
            elif has_images(dataset_folder):
                train_dir = dataset_folder
                val_dir = dataset_folder
                self._appendLog("检测到包含图片的目录，将用于训练和验证\n")
            # 3. 检查是否包含images目录
            elif os.path.exists(os.path.join(dataset_folder, 'images')):
                images_dir = os.path.join(dataset_folder, 'images')
                if has_images(images_dir):
                    train_dir = images_dir
                    val_dir = images_dir
                    self._appendLog("检测到包含图片的images目录\n")
            
            # 4. 如果以上都不匹配，尝试在子目录中查找
            if train_dir is None:
                for root, dirs, files in os.walk(dataset_folder):
                    if has_images(root):
                        train_dir = root
                        val_dir = root
                        self._appendLog(f"在子目录中找到图片: {root}\n")
                        break
            
            # 如果还是没找到图片，返回错误
            if train_dir is None or not has_images(train_dir):
                error_msg = f"错误: 未在 {dataset_folder} 及其子目录中找到有效的图片文件。\n"
                error_msg += f"支持的图片格式: {', '.join(image_extensions)}\n"
                error_msg += "请确保选择的目录中包含图片文件。\n"
                self._appendLog(error_msg)
                QtWidgets.QMessageBox.critical(
                    self.training_panel,
                    "错误",
                    error_msg
                )
                return None
            
            # 创建data.yaml内容
            data_config = {
                'path': os.path.dirname(os.path.abspath(dataset_folder)),  # 数据集根目录
                'train': os.path.relpath(train_dir, os.path.dirname(dataset_folder)).replace('\\', '/'),
                'val': os.path.relpath(val_dir, os.path.dirname(dataset_folder)).replace('\\', '/'),
                'nc': 1,  # 类别数量
                'names': ['liquid_level']  # 类别名称
            }
            
            # 确保验证集目录存在，如果不存在则使用训练集
            if not os.path.exists(os.path.join(os.path.dirname(dataset_folder), data_config['val'])):
                data_config['val'] = data_config['train']
                self._appendLog("警告: 验证集目录不存在，将使用训练集进行验证\n")
            
            # 写入文件
            with open(data_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data_config, f, default_flow_style=False, allow_unicode=True)
            
            self._appendLog(f"成功创建配置文件: {data_yaml_path}\n")
            self._appendLog(f"训练集目录: {data_config['train']}\n")
            self._appendLog(f"验证集目录: {data_config['val']}\n")
            
            return data_yaml_path
            
        except Exception as e:
            error_msg = f"创建配置文件失败: {str(e)}\n"
            self._appendLog(error_msg)
            import traceback
            self._appendLog(traceback.format_exc())
            
            QtWidgets.QMessageBox.critical(
                self.training_panel,
                "错误",
                f"创建数据集配置文件时出错:\n{str(e)}"
            )
            return None