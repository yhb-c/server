# -*- coding: utf-8 -*-

"""
设置相关的信号槽处理方法

包含所有与设置和配置相关的回调函数
"""

from qtpy import QtWidgets


class SettingsHandler:
    """
    设置处理器 (Mixin类)
    
    处理设置相关的所有操作：
    - openSettings: 打开通用设置
    - openModelSettings: 打开模型设置
    - openChannelManager: 打开通道管理
    - openMissionManager: 打开任务管理
    - showAbout: 显示关于对话框
    - showDocumentation: 显示帮助文档
    """
    
    def openSettings(self):
        """打开通用设置对话框"""
        from ..widgets import GeneralSettingDialog
        
        dialog = GeneralSettingDialog(self, self._config)
        if dialog.exec_():
            new_config = dialog.getConfig()
            self._config.update(new_config)
            self.statusBar().showMessage(self.tr("设置已更新"))
            
            # TODO: 应用新设置
            # self._applyConfig(new_config)
    
    def openModelSettings(self, channel_id=None):
        """
        打开模型设置对话框
        
        Args:
            channel_id: 指定通道ID（如 'channel1'），如果为None则尝试获取当前选中的通道
        """
        # 如果没有指定channel_id，尝试获取当前选中的通道
        if channel_id is None:
            channel_id = self._getCurrentSelectedChannel()
            if channel_id:
                print(f"[Settings] 检测到当前选中通道: {channel_id}")
            else:
                print(f"[Settings] 未检测到选中通道，将使用全局配置")
        
        # 使用新的 ModelSettingHandler 中的方法
        if hasattr(self, 'showModelSettingDialog'):
            self.showModelSettingDialog(channel_id)
        else:
            # 备用方案：直接创建对话框
            from ..widgets.videopage.modelsetting_dialogue import ModelSettingDialog
            
            model_config = self._config.get('model', {})
            dialog = ModelSettingDialog(self, model_config, channel_id)
            if dialog.exec_():
                new_model_config = dialog.getModelConfig()
                self._config['model'] = new_model_config
                self.statusBar().showMessage(self.tr("模型设置已更新"))
    
    def _getCurrentSelectedChannel(self):
        """
        获取当前选中的通道ID
        
        Returns:
            str or None: 通道ID（如 'channel1'），如果没有选中则返回None
        """
        # 方法1: 从通道面板映射获取（查找可见且获得焦点的面板）
        if hasattr(self, '_channel_panels_map'):
            for channel_id, panel in self._channel_panels_map.items():
                if panel.isVisible() and panel.hasFocus():
                    return channel_id
        
        # 方法2: 从可见的通道面板获取第一个
        if hasattr(self, '_channel_panels_map'):
            for channel_id, panel in self._channel_panels_map.items():
                if panel.isVisible():
                    return channel_id
        
        # 方法3: 从已连接的通道获取第一个
        if hasattr(self, '_channel_captures'):
            for channel_id in self._channel_captures.keys():
                return channel_id
        
        return None
    
    def openChannelManager(self):
        """打开通道管理"""
        # 显示通道面板（如果隐藏）
        if not self.channelPanel.isVisible():
            self.channelPanel.show()
        
        # 将焦点移到通道面板
        self.channelPanel.raise_()
        self.channelPanel.activateWindow()
        
        self.statusBar().showMessage(self.tr("已打开通道管理面板"))
    
    def openMissionManager(self):
        """打开任务管理"""
        # 显示任务面板（如果隐藏）
        if not self.missionPanel.isVisible():
            self.missionPanel.show()
        
        # 将焦点移到任务面板
        self.missionPanel.raise_()
        self.missionPanel.activateWindow()
        
        self.statusBar().showMessage(self.tr("已打开任务管理面板"))
    
    def showAbout(self):
        """显示关于对话框"""
        try:
            from widgets.style_manager import DialogManager
        except ImportError:
            DialogManager = None
        
        message = (
            "<h2>帕特智能油液位检测</h2>"
            "<p>版本: 1.0</p>"
        )
        
        if DialogManager:
            DialogManager.show_about(self, "关于", message)
        else:
            # 降级方案：使用标准对话框
            QtWidgets.QMessageBox.about(self, "关于", message)
    
    def showDocumentation(self):
        """显示帮助文档 - 打开用户手册"""
        import os
        import sys
        
        try:
            # 🔥 获取exe所在目录（兼容开发环境和打包后环境）
            if getattr(sys, 'frozen', False):
                # 打包后的exe环境：sys.executable 是 exe 文件路径
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                project_root = exe_dir
            else:
                # 开发环境：使用 __file__ 获取项目根目录
                current_file = os.path.abspath(__file__)
                project_root = os.path.dirname(os.path.dirname(current_file))
            
            # 用户手册文件路径
            manual_path = os.path.join(project_root, '用户手册.pdf')
            
            if os.path.exists(manual_path):
                # 使用系统默认应用打开文档
                import subprocess
                import platform
                
                if platform.system() == 'Windows':
                    os.startfile(manual_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', manual_path])
                else:  # Linux
                    subprocess.Popen(['xdg-open', manual_path])
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("提示"),
                    self.tr(f"未找到用户手册\n\n请在项目根目录放置 '用户手册.pdf' 文件")
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("错误"),
                self.tr(f"打开用户手册失败:\n{str(e)}")
            )
    
    def _applyConfig(self, config):
        """应用配置（待实现）"""
        # 根据配置更新UI和行为
        # - 语言切换
        # - 主题切换
        # - 性能设置
        pass
    
    def _reloadModel(self, model_config):
        """重新加载模型（待实现）"""
        # 卸载旧模型，加载新模型
        pass

