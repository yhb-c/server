# -*- coding: utf-8 -*-

"""
视图菜单相关的信号槽处理方法

包含所有与视图控制相关的回调函数
"""

from qtpy import QtWidgets

# 导入编译模式检查函数
try:
    from client.config import is_debug_mode
except ImportError:
    def is_debug_mode(config=None):
        return False


class ViewHandler:
    """
    视图处理器 (Mixin类)
    
    处理视图菜单的所有操作：
    - toggleToolBar: 切换工具栏显示
    - toggleStatusBar: 切换状态栏显示
    - toggleFullScreen: 切换全屏模式
    - toggleVideoPageMode: 切换视频页面模式（实时检测 <-> 曲线分析）
    """
    
    def __init__(self, *args, **kwargs):
        """初始化视图处理器"""
        super().__init__(*args, **kwargs)
        # 曲线分析模式状态（False=默认布局, True=曲线模式布局）
        self._is_curve_mode_active = False
    
    @property
    def is_curve_mode_active(self):
        """获取曲线模式是否激活"""
        return self._is_curve_mode_active
    
    @is_curve_mode_active.setter
    def is_curve_mode_active(self, value):
        """设置曲线模式状态"""
        self._is_curve_mode_active = value
    
    def _getCurveMissionPath(self):
        """从 curvemission 下拉框获取当前任务路径
        
        Returns:
            str: 任务文件夹完整路径，如果未选择则返回None
        """
        if not hasattr(self, 'curvemission'):
            return None
        
        mission_name = self.curvemission.currentText()
        if not mission_name or mission_name == "请选择任务":
            return None
        
        # 构建完整路径
        import os
        import sys
        
        # 动态获取数据目录（与storage_thread和curvepanel_handler保持一致）
        if getattr(sys, 'frozen', False):
            # 打包后：使用 sys._MEIPASS 指向 _internal 目录
            data_root = sys._MEIPASS
        else:
            try:
                from client.config import get_project_root
                data_root = get_project_root()
            except ImportError:
                data_root = os.getcwd()
        
        mission_path = os.path.join(data_root, 'database', 'mission_result', mission_name)
        
        return mission_path if os.path.exists(mission_path) else None
    
    def toggleToolBar(self):
        """切换工具栏显示"""
        # TODO: 当创建工具栏后实现
        # if hasattr(self, 'toolbar'):
        #     if self.toolbar.isVisible():
        #         self.toolbar.hide()
        #         self.menubar.checkAction('show_toolbar', False)
        #     else:
        #         self.toolbar.show()
        #         self.menubar.checkAction('show_toolbar', True)
        
        self.statusBar().showMessage(self.tr("工具栏切换功能待实现"))
    
    def toggleStatusBar(self):
        """切换状态栏显示"""
        if self.statusBar().isVisible():
            self.statusBar().hide()
            self.menubar.checkAction('show_statusbar', False)
        else:
            self.statusBar().show()
            self.menubar.checkAction('show_statusbar', True)
            self.statusBar().showMessage(self.tr("状态栏已显示"))
    
    def toggleFullScreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
            self.menubar.checkAction('fullscreen', False)
            self.statusBar().showMessage(self.tr("已退出全屏"))
        else:
            self.showFullScreen()
            self.menubar.checkAction('fullscreen', True)
            self.statusBar().showMessage(self.tr("已进入全屏"))
    
    def toggleVideoPageMode(self):
        """切换视频页面的布局模式（默认模式 <-> 曲线模式）"""
        if not hasattr(self, '_video_layout_mode'):
            return
        
        if self._video_layout_mode == 0:
            # 切换到曲线模式
            self._switchToCurveLayout()
        else:
            # 切换回默认模式
            self._switchToDefaultLayout()
    
    def _getCurrentDetectionState(self):
        """
        获取当前检测线程的运行状态（基于curvemission使用的通道）
        
        Returns:
            bool: True=curvemission使用的通道中有任意一个检测线程正在运行, False=全部停止
        """
        
        
        if not hasattr(self, 'thread_manager'):
            return False
        
        # 获取当前curvemission选择的任务
        if not hasattr(self, 'curvemission'):
            return False
        
        mission_name = self.curvemission.currentText()
        
        if not mission_name or mission_name == "请选择任务":
            return False
        
        # 第一层判断：检查任务状态
        mission_status = self._getMissionStatus(mission_name)
        
        if mission_status == "未启动":
            return False
        
        # 获取该任务使用的通道列表
        task_channels = self._getTaskChannels(mission_name)
        
        if not task_channels:
            return False
        
        # 将通道名称转换为通道ID（通道1 -> channel1）
        channel_ids = []
        for channel_name in task_channels:
            if '通道' in channel_name:
                # 提取数字部分
                channel_num = channel_name.replace('通道', '')
                channel_ids.append(f'channel{channel_num}')
        
        
        # 检查这些通道的channel_detect_status状态
        # 只要有任意一个通道的channel_detect_status为True，就返回True
        for channel_id in channel_ids:
            context = self.thread_manager.get_channel_context(channel_id)
            if context:
                channel_detect_status = context.channel_detect_status
                # 确保 channel_detect_status 是布尔值 True
                if channel_detect_status is True or channel_detect_status == True:
                    return True
            else:
                print(f"  [WARN] {channel_id}: 没有context")
        
        # 所有通道的channel_detect_status都为False
 
        return False
    
    def _getMissionStatus(self, mission_name):
        """
        获取任务的实际运行状态（检查是否有通道正在使用该任务）
        
        Args:
            mission_name: 任务名称
            
        Returns:
            str: 任务状态，"已启动" 或 "未启动"
        """
        try:
            # 检查任务是否被任何通道使用
            # MissionPanelHandler 是通过 Mixin 继承的，所以直接用 self._isTaskInUse
            if hasattr(self, '_isTaskInUse'):
                is_in_use = self._isTaskInUse(mission_name)
                status = "已启动" if is_in_use else "未启动"

                return status
            else:
                # 如果没有 _isTaskInUse 方法，默认返回"未启动"
                print(f"  [WARN] [任务状态检查] 没有_isTaskInUse方法，默认返回'未启动'")
                return "未启动"
            
        except Exception as e:
            print(f"[ERROR] [任务状态] 获取失败: {e}")
            import traceback
            traceback.print_exc()
            return "未启动"
    
    def _switchToCurveLayout(self):
        """切换到曲线模式：根据检测线程状态选择合适的子布局"""
        # 先设置模式为曲线模式（_video_layout_mode = 1），确保后续逻辑能正确判断
        self._video_layout_mode = 1
        
        # 检查检测线程状态，决定使用哪种子布局
        detection_running = self._getCurrentDetectionState()
        
        # 根据检测线程状态切换到对应的曲线子布局
        self._switchCurveSubLayout(detection_running)
        
        # 根据检测线程状态选择通道容器
        if detection_running:
            # 同步布局：使用通道面板容器（ChannelPanel）
            target_channel_widgets = self.channel_widgets_for_curve
            layout_description = "同步布局"
        else:
            # 历史回放布局：使用历史视频面板容器（HistoryVideoPanel）
            target_channel_widgets = self.history_channel_widgets_for_curve
            layout_description = "历史回放布局"
        
        # 根据检测线程状态选择要显示的面板类型
        if detection_running:
            # 同步布局：使用通道面板（ChannelPanel）
            panels_to_use = self.channelPanels
        else:
            # 历史回放布局：使用历史视频面板（HistoryVideoPanel）
            if hasattr(self, 'historyVideoPanels'):
                panels_to_use = self.historyVideoPanels
            else:
                panels_to_use = self.channelPanels
        
        # 先隐藏所有wrapper
        for wrapper in target_channel_widgets:
            wrapper.setVisible(False)
        
        # 移动面板到对应的容器
        for i, panel in enumerate(panels_to_use):
            if i < len(target_channel_widgets):
                wrapper = target_channel_widgets[i]
                
                # 先从当前父级中移除面板
                current_parent = panel.parent()
                if current_parent and current_parent != wrapper:
                    current_parent_layout = current_parent.layout()
                    if current_parent_layout:
                        current_parent_layout.removeWidget(panel)
                
                # 将面板添加到wrapper的布局中
                wrapper_layout = wrapper.layout()
                if wrapper_layout:
                    # 检查是否已经在布局中
                    if panel.parent() != wrapper:
                        panel.setParent(wrapper)
                        wrapper_layout.addWidget(panel)
                else:
                    # 如果没有布局，使用绝对定位
                    panel.setParent(wrapper)
                    panel.move(0, 0)
                
                # 先显示wrapper，再显示面板（顺序很重要！）
                wrapper.setVisible(True)
                panel.show()
                
                # 强制更新布局
                wrapper.updateGeometry()
                panel.updateGeometry()
        
        # 切换到曲线模式主布局（_video_layout_mode已在方法开头设置为1）
        self.videoLayoutStack.setCurrentIndex(1)
        
        # 更新状态栏信息
        status_message = f"曲线模式：{layout_description}"
        self.statusBar().showMessage(self.tr(status_message))
        
        # 启用曲线模式
        self.is_curve_mode_active = True
        
        #  设置线程管理器的曲线模式标记（用于检测线程启动时自动启动曲线线程）
        if hasattr(self, 'thread_manager'):
            self.thread_manager.is_curve_mode = True
        
        # 设置曲线面板的任务文件夹名称
        self._updateCurvePanelFolderName()
        
        # 根据检测线程状态更新通道显示
        if detection_running:
            # 同步布局：根据当前选择的任务更新通道显示
            if hasattr(self, 'curvemission'):
                current_mission = self.curvemission.currentText()
                if current_mission and current_mission != "请选择任务":
                    # 获取任务使用的通道列表并更新显示
                    selected_channels = self._getTaskChannels(current_mission)
                    if hasattr(self, '_updateCurveChannelDisplay'):
                        self._updateCurveChannelDisplay(selected_channels)
                else:
                    # 没有选择任务，隐藏所有通道
                    if hasattr(self, '_updateCurveChannelDisplay'):
                        self._updateCurveChannelDisplay([])
        else:
            # 历史回放布局：显示所有历史视频面板
            if hasattr(self, '_updateCurveChannelDisplay'):
                all_channels = ['通道1', '通道2', '通道3', '通道4']
                self._updateCurveChannelDisplay(all_channels)  # 显示所有4个历史视频面板
        
        # 强制刷新整个布局
        self.videoLayoutStack.currentWidget().updateGeometry()
        from qtpy.QtWidgets import QApplication
        QApplication.processEvents()
        
        # 延迟启动曲线线程，确保布局切换完成后再启动（避免进度条在切换前弹出）
        if self._video_layout_mode == 1:
            from qtpy import QtCore
            QtCore.QTimer.singleShot(100, self._loadCurveDataOrStartThreads)
  
    def _switchToDefaultLayout(self):
        """切换到默认布局（任务表格 + 2x2通道面板）"""
        # 停止所有曲线线程（切换回默认布局时）
        self._stopAllCurveThreads()
        
        # 切换曲线绘制模式为同步布局模式
        if hasattr(self, 'curvePanelHandler'):
            self.curvePanelHandler.setCurveLoadMode('realtime')
        
        # 将通道面板移回默认布局
        if hasattr(self, 'channelPanels'):
            for i, channel_panel in enumerate(self.channelPanels):
                if i < len(self.default_channel_positions):
                    # 从wrapper布局中移除
                    wrapper = self.channel_widgets_for_curve[i]
                    wrapper_layout = wrapper.layout()
                    if wrapper_layout and wrapper_layout.indexOf(channel_panel) >= 0:
                        wrapper_layout.removeWidget(channel_panel)
                    
                    # 重设父容器和位置
                    channel_panel.setParent(self.default_channel_container)
                    x, y = self.default_channel_positions[i]
                    channel_panel.move(x, y)
                    channel_panel.show()
        
        #  设置模式为默认模式（_video_layout_mode = 0）
        self._video_layout_mode = 0
        
        # 切换布局
        self.videoLayoutStack.setCurrentIndex(0)
        
        current_widget = self.videoLayoutStack.currentWidget()
        
        self.statusBar().showMessage(self.tr("当前页面: 实时检测管理"))
        
        # 禁用曲线模式
        self.is_curve_mode_active = False
        
        #  清除线程管理器的曲线模式标记
        if hasattr(self, 'thread_manager'):
            self.thread_manager.is_curve_mode = False
        
        # 清除曲线面板的所有数据
        if hasattr(self, 'clearCurvePanelOnLayoutSwitch'):
            self.clearCurvePanelOnLayoutSwitch()
        
        # 强制刷新整个布局
        self.videoLayoutStack.currentWidget().updateGeometry()
        from qtpy.QtWidgets import QApplication
        QApplication.processEvents()
    
    def switchToRealTimeDetectionPage(self):
        """切换到实时检测页面（兼容性方法，委托给 _switchToDefaultLayout）"""
        self._switchToDefaultLayout()
    
    def _switchCurveSubLayout(self, detection_running):
        """根据检测线程状态切换曲线子布局
        
        Args:
            detection_running: bool, True=检测线程运行中, False=检测线程停止
        """
        if not hasattr(self, 'curveLayoutStack'):
            print(f"[ERROR] [布局切换] 没有curveLayoutStack")
            return
        
        if detection_running:
            # 切换到同步布局（曲线模式布局的索引0）
            target_index = 0
            layout_name = "同步布局"
            mode_text = "同步"
            mode_style = "font-weight: bold; padding: 2px 8px;"
            curve_mode = 'realtime'

            
        else:
            # 切换到历史回放布局（曲线模式布局的索引1）
            target_index = 1
            layout_name = "历史回放布局"
            mode_text = "历史回放"
            mode_style = "font-weight: bold; padding: 2px 8px;"
            curve_mode = 'history'

            
        
        # 同步切换曲线绘制模式
        if hasattr(self, 'curvePanelHandler'):
            self.curvePanelHandler.setCurveLoadMode(curve_mode)
        
        # 更新模式标签
        if hasattr(self, 'curvePanel') and hasattr(self.curvePanel, 'mode_label'):
            self.curvePanel.mode_label.setText(mode_text)
            self.curvePanel.mode_label.setStyleSheet(mode_style)
            
            # 应用全局字体管理
            try:
                from widgets.style_manager import FontManager
                if FontManager:
                    FontManager.applyToWidget(self.curvePanel.mode_label)
            except ImportError:
                pass
        
        # 禁用/启用通道面板的查看曲线按钮
        # 只有在曲线模式(_video_layout_mode==1)的子布局切换时才需要处理
        # 子布局索引0（实时检测模式）时禁用，索引1（历史回放模式）时根据任务状态决定
        if hasattr(self, '_video_layout_mode') and self._video_layout_mode == 1:
            if hasattr(self, 'channelPanels'):
                for panel in self.channelPanels:
                    if hasattr(panel, 'btnCurve'):
                        if target_index == 0:
                            print(1)
                            # 曲线模式的同步布局：禁用查看曲线按钮
                            # panel.btnCurve.setEnabled(False)
                            # panel.btnCurve.setToolTip("同步布局下无法查看曲线")
                        else:
                            # 曲线模式的历史回放布局：检查通道是否有任务
                            has_task = False
                            if hasattr(panel, 'getTaskInfo'):
                                task_info = panel.getTaskInfo()
                                has_task = (task_info is not None and task_info != "未分配任务")
                            
                            if has_task:
                                # 有任务：启用查看曲线按钮
                                panel.btnCurve.setEnabled(True)
                                panel.btnCurve.setToolTip("查看曲线")
                            else:
                                # 无任务：保持禁用
                                panel.btnCurve.setEnabled(False)
                                panel.btnCurve.setToolTip("请先分配任务")
        
        # 执行布局切换
        current_index = self.curveLayoutStack.currentIndex()

        
        if current_index != target_index:
            self.curveLayoutStack.setCurrentIndex(target_index)
            self._curve_sub_layout_mode = target_index
        else:
            pass
    
    
    def _loadCurveDataOrStartThreads(self):
        """
        智能选择：加载历史数据 或 启动实时曲线线程
        
        业务逻辑：
        - 启动全局曲线线程，由线程负责加载历史数据和监控新数据
        - 避免重复加载：不再单独调用 _loadHistoricalCurveData()
        """
        if not hasattr(self, 'thread_manager'):
            return
        
        # 启动全局曲线线程
        # 线程启动时会自动发送历史数据，然后监控CSV文件变化
        self._startAllCurveThreads()
    
    def _startAllCurveThreads(self):
        """启动所有已打开通道的曲线线程（仅在曲线模式下）"""
        if not hasattr(self, 'thread_manager'):
            return
        
        #  严格检查：只有 _video_layout_mode == 1 时才允许启动
        if not hasattr(self, '_video_layout_mode') or self._video_layout_mode != 1:
            return
        
        # 调用线程管理器的批量启动方法
        self.thread_manager.start_all_curve_threads()
    
    def _loadHistoricalCurveData(self):
        """
        一次性加载历史曲线数据（无需启动曲线线程）
        
        适用场景：
        - 没有检测线程运行
        - 只查看历史数据
        - CSV文件不会变化
        """
        if not hasattr(self, 'loadHistoricalCurveData'):
            return
        
        #  从 curvemission 获取当前任务目录
        data_directory = self._getCurveMissionPath()
        
        if data_directory:
            success = self.loadHistoricalCurveData(data_directory)
    
    def _stopAllCurveThreads(self):
        """停止所有曲线线程（无条件执行）"""
        if not hasattr(self, 'thread_manager'):
            return
        
        #  无条件停止所有曲线线程（确保不在后台运行）
        self.thread_manager.stop_all_curve_threads()
    
    def _updateCurvePanelFolderName(self):
        """从 curvemission 获取任务路径并设置到曲线面板（文本框会自动提取文件夹名称）"""
        try:
            # 检查曲线面板是否存在
            if not hasattr(self, 'curvePanel') or self.curvePanel is None:
                return
            
            # 从 curvemission 获取任务路径
            mission_path = self._getCurveMissionPath()
            if mission_path:
                self.curvePanel.setFolderName(mission_path)
                
        except Exception as e:
            pass
    
    def isCurrentMissionValid(self):
        """
        检查当前任务是否有效（仅在debug模式下使用）
        
        Returns:
            bool: 如果任务有效返回True，否则返回False
        """
        try:
            # 从 curvemission 获取任务路径
            mission_path = self._getCurveMissionPath()
            
            # 如果路径为None或不存在，视为无效
            if not mission_path:
                return False
            
            import os
            if not os.path.exists(mission_path):
                return False
            
            # 其他情况视为有效
            return True
            
        except Exception:
            return False
    
    def shouldBlockInteraction(self):
        """
        判断是否应该阻止交互（仅在debug模式下）
        
        Returns:
            bool: 如果应该阻止交互返回True，否则返回False
        """
        try:
            # 只在debug模式下启用此功能
            config = None
            if hasattr(self, '_config'):
                config = self._config
            
            is_debug = is_debug_mode(config)
            
            if not is_debug:
                return False
            
            # 如果任务无效，阻止交互
            is_valid = self.isCurrentMissionValid()
            should_block = not is_valid
            
            # 只在需要阻止时才输出调试信息（减少日志量）
            return should_block
            
        except Exception:
            return False

