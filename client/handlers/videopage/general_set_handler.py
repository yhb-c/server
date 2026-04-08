# -*- coding: utf-8 -*-

"""
常规设置面板处理器 (Mixin类)

对应组件：widgets/videopage/general_set.py (GeneralSetPanel, AnnotationWidget)

职责：
- 处理文件浏览和路径处理逻辑
- 管理配置文件的读取和保存
- 处理模型列表扫描和刷新
- 管理标注引擎的创建和管理
- 处理任务ID选项的加载
"""

import os
import json
import yaml
import logging
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt
import cv2

from widgets.style_manager import DialogManager

# 导入统一的路径管理函数
try:
    from ...database.config import get_project_root
except ImportError:
    from database.config import get_project_root

class GeneralSetPanelHandler:
    """
    常规设置面板处理器 (Mixin类)
    
    处理常规设置面板相关的业务逻辑
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('client')
        self.general_set_panel = None
        self.annotation_widget = None
        self.annotation_engine = None
    
    def _showWarningDialog(self, parent, title, message):
        """显示自定义警告对话框（统一样式）"""
        msg_box = QtWidgets.QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)  # 不显示内容区域图标
        
        # 设置左上角图标为系统警告图标
        msg_box.setWindowIcon(
            msg_box.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
        )
        
        # 移除帮助按钮
        msg_box.setWindowFlags(
            msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        # 设置文字水平和垂直居中
        msg_box.setStyleSheet("""
            QMessageBox {
                min-height: 100px;
            }
            QLabel {
                min-height: 50px;
                qproperty-alignment: 'AlignCenter';
            }
        """)
        
        msg_box.exec_()
    
    def connectGeneralSetPanel(self, panel):
        """
        连接常规设置面板信号
        
        Args:
            panel: GeneralSetPanel实例
        """
        self.general_set_panel = panel
        
        # 连接信号
        panel.refreshModelListRequested.connect(self._handleRefreshModelList)
        panel.resetRequested.connect(self._handleResetRequest)
        panel.loadTaskIdOptionsRequested.connect(self._handleLoadTaskIdOptions)
        panel.loadSettingsRequested.connect(self._handleLoadSettings)
        panel.saveSettingsRequested.connect(self._handleSaveSettings)
        panel.createAnnotationEngineRequested.connect(self._handleCreateAnnotationEngine)
        panel.showAnnotationImageRequested.connect(self._handleShowAnnotationImage)
        panel.annotationRequested.connect(self._handleAnnotationRequest)
        panel.detectionStartRequested.connect(self._handleDetectionStartRequest)
        #  新增信号连接 - 业务逻辑处理
        panel.loadChannelModelConfigRequested.connect(self._handleLoadChannelModelConfig)
        panel.autoSaveModelPathRequested.connect(self._handleAutoSaveModelPath)
        
        # 🔥 关键修复：连接嵌入的 model_setting_widget 的信号
        # model_setting_widget 是在 GeneralSetPanel 中创建的，需要单独连接
        if hasattr(panel, 'model_setting_widget') and panel.model_setting_widget:
            panel.model_setting_widget.readModelDescriptionRequested.connect(
                lambda path: self._handleReadModelDescription(panel.model_setting_widget, path)
            )
        
        # 🔥 关键修复：如果panel已经设置了channel_id，立即加载配置
        # 这解决了信号在连接前被发送的时序问题
        if hasattr(panel, 'channel_id') and panel.channel_id:
            self._handleLoadChannelModelConfig(panel.channel_id)
    
    def connectAnnotationWidget(self, widget):
        """
        连接标注界面组件信号
        
        Args:
            widget: AnnotationWidget实例
        """
        self.annotation_widget = widget
        
        # 连接信号
        widget.annotationEngineRequested.connect(self._handleAnnotationEngineRequest)
        widget.frameLoadRequested.connect(self._handleFrameLoadRequest)
        widget.annotationDataRequested.connect(self._handleAnnotationDataRequest)
        
        # 连接ROI拖动完成信号 - 触发自动标注
        widget.roiDragCompleted.connect(self._handleRoiDragCompleted)
    
    def _handleRefreshModelList(self, model_widget=None):
        """处理刷新模型列表请求 - 从服务端获取模型列表"""
        try:
            # 使用远程配置管理器从服务端获取模型信息
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                from utils.config import RemoteConfigManager
            
            remote_config_manager = RemoteConfigManager()
            
            # 从服务端获取模型列表（通过SSH执行命令扫描服务端模型目录）
            model_list = self._scanRemoteModels(remote_config_manager)
            
            # 直接设置模型列表到widget
            if hasattr(self.general_set_panel, 'model_setting_widget'):
                widget = self.general_set_panel.model_setting_widget
                if hasattr(widget, 'setModelList'):
                    widget.setModelList(model_list)
                    self.logger.debug(f"[Handler] 从服务端加载了 {len(model_list)} 个模型")
                    
        except Exception as e:
            self.logger.debug(f"[Handler] 从服务端刷新模型列表失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果服务端获取失败，返回空列表而不是本地扫描
            if hasattr(self.general_set_panel, 'model_setting_widget'):
                widget = self.general_set_panel.model_setting_widget
                if hasattr(widget, 'setModelList'):
                    widget.setModelList([])
    
    def _scanRemoteModels(self, remote_config_manager):
        """
        通过SSH扫描服务端模型目录
        
        Args:
            remote_config_manager: 远程配置管理器实例
            
        Returns:
            list: 模型信息列表
        """
        model_list = []
        
        try:
            ssh_manager = remote_config_manager._get_ssh_manager()
            if not ssh_manager:
                self.logger.debug("[Handler] SSH连接不可用，无法扫描远程模型")
                return model_list
            
            # 服务端模型目录路径
            server_model_path = "/home/lqj/liquid/server/database/model/detection_model"
            
            # 执行远程命令扫描模型文件
            scan_cmd = f"find {server_model_path} -type f \\( -name '*.pt' -o -name '*.pth' -o -name '*.onnx' -o -name '*.dat' \\) 2>/dev/null || echo 'NO_MODELS_FOUND'"
            
            result = ssh_manager.execute_remote_command(scan_cmd)
            
            if result['success'] and result['stdout']:
                stdout = result['stdout'].strip()
                
                if stdout == 'NO_MODELS_FOUND' or not stdout:
                    self.logger.debug(f"[Handler] 服务端模型目录为空或不存在: {server_model_path}")
                    return model_list
                
                # 解析模型文件列表
                model_files = [line.strip() for line in stdout.split('\n') if line.strip()]
                
                for model_file in model_files:
                    try:
                        # 获取文件信息
                        file_info_cmd = f"stat -c '%s %Y' '{model_file}' 2>/dev/null || echo 'ERROR'"
                        info_result = ssh_manager.execute_remote_command(file_info_cmd)
                        
                        if info_result['success'] and info_result['stdout'].strip() != 'ERROR':
                            size_info = info_result['stdout'].strip().split()
                            if len(size_info) >= 1:
                                size_bytes = int(size_info[0])
                                size_mb = size_bytes / (1024 * 1024)
                                size_str = f"{size_mb:.2f} MB"
                            else:
                                size_str = "未知"
                        else:
                            size_str = "未知"
                        
                        # 构建模型信息
                        rel_path = model_file.replace(server_model_path + '/', '')
                        folder = os.path.dirname(rel_path) if '/' in rel_path else ''
                        filename = os.path.basename(model_file)
                        model_name = os.path.splitext(filename)[0]
                        
                        if folder:
                            model_name = f"{folder}-{model_name}"
                        
                        model_info = {
                            'name': model_name,
                            'full_path': model_file,  # 服务端路径
                            'rel_path': rel_path,
                            'folder': folder,
                            'type': os.path.splitext(filename)[1],
                            'size': size_str,
                            'description': '服务端模型',
                            'confidence': 0.5,
                            'iou': 0.45,
                            'input_size': [640, 640],
                            'classes': [],
                            'device': 'cuda',
                            'source': 'remote_server'
                        }
                        
                        model_list.append(model_info)
                        
                    except Exception as e:
                        self.logger.debug(f"[Handler] 解析模型文件信息失败 {model_file}: {e}")
                        continue
                
                self.logger.debug(f"[Handler] 从服务端扫描到 {len(model_list)} 个模型文件")
                
            else:
                self.logger.debug(f"[Handler] 扫描服务端模型目录失败: {result.get('stderr', '未知错误')}")
        
        except Exception as e:
            self.logger.debug(f"[Handler] 扫描远程模型异常: {e}")
            import traceback
            traceback.print_exc()
        
        return model_list
    

    
    def _handleResetRequest(self):
        """处理重置请求"""
        if not self.general_set_panel:
                return
            
        reply = QtWidgets.QMessageBox.question(
            self.general_set_panel, "确认重置",
            "确定要重置所有设置为默认值吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.general_set_panel.resetToDefaults()
            pass
    
    def _handleLoadTaskIdOptions(self):
        """处理加载任务ID选项请求 - 从任务配置文件夹加载所有任务编号"""
        try:
            task_ids = []
            
            # 从任务配置文件夹加载所有任务编号
            project_root = get_project_root()
            mission_dir = os.path.join(project_root, 'database', 'config', 'mission')
            
            if os.path.exists(mission_dir):
                # 扫描所有 .yaml 文件
                yaml_files = [f for f in os.listdir(mission_dir) if f.endswith('.yaml')]
                
                for yaml_file in yaml_files:
                    file_path = os.path.join(mission_dir, yaml_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = yaml.safe_load(f)
                        
                        if config_data:
                            task_id = config_data.get('task_id', '')
                            if task_id and task_id not in task_ids:
                                task_ids.append(task_id)
                    except Exception:
                        continue
            
            # 如果没有找到任务，使用默认选项（保持向后兼容）
            if not task_ids:
                task_ids = ["TASK001", "TASK002", "TASK003", "TASK004", "TASK005"]
            
            # 按任务编号排序
            task_ids.sort()
            
            if self.general_set_panel:
                self.general_set_panel.setTaskIdOptions(task_ids)
        except Exception as e:
            self.logger.debug(f"[Handler] 加载任务ID选项失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handleLoadSettings(self):
        """处理加载设置请求 - 从服务端 channel_config.yaml 加载"""
        try:
            self.logger.debug(f"[DEBUG] _handleLoadSettings 被调用")
            
            if not self.general_set_panel:
                self.logger.debug(f"[DEBUG] general_set_panel 为空，退出")
                return
            
            if not self.general_set_panel.channel_id:
                self.logger.debug(f"[DEBUG] channel_id 为空，退出")
                return
            
            channel_id = self.general_set_panel.channel_id
            self.logger.debug(f"[DEBUG] 正在为通道 {channel_id} 加载设置")

            # 使用远程配置管理器从服务端加载配置
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                try:
                    from utils.config import RemoteConfigManager
                except ImportError:
                    RemoteConfigManager = None

            if not RemoteConfigManager:
                self.logger.debug(f"[Handler] 远程配置管理器不可用")
                if self.general_set_panel:
                    self.general_set_panel.showLoadmission_result(False, "远程配置管理器不可用")
                return

            remote_config = RemoteConfigManager()

            self.logger.debug(f"[DEBUG] 正在从服务端加载通道配置...")
            config = remote_config.load_channel_config()

            if not config:
                self.logger.debug(f"[DEBUG] 服务端通道配置为空")
                if self.general_set_panel:
                    self.general_set_panel.showLoadmission_result(False, "无法从服务端加载通道配置")
                return

            self.logger.debug(f"[DEBUG] 成功从服务端加载通道配置，包含通道: {list(config.keys())}")

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            self.logger.debug(f"[DEBUG] 标准化后的通道键: {channel_key}")

            # 获取该通道的配置
            if channel_key not in config:
                self.logger.debug(f"[DEBUG] 通道 {channel_key} 在服务端配置中不存在")
                if self.general_set_panel:
                    self.general_set_panel.showLoadmission_result(False, f"通道 {channel_id} 的配置在服务端不存在")
                return

            channel_config = config[channel_key]
            self.logger.debug(f"[DEBUG] 找到通道 {channel_key} 的配置: {list(channel_config.keys())}")
            
            general_config = channel_config.get('general', {})
            self.logger.debug(f"[DEBUG] 通道 {channel_id} 的通用配置: {general_config}")
            
            # 🔥 先刷新任务编号选项列表，确保下拉框包含所有任务编号
            self._handleLoadTaskIdOptions()
            
            # 转换为面板设置格式
            settings = {
                'task_id': general_config.get('task_id', ''),
                'task_name': general_config.get('task_name', ''),
                'area_count': general_config.get('area_count', 3),
                'safe_low': general_config.get('safe_low', '0mm'),
                'safe_high': general_config.get('safe_high', '20mm'),
                'frequency': general_config.get('frequency', '25fps'),
                'video_format': general_config.get('video_format', 'AVI'),
                'push_address': general_config.get('push_address', ''),
                'video_path': general_config.get('video_path', ''),
                'save_liquid_data_path': general_config.get('save_liquid_data_path', ''),
                'areas': general_config.get('areas', {}),
                'area_heights': general_config.get('area_heights') if general_config.get('area_heights') else {f'area_{i+1}': '20mm' for i in range(general_config.get('area_count', 3))},
                'model_config': channel_config.get('model', {}),
                'logic_config': channel_config.get('logic', {})
            }
            
            self.logger.debug(f"[DEBUG] 构建的设置: {settings}")
            
            #  同时更新widget缓存的area_count
            area_count = general_config.get('area_count', 0)
            self.general_set_panel.setAreaCount(area_count)
            
            # 设置到面板
            if self.general_set_panel:
                self.general_set_panel.setSettings(settings)
                self.logger.debug(f"[DEBUG] 成功设置通道 {channel_id} 的配置到面板")
                
        except Exception as e:
            self.logger.debug(f"[DEBUG] 加载设置失败: {str(e)}")
            import traceback
            traceback.print_exc()
            if self.general_set_panel:
                self.general_set_panel.showLoadmission_result(False, f"从服务端加载设置失败: {str(e)}")
    
    def _handleLoadChannelModelConfig(self, channel_id):
        """处理加载通道模型配置请求 - 使用远程配置管理器"""
        try:
            # 使用远程配置管理器
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                from utils.config import RemoteConfigManager
            
            remote_config_manager = RemoteConfigManager()
            
            # 从远程加载默认配置
            default_config = remote_config_manager.load_default_config()
            
            if not default_config:
                self.logger.debug(f"[Handler] 无法从服务端加载配置")
                return
            
            # 获取通道特定的模型路径
            channel_model_key = f"{channel_id}_model_path"
            channel_model_path = default_config.get(channel_model_key, '')
            
            if channel_model_path:
                # 获取项目根目录
                try:
                    from ...database.config import get_project_root
                except ImportError:
                    from database.config import get_project_root
                
                project_root = get_project_root()
                
                # 解析相对路径
                if not os.path.isabs(channel_model_path):
                    absolute_path = os.path.normpath(os.path.join(project_root, channel_model_path))
                else:
                    absolute_path = channel_model_path
                
                # 更新面板展示的模型路径
                if self.general_set_panel:
                    self.general_set_panel.setModelPathDisplay(absolute_path)
                
                # 构建模型配置
                model_config = default_config.get('model', {}).copy()
                model_config['model_path'] = absolute_path
                
                # 调用widget的方法应用配置
                if self.general_set_panel:
                    self.general_set_panel.applyModelConfigFromHandler(
                        model_config, absolute_path, channel_model_key
                    )
            else:
                self.logger.debug(f"[Handler] 未找到通道 {channel_id} 的模型配置")
                if self.general_set_panel:
                    self.general_set_panel.setModelPathDisplay("")
        
        except Exception as e:
            self.logger.debug(f"[Handler] 加载模型配置失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handleAutoSaveModelPath(self, model_path):
        """处理自动保存模型路径请求 - 使用远程配置管理器"""
        try:
            if not self.general_set_panel or not self.general_set_panel.channel_id:
                self.logger.debug(f"[Handler] 无法保存：channel_id 为空")
                return
            
            channel_id = self.general_set_panel.channel_id
            
            # 使用远程配置管理器
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                from utils.config import RemoteConfigManager
            
            remote_config_manager = RemoteConfigManager()
            
            # 从远程加载默认配置
            default_config = remote_config_manager.load_default_config()
            
            if not default_config:
                self.logger.debug(f"[Handler] 无法从服务端加载配置")
                return
            
            # 获取项目根目录
            try:
                from ...database.config import get_project_root
            except ImportError:
                from database.config import get_project_root
            
            project_root = get_project_root()
            
            # 将绝对路径转换为相对路径（相对于项目根目录）
            try:
                relative_path = os.path.relpath(model_path, project_root)
                # 规范化路径分隔符（统一使用正斜杠）
                relative_path = relative_path.replace('\\', '/')
            except ValueError:
                # 如果无法转换为相对路径（例如在不同驱动器），使用绝对路径
                relative_path = model_path
            
            # 更新通道特定的模型路径配置
            channel_model_key = f"{channel_id}_model_path"
            default_config[channel_model_key] = relative_path
            
            # 保存配置到服务端（这里需要实现保存默认配置的功能）
            # 注意：RemoteConfigManager 目前只支持保存通道配置，需要扩展支持默认配置
            self.logger.debug(f"[Handler] 已更新模型路径配置:")
            print(f"  通道: {channel_id}")
            print(f"  配置键: {channel_model_key}")
            print(f"  绝对路径: {model_path}")
            print(f"  相对路径: {relative_path}")
            print(f"  注意: 当前版本暂不支持保存到服务端，仅在内存中更新")
            
        except Exception as e:
            self.logger.debug(f"[Handler] 保存模型路径失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handleSaveSettings(self, settings):
        """处理保存设置请求 - 保存到 channel_config.yaml"""
        try:
            if not self.general_set_panel or not self.general_set_panel.channel_id:
                pass
                return
            
            channel_id = self.general_set_panel.channel_id

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            # 配置文件路径（使用统一的项目根目录）
            project_root = get_project_root()
            config_dir = os.path.join(project_root, 'database', 'config')
            config_file = os.path.join(config_dir, 'channel_config.yaml')

            # 确保目录存在
            os.makedirs(config_dir, exist_ok=True)

            # 读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}

            # 如果该通道不存在，创建空配置
            if channel_key not in config:
                config[channel_key] = {}
            
            #  从标注结果获取区域配置
            area_count = settings.get('area_count', 0)
            areas_dict = {}
            area_heights_dict = {}
            
            # 尝试从标注结果文件读取区域配置
            try:
                annotation_file = os.path.join(config_dir, 'annotation_result.yaml')
                if os.path.exists(annotation_file):
                    with open(annotation_file, 'r', encoding='utf-8') as f:
                        annotation_data = yaml.safe_load(f)
                    
                    if annotation_data and channel_key in annotation_data:
                        areas_config = annotation_data[channel_key].get('areas', {})
                        for area_key, area_info in areas_config.items():
                            areas_dict[area_key] = area_info.get('name', '')
                            area_heights_dict[area_key] = area_info.get('height', '20mm')
            except Exception as e:
                print(f"️ 读取标注结果失败: {e}")
            
            # 转换面板设置为配置文件格式
            config[channel_key]['general'] = {
                'task_id': settings.get('task_id', ''),
                'task_name': settings.get('task_name', ''),
                'area_count': area_count,  # 从标注结果获取
                'safe_low': settings.get('safe_low', '2.0mm'),
                'safe_high': settings.get('safe_high', '10.0mm'),
                'frequency': settings.get('frequency', '25fps'),
                'video_format': settings.get('video_format', 'AVI'),
                'push_address': settings.get('push_address', ''),
                'video_path': settings.get('video_path', ''),
                'save_liquid_data_path': settings.get('save_liquid_data_path', ''),
                'areas': areas_dict,  # 从标注结果获取
                'area_heights': area_heights_dict  # 从标注结果获取
            }

            # 保存模型配置（如果有）
            if 'model_config' in settings and settings['model_config']:
                config[channel_key]['model'] = settings['model_config']

            # 保存逻辑配置（如果有）
            if 'logic_config' in settings and settings['logic_config']:
                config[channel_key]['logic'] = settings['logic_config']
            
            # 写入配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            #  更新widget缓存的area_count
            if self.general_set_panel:
                self.general_set_panel.setAreaCount(area_count)
                
            
            pass
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
            if self.general_set_panel:
                self.general_set_panel.showSavemission_result(False, f"保存设置失败: {str(e)}")
    
    def _handleCreateAnnotationEngine(self):
        """处理创建标注引擎请求"""
     
        self.annotation_engine = self._createAnnotationEngine()
            
     
    
    def _handleShowAnnotationImage(self, image_path):
        """处理显示标注图片请求"""
        try:
            if os.path.exists(image_path):
                if self.general_set_panel:
                    self.general_set_panel.showAnnotationImage(image_path)
                else:
                    pass
            else:
                pass
        except Exception as e:
            pass
    
    def _handleDetectionStartRequest(self):
        """处理开始检测请求"""
        try:
            self.logger.debug(f"[检测启动] 开始处理检测启动请求")
            
            if not self.general_set_panel or not self.general_set_panel.channel_id:
                self.logger.debug(f"[检测启动] 通道ID检查失败: panel={self.general_set_panel is not None}, channel_id={getattr(self.general_set_panel, 'channel_id', None)}")
                self._showWarningDialog(
                    self.general_set_panel,
                    "启动失败",
                    "通道ID未设置，无法启动检测"
                )
                return
            
            channel_id = self.general_set_panel.channel_id
            self.logger.debug(f"[检测启动] 通道ID: {channel_id}")
            
            # 检查网络命令管理器状态
            self.logger.debug(f"[检测启动] 检查网络命令管理器状态...")
            print(f"  - hasattr(self, 'ws_client'): {hasattr(self, 'ws_client')}")

            if not hasattr(self, 'ws_client') or self.ws_client is None:
                self.logger.debug(f"[检测启动] 网络命令管理器不存在")
                QtWidgets.QMessageBox.warning(
                    self.general_set_panel,
                    "启动失败",
                    "网络命令管理器未初始化，请检查系统配置"
                )
                return

            print(f"  - self.ws_client: {self.ws_client}")
            print(f"  - 网络命令管理器存在，检查连接状态...")

            # 检查连接状态
            is_connected = False
            if hasattr(self.ws_client, 'get_connection_status'):
                is_connected = self.ws_client.get_connection_status()
                print(f"  - get_connection_status(): {is_connected}")
            elif hasattr(self.ws_client, 'is_connected'):
                is_connected = self.ws_client.is_connected
                print(f"  - is_connected: {is_connected}")

            # 尝试发送命令
            if is_connected:
                self.logger.info(f"[检测启动] ========== 开始完整启动流程 ==========")
                self.logger.info(f"[检测启动] 通道ID: {channel_id}")

                import time

                # 步骤1: 订阅通道（必须先订阅才能接收检测结果）
                self.logger.info(f"[检测启动] ========== 步骤1: 订阅通道 ==========")
                if hasattr(self.ws_client, 'send_subscribe_command'):
                    subscribe_success = self.ws_client.send_subscribe_command(channel_id)
                    self.logger.info(f"[检测启动] 订阅命令发送结果: {subscribe_success}")
                else:
                    self.logger.error(f"[检测启动] ws_client没有send_subscribe_command方法")
                    subscribe_success = False

                time.sleep(0.3)

                # 步骤2: 加载模型
                self.logger.info(f"[检测启动] ========== 步骤2: 加载模型 ==========")
                # 从配置文件获取模型路径
                try:
                    import yaml
                    import os

                    # 使用绝对路径
                    config_path = '/home/lqj/liquid/server/database/config/default_config.yaml'
                    self.logger.info(f"[检测启动] 配置文件路径: {config_path}")
                    self.logger.info(f"[检测启动] 配置文件存在: {os.path.exists(config_path)}")

                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f)
                            model_path_key = f"{channel_id}_model_path"
                            model_path = config.get(model_path_key, '')

                            self.logger.info(f"[检测启动] 模型路径键: {model_path_key}")
                            self.logger.info(f"[检测启动] 模型路径值: {model_path}")

                            if model_path:
                                self.logger.info(f"[检测启动] 开始发送load_model命令...")
                                self.logger.info(f"[检测启动] 参数: channel_id={channel_id}, model_path={model_path}, device=cuda")

                                load_success = self.ws_client.ws_client.send_command('load_model',
                                    channel_id=channel_id,
                                    model_path=model_path,
                                    device='cuda')

                                self.logger.info(f"[检测启动] 模型加载命令发送结果: {load_success}")
                                time.sleep(1.0)  # 等待模型加载完成
                            else:
                                self.logger.error(f"[检测启动] 未找到模型路径配置: {model_path_key}")
                    else:
                        self.logger.error(f"[检测启动] 配置文件不存在: {config_path}")
                except Exception as e:
                    self.logger.error(f"[检测启动] 加载模型配置失败: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

                # 步骤3: 配置通道
                self.logger.info(f"[检测启动] ========== 步骤3: 配置通道 ==========")
                try:
                    # 从annotation_result.yaml加载ROI配置
                    annotation_file = '/home/lqj/liquid/server/database/config/annotation_result.yaml'
                    self.logger.info(f"[检测启动] ROI配置文件路径: {annotation_file}")
                    self.logger.info(f"[检测启动] ROI配置文件存在: {os.path.exists(annotation_file)}")

                    if os.path.exists(annotation_file):
                        with open(annotation_file, 'r', encoding='utf-8') as f:
                            all_annotations = yaml.safe_load(f)
                            annotation_config = all_annotations.get(channel_id, {})

                            self.logger.info(f"[检测启动] ROI配置: {annotation_config}")

                            config = {
                                'detection_config': {
                                    'confidence_threshold': 0.5,
                                    'iou_threshold': 0.45
                                },
                                'annotation_config': annotation_config
                            }

                            self.logger.info(f"[检测启动] 开始发送configure_channel命令...")
                            config_success = self.ws_client.ws_client.send_command('configure_channel',
                                channel_id=channel_id,
                                config=config)
                            self.logger.info(f"[检测启动] 通道配置命令发送结果: {config_success}")
                            time.sleep(0.5)
                    else:
                        self.logger.error(f"[检测启动] ROI配置文件不存在: {annotation_file}")
                except Exception as e:
                    self.logger.error(f"[检测启动] 配置通道失败: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

                # 步骤4: 启动检测
                self.logger.info(f"[检测启动] ========== 步骤4: 启动检测 ==========")
                if hasattr(self.ws_client, 'send_detection_command'):
                    success = self.ws_client.send_detection_command(channel_id, 'start_detection')
                else:
                    # 向后兼容旧的接口
                    success = self.ws_client.send_command('start_detection', channel_id=channel_id)

                self.logger.info(f"[检测启动] start_detection命令发送结果: {success}")
                self.logger.info(f"[检测启动] ========== 启动流程完成 ==========")

                if success:
                    QtWidgets.QMessageBox.information(
                        self.general_set_panel,
                        "检测已启动",
                        f"通道 {channel_id} 的检测功能已成功启动！\n\n服务端正在进行液位检测..."
                    )
                else:
                    self.logger.debug(f"[检测启动] 命令发送失败")
                    QtWidgets.QMessageBox.warning(
                        self.general_set_panel,
                        "启动失败",
                        "发送检测启动命令失败"
                    )
            else:
                self.logger.debug(f"[检测启动] 网络未连接，尝试强制重连...")

                # 尝试强制重连
                if hasattr(self.ws_client, 'force_reconnect'):
                    self.ws_client.force_reconnect()

                    # 等待连接建立
                    import time
                    for i in range(20):  # 最多等待2秒
                        time.sleep(0.1)
                        
                        # 重新检查连接状态
                        if hasattr(self.ws_client, 'get_connection_status'):
                            is_connected = self.ws_client.get_connection_status()
                        elif hasattr(self.ws_client, 'is_connected'):
                            is_connected = self.ws_client.is_connected
                        
                        if is_connected:
                            self.logger.debug(f"[检测启动] 重连成功，先订阅通道，再发送检测命令...")

                            # 步骤1: 订阅通道
                            self.logger.debug(f"[检测启动] 步骤1: 订阅通道 {channel_id}")
                            if hasattr(self.ws_client, 'send_subscribe_command'):
                                subscribe_success = self.ws_client.send_subscribe_command(channel_id)
                                self.logger.debug(f"[检测启动] 订阅命令发送结果: {subscribe_success}")

                            # 等待订阅完成
                            time.sleep(0.5)

                            # 步骤2: 启动检测
                            self.logger.debug(f"[检测启动] 步骤2: 发送启动检测命令")
                            if hasattr(self.ws_client, 'send_detection_command'):
                                success = self.ws_client.send_detection_command(channel_id, 'start_detection')
                            else:
                                success = self.ws_client.send_command('start_detection', channel_id=channel_id)
                            
                            if success:
                                QtWidgets.QMessageBox.information(
                                    self.general_set_panel,
                                    "检测已启动",
                                    f"通道 {channel_id} 的检测功能已成功启动！\n\n服务端正在进行液位检测..."
                                )
                            else:
                                QtWidgets.QMessageBox.warning(
                                    self.general_set_panel,
                                    "启动失败",
                                    "重连后发送检测启动命令失败"
                                )
                            return

                QtWidgets.QMessageBox.warning(
                    self.general_set_panel,
                    "启动失败",
                    f"网络未连接，无法启动检测\n\n问题诊断：\n"
                    f"• 服务端地址: ws://192.168.0.121:8085\n"
                    f"• 连接状态: 未连接\n"
                    f"• 错误类型: 网络连接异常\n\n"
                    f"可能原因：\n"
                    f"• 服务端WebSocket服务启动失败\n"
                    f"• 网络连接问题\n"
                    f"• 防火墙阻止连接\n\n"
                    f"建议解决方案：\n"
                    f"1. 检查服务端日志中的WebSocket启动错误\n"
                    f"2. 确认服务端192.168.0.121:8085端口可访问\n"
                    f"3. 重启服务端WebSocket服务"
                )

        except Exception as e:
            self.logger.debug(f"[检测启动] 异常: {e}")
            import traceback
            traceback.print_exc()
            if self.general_set_panel:
                QtWidgets.QMessageBox.critical(
                    self.general_set_panel,
                    "错误",
                    f"启动检测时发生错误：\n{str(e)}"
                )
    
    def _loadHistoryAnnotation(self, channel_id):
        """
        从annotation_result.yaml加载历史ROI标注数据
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            
        Returns:
            dict: 历史标注数据，包含boxes, bottoms, tops, area_names, area_heights, area_states
                  如果没有历史数据则返回None
        """
        try:
            project_root = get_project_root()
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if not os.path.exists(annotation_file):
                return None
            
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation_data = yaml.safe_load(f)

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            if not annotation_data or channel_key not in annotation_data:
                return None

            channel_data = annotation_data[channel_key]
            
            # 提取boxes数据 - 格式为 [[cx, cy, size], ...]
            boxes = channel_data.get('boxes', [])
            if not boxes:
                return None
            
            # 转换boxes为元组格式
            boxes = [tuple(box) for box in boxes]
            
            # 提取fixed_bottoms和fixed_tops（只有y坐标）
            fixed_bottoms = channel_data.get('fixed_bottoms', [])
            fixed_tops = channel_data.get('fixed_tops', [])
            
            # 提取init_levels（像素坐标 [x, y]），fixed_init_levels是高度值不用于绘制
            init_levels = channel_data.get('init_levels', [])
            
            # 重建bottom_points、top_points和init_level_points - 使用box的cx作为x坐标
            # 🔥 确保所有坐标都是整数，避免OpenCV报错 "Can't parse 'pt1'"
            bottom_points = []
            top_points = []
            init_level_points = []
            for i, (cx, cy, size) in enumerate(boxes):
                cx = int(cx)  # 确保cx是整数
                if i < len(fixed_bottoms):
                    bottom_points.append((cx, int(fixed_bottoms[i])))
                if i < len(fixed_tops):
                    top_points.append((cx, int(fixed_tops[i])))
                # 初始液位线：使用init_levels像素坐标，而非fixed_init_levels高度值
                if i < len(init_levels):
                    init_level_points.append((int(init_levels[i][0]), int(init_levels[i][1])))
                elif i < len(fixed_bottoms) and i < len(fixed_tops):
                    # 默认在容器中间位置
                    mid_y = (fixed_tops[i] + fixed_bottoms[i]) / 2
                    init_level_points.append((cx, int(mid_y)))
            
            # 提取区域配置
            areas_config = channel_data.get('areas', {})
            area_names = []
            area_heights = []
            area_states = []
            
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                area_info = areas_config.get(area_key, {})
                area_names.append(area_info.get('name', f'区域{i+1}'))
                area_heights.append(area_info.get('height', '20mm'))
                area_states.append(area_info.get('state', '默认'))
            
            return {
                'boxes': boxes,
                'bottom_points': bottom_points,
                'top_points': top_points,
                'init_level_points': init_level_points,
                'area_names': area_names,
                'area_heights': area_heights,
                'area_states': area_states
            }
            
        except Exception as e:
            return None
    
    def _applyHistoryAnnotation(self, annotation_widget, history_data):
        """
        将历史标注数据应用到标注引擎和标注界面
        
        Args:
            annotation_widget: 标注界面组件
            history_data: 历史标注数据字典
        """
        if not history_data or not self.annotation_engine:
            return
        
        try:
            # 清空现有数据
            self.annotation_engine.boxes = []
            self.annotation_engine.bottom_points = []
            self.annotation_engine.top_points = []
            if hasattr(self.annotation_engine, 'init_level_points'):
                self.annotation_engine.init_level_points = []
            
            # 加载历史boxes - 确保所有坐标都是整数
            for box in history_data.get('boxes', []):
                self.annotation_engine.boxes.append(tuple(int(v) for v in box))
            
            # 加载历史bottom_points - 确保所有坐标都是整数
            for pt in history_data.get('bottom_points', []):
                self.annotation_engine.bottom_points.append(tuple(int(v) for v in pt))
            
            # 加载历史top_points - 确保所有坐标都是整数
            for pt in history_data.get('top_points', []):
                self.annotation_engine.top_points.append(tuple(int(v) for v in pt))
            
            # 加载历史init_level_points - 确保所有坐标都是整数
            if hasattr(self.annotation_engine, 'init_level_points'):
                for pt in history_data.get('init_level_points', []):
                    self.annotation_engine.init_level_points.append(tuple(int(v) for v in pt))
            
            # 加载区域配置到标注界面
            annotation_widget.area_names = history_data.get('area_names', [])
            annotation_widget.area_heights = history_data.get('area_heights', [])
            annotation_widget.area_states = history_data.get('area_states', [])
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
    
    def _getFrameFromVideoPath(self):
        """
        从配置的视频路径获取帧（用于未连接通道时的标注）
        
        Returns:
            numpy.ndarray: 视频帧，如果获取失败返回None
        """
        try:
            # 尝试从general_set_panel获取视频路径
            video_path = None
            if self.general_set_panel:
                # 尝试从video_path_edit获取
                if hasattr(self.general_set_panel, 'video_path_edit'):
                    video_path = self.general_set_panel.video_path_edit.text().strip()
                
                # 如果没有，尝试从配置文件获取
                if not video_path and self.general_set_panel.channel_id:
                    # 使用远程配置管理器获取配置
                    try:
                        from ....utils.config import RemoteConfigManager
                    except ImportError:
                        from utils.config import RemoteConfigManager
                    
                    remote_config_manager = RemoteConfigManager()
                    config = remote_config_manager.load_default_config()
                    
                    if config:
                        channel_config = config.get(self.general_set_panel.channel_id, {})
                        video_path = channel_config.get('video_path', '')
                    else:
                        self.logger.debug("[标注] 无法从服务端加载配置")
                        video_path = ''
            
            if not video_path or not os.path.exists(video_path):
                return None
            
            # 判断是视频文件还是图片文件
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
            
            file_ext = os.path.splitext(video_path)[1].lower()
            
            if file_ext in video_extensions:
                # 视频文件：读取第10帧
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 9)
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        self.logger.debug(f"[标注] 从视频文件获取帧成功: {video_path}")
                        return frame
            elif file_ext in image_extensions:
                # 图片文件：直接读取
                frame = cv2.imread(video_path)
                if frame is not None:
                    self.logger.debug(f"[标注] 从图片文件获取帧成功: {video_path}")
                    return frame
                else:
                    # 尝试使用PIL读取（处理中文路径）
                    try:
                        from PIL import Image
                        import numpy as np
                        pil_image = Image.open(video_path)
                        if pil_image.mode == 'RGB':
                            frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                        elif pil_image.mode == 'RGBA':
                            frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
                        else:
                            frame = np.array(pil_image)
                        self.logger.debug(f"[标注] 使用PIL从图片文件获取帧成功: {video_path}")
                        return frame
                    except Exception as pil_e:
                        self.logger.debug(f"[标注] PIL读取图片失败: {pil_e}")
            elif os.path.isdir(video_path):
                # 文件夹：读取第一张图片
                for file in os.listdir(video_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_path = os.path.join(video_path, file)
                        frame = cv2.imread(image_path)
                        if frame is not None:
                            self.logger.debug(f"[标注] 从文件夹获取帧成功: {image_path}")
                            return frame
            
            return None
            
        except Exception as e:
            self.logger.debug(f"[标注] 从视频路径获取帧失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _handleAnnotationRequest(self):
        """处理标注请求（使用新的AnnotationManager）"""
        try:
            print(f"\n[标注调试] ========== 使用AnnotationManager处理标注请求 ==========")
            
            if not self.general_set_panel or not self.general_set_panel.channel_id:
                QtWidgets.QMessageBox.warning(
                    self.main_window if hasattr(self, 'main_window') else None,
                    "标注失败",
                    "通道ID未设置，无法进行标注"
                )
                return
            
            channel_id = self.general_set_panel.channel_id
            self.logger.debug(f"[标注调试] 开始为通道 {channel_id} 启动标注")
            
            # 创建标注管理器（如果还没有）
            if not hasattr(self, '_annotation_manager') or not self._annotation_manager:
                from .annotation_manager import AnnotationManager
                self._annotation_manager = AnnotationManager(main_window=self)
                
                # 连接信号
                self._annotation_manager.annotationCompleted.connect(self._on_annotation_manager_completed)
                self._annotation_manager.annotationFailed.connect(self._on_annotation_manager_failed)
                
                self.logger.debug(f"[标注调试] 标注管理器已创建")
            
            # 启动标注流程
            success = self._annotation_manager.start_annotation(channel_id)
            
            if success:
                self.logger.debug(f"[标注调试] 标注流程启动成功")
            else:
                self.logger.debug(f"[标注调试] 标注流程启动失败")
            
            self.logger.debug(f"[标注调试] ========== 标注请求处理完成 ==========\n")
            
        except Exception as e:
            self.logger.debug(f"[标注调试] 标注请求处理异常: {e}")
            import traceback
            traceback.print_exc()
            
            QtWidgets.QMessageBox.critical(
                self.main_window if hasattr(self, 'main_window') else None,
                "标注异常",
                f"标注功能发生异常：\n{str(e)}"
            )
            self.logger.debug(f"[标注调试] ========== 标注请求处理异常结束 ==========\n")
    
    def _on_annotation_manager_completed(self, channel_id, annotation_data):
        """
        处理标注管理器完成事件
        
        Args:
            channel_id: 通道ID
            annotation_data: 标注数据
        """
        try:
            self.logger.debug(f"[标注处理] 通道 {channel_id} 标注完成")
            
            # 更新面板状态
            if self.general_set_panel:
                area_count = len(annotation_data.get('boxes', []))
                self.general_set_panel.updateAnnotationStatus(True, area_count)
                
                # 显示标注结果图像（如果有原始帧）
                if hasattr(self, '_annotation_source_frame') and self._annotation_source_frame is not None:
                    try:
                        pixmap = self._createAnnotationmission_resultPixmap(
                            self._annotation_source_frame,
                            annotation_data['boxes'],
                            annotation_data['bottoms'],
                            annotation_data['tops'],
                            annotation_data.get('init_levels')
                        )
                        
                        if pixmap:
                            self.general_set_panel.showAnnotationmission_result(pixmap, area_count)
                    except Exception as e:
                        self.logger.debug(f"[标注处理] 显示标注结果图像失败: {e}")
            
            self.logger.debug(f"[标注处理] 标注完成处理结束")
            
        except Exception as e:
            self.logger.debug(f"[标注处理] 处理标注完成异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_annotation_manager_failed(self, channel_id, error_message):
        """
        处理标注管理器失败事件
        
        Args:
            channel_id: 通道ID
            error_message: 错误信息
        """
        try:
            self.logger.debug(f"[标注处理] 通道 {channel_id} 标注失败: {error_message}")
            
            QtWidgets.QMessageBox.warning(
                self.main_window if hasattr(self, 'main_window') else None,
                "标注失败",
                f"通道 {channel_id} 标注失败：\n{error_message}"
            )
            
        except Exception as e:
            self.logger.debug(f"[标注处理] 处理标注失败异常: {e}")
            
            # 3. 创建标注界面组件
            annotation_widget = self.showAnnotationWidget(self.general_set_panel)
            
            #  设置通道名称（用于生成区域默认名称）
            if self.general_set_panel and self.general_set_panel.channel_name:
                annotation_widget.setChannelName(self.general_set_panel.channel_name)
            
            # 3.5. 初始化物理变焦控制器
            self._initPhysicalZoomForAnnotation(annotation_widget)
            
            # 3.6. 加载历史ROI标注数据
            if self.general_set_panel and self.general_set_panel.channel_id:
                history_data = self._loadHistoryAnnotation(self.general_set_panel.channel_id)
                if history_data:
                    self._applyHistoryAnnotation(annotation_widget, history_data)
            
            # 4. 连接标注完成信号
            def on_annotation_completed(boxes, bottoms, tops, init_levels=None):
                # 保存标注结果到配置文件（包含区域名称、高度、初始液位线和状态）
                if self.general_set_panel and self.general_set_panel.channel_id:
                    channel_id = self.general_set_panel.channel_id
                    self._saveAnnotationmission_result(
                        channel_id,
                        boxes,
                        bottoms,
                        tops,
                        annotation_widget.area_names,  # 区域名称
                        annotation_widget.area_heights,  # 区域高度
                        init_levels=init_levels,  # 初始液位线
                        area_states=annotation_widget.area_states  # 区域状态（默认/空/满）
                    )
                
                # 生成并显示标注结果
                if self._annotation_source_frame is not None and self.general_set_panel:
                    try:
                        # 调用handler方法处理标注结果
                        pixmap = self._createAnnotationmission_resultPixmap(
                            self._annotation_source_frame, 
                            boxes, 
                            bottoms, 
                            tops,
                            init_levels
                        )
                        
                        if pixmap:
                            # 显示处理好的pixmap
                            self.general_set_panel.showAnnotationmission_result(pixmap, len(boxes))
                            pass
                        else:
                            # pixmap创建失败，只更新状态
                            self.general_set_panel.updateAnnotationStatus(True, len(boxes))
                        
                    except Exception as e:
                        pass
                        import traceback
                        traceback.print_exc()
                        # 即使显示失败，也更新状态
                        if self.general_set_panel:
                            self.general_set_panel.updateAnnotationStatus(True, len(boxes))
                else:
                    # 没有图像，只更新状态
                    if self.general_set_panel:
                        self.general_set_panel.updateAnnotationStatus(True, len(boxes))
            
            def on_annotation_cancelled():
                pass
            
            annotation_widget.annotationCompleted.connect(on_annotation_completed)
            annotation_widget.annotationCancelled.connect(on_annotation_cancelled)
            
            # 5. 加载图像并显示标注界面
            if annotation_widget.loadFrame(channel_frame):
                # 🔥 关键修复：延迟显示窗口，确保全屏应用后再显示
                # 这样可以确保标注帧在全屏模式下立即显示
                QtCore.QTimer.singleShot(150, annotation_widget.show)
                pass
            else:
                pass
            
            self.logger.debug(f"[标注调试] ========== 标注请求处理完成 ==========\n")
            
        except Exception as e:
            self.logger.debug(f"[标注调试] 标注请求处理异常: {e}")
            import traceback
            traceback.print_exc()
            self.logger.debug(f"[标注调试] ========== 标注请求处理异常结束 ==========\n")
    
    def _saveAnnotationmission_result(self, channel_id, boxes, bottoms, tops, area_names=None, area_heights=None, init_levels=None, area_states=None):
        """
        保存标注结果到配置文件
        
        注意：只保存标注数据到 annotation_result.yaml，不同步到其他配置文件
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            boxes: 检测框列表 [(cx, cy, size), ...]
            bottoms: 底部线条列表 [(x, y), ...]
            tops: 顶部线条列表 [(x, y), ...]
            area_names: 区域名称列表（可选）
            area_heights: 区域高度列表（可选）
            init_levels: 初始液位线点列表（可选）[(x, y), ...]
            area_states: 区域状态列表（可选）["默认"/"空"/"满", ...]
        """
        if init_levels is None:
            init_levels = []
        if area_states is None:
            area_states = []
        try:
            import os
            import yaml
            from datetime import datetime
            
            # 配置文件路径（使用统一的项目根目录）
            project_root = get_project_root()
            config_dir = os.path.join(project_root, 'database', 'config')
            config_file = os.path.join(config_dir, 'annotation_result.yaml')
            
            # 确保目录存在
            os.makedirs(config_dir, exist_ok=True)
            
            # 读取现有配置（如果存在）
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # 提取固定的 bottom 和 top（假设每个区域对应一个 bottom 和一个 top）
            fixed_bottoms = [pt[1] for pt in bottoms]  # 只保存 y 坐标
            fixed_tops = [pt[1] for pt in tops]  # 只保存 y 坐标
            
            #  构建区域配置字典（包含名称、高度和状态）
            areas_config = {}
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                # 获取状态并转换为detect_initstatus值：默认=0, 满=1, 空=2
                state_str = area_states[i] if area_states and i < len(area_states) else "默认"
                if state_str == "满":
                    init_status = 1
                elif state_str == "空":
                    init_status = 2
                else:
                    init_status = 0
                
                areas_config[area_key] = {
                    'name': area_names[i] if area_names and i < len(area_names) else f'区域{i+1}',
                    'height': area_heights[i] if area_heights and i < len(area_heights) else '20mm',
                    'state': state_str,  # 保存原始状态字符串（默认/空/满）
                    'init_status': init_status  # 保存detect_initstatus值（0/1/2）
                }
            
            # 处理初始液位线数据 - 转换为实际高度（毫米）
            fixed_init_levels = []
            if init_levels:
                import re
                for i, pt in enumerate(init_levels):
                    init_level_y = pt[1] if isinstance(pt, (tuple, list)) else pt
                    # 获取对应区域的容器底部、顶部和实际高度
                    if i < len(fixed_bottoms) and i < len(fixed_tops):
                        bottom_y = fixed_bottoms[i]
                        top_y = fixed_tops[i]
                        container_pixel_height = bottom_y - top_y
                        
                        # 获取实际容器高度（毫米）
                        area_key = f'area_{i+1}'
                        height_str = areas_config.get(area_key, {}).get('height', '20mm')
                        height_match = re.search(r'([\d.]+)', str(height_str))
                        actual_height_mm = float(height_match.group(1)) if height_match else 20.0
                        
                        # 计算初始液位高度（从底部到初始液位线的像素距离）
                        if container_pixel_height > 0:
                            init_level_pixel_height = bottom_y - init_level_y
                            # 映射到实际高度（毫米）
                            init_level_mm = (init_level_pixel_height / container_pixel_height) * actual_height_mm
                            fixed_init_levels.append(round(init_level_mm, 2))
                        else:
                            fixed_init_levels.append(actual_height_mm / 2)  # 默认中间位置
                    else:
                        fixed_init_levels.append(10.0)  # 默认10mm

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            # 更新该通道的标注数据
            config[channel_key] = {
                'boxes': [list(box) for box in boxes],  # 转换为列表格式
                'fixed_bottoms': fixed_bottoms,
                'fixed_tops': fixed_tops,
                'init_levels': [list(pt) for pt in init_levels] if init_levels else [],  # 保存完整坐标 [(x, y), ...]
                'fixed_init_levels': fixed_init_levels,  # 保存实际高度（毫米）
                'annotation_count': len(boxes),
                'areas': areas_config,  #  保存区域配置
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存到文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _syncAreaInfoToChannelConfig(self, channel_id, area_count, areas_config):
        """
        同步区域信息到 channel_config.yaml
        
        Args:
            channel_id: 通道ID
            area_count: 区域数量
            areas_config: 区域配置字典 {'area_1': {'name': '...', 'height': '...'}, ...}
        """
        try:
            import os
            import yaml
            
            self.logger.debug(f"[DEBUG] ========== 同步到 channel_config.yaml ==========")
            self.logger.debug(f"[DEBUG] 通道ID: {channel_id}")
            self.logger.debug(f"[DEBUG] 区域数量: {area_count}")
            self.logger.debug(f"[DEBUG] 区域配置: {areas_config}")
            
            # 配置文件路径（使用统一的项目根目录）
            project_root = get_project_root()
            config_dir = os.path.join(project_root, 'database', 'config')
            config_file = os.path.join(config_dir, 'channel_config.yaml')
            
            self.logger.debug(f"[DEBUG] 配置文件路径: {config_file}")
            self.logger.debug(f"[DEBUG] 文件是否存在: {os.path.exists(config_file)}")
            
            # 确保目录存在
            os.makedirs(config_dir, exist_ok=True)
            
            # 读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                self.logger.debug(f"[DEBUG] 已读取现有配置，包含通道: {list(config.keys())}")
            else:
                config = {}
                self.logger.debug(f"[DEBUG] 配置文件不存在，创建新配置")

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            # 如果该通道不存在，创建新通道配置
            if channel_key not in config:
                self.logger.debug(f"[DEBUG] 通道 {channel_key} 不存在，创建新配置")
                config[channel_key] = {}
            else:
                self.logger.debug(f"[DEBUG] 通道 {channel_key} 已存在")

            # 确保 general 配置存在
            if 'general' not in config[channel_key]:
                self.logger.debug(f"[DEBUG] 通道 {channel_key} 的 general 配置不存在，创建新配置")
                config[channel_key]['general'] = {}
            else:
                self.logger.debug(f"[DEBUG] 通道 {channel_key} 的 general 配置已存在")

            #  更新区域数量
            config[channel_key]['general']['area_count'] = area_count
            self.logger.debug(f"[DEBUG] 已更新区域数量: {area_count}")

            #  更新区域名称和高度
            areas_dict = {}
            area_heights_dict = {}

            for area_key, area_info in areas_config.items():
                areas_dict[area_key] = area_info.get('name', '')
                area_heights_dict[area_key] = area_info.get('height', '20mm')

            config[channel_key]['general']['areas'] = areas_dict
            config[channel_key]['general']['area_heights'] = area_heights_dict
            
            self.logger.debug(f"[DEBUG] 已更新区域名称: {areas_dict}")
            self.logger.debug(f"[DEBUG] 已更新区域高度: {area_heights_dict}")
            
            # 写回配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            self.logger.debug(f"[DEBUG] ✓ 已同步到 channel_config.yaml: {channel_id} (区域数: {area_count})\")\n")
            
        except Exception as e:
            self.logger.debug(f"[DEBUG] ✗ 同步到 channel_config.yaml 失败: {e}\")\n")
            import traceback
            traceback.print_exc()
    
    def _createAnnotationmission_resultPixmap(self, source_frame, boxes, bottoms, tops, init_levels=None):
        """
        创建标注结果的QPixmap（业务逻辑）
        
        注意：此函数仅创建用于界面显示的图像，不保存图像到文件系统
        
        Args:
            source_frame: 原始图像帧
            boxes: 检测框列表 [(cx, cy, size), ...]
            bottoms: 底部线条列表 [(x, y), ...]
            tops: 顶部线条列表 [(x, y), ...]
            init_levels: 初始液位线列表 [(x, y), ...] （可选）
        
        Returns:
            QtGui.QPixmap: 600x450尺寸的标注结果图像，失败返回None
        """
        if init_levels is None:
            init_levels = []
        try:
            import numpy as np
            from qtpy import QtGui
            
            # 1. 在原始帧上绘制标注结果
            annotated_frame = source_frame.copy()
            
            # 获取用户设置的区域名称
            area_names = []
            if self.general_set_panel:
                settings = self.general_set_panel.getSettings()
                areas = settings.get('areas', {})
                for i in range(len(boxes)):
                    area_key = f'area_{i+1}'
                    area_name = areas.get(area_key, f'区域{i+1}')
                    # 如果区域名称为空，使用默认名称
                    if not area_name or area_name.strip() == '':
                        area_name = f'区域{i+1}'
                    area_names.append(area_name)
            else:
                # 如果没有面板，使用默认名称
                area_names = [f'区域{i+1}' for i in range(len(boxes))]
            
            # 第一步：使用OpenCV绘制所有的框和点（与全屏标注一致）
            # 绘制检测框（黄色，与全屏标注一致）
            for i, (cx, cy, size) in enumerate(boxes):
                half = size // 2
                top = cy - half
                bottom = cy + half
                left = cx - half
                right = cx + half
                
                # 绘制矩形框（黄色）
                cv2.rectangle(annotated_frame, (left, top), (right, bottom), (0, 255, 255), 3)
            
            # 绘制底部线条的水平线条（绿色，1px宽，长度与检测框宽度一致）
            for i, pt in enumerate(bottoms):
                # 获取对应框的宽度作为线条长度
                if i < len(boxes):
                    _, _, size = boxes[i]
                    line_length = size  # 线条长度等于框的宽度
                else:
                    line_length = 30  # 默认长度（不应该发生）
                half_length = line_length // 2
                x, y = pt
                start_point = (x - half_length, y)
                end_point = (x + half_length, y)
                cv2.line(annotated_frame, start_point, end_point, (0, 255, 0), 1)
            
            # 绘制顶部线条的水平线条（红色，1px宽，长度与检测框宽度一致）
            for i, pt in enumerate(tops):
                # 获取对应框的宽度作为线条长度
                if i < len(boxes):
                    _, _, size = boxes[i]
                    line_length = size  # 线条长度等于框的宽度
                else:
                    line_length = 30  # 默认长度（不应该发生）
                half_length = line_length // 2
                x, y = pt
                start_point = (x - half_length, y)
                end_point = (x + half_length, y)
                cv2.line(annotated_frame, start_point, end_point, (0, 0, 255), 1)
            
            # 绘制初始液位线的水平线条（橙色，2px宽，长度与检测框宽度一致）
            for i, pt in enumerate(init_levels):
                # 获取对应框的宽度作为线条长度
                if i < len(boxes):
                    _, _, size = boxes[i]
                    line_length = size  # 线条长度等于框的宽度
                else:
                    line_length = 30  # 默认长度
                half_length = line_length // 2
                x, y = pt
                start_point = (x - half_length, y)
                end_point = (x + half_length, y)
                cv2.line(annotated_frame, start_point, end_point, (0, 165, 255), 2)  # BGR橙色
            
            # 第二步：使用PIL绘制中文文本（包括底部/顶部标签、区域名称和高度）
            try:
                from PIL import Image, ImageDraw, ImageFont
                import numpy as np
                
                # 转换为PIL图像
                img_pil = Image.fromarray(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(img_pil)
                
                # 尝试加载中文字体（与全屏标注一致）
                try:
                    font_name = ImageFont.truetype("simhei.ttf", 24)  # 名称字体（黑体，大号）
                    font_height = ImageFont.truetype("msyh.ttc", 20)  # 高度字体（微软雅黑，中号）
                    font_label = ImageFont.truetype("msyh.ttc", 18)  # 底部/顶部标签字体（微软雅黑，中号）
                except:
                    try:
                        font_name = ImageFont.truetype("msyh.ttc", 24)
                        font_height = ImageFont.truetype("msyh.ttc", 20)
                        font_label = ImageFont.truetype("msyh.ttc", 18)
                    except:
                        font_name = ImageFont.load_default()
                        font_height = ImageFont.load_default()
                        font_label = ImageFont.load_default()
                
                # 绘制底部线条标签（绿色）
                for i, pt in enumerate(bottoms):
                    label_text = f"容器底部{i+1}"
                    label_pos = (pt[0] + 15, pt[1] - 5)
                    draw.text(label_pos, label_text, fill=(0, 255, 0), font=font_label)
                
                # 绘制顶部线条标签（红色）
                for i, pt in enumerate(tops):
                    label_text = f"容器顶部{i+1}"
                    label_pos = (pt[0] + 15, pt[1] - 5)
                    draw.text(label_pos, label_text, fill=(255, 0, 0), font=font_label)
                
                # 绘制初始液位线标签（橙色）
                for i, pt in enumerate(init_levels):
                    label_text = f"初始液位{i+1}"
                    label_pos = (pt[0] + 15, pt[1] - 5)
                    draw.text(label_pos, label_text, fill=(255, 165, 0), font=font_label)
                
                # 绘制区域名称和高度文本（与全屏标注完全一致）
                for i, (cx, cy, size) in enumerate(boxes):
                    half = size // 2
                    top = cy - half
                    left = cx - half
                    right = cx + half
                    
                    # 在框内顶部显示：区域名称 + 高度（同一行）
                    area_name = area_names[i] if i < len(area_names) else f'区域{i+1}'
                    # 获取区域高度（如果有的话）
                    area_height = "20mm"  # 默认高度
                    if hasattr(self, 'general_set_panel') and self.general_set_panel:
                        settings = self.general_set_panel.getSettings()
                        area_heights = settings.get('area_heights', {})
                        area_key = f'area_{i+1}'
                        area_height = area_heights.get(area_key, "20mm")
                    
                    # 名称位置：框内顶部，距离顶边5像素
                    text_y = top + 5
                    name_pos = (left + 5, text_y)
                    draw.text(name_pos, area_name, fill=(0, 255, 0), font=font_name)
                    
                    # 计算名称宽度，高度紧跟在后面
                    try:
                        # 获取名称文本的宽度
                        name_bbox = draw.textbbox(name_pos, area_name, font=font_name)
                        name_width = name_bbox[2] - name_bbox[0]
                    except:
                        # 如果获取失败，估算宽度
                        name_width = len(area_name) * 20
                    
                    # 高度位置：名称后面（留15像素间隔）
                    height_pos = (left + 5 + name_width + 15, text_y)
                    draw.text(height_pos, area_height, fill=(255, 255, 0), font=font_height)
                
                # 转换回OpenCV图像
                annotated_frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                
            except (ImportError, Exception) as e:
                # 如果PIL绘制失败，使用cv2.putText（中文可能显示为乱码）
                # 绘制底部线条标签（绿色）- 中文可能显示为乱码
                for i, pt in enumerate(bottoms):
                    label_text = f"容器底部{i+1}"
                    cv2.putText(annotated_frame, label_text, (pt[0] + 15, pt[1] + 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # 绘制顶部线条标签（红色）- 中文可能显示为乱码
                for i, pt in enumerate(tops):
                    label_text = f"容器顶部{i+1}"
                    cv2.putText(annotated_frame, label_text, (pt[0] + 15, pt[1] + 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                for i, (cx, cy, size) in enumerate(boxes):
                    half = size // 2
                    top = cy - half
                    left = cx - half
                    right = cx + half
                    
                    # 在框内顶部显示：区域名称 + 高度（同一行）
                    area_name = area_names[i] if i < len(area_names) else f'区域{i+1}'
                    area_height = "20mm"  # 默认高度
                    
                    # 文本Y坐标：框内顶部，距离顶边25像素（留出文本高度）
                    text_y = top + 25
                    
                    # 名称位置：框内顶部左侧
                    name_pos = (left + 5, text_y)
                    cv2.putText(annotated_frame, area_name, name_pos, 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # 估算名称宽度，高度紧跟在后面
                    name_width = len(area_name) * 14
                    height_pos = (left + 5 + name_width + 15, text_y)
                    cv2.putText(annotated_frame, area_height, height_pos, 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # 2. 缩放图像到600x450（保持宽高比）
            target_width = 800
            target_height = 600
            
            h, w = annotated_frame.shape[:2]
            
            # 计算缩放比例
            scale_w = target_width / w
            scale_h = target_height / h
            scale = min(scale_w, scale_h)
            
            # 计算缩放后的尺寸
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # 缩放图像
            resized_frame = cv2.resize(annotated_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # 3. 创建600x450的黑色画布，将图像居中
            canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            y_offset = (target_height - new_h) // 2
            x_offset = (target_width - new_w) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_frame
            
            # 4. 转换为RGB格式
            img_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            
            # 5. 创建QImage和QPixmap
            qt_image = QtGui.QImage(img_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            
            pass
            return pixmap
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
            return None
    
    def _loadModelForAnnotation(self):
        """
        为标注功能在服务器上加载检测模型到显卡
        
        通过WebSocket或API调用服务端，在服务器显卡上加载模型用于标注功能。
        
        Returns:
            bool: 服务端模型加载是否成功
        """
        try:
            self.logger.debug(f"[DEBUG] _loadModelForAnnotation 开始在服务端加载模型")
            
            # 获取当前通道ID
            channel_id = None
            if self.general_set_panel and self.general_set_panel.channel_id:
                channel_id = self.general_set_panel.channel_id
                self.logger.debug(f"[DEBUG] 从general_set_panel获取通道ID: {channel_id}")
            else:
                self.logger.debug(f"[DEBUG] 无法获取通道ID，使用默认通道")
                channel_id = "channel1"  # 默认通道
            
            self.logger.debug(f"[DEBUG] 为通道 {channel_id} 在服务端加载模型")
            
            # 从服务端配置获取模型路径
            try:
                from ...utils.config import RemoteConfigManager
            except ImportError:
                try:
                    from utils.config import RemoteConfigManager
                except ImportError:
                    RemoteConfigManager = None
                    
            if not RemoteConfigManager:
                self.logger.debug(f"[DEBUG] 远程配置管理器不可用")
                return False
                
            remote_config = RemoteConfigManager()
            
            self.logger.debug(f"[DEBUG] 正在从服务端加载默认配置...")
            default_config = remote_config.load_default_config()
            
            if not default_config:
                self.logger.debug(f"[DEBUG] 无法从服务端加载配置")
                return False
            
            self.logger.debug(f"[DEBUG] 成功从服务端加载配置，包含键: {list(default_config.keys())}")
            
            # 获取通道特定的模型路径
            model_path_key = f"{channel_id}_model_path"
            model_path = default_config.get(model_path_key)
            
            self.logger.debug(f"[DEBUG] 查找模型路径键: {model_path_key}")
            self.logger.debug(f"[DEBUG] 找到模型路径: {model_path}")
            
            if not model_path:
                self.logger.debug(f"[DEBUG] 服务端配置中没有找到 {model_path_key}")
                # 尝试从全局model配置获取
                model_config = default_config.get('model', {})
                model_path = model_config.get('model_path')
                self.logger.debug(f"[DEBUG] 尝试从全局model配置获取: {model_path}")
                
                if not model_path:
                    self.logger.debug(f"[DEBUG] 全局model配置中也没有找到model_path")
                    return False
            
            self.logger.debug(f"[DEBUG] 最终使用的服务端模型路径: {model_path}")
            
            # 检查是否有WebSocket客户端
            websocket_available = hasattr(self, 'ws_client') and self.ws_client
            self.logger.debug(f"[DEBUG] WebSocket可用性: {websocket_available}")
            
            # 通过WebSocket向服务端发送模型加载请求
            if websocket_available:
                load_model_request = {
                    "action": "load_model",
                    "channel_id": channel_id,
                    "model_path": model_path,
                    "device": "cuda",  # 指定使用GPU
                    "purpose": "annotation"  # 标注用途
                }
                
                self.logger.debug(f"[DEBUG] 发送模型加载请求到服务端: {load_model_request}")
                
                try:
                    # 发送请求到服务端
                    response = self.ws_client.send_command('load_model', **load_model_request)
                    self.logger.debug(f"[DEBUG] 服务端响应: {response}")
                    
                    if response:
                        self.logger.debug(f"[DEBUG] 服务端模型加载成功")
                        return True
                    else:
                        self.logger.debug(f"[DEBUG] 服务端模型加载失败")
                        # 继续尝试SSH方式
                except Exception as e:
                    self.logger.debug(f"[DEBUG] WebSocket请求异常: {e}")
                    # 继续尝试SSH方式
            
            # 如果WebSocket不可用或失败，尝试通过SSH直接在服务端执行模型加载
            self.logger.debug(f"[DEBUG] 尝试通过SSH在服务端加载模型")
            
            ssh_manager = remote_config._get_ssh_manager()
            if not ssh_manager:
                self.logger.debug(f"[DEBUG] SSH连接不可用")
                return False
            
            self.logger.debug(f"[DEBUG] SSH连接可用，准备执行服务端模型加载命令")
            
            # 构建服务端模型加载命令
            load_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
try:
    from detection import LiquidDetectionEngine
    engine = LiquidDetectionEngine(
        model_path='{model_path}',
        device='cuda',
        batch_size=1
    )
    print('SUCCESS: 服务端模型加载到GPU成功')
except Exception as e:
    print(f'ERROR: 服务端模型加载失败: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
            
            self.logger.debug(f"[DEBUG] 执行服务端模型加载命令")
            result = ssh_manager.execute_remote_command(load_cmd)
            
            self.logger.debug(f"[DEBUG] SSH命令执行结果: success={result['success']}")
            self.logger.debug(f"[DEBUG] SSH命令输出: {result.get('stdout', '')}")
            self.logger.debug(f"[DEBUG] SSH命令错误: {result.get('stderr', '')}")
            
            if result['success'] and 'SUCCESS' in result['stdout']:
                self.logger.debug(f"[DEBUG] 通过SSH成功在服务端加载模型到GPU")
                return True
            else:
                error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                self.logger.debug(f"[DEBUG] 通过SSH在服务端加载模型失败: {error_msg}")
                return False
            
        except Exception as e:
            self.logger.debug(f"[DEBUG] 服务端模型加载异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
                    self.init_level_points = []  # 存储初始液位线点
                
                def add_box(self, cx, cy, size):
                    """
                    添加ROI，并自动计算顶部线条、底部线条、初始液位线
                    
                    Args:
                        cx: 框中心x坐标
                        cy: 框中心y坐标
                        size: 框的边长
                    """
                    self.boxes.append((cx, cy, size))
                    
                    # 自动计算并添加底部线条和顶部线条
                    # 底部线条：box底边y坐标 - box高度的10%，x为中心
                    half_size = size / 2
                    bottom_y = cy + half_size - (size * 0.1)  # 底边y - 10%高度
                    bottom_x = cx  # x位置为box轴对称中心
                    self.bottom_points.append((int(bottom_x), int(bottom_y)))
                    
                    # 顶部线条：box顶边y坐标 + box高度的10%，x为中心
                    top_y = cy - half_size + (size * 0.1)  # 顶边y + 10%高度
                    top_x = cx  # x位置为box轴对称中心
                    self.top_points.append((int(top_x), int(top_y)))
                    
                    # 初始液位线：默认在容器中间位置
                    init_level_y = (top_y + bottom_y) / 2
                    self.init_level_points.append((int(cx), int(init_level_y)))
                    
                def add_bottom(self, x, y):
                    """添加底部标记点（保留用于兼容性，但不再使用）"""
                    # 此方法保留但不再使用，因为底部线条会在add_box时自动添加
                    pass
                
                def add_top(self, x, y):
                    """添加顶部标记点（保留用于兼容性，但不再使用）"""
                    # 此方法保留但不再使用，因为顶部线条会在add_box时自动添加
                    pass
                
                def get_mission_results(self):
                    """获取标注结果"""
                    return {
                        'boxes': self.boxes,
                        'bottom_points': self.bottom_points,
                        'top_points': self.top_points,
                        'init_level_points': self.init_level_points
                    }
            
            engine = SimpleAnnotationEngine()
            return engine
            
        except Exception as e:
            return None
    
    def _applyAutoAnnotation(self, frame):
        """通过服务端调用自动标注检测器获取初始位置，设置到标注引擎中"""
        import time
        
        # 自动标注功能开关：True=启用，False=关闭
        annotation_debug = False
        
        if not annotation_debug:
            self.logger.debug(f"[自动标注] annotation_debug=False，跳过自动标注功能")
            return
        
        print(f"\n{'='*60}")
        self.logger.debug(f"[自动标注] ===== 服务端自动标注开始 =====")
        
        try:
            if frame is None or self.annotation_engine is None:
                self.logger.debug(f"[自动标注] 前置条件不满足! frame={frame is not None}, engine={self.annotation_engine is not None}")
                return
            
            self.logger.debug(f"[自动标注] 输入图像: shape={frame.shape}, dtype={frame.dtype}")
            
            channel_id = self.general_set_panel.channel_id if self.general_set_panel else None
            self.logger.debug(f"[自动标注] 通道ID: {channel_id}")
            
            # 通过WebSocket向服务端发送自动标注请求
            if hasattr(self, 'ws_client') and self.ws_client:
                # 将图像编码为base64发送到服务端
                import cv2
                import base64
                
                # 编码图像
                _, buffer = cv2.imencode('.jpg', frame)
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                auto_annotation_request = {
                    "action": "auto_annotation",
                    "channel_id": channel_id,
                    "frame_data": frame_base64,
                    "conf_threshold": 0.5,
                    "min_area": 50,
                    "padding": 10
                }
                
                self.logger.debug(f"[自动标注] 发送自动标注请求到服务端")
                
                # 发送请求到服务端
                response = self.ws_client.send_command('auto_annotation', **auto_annotation_request)
                
                if response:
                    # 注意：由于send_command返回bool，实际的检测数据需要通过其他方式获取
                    # 这里暂时使用模拟数据，实际应该通过消息回调获取
                    self.logger.debug(f"[自动标注] 服务端自动标注命令发送成功")
                    # TODO: 实现通过消息回调获取检测结果的机制
                else:
                    self.logger.debug(f"[自动标注] 服务端自动标注命令发送失败")
            else:
                # 如果WebSocket不可用，尝试通过SSH调用服务端自动标注
                self.logger.debug(f"[自动标注] WebSocket不可用，尝试通过SSH调用服务端自动标注")
                
                try:
                    from ...utils.config import RemoteConfigManager
                except ImportError:
                    try:
                        from utils.config import RemoteConfigManager
                    except ImportError:
                        RemoteConfigManager = None
                        
                if not RemoteConfigManager:
                    self.logger.debug(f"[自动标注] 远程配置管理器不可用")
                    return
                    
                remote_config = RemoteConfigManager()
                ssh_manager = remote_config._get_ssh_manager()
                
                if not ssh_manager:
                    self.logger.debug(f"[自动标注] SSH连接不可用")
                    return
                
                # 先将图像保存到临时文件
                import cv2
                import tempfile
                import os
                
                temp_dir = tempfile.mkdtemp()
                temp_image_path = os.path.join(temp_dir, 'annotation_frame.jpg')
                cv2.imwrite(temp_image_path, frame)
                
                # 上传图像到服务端
                remote_temp_path = f"/tmp/annotation_frame_{channel_id}.jpg"
                upload_cmd = f"scp {temp_image_path} liquid:{remote_temp_path}"
                
                import subprocess
                upload_result = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True)
                
                if upload_result.returncode == 0:
                    # 在服务端执行自动标注
                    annotation_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
import cv2
import json
from detection import LiquidDetectionEngine

try:
    # 加载图像
    frame = cv2.imread('{remote_temp_path}')
    if frame is None:
        print('ERROR: 无法加载图像')
        exit(1)
    
    # 获取模型路径
    from utils.config import load_config
    config = load_config()
    model_path = config.get('{channel_id}_model_path', 'database/model/detection_model/bestmodel/tensor.pt')
    
    # 创建检测引擎
    engine = LiquidDetectionEngine(
        model_path=model_path,
        device='cuda',
        batch_size=1
    )
    
    # 创建自动标注检测器
    auto_detector = AutoAnnotationDetector(model=engine.model, device='cuda')
    
    # 执行检测
    result = auto_detector.detect(frame, conf_threshold=0.5, min_area=50)
    
    if result.get('success'):
        # 获取系统格式数据
        data = auto_detector.get_system_format(result, padding=10)
        print('SUCCESS:' + json.dumps(data))
    else:
        print('ERROR: 检测失败')
        
except Exception as e:
    print(f'ERROR: {{e}}')
finally:
    import os
    if os.path.exists('{remote_temp_path}'):
        os.remove('{remote_temp_path}')
"
"""
                    
                    self.logger.debug(f"[自动标注] 执行服务端自动标注命令")
                    result = ssh_manager.execute_remote_command(annotation_cmd)
                    
                    if result['success'] and 'SUCCESS:' in result['stdout']:
                        # 解析结果
                        import json
                        success_line = [line for line in result['stdout'].split('\n') if line.startswith('SUCCESS:')][0]
                        data_json = success_line.replace('SUCCESS:', '')
                        detection_data = json.loads(data_json)
                        
                        boxes = detection_data.get('boxes', [])
                        bottom_points = detection_data.get('bottom_points', [])
                        top_points = detection_data.get('top_points', [])
                        
                        self.logger.debug(f"[自动标注] 通过SSH检测到 {len(boxes)} 个区域")
                        
                        # 添加到标注引擎
                        for i, (box, bottom, top) in enumerate(zip(boxes, bottom_points, top_points)):
                            self.annotation_engine.boxes.append(box)
                            self.annotation_engine.bottom_points.append(bottom)
                            self.annotation_engine.top_points.append(top)
                            print(f"   区域{i+1}: box{box}, top{top}, bottom{bottom}")
                        
                        self.logger.debug(f"[自动标注] 完成，已添加 {len(self.annotation_engine.boxes)} 个区域")
                    else:
                        error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                        self.logger.debug(f"[自动标注] 通过SSH自动标注失败: {error_msg}")
                
                # 清理临时文件
                try:
                    os.remove(temp_image_path)
                    os.rmdir(temp_dir)
                except:
                    pass
            
            print(f"{'='*60}\n")
            
        except Exception as e:
            self.logger.debug(f"[自动标注] 异常: {e}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
    
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
            pass
            import traceback
            traceback.print_exc()
            if self.annotation_widget:
                self.annotation_widget.showAnnotationError(f"获取标注数据失败: {str(e)}")
    
    def _handleRoiDragCompleted(self, roi_index: int, roi_box: tuple):
        """
        处理ROI拖动完成信号 - 自动标注顶部线条、底部线条、初始液位线
        
        流程：
        1. 尝试使用模型自动标注
        2. 若自动标注失败则使用固定比例设置液位线
        
        Args:
            roi_index: ROI索引
            roi_box: ROI框数据 (cx, cy, size)
        """
        try:
            if not self.annotation_widget or not self.annotation_engine:
                return
            
            cx, cy, size = roi_box
            
            # 计算固定比例的默认位置（作为备选）
            half_size = size // 2
            default_top = (cx, cy - half_size + int(size * 0.1))      # 顶部：ROI顶部向下10%
            default_bottom = (cx, cy + half_size - int(size * 0.1))   # 底部：ROI底部向上10%
            default_init_level = (cx, cy)                              # 初始液位：ROI中心
            
            # 获取当前帧
            frame = self.annotation_widget.current_frame
            if frame is None:
                self._applyAnnotationPoints(roi_index, default_top, default_bottom, default_init_level, 'fixed_ratio')
                return
            
            # 尝试自动标注
            auto_success = False
            try:
                from utils.auto_dot import auto_annotate_single_roi, get_model_from_pool
                
                # 获取通道ID
                channel_id = None
                if self.general_set_panel and hasattr(self.general_set_panel, 'channel_id'):
                    channel_id = self.general_set_panel.channel_id
                
                # 尝试从全局模型池获取模型
                model = get_model_from_pool(channel_id)
                
                if model is not None:
                    # 执行自动标注
                    result = auto_annotate_single_roi(frame, roi_box, model, channel_id)
                    
                    if result.get('success') and result.get('method') != 'default' and result.get('method') != 'default_fallback':
                        top_point = result['top_point']
                        bottom_point = result['bottom_point']
                        init_level_point = result['init_level_point']
                        method = result.get('method', 'unknown')
                        confidence = result.get('confidence', 0.0)
                        
                        self._applyAnnotationPoints(roi_index, top_point, bottom_point, init_level_point, method)
                        auto_success = True
                    
            except ImportError:
                pass
            except Exception:
                pass
            
            # 若自动标注失败，使用固定比例
            if not auto_success:
                self._applyAnnotationPoints(roi_index, default_top, default_bottom, default_init_level, 'fixed_ratio')
                
        except Exception:
            pass
    
    def _applyAnnotationPoints(self, roi_index: int, top_point: tuple, bottom_point: tuple, 
                                init_level_point: tuple, method: str):
        """
        应用标注点位置到标注引擎
        
        Args:
            roi_index: ROI索引
            top_point: 顶部线条位置 (x, y)
            bottom_point: 底部线条位置 (x, y)
            init_level_point: 初始液位线位置 (x, y)
            method: 标注方法（用于日志）
        """
        try:
            # 更新顶部线条
            if roi_index < len(self.annotation_engine.top_points):
                self.annotation_engine.top_points[roi_index] = top_point
            
            # 更新底部线条
            if roi_index < len(self.annotation_engine.bottom_points):
                self.annotation_engine.bottom_points[roi_index] = bottom_point
            
            # 更新初始液位线
            if hasattr(self.annotation_engine, 'init_level_points'):
                while len(self.annotation_engine.init_level_points) <= roi_index:
                    self.annotation_engine.init_level_points.append(init_level_point)
                self.annotation_engine.init_level_points[roi_index] = init_level_point
            
            # 刷新显示
            if self.annotation_widget:
                self.annotation_widget._updateDisplay()
                
        except Exception:
            pass
    
    def _initPhysicalZoomForAnnotation(self, annotation_widget):
        """为标注界面初始化物理变焦控制器"""
        try:
            # 尝试导入物理变焦控制器
            try:
                from handlers.videopage.physical_zoom_controller import PhysicalZoomController
            except ImportError:
                try:
                    from physical_zoom_controller import PhysicalZoomController
                except ImportError:
                    return
            
            # 获取通道配置
            if not self.general_set_panel or not self.general_set_panel.channel_id:
                return
            
            channel_id = self.general_set_panel.channel_id
            
            # 从配置文件获取设备IP
            config = self._getChannelConfig(channel_id)
            if not config:
                return
            
            device_ip = config.get('address', '')
            if not device_ip or 'rtsp://' not in device_ip:
                return
            
            # 提取IP地址
            import re
            match = re.search(r'@(\d+\.\d+\.\d+\.\d+)', device_ip)
            if not match:
                return
            
            device_ip = match.group(1)
            
            # 创建物理变焦控制器
            physical_zoom_controller = PhysicalZoomController(
                device_ip=device_ip,
                username='admin',
                password='cei345678',
                channel=1
            )
            
            # 尝试连接设备
            if physical_zoom_controller.connect_device():
                # 设置到标注界面
                annotation_widget.setPhysicalZoomController(physical_zoom_controller)
                
        except Exception as e:
            pass
    
    def showGeneralSetPanel(self):
        """显示常规设置面板"""
        from widgets.videopage.general_set import GeneralSetPanel
        
        # 创建面板
        panel = GeneralSetPanel(self)
        
        # 连接信号
        self.connectGeneralSetPanel(panel)
        
        return panel
    
    def showGeneralSetDialog(self, channel_name=None, channel_id=None, task_info=None):
        """显示常规设置对话框"""
        from widgets.videopage.general_set import GeneralSetDialog
        
        # 创建对话框
        dialog = GeneralSetDialog(self, channel_name, channel_id, task_info)
        
        # 连接信号（这会设置 self.general_set_panel）
        self.connectGeneralSetPanel(dialog.getPanel())
        
        # 自动加载该通道的配置
        if channel_id:
            pass
            
            # 使用QTimer延迟加载，确保UI初始化完成
            from qtpy.QtCore import QTimer
            QTimer.singleShot(200, self._handleLoadSettings)
        
        return dialog
    
    def showAnnotationWidget(self, parent=None):
        """显示标注界面组件"""
        from widgets.videopage.annotation import AnnotationWidget
        
        # 创建标注界面组件
        widget = AnnotationWidget(parent, self.annotation_engine)
        
        # 连接信号
        self.connectAnnotationWidget(widget)
        
        return widget