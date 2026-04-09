# -*- coding: utf-8 -*-

"""
任务面板处理器 (Mixin类)

对应组件：widgets/videopage/missionpanel.py (MissionPanel)

职责：
- 处理新建任务对话框的创建和管理
- 处理任务数据的处理
- 管理任务的生命周期
"""

import os
import yaml
import shutil
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

# 导入统一的路径管理函数
try:
    from ...database.config import get_project_root
except ImportError:
    from database.config import get_project_root


class MissionPanelHandler:
    """
    任务面板处理器 (Mixin类)
    
    处理任务面板相关的业务逻辑
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mission_panel = None
        self.mission_text_status = None  # 文本状态管理器
    
    def connectMissionPanel(self, mission_panel):
        """
        连接任务面板信号
        
        Args:
            mission_panel: MissionPanel实例
        """
        self.mission_panel = mission_panel
        
        # 🔥 创建文本状态管理器
        self.mission_text_status = MissionTextStatus(mission_panel)
        
        # 连接信号
        mission_panel.removeTaskRequested.connect(self._handleRemoveTask)
        mission_panel.clearTableRequested.connect(self._handleClearTable)
        mission_panel.taskConfirmed.connect(self._handleTaskConfirmed)
        mission_panel.taskCancelled.connect(self._handleTaskCancelled)
        mission_panel.taskSelected.connect(self._handleTaskSelected)
        
        # 🔥 连接曲线按钮点击信号
        mission_panel.buttonClicked.connect(self._handleButtonClicked)
        
        # 🔥 连接通道管理信号
        mission_panel.channelManageClicked.connect(self._handleChannelManage)
        mission_panel.channelConfirmed.connect(self._handleChannelConfirmed)
        mission_panel.channelCancelled.connect(self._handleChannelCancelled)
        mission_panel.channelDebugRequested.connect(self._handleChannelDebug)

        # 🔥 连接一键启动信号
        mission_panel.startAllClicked.connect(self._handleStartAll)
        
        # 🔥 连接表格单击事件（规则2：单击选中行时置为黑色）
        mission_panel.table.cellClicked.connect(self._onMissionRowClicked)
        
        #  自动加载已保存的任务配置
        self._loadAllMissions()
    
    def _handleButtonClicked(self, row_index, column_index):
        """
        处理任务面板按钮点击（来源1）
        
        Args:
            row_index: 行索引
            column_index: 列索引
        """
        try:
            # 获取曲线按钮所在列（从MissionPanel配置中读取）
            from widgets.videopage.missionpanel import MissionPanel
            CURVE_BUTTON_COLUMN = MissionPanel.CURVE_BUTTON_COLUMN
            
            # 如果点击的是曲线按钮
            if column_index == CURVE_BUTTON_COLUMN:
                # 获取该行的任务信息
                if hasattr(self, 'mission_panel') and self.mission_panel:
                    # 从表格获取任务编号和任务名称
                    task_id_item = self.mission_panel.table.item(row_index, 0)  # 任务编号列
                    task_name_item = self.mission_panel.table.item(row_index, 1)  # 任务名称列
                    
                    if task_id_item and task_name_item:
                        task_id = task_id_item.text()
                        task_name = task_name_item.text()
                        # 组合任务文件夹名称
                        mission_folder_name = f"{task_id}_{task_name}"
                        
                        # 🔥 先刷新任务列表，确保新建的任务能被找到
                        if hasattr(self, 'curvePanel') and self.curvePanel:
                            self._refreshCurveMissionList()
                            # 设置 curvemission 的值
                            success = self.curvePanel.setMissionFromTaskName(mission_folder_name)
                
                # 调用ViewHandler的toggleVideoPageMode方法切换布局
                if hasattr(self, 'toggleVideoPageMode'):
                    self.toggleVideoPageMode()
        
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _onMissionRowClicked(self, row, column):
        """
        任务行被点击（规则2：单击选中行时该行文本置为黑色）
        
        只有当任务状态为"已启动"时才置黑
        
        Args:
            row: 行索引
            column: 列索引
        """
        if not self.mission_text_status or not self.mission_panel:
            return
        
        try:
            # 获取任务状态列（第2列）
            status_item = self.mission_panel.table.item(row, 2)
            if not status_item:
                return
            
            task_status = status_item.text()
            
            # 只有任务状态为"已启动"时才置黑
            if task_status == "已启动":
                self.mission_text_status.setRowBlackOnSelect(row)
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _handleTaskConfirmed(self, task_info):
        """处理任务确认（从新建任务界面）"""
        try:
            # 🔥 第一步：先创建结果文件夹并获取路径
            mission_result_folder_path = self._createmission_resultFolder(task_info)
            if mission_result_folder_path:
                # 将结果文件夹路径添加到task_info中
                task_info['mission_result_folder_path'] = mission_result_folder_path
            
            # 第二步：保存任务配置到YAML文件（包含mission_result_folder_path）
            if self._saveMissionConfig(task_info):
                # 获取保存的YAML文件路径
                yaml_file_path = self._getYamlFilePath(task_info)
                
                # 第三步：复制YAML文件到结果文件夹
                if mission_result_folder_path and yaml_file_path:
                    self._copyYamlTomission_resultFolder(yaml_file_path, mission_result_folder_path)
                
                # 第四步：添加到表格
                if self.mission_panel:
                    self.mission_panel.addTaskRow(task_info)
            else:
                QtWidgets.QMessageBox.warning(
                    self.mission_panel, "警告", "任务配置保存失败，但任务已添加到列表"
                )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(
                self.mission_panel, "错误", f"添加任务失败: {str(e)}"
            )
    
    def _handleTaskCancelled(self):
        """处理任务取消"""
        pass
    
    def _handleTaskSelected(self, task_info):
        """
        处理任务选中事件（双击任务时）
        
        将任务配置信息同步到对应通道的配置文件中
        
        Args:
            task_info: 任务信息字典，包含：
                - task_id: 任务编号
                - task_name: 任务名称
                - selected_channels: 选中的通道列表（如 ['通道1', '通道2']）
        """
        try:
            task_id = task_info.get('task_id', '')
            task_name = task_info.get('task_name', '')
            selected_channels = task_info.get('selected_channels', [])
            
            if not task_id or not task_name:
                # 重置current_mission为默认值
                if hasattr(self, 'current_mission'):
                    self.current_mission = r"D:\restructure\liquid_level_line_detection_system\database\mission_result\None"
                return
            
            if not selected_channels:
                return
            
            # 🔥 从任务配置文件中读取完整的任务信息（包括mission_result_folder_path）
            full_task_info = self._loadMissionConfig(task_id, task_name)
            if not full_task_info:
                full_task_info = task_info
            
            # 获取结果文件夹路径（作为save_liquid_data_path）
            mission_result_folder_path = full_task_info.get('mission_result_folder_path', '')
            
            # 🔥 如果没有mission_result_folder_path（旧任务），尝试重新生成或查找
            if not mission_result_folder_path:
                # 尝试创建或获取现有的结果文件夹
                mission_result_folder_path = self._createmission_resultFolder(full_task_info)
                
                if mission_result_folder_path:
                    # 🔥 更新任务配置文件，保存mission_result_folder_path
                    full_task_info['mission_result_folder_path'] = mission_result_folder_path
                    self._saveMissionConfig(full_task_info)
            
            # 🔥 多任务支持：不再使用全局 current_mission，而是为每个通道独立存储任务信息
            # 提取任务文件夹名称（用于显示）
            import os
            if mission_result_folder_path:
                if os.path.sep in str(mission_result_folder_path) or '/' in str(mission_result_folder_path):
                    task_folder_name = os.path.basename(os.path.normpath(mission_result_folder_path))
                else:
                    task_folder_name = str(mission_result_folder_path).strip()
            else:
                task_folder_name = f"{task_id}_{task_name}"
            
            # 🔥 检查通道是否已有任务，如果有则弹出确认对话框
            channels_with_tasks = self._checkChannelsWithExistingTasks(selected_channels, task_folder_name)
            
            if channels_with_tasks:
                # 构建提示信息
                channel_task_list = []
                for ch_key, existing_task in channels_with_tasks:
                    channel_task_list.append(f"{ch_key} 已有任务: {existing_task}")
                
                message = "以下通道已有任务：\n\n" + "\n".join(channel_task_list)
                message += f"\n\n确定要切换任务 [{task_id}_{task_name}] 吗？"
                
                # 🔥 创建自定义确认对话框（标题栏显示警告图标，内容区域无图标，中文按钮）
                msg_box = QtWidgets.QMessageBox(
                    self.mission_panel if hasattr(self, 'mission_panel') else None
                )
                msg_box.setWindowTitle("切换任务确认")
                msg_box.setText(message)
                msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)  # 内容区域不显示图标
                
                # 设置窗口标题栏图标为系统警告图标
                warning_icon = msg_box.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
                msg_box.setWindowIcon(warning_icon)
                
                # 移除帮助按钮
                original_flags = msg_box.windowFlags()
                msg_box.setWindowFlags(
                    msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
                )
                
                # 添加自定义按钮（中文）
                btn_confirm = msg_box.addButton("确认", QtWidgets.QMessageBox.YesRole)
                btn_cancel = msg_box.addButton("取消", QtWidgets.QMessageBox.NoRole)
                
                # 设置默认按钮为"取消"
                msg_box.setDefaultButton(btn_cancel)
                
                # 显示对话框并获取结果
                msg_box.exec_()
                clicked_button = msg_box.clickedButton()
                
                if clicked_button == btn_cancel:
                    # 🔥 通知Widget取消任务分配，不高亮行
                    if self.mission_panel:
                        self.mission_panel.cancelTaskAssignment()
                    
                    # 🔥 恢复之前选中行的黑色状态（如果有的话）
                    if self.mission_text_status and self.mission_text_status.selected_row >= 0:
                        # 保存当前选中行
                        previous_selected_row = self.mission_text_status.selected_row
                        # 重新设置为黑色
                        self.mission_text_status.setRowBlackOnSelect(previous_selected_row)
                    return
            
            # 🔥 遍历选中的通道，只更新这些通道的任务标签（不影响其他通道）
            for channel_key in selected_channels:
                # 将 '通道1' 转换为 'channel1'
                # 格式：'通道X' -> 'channelX'
                if channel_key.startswith('通道'):
                    channel_num = channel_key.replace('通道', '').strip()
                    channel_id = f'channel{channel_num}'
                    
                    # 🔥 直接更新通道任务标签（使用新的变量名方式）
                    self._updateChannelMissionLabel(channel_id, task_folder_name)
                    
                    # 更新通道面板的任务信息和配置文件
                    self._updateChannelTaskInfo(channel_id, task_id, task_name, mission_result_folder_path)
            
            # 🔥 确认任务分配，高亮选中的行
            if self.mission_panel:
                self.mission_panel.confirmTaskAssignment()
            
            # 🔥 恢复自动状态刷新：任务分配后刷新所有任务状态
            self._refreshAllTaskStatus()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _loadMissionConfig(self, task_id, task_name):
        """
        从YAML文件加载任务配置
        
        Args:
            task_id: 任务编号
            task_name: 任务名称
        
        Returns:
            dict: 任务配置字典，失败返回None
        """
        try:
            mission_dir = self._getMissionConfigPath()
            if not mission_dir:
                return None
            
            # 构建文件名
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            filename = f"{safe_task_id}_{safe_task_name}.yaml"
            file_path = os.path.join(mission_dir, filename)
            
            # 读取YAML文件
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                return None
            
            return config_data
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _syncTaskToConfigFile(self, channel_id, task_id, task_name, save_liquid_data_path=''):
        """
        将任务信息同步到channel_config.yaml配置文件
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            task_id: 任务编号
            task_name: 任务名称
            save_liquid_data_path: 结果保存路径（结果文件夹路径）
        
        Returns:
            bool: 同步是否成功
        """
        try:
            # 获取channel_config.yaml配置文件路径（使用统一的路径管理）
            project_root = get_project_root()
            config_file = os.path.join(project_root, 'database', 'config', 'channel_config.yaml')
            
            if not os.path.exists(config_file):
                return False
            
            # 读取现有配置
            with open(config_file, 'r', encoding='utf-8') as f:
                channel_config = yaml.safe_load(f) or {}

            # 标准化通道ID格式为字符串 'channelN'
            if isinstance(channel_id, int):
                channel_key = f'channel{channel_id}'
            elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                channel_key = f'channel{channel_id}'
            else:
                channel_key = channel_id

            # 确保通道配置存在
            if channel_key not in channel_config:
                channel_config[channel_key] = {}

            # 检查是否有旧的顶层配置结构（如channel1）
            # 如果存在旧结构，同时更新顶层和general
            if 'task_id' in channel_config[channel_key]:
                # 更新顶层配置（向后兼容）
                channel_config[channel_key]['task_id'] = task_id
                channel_config[channel_key]['task_name'] = task_name
                channel_config[channel_key]['save_liquid_data_path'] = save_liquid_data_path

            # 确保general配置存在
            if 'general' not in channel_config[channel_key]:
                channel_config[channel_key]['general'] = {}

            # 更新general部分的任务信息
            channel_config[channel_key]['general']['task_id'] = task_id
            channel_config[channel_key]['general']['task_name'] = task_name
            channel_config[channel_key]['general']['save_liquid_data_path'] = save_liquid_data_path
            
            # 保存回配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(channel_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _updateChannelTaskInfo(self, channel_id, task_id, task_name, save_liquid_data_path=''):
        """
        更新指定通道的任务信息
        
        将任务配置同步到：
        1. 通道面板UI显示
        2. channel_config.yaml 配置文件
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            task_id: 任务编号
            task_name: 任务名称
            save_liquid_data_path: 结果保存路径（结果文件夹路径）
        """
        try:
            # 🔥 第一步：同步到 channel_config.yaml（独立业务，无论通道是否打开都执行）
            sync_success = self._syncTaskToConfigFile(channel_id, task_id, task_name, save_liquid_data_path)
            
            # 🔥 第二步：更新通道面板UI（可选操作，仅在通道已打开时执行）
            # 检查是否有通道面板映射（从ChannelPanelHandler获取）
            if not hasattr(self, '_channel_panels_map'):
                return
            
            # 获取对应的通道面板
            channel_panel = self._channel_panels_map.get(channel_id)
            
            if not channel_panel:
                return
            
            # 更新通道的channel_data，添加任务信息
            channel_data = {
                'task_id': task_id,
                'task_name': task_name,
                'save_liquid_data_path': save_liquid_data_path
            }
            
            # 调用通道面板的updateChannel方法（更新内部存储）
            if hasattr(channel_panel, 'updateChannel'):
                success = channel_panel.updateChannel(channel_id, channel_data)
            
            # 🔥 多任务支持：不再从全局 current_mission 读取，而是使用传入的任务信息
            # 更新UI显示（从 save_liquid_data_path 提取文件夹名称）
            if hasattr(channel_panel, 'setTaskInfo'):
                import os
                # 从 save_liquid_data_path 提取文件夹名称
                if save_liquid_data_path:
                    if os.path.sep in str(save_liquid_data_path) or '/' in str(save_liquid_data_path):
                        folder_name = os.path.basename(os.path.normpath(save_liquid_data_path))
                    else:
                        folder_name = str(save_liquid_data_path).strip()
                    
                    # 如果文件夹名称为空或为"None"，使用任务名称
                    if folder_name and folder_name.lower() != "none":
                        channel_panel.setTaskInfo(folder_name)
                    else:
                        # 使用任务名称作为备选
                        channel_panel.setTaskInfo(f"{task_id}_{task_name}")
                else:
                    # 没有路径，使用任务名称
                    channel_panel.setTaskInfo(f"{task_id}_{task_name}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _getMissionConfigPath(self):
        """
        获取任务配置文件保存路径（动态路径）
        
        Returns:
            str: 任务配置文件夹路径
        """
        try:
            # 使用项目根目录的动态路径（统一的路径管理）
            project_root = get_project_root()
            
            # 任务配置文件夹路径
            mission_dir = os.path.join(project_root, 'database', 'config', 'mission')
            
            #  确保目录存在
            if not os.path.exists(mission_dir):
                os.makedirs(mission_dir)
            
            return mission_dir
            
        except Exception as e:
            return None
    
    def _saveMissionConfig(self, task_info):
        """
        保存任务配置到YAML文件
        
        Args:
            task_info: 任务信息字典，包含：
                - task_id: 任务编号
                - task_name: 任务名称
                - selected_channels: 选中的通道列表
                - status: 状态
                - mission_result_folder_path: 结果文件夹路径（可选）
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 获取任务配置路径
            mission_dir = self._getMissionConfigPath()
            if not mission_dir:
                return False
            
            #  构建文件名：任务编号_任务名称.yaml
            task_id = task_info.get('task_id', '')
            task_name = task_info.get('task_name', '')
            
            if not task_id or not task_name:
                return False
            
            # 清理文件名中的非法字符
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            
            filename = f"{safe_task_id}_{safe_task_name}.yaml"
            file_path = os.path.join(mission_dir, filename)
            
            #  准备保存的配置数据
            config_data = {
                'task_id': task_info.get('task_id', ''),
                'task_name': task_info.get('task_name', ''),
                'status': task_info.get('status', '未启动'),
                'selected_channels': task_info.get('selected_channels', []),
                'created_time': QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss'),
                'mission_result_folder_path': task_info.get('mission_result_folder_path', ''),  # 🔥 添加结果文件夹路径
            }
            
            #  保存到YAML文件
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _sanitizeFilename(self, filename):
        """
        清理文件名中的非法字符
        
        Args:
            filename: 原始文件名
        
        Returns:
            str: 清理后的安全文件名
        """
        # Windows文件名非法字符：< > : " / \ | ? *
        illegal_chars = '<>:"/\\|?*'
        safe_filename = filename
        
        for char in illegal_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        return safe_filename
    
    def _getmission_resultPath(self):
        """
        获取结果文件夹路径（动态路径）
        
        Returns:
            str: 结果文件夹路径
        """
        try:
            # 使用项目根目录的动态路径（统一的路径管理）
            project_root = get_project_root()
            
            # 结果文件夹路径
            mission_result_dir = os.path.join(project_root, 'database', 'mission_result')
            
            # 确保目录存在
            if not os.path.exists(mission_result_dir):
                os.makedirs(mission_result_dir)
            
            return mission_result_dir
            
        except Exception as e:
            return None
    
    def _getYamlFilePath(self, task_info):
        """
        获取任务YAML文件的完整路径
        
        Args:
            task_info: 任务信息字典
        
        Returns:
            str: YAML文件路径
        """
        try:
            mission_dir = self._getMissionConfigPath()
            if not mission_dir:
                return None
            
            # 构建文件名
            task_id = task_info.get('task_id', '')
            task_name = task_info.get('task_name', '')
            
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            
            filename = f"{safe_task_id}_{safe_task_name}.yaml"
            return os.path.join(mission_dir, filename)
            
        except Exception as e:
            return None
    
    def _createmission_resultFolder(self, task_info):
        """
        在mission_result目录下创建任务文件夹
        
        Args:
            task_info: 任务信息字典
        
        Returns:
            str: 创建的文件夹路径，失败返回None
        """
        try:
            # 获取结果目录路径
            mission_result_dir = self._getmission_resultPath()
            if not mission_result_dir:
                return None
            
            # 构建任务文件夹名称：任务编号_任务名称
            task_id = task_info.get('task_id', '')
            task_name = task_info.get('task_name', '')
            
            if not task_id or not task_name:
                return None
            
            # 清理文件夹名称中的非法字符
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            
            folder_name = f"{safe_task_id}_{safe_task_name}"
            task_folder_path = os.path.join(mission_result_dir, folder_name)
            
            # 创建任务文件夹
            if not os.path.exists(task_folder_path):
                os.makedirs(task_folder_path)
            
            # 返回创建的文件夹路径
            return task_folder_path
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _copyYamlTomission_resultFolder(self, yaml_file_path, mission_result_folder_path):
        """
        复制YAML文件到结果文件夹
        
        Args:
            yaml_file_path: YAML文件路径
            mission_result_folder_path: 结果文件夹路径
        
        Returns:
            bool: 复制是否成功
        """
        try:
            if not yaml_file_path or not os.path.exists(yaml_file_path):
                return False
            
            if not mission_result_folder_path or not os.path.exists(mission_result_folder_path):
                return False
            
            # 复制YAML文件到结果文件夹
            yaml_filename = os.path.basename(yaml_file_path)
            dest_yaml_path = os.path.join(mission_result_folder_path, yaml_filename)
            
            shutil.copy2(yaml_file_path, dest_yaml_path)
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _handleRemoveTask(self, row_index):
        """
        处理删除任务请求
        
        注意：此方法由Widget的右键菜单调用，Widget已经显示了确认对话框
        所以这里不需要再次确认，直接执行删除操作
        
        Args:
            row_index: 要删除的任务行索引
        """
        if not self.mission_panel:
            return
        
        row_data = self.mission_panel.getRowData(row_index)
        if not row_data:
            return
        
        task_id = row_data[0] if len(row_data) > 0 else ''
        task_name = row_data[1] if len(row_data) > 1 else f"任务 {row_index}"
        
        try:
            # 🔥 删除结果文件夹
            self._deletemission_resultFolder(task_id, task_name)
            
            # 删除对应的YAML配置文件
            self._deleteMissionConfig(task_id, task_name)
            
            # 重新加载任务列表（而不是只删除单行）
            # 这样可以确保分页数据和UI完全同步
            self._loadAllMissions()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _handleClearTable(self):
        """处理清空表格请求"""
        if not self.mission_panel:
            return
        
        row_count = self.mission_panel.rowCount()
        
        # 显示确认对话框
        if self.mission_panel.showConfirmDialog(
            "确认清空", f"确定要清空所有 {row_count} 个任务吗？\n这将删除所有任务配置文件和结果文件夹！"
        ):
            # 🔥 删除所有结果文件夹
            self._deleteAllmission_resultFolders()
            
            # 删除所有YAML配置文件
            self._deleteAllMissionConfigs()
            
            # 清空表格
            self.mission_panel.clearTable()
    
    def showMissionPanel(self):
        """显示任务面板"""
        from widgets.videopage.missionpanel import MissionPanel
        
        # 创建任务面板
        panel = MissionPanel(self)
        
        # 连接信号
        self.connectMissionPanel(panel)
        
        return panel
    
    def _loadAllMissions(self):
        """
        从配置文件夹加载所有任务配置
        
        在程序启动时自动调用，恢复之前保存的任务
        """
        try:
            # 🔥 先清空现有任务列表，避免重复添加
            if self.mission_panel:
                self.mission_panel.clearTable()
            
            # 获取任务配置路径
            mission_dir = self._getMissionConfigPath()
            if not mission_dir or not os.path.exists(mission_dir):
                return
            
            # 扫描所有 .yaml 文件
            yaml_files = [f for f in os.listdir(mission_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                return
            
            loaded_count = 0
            tasks_to_load = []
            
            #  第一步：解析所有配置文件
            for yaml_file in yaml_files:
                file_path = os.path.join(mission_dir, yaml_file)
                
                try:
                    # 读取YAML配置
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                    
                    if not config_data:
                        continue
                    
                    # 构建任务信息
                    task_info = {
                        'task_id': config_data.get('task_id', ''),
                        'task_name': config_data.get('task_name', ''),
                        'status': config_data.get('status', '未启动'),
                        'selected_channels': config_data.get('selected_channels', []),
                        'mission_result_folder_path': config_data.get('mission_result_folder_path', ''),  # 🔥 加载结果文件夹路径
                    }
                    
                    # 验证必填字段
                    if not task_info['task_id'] or not task_info['task_name']:
                        continue
                    
                    tasks_to_load.append(task_info)
                    
                except Exception as e:
                    continue
            
            #  第二步：批量添加到任务面板（禁用实时刷新）
            if self.mission_panel and tasks_to_load:
                for task_info in tasks_to_load:
                    # 🔥 根据通道使用情况动态计算状态
                    task_id = task_info.get('task_id', '')
                    task_name = task_info.get('task_name', '')
                    task_folder_name = f"{task_id}_{task_name}"
                    
                    # 检查是否有通道正在使用这个任务
                    is_task_in_use = self._isTaskInUse(task_folder_name)
                    actual_status = "已启动" if is_task_in_use else "未启动"
                    
                    # 🔥 将通道列表拆分为4个独立的列
                    selected_channels = task_info.get('selected_channels', [])
                    channel_cols = ['', '', '', '']  # 4个通道列，默认为空
                    for ch in selected_channels:
                        # 提取通道编号（如"通道1" -> 0, "通道2" -> 1）
                        if ch.startswith('通道'):
                            try:
                                ch_num = int(ch.replace('通道', '')) - 1
                                if 0 <= ch_num < 4:
                                    # 🔥 显示完整的通道名称（如 "通道1", "通道2", "通道3", "通道4"）
                                    channel_cols[ch_num] = '通道' + str(ch_num + 1)
                            except ValueError:
                                pass
                    
                    row_data = [
                        task_id,
                        task_name,
                        actual_status,  # 使用动态计算的状态
                        channel_cols[0],  # 通道1
                        channel_cols[1],  # 通道2
                        channel_cols[2],  # 通道3
                        channel_cols[3],  # 通道4
                        ''  # 曲线列
                    ]
                    #  update_display=False：不立即刷新
                    self.mission_panel.addRow(row_data, task_info, update_display=False)
                    loaded_count += 1
                
                #  第三步：统一刷新显示
                self.mission_panel.refreshDisplay()
                
                # 🔥 第四步：初始化所有行为灰色（规则1）
                if self.mission_text_status:
                    self.mission_text_status.initializeAllRowsGray()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    # 🔥 已删除 _updateChannelCellColors 方法
    # 通道列颜色现在由 MissionTextStatus 类统一管理
    
    def _isChannelDetecting(self, channel_id):
        """
        检查指定通道是否正在检测
        
        Args:
            channel_id: 通道ID（如'channel1'）
        
        Returns:
            bool: True表示正在检测，False表示未检测
        """
        try:
            # 🔥 直接从主窗口获取 channelXdetect 变量
            detect_var_name = f'{channel_id}detect'
            if hasattr(self, detect_var_name):
                is_detecting = getattr(self, detect_var_name, False)
                return is_detecting
            return False
        except Exception as e:
            return False
    
    def _deleteMissionConfig(self, task_id, task_name):
        """
        删除单个任务的YAML配置文件
        
        Args:
            task_id: 任务编号
            task_name: 任务名称
        """
        try:
            mission_dir = self._getMissionConfigPath()
            if not mission_dir:
                return
            
            # 构建文件名
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            filename = f"{safe_task_id}_{safe_task_name}.yaml"
            file_path = os.path.join(mission_dir, filename)
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _deleteAllMissionConfigs(self):
        """删除所有任务的YAML配置文件"""
        try:
            mission_dir = self._getMissionConfigPath()
            if not mission_dir or not os.path.exists(mission_dir):
                return
            
            # 扫描所有 .yaml 文件
            yaml_files = [f for f in os.listdir(mission_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                return
            
            deleted_count = 0
            for yaml_file in yaml_files:
                file_path = os.path.join(mission_dir, yaml_file)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"️ 已删除: {yaml_file}")
                except Exception as e:
                    print(f" 删除失败 ({yaml_file}): {e}")
            
            print(f" 已删除 {deleted_count}/{len(yaml_files)} 个任务配置文件")
        
        except Exception as e:
            print(f" 删除所有任务配置失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _deletemission_resultFolder(self, task_id, task_name):
        """
        删除单个任务的结果文件夹
        
        Args:
            task_id: 任务编号
            task_name: 任务名称
        """
        try:
            mission_result_dir = self._getmission_resultPath()
            if not mission_result_dir:
                print("❌ 无法获取结果目录路径")
                return
            
            # 构建文件夹名称
            safe_task_id = self._sanitizeFilename(task_id)
            safe_task_name = self._sanitizeFilename(task_name)
            folder_name = f"{safe_task_id}_{safe_task_name}"
            task_folder_path = os.path.join(mission_result_dir, folder_name)
            
            # 删除文件夹
            if os.path.exists(task_folder_path):
                shutil.rmtree(task_folder_path)
                print(f"🗑️ 已删除任务结果文件夹: {folder_name}")
            else:
                print(f"⚠️ 任务结果文件夹不存在: {folder_name}")
        
        except Exception as e:
            print(f"❌ 删除任务结果文件夹失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _deleteAllmission_resultFolders(self):
        """删除所有任务的结果文件夹"""
        try:
            mission_result_dir = self._getmission_resultPath()
            if not mission_result_dir or not os.path.exists(mission_result_dir):
                print("⚠️ 结果目录不存在")
                return
            
            # 扫描所有文件夹
            folders = [f for f in os.listdir(mission_result_dir) 
                      if os.path.isdir(os.path.join(mission_result_dir, f))]
            
            if not folders:
                print("ℹ️ 没有结果文件夹需要删除")
                return
            
            deleted_count = 0
            for folder_name in folders:
                folder_path = os.path.join(mission_result_dir, folder_name)
                try:
                    shutil.rmtree(folder_path)
                    deleted_count += 1
                    print(f"🗑️ 已删除结果文件夹: {folder_name}")
                except Exception as e:
                    print(f"❌ 删除失败 ({folder_name}): {e}")
            
            print(f"🗑️ 已删除 {deleted_count}/{len(folders)} 个结果文件夹")
        
        except Exception as e:
            print(f"❌ 删除所有结果文件夹失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handleChannelManage(self):
        """处理通道管理按钮点击"""
        try:
            # 从配置文件加载当前通道配置
            channel_data = self._loadChannelConfig()
            
            # 加载数据到任务面板的通道管理视图
            self.mission_panel.loadChannelData(channel_data)
            
            # 切换到通道管理视图
            self.mission_panel.showChannelManageView()
            
        except Exception:
            pass
    
    def _handleChannelConfirmed(self, channel_data):
        """处理通道管理确认"""
        try:
            # 保存通道配置
            if self._saveChannelConfig(channel_data):
                # 刷新通道面板的名称显示
                self._refreshChannelPanelNames()
                
        except Exception:
            pass
    
    def _handleChannelCancelled(self):
        """处理通道管理取消"""
        pass
    
    def _loadChannelConfig(self):
        """从 default_config.yaml 加载通道配置"""
        try:
            from database.config import get_project_root
            import yaml
            
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return {'channels': {}}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            
            # 从 default_config.yaml 中提取通道配置
            channels = {}
            for i in range(1, 5):
                channel_key = f'channel{i}'
                if channel_key in config_data:
                    channel_info = config_data[channel_key]
                    channels[i] = {
                        'channel_id': i,
                        'name': channel_info.get('name', f'通道{i}'),
                        'address': channel_info.get('address', ''),
                        'file_path': channel_info.get('file_path', '')
                    }
            
            return {'channels': channels}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'channels': {}}
    
    def _saveChannelConfig(self, channel_data):
        """保存通道配置到 default_config.yaml"""
        try:
            from database.config import get_project_root
            import yaml
            
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            # 读取现有配置
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # 更新通道配置
            channels = channel_data.get('channels', {})
            for channel_id, channel_info in channels.items():
                channel_key = f'channel{channel_id}'
                
                # 获取地址并确保以 rtsp:// 开头
                address = channel_info.get('address', '')
                if address and not address.startswith('rtsp://'):
                    address = 'rtsp://' + address
                
                # 🔥 保留原有的其他字段（如 model_path），只更新 name, address, file_path
                if channel_key not in config:
                    config[channel_key] = {}
                config[channel_key]['name'] = channel_info.get('name', f'通道{channel_id}')
                config[channel_key]['address'] = address
                config[channel_key]['file_path'] = channel_info.get('file_path', '')
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            # 🔥 关键修复：同步更新内存中的 self._config 缓存
            # 这样 _getChannelConfigFromFile 才能读取到最新配置
            if hasattr(self, '_config'):
                self._config = config
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _refreshChannelPanelNames(self):
        """刷新所有通道面板的名称显示"""
        try:
            # 检查是否有通道面板映射（从 ChannelPanelHandler 继承）
            if not hasattr(self, '_channel_panels_map'):
                return
            
            # 从 default_config.yaml 重新加载通道配置
            from database.config import get_project_root
            import yaml
            
            project_root = get_project_root()
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            # 更新每个通道面板的名称
            for i in range(1, 5):
                channel_id = f'channel{i}'
                channel_key = f'channel{i}'
                
                # 获取通道面板
                panel = self._channel_panels_map.get(channel_id)
                if not panel:
                    continue
                
                # 从配置中获取通道名称
                if channel_key in config:
                    channel_name = config[channel_key].get('name', f'通道{i}')
                else:
                    channel_name = f'通道{i}'
                
                # 更新面板显示的名称
                if hasattr(panel, 'setChannelName'):
                    panel.setChannelName(channel_name)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _handleChannelDebug(self, channel_id, address):
        """处理通道调试请求 - 测试RTSP连接"""

        # 在新线程中测试RTSP连接，避免阻塞UI
        from qtpy.QtCore import QThread
        from handlers.videopage.HK_SDK.HKcapture import HKcapture

        class RtspTestThread(QThread):
            """RTSP连接测试线程"""
            finished = QtCore.Signal(bool, str)  # 成功/失败，消息

            def __init__(self, address):
                super().__init__()
                self.address = address

            def run(self):
                cap = None
                try:
                    # 使用HKcapture类进行连接测试
                    cap = HKcapture(self.address)

                    # 尝试打开连接
                    if not cap.open():
                        self.finished.emit(False, "无法打开连接")
                        return

                    # 尝试开始捕获
                    if not cap.start_capture():
                        self.finished.emit(False, "无法启动捕获")
                        cap.release()
                        return

                    # 等待并读取帧
                    import time
                    max_retries = 10
                    success = False

                    for i in range(max_retries):
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            success = True
                            break
                        time.sleep(0.2)  # 等待200ms

                    if success:
                        self.finished.emit(True, "连接成功")
                    else:
                        self.finished.emit(False, "无法读取视频帧")

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.finished.emit(False, f"连接失败: {str(e)}")
                finally:
                    # 确保释放资源
                    if cap is not None:
                        cap.release()

        # 创建测试线程
        test_thread = RtspTestThread(address)

        # 连接完成信号
        def on_test_finished(success, message):
            # 更新UI按钮状态
            if hasattr(self, 'mission_panel') and self.mission_panel:
                self.mission_panel.updateDebugButtonStatus(channel_id, success, message)

        test_thread.finished.connect(on_test_finished)

        # 启动测试线程
        test_thread.start()

        # 保存线程引用，防止被垃圾回收
        if not hasattr(self, '_rtsp_test_threads'):
            self._rtsp_test_threads = {}
        self._rtsp_test_threads[channel_id] = test_thread

    def _handleStartAll(self):
        """处理一键启动按钮点击 - 发送start_all指令到服务器"""
        try:
            print("[一键启动] ========== 开始一键启动流程 ==========")

            # 检查是否有WebSocket连接
            if not hasattr(self, 'ws_client') or not self.ws_client:
                print("[一键启动] 错误: WebSocket未初始化")
                QtWidgets.QMessageBox.warning(
                    self.mission_panel,
                    "警告",
                    "WebSocket未连接，无法启动检测"
                )
                return

            # 检查连接状态
            if not self.ws_client.is_connected:
                print("[一键启动] 错误: WebSocket未连接")
                QtWidgets.QMessageBox.warning(
                    self.mission_panel,
                    "警告",
                    "WebSocket未连接，请先连接服务器"
                )
                return

            print("[一键启动] WebSocket连接正常，开始订阅所有通道...")

            # 步骤1: 先订阅所有通道（确保能接收检测结果）
            all_channels = [f'channel{i}' for i in range(1, 9)]  # channel1-channel8
            subscribe_success_count = 0

            for channel_id in all_channels:
                if hasattr(self.ws_client, 'send_subscribe_command'):
                    if self.ws_client.send_subscribe_command(channel_id):
                        subscribe_success_count += 1
                        print(f"[一键启动] 订阅通道成功: {channel_id}")
                    else:
                        print(f"[一键启动] 订阅通道失败: {channel_id}")

            print(f"[一键启动] 订阅完成: {subscribe_success_count}/16 个通道")

            # 等待订阅完成
            import time
            time.sleep(0.5)

            # 步骤2: 发送start_all指令到服务器
            print("[一键启动] 发送start_all指令...")
            success = self.ws_client.ws_client.send_command('start_all')

            if success:
                print(f"[一键启动] start_all指令发送成功")
                print(f"[一键启动] 已订阅 {subscribe_success_count}/16 个通道")
                print(f"[一键启动] WebSocket连接状态: {self.ws_client.is_connected}")
                print(f"[一键启动] ========== 一键启动流程完成，保持连接接收数据 ==========")

                # 不显示MessageBox，避免阻塞事件循环
                # 改为在状态栏显示消息
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage(f"一键启动成功，已订阅 {subscribe_success_count}/16 个通道", 5000)

                print(f"[一键启动] 提示: 连接将保持活跃，持续接收检测结果")
            else:
                print("[一键启动] 错误: start_all指令发送失败")
                QtWidgets.QMessageBox.warning(
                    self.mission_panel,
                    "警告",
                    "发送启动指令失败"
                )

        except Exception as e:
            print(f"[一键启动] 异常: {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(
                self.mission_panel,
                "错误",
                f"发送启动指令失败: {str(e)}"
            )
    
    def _checkChannelsWithExistingTasks(self, selected_channels, new_task_name):
        """
        检查选中的通道是否已有任务（且不是当前要分配的任务）
        
        Args:
            selected_channels: 选中的通道列表（如 ['通道1', '通道2']）
            new_task_name: 新任务名称（如 '1_1'）
        
        Returns:
            list: 已有任务的通道列表 [(通道key, 现有任务名), ...]
                  如果所有通道都没有任务或任务相同，返回空列表
        """
        channels_with_tasks = []
        
        try:
            for channel_key in selected_channels:
                # 将 '通道1' 转换为 'channel1'
                if not channel_key.startswith('通道'):
                    continue
                
                channel_num = channel_key.replace('通道', '').strip()
                channel_id = f'channel{channel_num}'
                
                # 获取通道当前的任务信息
                existing_task = self._getChannelCurrentTask(channel_id)
                
                # 如果通道有任务且不是当前要分配的任务，记录下来
                if existing_task and existing_task != new_task_name:
                    channels_with_tasks.append((channel_key, existing_task))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return channels_with_tasks
    
    def _getChannelCurrentTask(self, channel_id):
        """
        获取通道当前的任务名称
        
        Args:
            channel_id: 通道ID（如 'channel1'）
        
        Returns:
            str: 任务名称，如果没有任务返回None
        """
        try:
            # 方法1：从通道面板UI读取
            if hasattr(self, '_channel_panels_map'):
                panel = self._channel_panels_map.get(channel_id)
                if panel and hasattr(panel, 'getTaskInfo'):
                    task_info = panel.getTaskInfo()
                    if task_info and task_info != "未分配任务":
                        return task_info
            
            # 方法2：从任务标签变量读取
            channel_num = int(channel_id.replace('channel', ''))
            mission_var_name = f'channel{channel_num}mission'
            if hasattr(self, mission_var_name):
                mission_label = getattr(self, mission_var_name)
                task_text = mission_label.text()
                if task_text and task_text != "未分配任务":
                    return task_text
            
            return None
            
        except Exception as e:
            print(f"⚠️ 获取通道任务失败 ({channel_id}): {e}")
            return None
    
    def _updateChannelMissionLabel(self, channel_id, task_folder_name):
        """
        直接更新指定通道的任务标签显示（支持多任务并行）
        
        使用新的变量名方式（channel1mission, channel2mission等）直接更新标签，
        不影响其他通道的任务标签。同时将任务行对应的通道列置黑。
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            task_folder_name: 任务文件夹名称（如 '1_1'）
        """

            # 从 channel_id 提取通道编号
        if not channel_id.startswith('channel'):
            return
        
        channel_num = int(channel_id.replace('channel', ''))
        
        # 使用 updateMissionLabelByVar 方法更新标签
        if hasattr(self, 'updateMissionLabelByVar'):
            self.updateMissionLabelByVar(channel_num, task_folder_name)
            
            # 删除状态更新逻辑，双击不改变任务状态
        else:
            # 备用方案：直接通过变量名更新
            mission_var_name = f'channel{channel_num}mission'
            if hasattr(self, mission_var_name):
                mission_label = getattr(self, mission_var_name)
                mission_label.setText(str(task_folder_name))
                mission_label.adjustSize()
                
                # 重新定位标签
                panel = self._channel_panels_map.get(channel_id)
                if panel and hasattr(panel, '_positionTaskLabel'):
                    panel._positionTaskLabel()
    
    def _isTaskInUse(self, task_folder_name):
        """
        检查指定任务是否被任何通道使用
        
        Args:
            task_folder_name: 任务文件夹名称（如 "2001115_test"）
            
        Returns:
            bool: 如果任务被使用返回True，否则返回False
        """
        # 检查所有通道（channel1-channel4）
        for channel_num in range(1, 5):
            channel_id = f'channel{channel_num}'
            
            # 方法1：检查通道任务标签
            mission_var_name = f'channel{channel_num}mission'
            if hasattr(self, mission_var_name):
                mission_label = getattr(self, mission_var_name)
                current_task = mission_label.text()
                if current_task == task_folder_name:
                    return True
            
            # 方法2：检查通道面板内存（备用）
            if hasattr(self, '_channel_panels_map'):
                panel = self._channel_panels_map.get(channel_id)
                if panel and hasattr(panel, 'getTaskInfo'):
                    panel_task = panel.getTaskInfo()
                    if panel_task == task_folder_name:
                        return True
        
        return False
    
    def _refreshAllTaskStatus(self):
        """
        刷新任务面板中所有任务的状态显示
        
        委托给 MissionTextStatus 类处理
        """
        if self.mission_text_status:
            self.mission_text_status.refreshAllTaskStatus(self)
    
    def _updateTaskStatus(self, task_folder_name, new_status):
        """
        更新任务面板中指定任务的状态
        
        Args:
            task_folder_name: 任务文件夹名称（如 "21321_312312"）
            new_status: 新状态（如 "已启动"）
        """
        if not hasattr(self, 'mission_panel'):
            return
        
        # 遍历任务面板的所有行，查找匹配的任务
        table = self.mission_panel.table
        for row in range(table.rowCount()):
            # 获取任务编号和任务名称
            task_id_item = table.item(row, 0)  # 任务编号列
            task_name_item = table.item(row, 1)  # 任务名称列
            
            if task_id_item and task_name_item:
                # 构建任务文件夹名称进行匹配
                current_task_folder = f"{task_id_item.text()}_{task_name_item.text()}"
                    
                if current_task_folder == task_folder_name:
                    # 找到匹配的任务，更新状态列（第2列）
                    status_item = table.item(row, 2)
                    if status_item:
                        old_status = status_item.text()
                        status_item.setText(new_status)
                        
                        # 同时更新配置文件中的状态
                        self._updateTaskConfigStatus(task_id_item.text(), new_status)
                        return
    
    # 🔥 已删除 _updateRowColor 和 _updateRowColorForQTableWidgetItem 方法
    # 所有文本颜色管理现在由 MissionTextStatus 类统一处理
    
    def _updateChannelColumnColor(self):
        """
        🔥 根据通道检测状态更新任务面板中通道列和状态列
        
        委托给 MissionTextStatus 类处理所有文本颜色更新
        """
        if self.mission_text_status:
            self.mission_text_status.updateAllChannelColumnColors(self)
    
    def _updateTaskConfigStatus(self, task_id, new_status):
        """
        更新任务配置文件中的状态
        
        Args:
            task_id: 任务编号
            new_status: 新状态
        """
        from database.config import get_project_root
        import yaml
        import os
        
        config_dir = os.path.join(get_project_root(), 'database', 'config', 'mission')
        
        # 查找对应的任务配置文件
        for filename in os.listdir(config_dir):
            if filename.endswith('.yaml') and filename.startswith(f"{task_id}_"):
                config_path = os.path.join(config_dir, filename)
                
                # 读取配置文件
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                
                # 更新状态
                config_data['status'] = new_status
                
                # 写回配置文件
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(config_data, f, allow_unicode=True, default_flow_style=False)
                
                return
    
    def _refreshCurveMissionList(self):
        """
        刷新曲线面板的任务列表
        
        从 mission_result 目录重新扫描任务文件夹并更新下拉框
        """
        # 如果有 curvePanelHandler，调用其 loadMissionFolders 方法
        if hasattr(self, 'curvePanelHandler') and self.curvePanelHandler:
            self.curvePanelHandler.loadMissionFolders()
        # 否则尝试直接调用 curvePanel 的方法
        elif hasattr(self, 'curvePanel') and self.curvePanel:
            # 手动扫描任务文件夹
            import sys
            project_root = get_project_root()
            mission_result_dir = os.path.join(project_root, 'database', 'mission_result')
            
            if os.path.exists(mission_result_dir):
                mission_folders = []
                for item in os.listdir(mission_result_dir):
                    item_path = os.path.join(mission_result_dir, item)
                    if os.path.isdir(item_path):
                        mission_folders.append({
                            'name': item,
                            'path': item_path
                        })
                
                # 按文件夹名称排序
                mission_folders.sort(key=lambda x: x['name'])
                
                # 更新下拉框
                self.curvePanel.updateMissionFolderList(mission_folders)


class MissionTextStatus:
    """
    任务面板文本状态管理器
    
    职责：
    1. 管理任务面板中所有文本的颜色状态
    2. 初始化时所有文本为灰色
    3. 单击选中行时该行文本置为黑色
    4. 启动检测线程时对应任务的状态列置为绿色
    5. 新建任务时文本初始为灰色
    
    颜色规则：
    - 灰色 (128, 128, 128): 未启动任务/默认状态
    - 黑色 (0, 0, 0): 已选中的任务行
    - 绿色 (0, 128, 0): 检测中的任务状态列
    """
    
    # 颜色常量
    COLOR_GRAY = QtGui.QColor(128, 128, 128)    # 灰色：未启动/默认
    COLOR_BLACK = QtGui.QColor(0, 0, 0)         # 黑色：已选中
    COLOR_GREEN = QtGui.QColor(0, 128, 0)       # 绿色：检测中
    
    def __init__(self, mission_panel):
        """
        初始化文本状态管理器
        
        Args:
            mission_panel: MissionPanel实例
        """
        self.mission_panel = mission_panel
        self.table = mission_panel.table
        self.selected_row = -1  # 当前选中的行
    
    def initializeAllRowsGray(self):
        """
        1. 初始化所有任务行文本为灰色
        """
        for row in range(self.table.rowCount()):
            self._setRowColor(row, self.COLOR_GRAY, exclude_columns=[])
    
    def setRowBlackOnSelect(self, row_index):
        """
        2. 单击选中行时该行文本置为黑色
        
        所有"已启动"的任务在被点击后都保持黑色，不会恢复为灰色
        
        Args:
            row_index: 选中的行索引
        """
            # 🔥 不再恢复之前选中行的颜色，所有"已启动"的任务点击后都保持黑色
            # 将新选中的行置为黑色
        self._setRowColor(row_index, self.COLOR_BLACK, exclude_columns=[2])  # 排除状态列
        self.selected_row = row_index
    
    def setStatusColumnGreenOnDetection(self, task_folder_name):
        """
        3. 启动检测线程时对应任务的状态列置为绿色
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
        """

        # 查找对应的任务行
        row_index = self._findTaskRow(task_folder_name)
        if row_index >= 0:
            status_item = self.table.item(row_index, 2)  # 状态列索引为2
            if status_item:
                status_item.setText("检测中")
                status_item.setForeground(self.COLOR_GREEN) 

    
    def resetStatusColumnOnStopDetection(self, task_folder_name):
        """
        停止检测线程时恢复状态列颜色
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
        """
        row_index = self._findTaskRow(task_folder_name)
        if row_index >= 0:
            status_item = self.table.item(row_index, 2)
            if status_item:
                status_item.setText("已启动")
                # 如果是选中行，保持黑色；否则恢复为灰色
                if row_index == self.selected_row:
                    status_item.setForeground(self.COLOR_BLACK)
                else:
                    status_item.setForeground(self.COLOR_GRAY)
    
    def setStatusColumnBlackOnStarted(self, task_folder_name):
        """
        设置状态列为黑色"已启动"
        
        当任务的所有通道都停止检测，但任务仍被分配时调用
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
        """
        row_index = self._findTaskRow(task_folder_name)
        if row_index >= 0:
            status_item = self.table.item(row_index, 2)
            if status_item:
                status_item.setText("已启动")
                status_item.setForeground(self.COLOR_BLACK)
    
    def setChannelColumnGreenOnDetection(self, task_folder_name, channel_num):
        """
        启动检测线程时对应任务的对应通道列置为绿色
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
            channel_num: 通道编号（1-4）
        """
        # 查找对应的任务行
        row_index = self._findTaskRow(task_folder_name)
        if row_index >= 0:
            # 通道列从第3列开始（0:任务编号, 1:任务名称, 2:状态, 3-6:通道1-4）
            col_index = 3 + (channel_num - 1)
            
            channel_item = self.table.item(row_index, col_index)
            if channel_item:
                channel_item.setForeground(self.COLOR_GREEN)
    
    def resetChannelColumnOnStopDetection(self, task_folder_name, channel_num):
        """
        停止检测线程时恢复通道列颜色
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
            channel_num: 通道编号（1-4）
        """
        row_index = self._findTaskRow(task_folder_name)
        if row_index >= 0:
            col_index = 3 + (channel_num - 1)
            channel_item = self.table.item(row_index, col_index)
            if channel_item:
                # 如果是选中行，恢复为黑色；否则恢复为灰色
                if row_index == self.selected_row:
                    channel_item.setForeground(self.COLOR_BLACK)
                else:
                    channel_item.setForeground(self.COLOR_GRAY)
    
    def updateAllChannelColumnColors(self, main_window):
        """
        更新所有任务的通道列和状态列颜色
        
        根据通道检测状态更新任务面板中的通道列和状态列：
        - 获取每个通道当前执行的任务（从channelXmission标签）
        - 更新通道列颜色：检测中为绿色，否则恢复
        - 更新状态列颜色：所有通道都在检测时为绿色
        
        Args:
            main_window: 主窗口实例，用于访问通道任务标签和检测状态
        """
        # 🔥 第一步：收集所有通道当前正在执行的任务
        active_tasks = set()  # 存储正在执行的任务名称
        channel_task_map = {}  # 通道 -> 任务映射
        
        for channel_num in range(1, 5):
            channel_id = f'channel{channel_num}'
            mission_var_name = f'{channel_id}mission'
            
            if hasattr(main_window, mission_var_name):
                mission_label = getattr(main_window, mission_var_name)
                current_task = mission_label.text()
                
                if current_task and current_task != "未分配任务":
                    active_tasks.add(current_task)
                    channel_task_map[channel_id] = current_task
        
        # 🔥 第二步：遍历所有任务行，更新通道列颜色
        for row in range(self.table.rowCount()):
            task_id_item = self.table.item(row, 0)
            task_name_item = self.table.item(row, 1)
            status_item = self.table.item(row, 2)
            
            if not (task_id_item and task_name_item and status_item):
                continue
            
            # 获取任务文件夹名称
            task_folder_name = f"{task_id_item.text()}_{task_name_item.text()}"
            
            # 🔥 处理所有任务的通道列（包括正在执行和未执行的）
            # 获取该任务使用的通道列表（从表格中读取）
            task_channels = []
            for ch_idx in range(1, 5):
                col_idx = 3 + (ch_idx - 1)
                ch_item = self.table.item(row, col_idx)
                if ch_item and ch_item.text():
                    task_channels.append(ch_idx)
            
            # 检查每个通道的检测状态
            for channel_num in task_channels:
                channel_id = f'channel{channel_num}'
                
                # 检查该通道是否正在执行这个任务
                if channel_task_map.get(channel_id) == task_folder_name:
                    # 检查该通道的检测状态
                    detect_var_name = f'{channel_id}detect'
                    if hasattr(main_window, detect_var_name):
                        is_detecting = getattr(main_window, detect_var_name)
                        if is_detecting:
                            # 🔥 设置对应通道列为绿色
                            self.setChannelColumnGreenOnDetection(task_folder_name, channel_num)
                        else:
                            # 🔥 恢复通道列颜色
                            self.resetChannelColumnOnStopDetection(task_folder_name, channel_num)
                else:
                    # 通道未分配此任务，恢复颜色
                    self.resetChannelColumnOnStopDetection(task_folder_name, channel_num)
            
            # 🔥 只处理正在执行的任务（更新状态列）
            if task_folder_name in active_tasks:
                # 检查该任务使用的所有通道是否都在检测
                # 只统计分配给该任务的通道
                assigned_channels_count = 0  # 分配给该任务的通道数
                detecting_channels_count = 0  # 正在检测的通道数
                
                for channel_num in task_channels:
                    channel_id = f'channel{channel_num}'
                    
                    # 检查该通道是否正在执行这个任务
                    if channel_task_map.get(channel_id) == task_folder_name:
                        assigned_channels_count += 1
                        
                        # 检查该通道的检测状态
                        detect_var_name = f'{channel_id}detect'
                        if hasattr(main_window, detect_var_name):
                            is_detecting = getattr(main_window, detect_var_name)
                            if is_detecting:
                                detecting_channels_count += 1
                
                # 🔥 规则：根据检测状态设置状态列颜色
                # 只有当分配给该任务的所有通道都在检测时，才设置为绿色"检测中"
                if assigned_channels_count > 0 and detecting_channels_count == assigned_channels_count:
                    # 所有分配的通道都在检测中 -> 绿色"检测中"
                    self.setStatusColumnGreenOnDetection(task_folder_name)
                elif detecting_channels_count == 0:
                    # 所有通道都未检测，但任务已分配 -> 黑色"已启动"
                    self.setStatusColumnBlackOnStarted(task_folder_name)
                else:
                    # 部分通道在检测 -> 黑色"已启动"（不是所有通道都在检测）
                    self.setStatusColumnBlackOnStarted(task_folder_name)
    
    def initializeNewTaskRowGray(self, row_index):
        """
        4. 新建任务时该行文本初始为灰色
        
        Args:
            row_index: 新建任务的行索引
        """
        try:
            self._setRowColor(row_index, self.COLOR_GRAY, exclude_columns=[])
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def refreshAllTaskStatus(self, main_window):
        """
        刷新任务面板中所有任务的状态和文本颜色
        
        根据当前通道使用情况，动态更新每个任务的状态和颜色：
        - 被通道使用的任务：已启动（灰色，等待用户点击时置黑）
        - 未被通道使用的任务：未启动（灰色）
        
        Args:
            main_window: MainWindow实例，用于检查通道任务状态
        """
        try:
            # 遍历任务面板中的所有行
            for row in range(self.table.rowCount()):
                task_id_item = self.table.item(row, 0)  # 任务编号列
                task_name_item = self.table.item(row, 1)  # 任务名称列
                status_item = self.table.item(row, 2)  # 状态列
                
                if task_id_item and task_name_item and status_item:
                    task_id = task_id_item.text()
                    task_name = task_name_item.text()
                    
                    if task_id and task_name:
                        task_folder_name = f"{task_id}_{task_name}"
                        
                        # 检查任务是否被使用
                        is_in_use = self._isTaskInUse(main_window, task_folder_name)
                        new_status = "已启动" if is_in_use else "未启动"
                        
                        # 更新状态显示
                        current_status = status_item.text()
                        if current_status != new_status:
                            status_item.setText(new_status)
                            
                            # 🔥 更新文本颜色
                            if new_status == "未启动":
                                # 任务未启动时，整行置为灰色（包括状态列）
                                # 如果该行是当前选中行，需要清除选中状态
                                if self.selected_row == row:
                                    self.selected_row = -1
                                self._setRowColor(row, self.COLOR_GRAY, exclude_columns=[])
                            elif new_status == "已启动":
                                # 任务已启动时，不修改颜色，保持原有状态
                                # 如果是当前选中行，保持黑色；如果不是，保持灰色
                                pass
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _isTaskInUse(self, main_window, task_folder_name):
        """
        检查指定任务是否被任何通道使用
        
        Args:
            main_window: MainWindow实例
            task_folder_name: 任务文件夹名称（如 "2001115_test"）
            
        Returns:
            bool: 如果任务被使用返回True，否则返回False
        """
        try:
            # 检查所有通道（channel1-channel4）
            for channel_num in range(1, 5):
                mission_var_name = f'channel{channel_num}mission'
                if hasattr(main_window, mission_var_name):
                    mission_label = getattr(main_window, mission_var_name)
                    current_task = mission_label.text()
                    if current_task == task_folder_name:
                        return True
            
            return False
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _setRowColor(self, row_index, color, exclude_columns=None):
        """
        设置指定行的所有列文本颜色
        
        Args:
            row_index: 行索引
            color: QColor对象
            exclude_columns: 排除的列索引列表（如状态列）
        """
        if exclude_columns is None:
            exclude_columns = []
        
        try:
            for col in range(self.table.columnCount()):
                # 跳过排除的列
                if col in exclude_columns:
                    continue
                
                # 跳过曲线按钮列
                if hasattr(self.mission_panel, 'CURVE_BUTTON_COLUMN'):
                    if col == self.mission_panel.CURVE_BUTTON_COLUMN:
                        continue
                
                item = self.table.item(row_index, col)
                if item:
                    item.setForeground(color)
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _findTaskRow(self, task_folder_name):
        """
        根据任务文件夹名称查找对应的行索引
        
        Args:
            task_folder_name: 任务文件夹名称（如 "1_1"）
            
        Returns:
            int: 行索引，未找到返回-1
        """
        try:
            for row in range(self.table.rowCount()):
                task_id_item = self.table.item(row, 0)
                task_name_item = self.table.item(row, 1)
                
                if task_id_item and task_name_item:
                    current_task_name = f"{task_id_item.text()}_{task_name_item.text()}"
                    if current_task_name == task_folder_name:
                        return row
            return -1
        except Exception as e:
            import traceback
            traceback.print_exc()
            return -1