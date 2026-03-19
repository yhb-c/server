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
from pathlib import Path
from qtpy import QtCore
from qtpy import QtWidgets

try:
    from widgets.style_manager import DialogManager
except ImportError:
    DialogManager = None

# 尝试导入 pyqtSignal
try:
    from PyQt5.QtCore import pyqtSignal
except ImportError:
    try:
        from PyQt6.QtCore import pyqtSignal
    except ImportError:
        from qtpy.QtCore import Signal as pyqtSignal

from qtpy.QtCore import QThread

# 导入统一的路径管理函数
try:
    from ...database.config import get_project_root
except ImportError:
    from database.config import get_project_root


class TrainingWorker(QThread):
    """训练工作线程 - 使用subprocess在yeweienv环境中执行"""
    
    # 信号定义
    log_output = pyqtSignal(str)  # 日志输出信号
    training_finished = pyqtSignal(bool)  # 训练完成信号
    training_progress = pyqtSignal(int, dict)  # 训练进度信号 (epoch, loss_dict)
    
    def __init__(self, training_params):
        super().__init__()
        self.training_params = training_params
        self.is_running = True
        self.process = None
        
    def run(self):
        """执行训练 - 使用subprocess在yeweienv环境中"""
        config_file = None
        try:
            import subprocess
            import json
            import os
            
            # 创建训练配置文件
            device_param = self.training_params.get('device', 'cpu')
            
            # 规范化设备参数
            if device_param.upper() == 'CPU':
                device_param = 'cpu'
            elif device_param in ['', 'auto', 'Auto', 'AUTO']:
                device_param = 'cpu'
            elif device_param.isdigit():
                device_param = device_param
            else:
                device_param = 'cpu'
            
            train_config = {
                'base_model': os.path.abspath(self.training_params['base_model']),
                'save_liquid_data_path': os.path.abspath(self.training_params['save_liquid_data_path']),
                'imgsz': self.training_params['imgsz'],
                'epochs': self.training_params['epochs'],
                'batch': self.training_params['batch'],
                'workers': self.training_params['workers'],
                'device': device_param,
                'optimizer': self.training_params['optimizer'],
                'close_mosaic': self.training_params['close_mosaic'],
                'exp_name': self.training_params['exp_name'],
                'resume': self.training_params.get('resume', False),
                'cache': self.training_params.get('cache', False),
                'pretrained': self.training_params.get('pretrained', False),
                'single_cls': self.training_params.get('single_cls', False)
            }
            
            # 创建临时配置文件
            config_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, encoding='utf-8'
            )
            json.dump(train_config, config_file, ensure_ascii=False, indent=2)
            config_file.close()
            
            # 获取yeweienv环境的Python路径
            yeweienv_python = r"C:\Users\admin\.conda\envs\yeweienv\python.exe"
            
            # 获取训练脚本路径（使用统一的路径管理）
            project_root = get_project_root()
            train_script = os.path.join(project_root, 'train_in_env.py')
            
            # 输出开始信息
            device_display = train_config['device'] if train_config['device'] else '自动选择（GPU优先）'
            self.log_output.emit("=" * 60 + "\n")
            self.log_output.emit("使用yeweienv环境启动训练\n")
            self.log_output.emit(f"Python环境: {yeweienv_python}\n")
            self.log_output.emit(f"训练脚本: {train_script}\n")
            self.log_output.emit(f"基础模型: {self.training_params['base_model']}\n")
            self.log_output.emit(f"数据集: {self.training_params['save_liquid_data_path']}\n")
            self.log_output.emit(f"训练轮数: {self.training_params['epochs']}\n")
            self.log_output.emit(f"批次大小: {self.training_params['batch']}\n")
            self.log_output.emit(f"图像尺寸: {self.training_params['imgsz']}\n")
            self.log_output.emit(f"工作线程: {self.training_params['workers']}\n")
            self.log_output.emit(f"设备: {device_display}\n")
            self.log_output.emit(f"实验名称: {self.training_params['exp_name']}\n")
            self.log_output.emit("=" * 60 + "\n\n")
            
            # 检查文件是否存在
            if not os.path.exists(yeweienv_python):
                self.log_output.emit(f"[ERROR] 找不到yeweienv Python: {yeweienv_python}\n")
                self.training_finished.emit(False)
                return
            
            if not os.path.exists(train_script):
                self.log_output.emit(f"[ERROR] 找不到训练脚本: {train_script}\n")
                self.training_finished.emit(False)
                return
            
            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 启动subprocess
            self.process = subprocess.Popen(
                [yeweienv_python, '-u', train_script, '--config', config_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=0,
                universal_newlines=True,
                cwd=current_dir,
                env=env
            )
            
            # 实时读取并发送输出
            import re
            for line in self.process.stdout:
                if not self.is_running:
                    self.process.terminate()
                    self.log_output.emit("\n[WARNING] 训练被用户停止\n")
                    break
                
                # 发送每一行到UI
                self.log_output.emit(line)
                
                # 解析进度信息
                if '[PROGRESS]' in line:
                    try:
                        match = re.search(r'Epoch\s+(\d+)/(\d+)', line)
                        if match:
                            current_epoch = int(match.group(1))
                            total_epochs = int(match.group(2))
                            self.training_progress.emit(current_epoch, {'total': total_epochs})
                    except:
                        pass
            
            # 等待进程结束
            return_code = self.process.wait()
            
            # 检查训练结果
            if return_code == 0 and self.is_running:
                self.log_output.emit("\n[SUCCESS] 训练完成！\n")
                self.training_finished.emit(True)
            elif not self.is_running:
                self.log_output.emit("\n[WARNING] 训练被中断\n")
                self.training_finished.emit(False)
            else:
                self.log_output.emit(f"\n[ERROR] 训练失败，退出码: {return_code}\n")
                self.training_finished.emit(False)
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log_output.emit(f"\n[ERROR] 训练过程出错: {str(e)}\n")
            self.log_output.emit(f"详细错误:\n{error_details}\n")
            self.training_finished.emit(False)
        finally:
            # 清理临时配置文件
            if config_file and os.path.exists(config_file.name):
                try:
                    os.remove(config_file.name)
                except:
                    pass
    
    def stop_training(self):
        """停止训练"""
        self.is_running = False


class TrainingHandler:
    """
    模型训练处理器
    
    处理模型训练相关的所有功能
    """
    
    def __init__(self, training_panel):
        """
        初始化训练处理器
        
        Args:
            training_panel: 训练面板实例
        """
        self.training_panel = training_panel
        self.training_worker = None
        self.training_active = False
        
        # 连接信号
        self._connectSignals()
    
    def _connectSignals(self):
        """连接训练面板的信号"""
        self.training_panel.startTrainingClicked.connect(self._onStartTraining)
        self.training_panel.stopTrainingClicked.connect(self._onStopTraining)
    
    def _onStartTraining(self, training_params):
        """开始训练"""
        try:
            # 验证参数
            if not training_params.get('base_model'):
                QtWidgets.QMessageBox.critical(
                    self.training_panel, 
                    "参数错误", 
                    "未找到可用的基础模型文件"
                )
                return False
            
            if not training_params.get('save_liquid_data_path'):
                QtWidgets.QMessageBox.critical(
                    self.training_panel, 
                    "参数错误", 
                    "未找到可用的数据集配置文件"
                )
                return False
            
            if not training_params.get('exp_name'):
                QtWidgets.QMessageBox.critical(self.training_panel, "参数错误", "请输入实验名称")
                return False
            
            # 验证文件是否存在
            base_model = training_params['base_model']
            save_liquid_data_path = training_params['save_liquid_data_path']
            
            if not os.path.exists(base_model):
                QtWidgets.QMessageBox.critical(
                    self.training_panel, 
                    "文件错误", 
                    f"基础模型文件不存在\n\n{base_model}"
                )
                return False
            
            if not os.path.exists(save_liquid_data_path):
                QtWidgets.QMessageBox.critical(
                    self.training_panel, 
                    "文件错误", 
                    f"数据集配置文件不存在\n\n{save_liquid_data_path}"
                )
                return False
            
            # 确认对话框
            confirm_msg = f"确定要开始训练吗？\n\n"
            confirm_msg += f"基础模型: {os.path.basename(base_model)}\n"
            confirm_msg += f"数据集: {os.path.basename(save_liquid_data_path)}\n"
            confirm_msg += f"图像尺寸: {training_params['imgsz']}\n"
            confirm_msg += f"训练轮数: {training_params['epochs']}\n"
            confirm_msg += f"批次大小: {training_params['batch']}\n"
            confirm_msg += f"实验名称: {training_params['exp_name']}"
            
            reply = QtWidgets.QMessageBox.question(
                self.training_panel, "确认开始训练", confirm_msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                return self._startTrainingWorker(training_params)
            
            return False
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.training_panel, "错误", f"启动训练失败: {str(e)}")
            return False
    
    def _startTrainingWorker(self, training_params):
        """启动训练工作线程"""
        try:
            # 清空日志
            self.training_panel.clear_training_log()
            
            # 创建并启动训练线程
            self.training_worker = TrainingWorker(training_params)
            self.training_worker.log_output.connect(self._appendLog)
            self.training_worker.training_finished.connect(self._onTrainingFinished)
            self.training_worker.training_progress.connect(self._onTrainingProgress)
            
            self.training_active = True
            self.training_panel.set_training_active(True)
            
            self.training_worker.start()
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.training_panel, "错误", f"启动训练线程失败: {str(e)}")
            return False
    
    def _onStopTraining(self):
        """停止训练"""
        if self.training_worker and self.training_active:
            self.training_active = False
            self.training_worker.stop_training()
            self._appendLog("[WARNING] 用户手动停止训练\n")
            self.training_panel.set_training_active(False)
            return True
        else:
            QtWidgets.QMessageBox.information(self.training_panel, "提示", "当前没有正在进行的训练")
            return False
    
    def _onTrainingFinished(self, success):
        """训练完成回调"""
        try:
            self.training_active = False
            self.training_panel.set_training_active(False)
            
            if success:
                QtWidgets.QMessageBox.information(self.training_panel, "训练完成", "训练已完成！")
            else:
                QtWidgets.QMessageBox.warning(self.training_panel, "训练失败", "训练过程中出现错误")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.training_panel, "错误", f"训练完成处理失败: {str(e)}")
    
    def _onTrainingProgress(self, epoch, loss_dict):
        """训练进度回调"""
        # 这里可以更新进度条或显示loss信息
        pass
    
    def _appendLog(self, message):
        """追加日志到UI"""
        print(message, end='')
        self.training_panel.append_training_log(message)

