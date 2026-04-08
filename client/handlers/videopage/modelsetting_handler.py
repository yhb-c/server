# -*- coding: utf-8 -*-

"""
模型设置对话框相关的信号槽处理方法

包含所有与模型设置相关的回调函数
"""

import os
import yaml
from qtpy import QtCore
from qtpy import QtWidgets

# 导入远程配置管理器
try:
    from ...utils.config import RemoteConfigManager
except ImportError:
    try:
        from utils.config import RemoteConfigManager
    except ImportError:
        RemoteConfigManager = None


class ModelSettingHandler:
    """
    模型设置处理器 (Mixin类)
    
    处理模型设置对话框相关的功能
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 存储从模型管理面板同步的模型信息
        self._available_models_from_panel = []
        # 初始化远程配置管理器
        self._remote_config = RemoteConfigManager()
    
    def showModelSettingDialog(self, channel_id=None):
        """
        显示模型设置对话框
        
        Args:
            channel_id: 指定通道ID（如 'channel1'），如果为None则使用全局配置
        """
        from widgets.videopage.modelsetting_dialogue import ModelSettingDialog
        
        # 加载当前模型配置（包含通道特定的model_path）
        model_config, config_source = self._loadModelConfig(channel_id)
        
        # 创建并显示对话框
        dialog = ModelSettingDialog(self, model_config, channel_id)
        
        # 连接信号
        dialog.refreshModelListRequested.connect(lambda: self._handleRefreshModelList(dialog))
        dialog.modelSelected.connect(self._handleModelSelected)
        dialog.browseModelRequested.connect(lambda: self._handleBrowseModel(dialog))
        dialog.browseConfigRequested.connect(lambda: self._handleBrowseConfig(dialog))
        dialog.loadModelRequested.connect(self._handleLoadModel)
        dialog.readModelDescriptionRequested.connect(lambda path: self._handleReadModelDescription(dialog, path))
        
        # 初始加载模型列表
        self._handleRefreshModelList(dialog)

        # 确保当前模型栏立即显示配置文件中的模型路径
        initial_model_path = model_config.get('model_path', '') if model_config else ''
        
        if initial_model_path:
            dialog.updateCurrentModelDisplay(initial_model_path)
            # 🔥 关键修复：信号连接后立即读取模型描述
            # 使用 QTimer 延迟调用，确保 UI 已初始化
            from qtpy.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._handleReadModelDescription(dialog, initial_model_path))
        else:
            dialog.updateCurrentModelDisplay('')
        
        mission_result = dialog.exec_()
        
        if mission_result == QtWidgets.QDialog.Accepted:
            # 获取用户设置的模型参数
            new_config = dialog.getModelConfig()
            
            # 保存模型配置
            if self._saveModelConfig(new_config, channel_id):
                channel_name = f" ({channel_id})" if channel_id else ""
                self.statusBar().showMessage(
                    self.tr("模型配置已保存{}").format(channel_name)
                )
                print(f"模型配置已保存{channel_name}: {new_config}")
            else:
                self.statusBar().showMessage(
                    self.tr("模型配置保存失败")
                )
        else:
            print("模型设置已取消")
            self.statusBar().showMessage(self.tr("模型设置已取消"))
    
    def _loadModelConfig(self, channel_id=None):
        """
        从服务端配置文件加载模型配置
        
        优先级：
        1. channel_config.yaml 中的通道特定配置
        2. default_config.yaml 中的通道特定模型路径
        3. default_config.yaml 中的全局模型配置
        
        Args:
            channel_id: 通道ID（如 'channel1'），如果为None则使用全局配置
        
        Returns:
            tuple: (模型配置数据, 配置来源描述)
        """
        try:
            # 1. 从服务端加载通道配置
            channel_config = self._remote_config.load_channel_config()
            
            # 2. 从服务端加载默认配置
            default_config = self._remote_config.load_default_config()
            
            # 如果指定了通道ID，则从通道配置中获取模型配置
            if channel_id:
                # 优先从 channel_config.yaml 获取通道配置
                if channel_id in channel_config and 'model' in channel_config[channel_id]:
                    model_config = channel_config[channel_id]['model'].copy()
                    model_path = model_config.get('model_path', '')
                    config_source = f"channel_config.yaml → {channel_id} → model"
                    self.logger.debug(f"[channel_config.yaml] 加载通道 {channel_id} 的模型配置: {model_path}")
                else:
                    # 从 default_config.yaml 获取通道特定的模型路径
                    channel_model_key = f"{channel_id}_model_path"
                    channel_model_path = default_config.get(channel_model_key, '')
                    
                    if channel_model_path:
                        # 合并 default_config 中的全局模型配置
                        model_config = default_config.get('model', {}).copy()
                        model_config['model_path'] = channel_model_path
                        
                        config_source = f"default_config.yaml → {channel_model_key} + model (全局参数)"
                    else:
                        # 使用全局模型配置
                        model_config = default_config.get('model', {}).copy()
                        config_source = f"default_config.yaml → model (未找到 {channel_id} 的特定配置)"
                        self.logger.debug(f"[Handler] 未找到通道 {channel_id} 的特定配置，使用全局配置")
                        print(f"  model_config['model_path'] = {model_config.get('model_path', 'None')}")
                
                self.logger.debug(f"[Handler] 返回配置: model_path = {model_config.get('model_path', 'None')}")
                return model_config, config_source
            else:
                # 使用全局配置
                # 优先从 channel_config.yaml 获取
                if 'model' in channel_config:
                    model_config = channel_config['model'].copy()
                    config_source = "channel_config.yaml → model"
                    self.logger.debug(f"[Handler] 加载全局模型配置 (channel_config.yaml)")
                else:
                    # 从 default_config.yaml 获取
                    model_config = default_config.get('model', {}).copy()
                    config_source = "default_config.yaml → model"
                    self.logger.debug(f"[Handler] 加载全局模型配置 (default_config.yaml)")
                
                self.logger.debug(f"[Handler] 返回全局配置: model_path = {model_config.get('model_path', 'None')}")
                return model_config, config_source
        
        except Exception as e:
            print(f"加载模型配置失败: {e}")
            import traceback
            traceback.print_exc()
            return {}, "加载失败"
    
    def _getProjectRoot(self):
        """
        获取项目根目录
        
        Returns:
            str: 项目根目录的绝对路径
        """
        # __file__ 是 handlers/videopage/modelsetting_handler.py
        # 向上三级到项目根目录
        return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    def _resolveModelPath(self, model_path, project_root):
        """
        解析模型路径（支持相对路径和绝对路径）
        
        Args:
            model_path: 模型路径（可能是相对路径或绝对路径）
            project_root: 项目根目录
        
        Returns:
            str: 绝对路径
        """
        if not model_path:
            return ''
        
        # 如果已经是绝对路径，直接返回
        if os.path.isabs(model_path):
            return model_path
        
        # 相对路径，基于项目根目录解析
        absolute_path = os.path.join(project_root, model_path)
        absolute_path = os.path.normpath(absolute_path)
        
        return absolute_path
    
    def _saveModelConfig(self, model_config, channel_id=None):
        """
        保存模型配置到服务端配置文件
        
        Args:
            model_config: 模型配置字典
            channel_id: 通道ID（如 'channel1'），如果为None则保存到全局配置
        
        Returns:
            bool: 保存是否成功
        """
        try:
            self.logger.debug(f"[DEBUG] _saveModelConfig 被调用，channel_id={channel_id}")
            self.logger.debug(f"[DEBUG] model_config={model_config}")
            
            # 使用远程配置管理器
            channel_config = self._remote_config.load_channel_config()
            
            if not channel_config:
                self.logger.debug(f"[DEBUG] 无法从服务端加载通道配置")
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("保存失败"),
                    self.tr("无法从服务端加载通道配置")
                )
                return False
            
            self.logger.debug(f"[DEBUG] 成功从服务端加载通道配置")

            # 如果指定了通道ID，则保存到对应通道的model部分
            if channel_id:
                # 标准化通道ID格式为字符串 'channelN'
                if isinstance(channel_id, int):
                    channel_key = f'channel{channel_id}'
                elif isinstance(channel_id, str) and not channel_id.startswith('channel'):
                    channel_key = f'channel{channel_id}'
                else:
                    channel_key = channel_id

                if channel_key not in channel_config:
                    channel_config[channel_key] = {}

                if 'model' not in channel_config[channel_key]:
                    channel_config[channel_key]['model'] = {}

                # 更新通道的model配置
                channel_config[channel_key]['model'].update(model_config)

                model_path = model_config.get('model_path', '')
                self.logger.debug(f"[DEBUG] 保存模型配置到通道 {channel_key}")
                self.logger.debug(f"[DEBUG]   - model_path: {model_path}")
            else:
                # 保存到全局配置
                if 'model' not in channel_config:
                    channel_config['model'] = {}
                channel_config['model'].update(model_config)
                self.logger.debug(f"[DEBUG] 保存模型配置到全局配置")
            
            # 保存回服务端配置文件
            success = self._remote_config.save_channel_config(channel_config)
            
            if success:
                self.logger.debug(f"[DEBUG] 模型配置已成功保存到服务端")
                return True
            else:
                self.logger.debug(f"[DEBUG] 保存模型配置到服务端失败")
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("保存失败"),
                    self.tr("保存模型配置到服务端失败")
                )
                return False
        
        except Exception as e:
            self.logger.debug(f"[DEBUG] 保存模型配置异常: {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("保存失败"),
                self.tr(f"保存模型配置失败: {str(e)}")
            )
            return False
    
    def _handleRefreshModelList(self, dialog):
        """处理刷新模型列表请求 - 从服务端扫描模型"""
        try:
            # 获取服务端模型基础路径
            model_base_path = self._getModelBasePath()
            print(f"扫描服务端模型目录: {model_base_path}")
            
            model_list = []
            
            # 通过SSH从服务端扫描模型文件
            model_list = self._scanModelsFromServer(model_base_path)
            
            print(f"总共找到 {len(model_list)} 个服务端模型")
            
            # 设置到对话框
            dialog.setModelList(model_list)
            
        except Exception as e:
            print(f"刷新服务端模型列表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _getModelBasePath(self):
        """
        获取模型基础路径 - 从服务端配置获取
        
        优先级：
        1. channel_config.yaml 中的 model_base_path
        2. default_config.yaml 中的 model_base_path
        3. 服务端默认路径
        
        Returns:
            str: 服务端模型基础路径
        """
        try:
            # 1. 尝试从服务端 channel_config.yaml 读取
            channel_config = self._remote_config.load_channel_config()
            model_config = channel_config.get('model', {})
            model_base_path = model_config.get('model_base_path', '')
            
            if model_base_path:
                self.logger.debug(f"[channel_config.yaml] 使用服务端模型基础路径: {model_base_path}")
                return model_base_path
            
            # 2. 尝试从服务端 default_config.yaml 读取
            default_config = self._remote_config.load_default_config()
            model_base_path = default_config.get('model_base_path', '')
            if model_base_path:
                self.logger.debug(f"[default_config.yaml] 使用服务端模型基础路径: {model_base_path}")
                return model_base_path
            
            # 3. 使用服务端默认路径
            default_path = "/home/lqj/liquid/server/database/model/detection_model"
            print(f"使用服务端默认模型路径: {default_path}")
            return default_path
            
        except Exception as e:
            print(f"获取服务端模型基础路径失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 出错时返回服务端默认路径
            return "/home/lqj/liquid/server/database/model/detection_model"
    
    
    def _handleBrowseModel(self, dialog):
        """处理浏览模型文件请求"""
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            dialog,
            dialog.tr("选择模型文件"),
            "",
            dialog.tr("模型文件 (*.pt *.onnx *.pth *.weights);;所有文件 (*.*)")
        )
        if fileName:
            dialog.setModelPath(fileName)
    
    def _handleBrowseConfig(self, dialog):
        """处理浏览配置文件请求"""
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            dialog,
            dialog.tr("选择配置文件"),
            "",
            dialog.tr("配置文件 (*.yaml *.yml *.cfg);;所有文件 (*.*)")
        )
        if fileName:
            dialog.setConfigPath(fileName)
    
    def _handleLoadModel(self, model_path):
        """处理加载模型请求"""
        print(f"请求加载模型: {model_path}")
        
        # 这里应该实际加载模型
        # 暂时显示加载中对话框
        success = True  # 模拟成功
        message = "模型加载功能待实现"
        
        # 通过信号发送结果给对话框
        sender = self.sender()
        if hasattr(sender, 'showLoadModelmission_result'):
            sender.showLoadModelmission_result(success, message)
    
    def _handleReadModelDescription(self, dialog, model_path):
        """处理读取模型描述请求 - 直接读取同文件夹内的txt文件"""
        try:
            import os
            
            if not model_path:
                dialog.setModelDescription("模型路径为空")
                return
            
            model_dir = os.path.dirname(model_path)
            
            if not os.path.exists(model_dir):
                dialog.setModelDescription("模型文件夹不存在")
                return
            
            # 直接查找文件夹下的任意txt文件
            for file in os.listdir(model_dir):
                if file.endswith('.txt'):
                    txt_path = os.path.join(model_dir, file)
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                dialog.setModelDescription(content)
                                return
                    except Exception as e:
                        continue
            
            dialog.setModelDescription("未找到模型描述文件（txt）")
            
        except Exception as e:
            dialog.setModelDescription(f"读取模型描述失败: {str(e)}")
    
    def _handleModelSelected(self, model_path):
        """处理模型选择"""
        print(f"模型已选择: {model_path}")
        
        # 更新当前模型显示（通过对话框的方法）
        sender = self.sender()
        if hasattr(sender, 'updateCurrentModelDisplay'):
            sender.updateCurrentModelDisplay(model_path)
    
    def onModelChanged(self, model_id, model_name):
        """
        模型切换
        
        Args:
            model_id: 模型ID
            model_name: 模型名称
        """
        print(f"切换模型: {model_name} (ID: {model_id})")
        
        self.statusBar().showMessage(
            self.tr("当前模型: {}").format(model_name)
        )
        
        # TODO: 实现模型切换后的操作
        # 例如：卸载旧模型、加载新模型等
    
    def onModelLoaded(self, model_id):
        """
        模型加载成功
        
        Args:
            model_id: 模型ID
        """
        print(f"模型加载成功: {model_id}")
        
        self.statusBar().showMessage(
            self.tr("模型已加载: {}").format(model_id)
        )
    
    def onModelUnloaded(self, model_id):
        """
        模型卸载
        
        Args:
            model_id: 模型ID
        """
        print(f"模型已卸载: {model_id}")
        
        self.statusBar().showMessage(
            self.tr("模型已卸载: {}").format(model_id)
        )
    
    def updateAvailableModels(self, models_list):
        """
        更新可用模型列表（从模型管理面板同步）
        
        Args:
            models_list: 模型信息列表
        """
        self._available_models_from_panel = models_list
        self.logger.debug(f"[MODEL_SETTINGS] 已接收 {len(models_list)} 个模型信息")
        
        # 如果有正在显示的模型设置对话框，更新其模型列表
        self._updateActiveDialogModelList()
    
    def _updateActiveDialogModelList(self):
        """更新当前活动的模型设置对话框的模型列表"""
        # 这个方法将在对话框显示时被调用
        pass
    
    def getAvailableModelsFromPanel(self):
        """
        获取从模型管理面板同步的模型列表
        
        Returns:
            list: 模型信息列表
        """
        return self._available_models_from_panel
    
    def _scanModelsFromServer(self, base_path):
        """
        通过SSH从服务端扫描模型文件
        
        Args:
            base_path: 服务端模型基础路径
            
        Returns:
            list: 模型文件信息列表
        """
        try:
            ssh_manager = self._remote_config._get_ssh_manager()
            if not ssh_manager:
                print("SSH连接不可用，无法扫描服务端模型")
                return []
            
            # 使用find命令递归查找.dat和.pt文件
            find_cmd = f"find {base_path} -type f \\( -name '*.dat' -o -name '*.pt' \\) 2>/dev/null"
            result = ssh_manager.execute_remote_command(find_cmd)
            
            if not result['success']:
                print(f"扫描服务端模型失败: {result.get('stderr', '未知错误')}")
                return []
            
            model_files = result['stdout'].strip().split('\n') if result['stdout'].strip() else []
            model_list = []
            
            for file_path in model_files:
                if not file_path:
                    continue
                    
                try:
                    # 获取文件信息
                    stat_cmd = f"stat -c '%s %Y' '{file_path}'"
                    stat_result = ssh_manager.execute_remote_command(stat_cmd)
                    
                    if stat_result['success']:
                        stat_info = stat_result['stdout'].strip().split()
                        file_size = int(stat_info[0]) if len(stat_info) > 0 else 0
                        file_mtime = int(stat_info[1]) if len(stat_info) > 1 else 0
                    else:
                        file_size = 0
                        file_mtime = 0
                    
                    # 构建模型信息
                    model_info = {
                        'name': os.path.basename(file_path),
                        'path': file_path,
                        'type': self._getModelTypeFromExtension(file_path),
                        'size': self._formatFileSize(file_size),
                        'size_bytes': file_size,
                        'modified_time': file_mtime,
                        'relative_path': os.path.relpath(file_path, base_path) if file_path.startswith(base_path) else file_path
                    }
                    
                    model_list.append(model_info)
                    print(f"找到服务端模型: {model_info['name']} ({model_info['size']})")
                    
                except Exception as e:
                    print(f"处理服务端模型文件 {file_path} 时出错: {e}")
                    continue
            
            # 按名称排序
            model_list.sort(key=lambda x: x['name'].lower())
            return model_list
            
        except Exception as e:
            print(f"扫描服务端模型目录失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _formatFileSize(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _scanModelsRecursively(self, base_path):
        """
        递归扫描模型文件（增强版，结合模型管理面板的信息）
        
        Args:
            base_path: 扫描的基础路径
            
        Returns:
            list: 模型信息列表
        """
        import os
        from pathlib import Path
        
        model_list = []
        
        print(f"\n开始递归扫描模型目录...")
        print(f"基础路径: {base_path}")
        print(f"路径是否存在: {os.path.exists(base_path)}")
        
        # 首先添加从模型管理面板同步的模型
        print(f"从模型管理面板添加 {len(self._available_models_from_panel)} 个模型")
        for panel_model in self._available_models_from_panel:
            model_info = {
                'name': panel_model['display_name'],
                'full_path': panel_model['path'],
                'rel_path': os.path.relpath(panel_model['path'], base_path) if os.path.exists(panel_model['path']) else panel_model['path'],
                'folder': os.path.dirname(panel_model['path']),
                'type': panel_model['type'],
                'size': panel_model['size'],
                'description': panel_model['description'],
                'confidence': panel_model['confidence'],
                'iou': panel_model['iou'],
                'input_size': panel_model['input_size'],
                'classes': panel_model['classes'],
                'device': panel_model['device'],
                'source': 'model_panel'  # 标记来源
            }
            model_list.append(model_info)
            print(f"  [模型管理面板] {panel_model['display_name']}")
        
        # 然后扫描文件系统中的其他模型（避免重复）
        panel_paths = {model['path'] for model in self._available_models_from_panel}
        
        print(f"\n开始扫描文件系统...")
        try:
            if not os.path.exists(base_path):
                print(f"错误：路径不存在！")
                return model_list
            
            if not os.path.isdir(base_path):
                print(f"错误：路径不是目录！")
                return model_list
            
            # 递归扫描所有子目录
            for root, dirs, files in os.walk(base_path):
                print(f"\n扫描目录: {root}")
                print(f"  子文件夹: {dirs}")
                print(f"  文件数量: {len(files)}")
                
                # 统计模型文件
                model_files = [f for f in files if f.endswith(('.dat', '.pt', '.pth', '.onnx'))]
                if model_files:
                    print(f"  找到 {len(model_files)} 个模型文件: {model_files}")
                
                for file in files:
                    if file.endswith(('.dat', '.pt', '.pth', '.onnx')):
                        full_path = os.path.join(root, file)
                        
                        # 跳过已经从模型管理面板添加的模型
                        if full_path in panel_paths:
                            print(f"  跳过（已在模型管理面板中）: {file}")
                            continue
                        
                        rel_path = os.path.relpath(full_path, base_path)
                        folder_name = os.path.basename(root)
                        
                        model_info = {
                            'name': f"{folder_name}-{os.path.splitext(file)[0]}",
                            'full_path': full_path,
                            'rel_path': rel_path,
                            'folder': folder_name,
                            'type': self._getModelTypeFromExtension(file),
                            'size': self._getFileSize(full_path),
                            'description': f"文件系统扫描发现的模型\n路径: {rel_path}",
                            'confidence': 0.5,
                            'iou': 0.45,
                            'input_size': '640x640',
                            'classes': '未知',
                            'device': 'CPU',
                            'source': 'file_system'  # 标记来源
                        }
                        model_list.append(model_info)
                        print(f"   添加模型: {rel_path} ({model_info['size']})")
                        
        except Exception as e:
            print(f"扫描文件系统模型失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 按来源和名称排序（模型管理面板的模型优先）
        model_list.sort(key=lambda x: (x['source'] != 'model_panel', x['name']))
        
        print(f"\n扫描完成，共找到 {len(model_list)} 个模型文件")
        return model_list
    
    def _getModelTypeFromExtension(self, filename):
        """根据文件扩展名获取模型类型"""
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            '.dat': '自定义模型(DAT)',
            '.pt': 'PyTorch模型(PT)',
            '.pth': 'PyTorch模型(PTH)',
            '.onnx': 'ONNX模型'
        }
        return type_map.get(ext, '未知类型')
    
    def _getFileSize(self, file_path):
        """获取文件大小的可读格式"""
        try:
            size = os.path.getsize(file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "未知大小"

