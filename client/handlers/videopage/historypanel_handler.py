# -*- coding: utf-8 -*-

"""
 (Mixin)

widgets/videopage/historypanel.py (HistoryPanel)


- 
- /
- 
"""

from qtpy import QtWidgets, QtCore


class HistoryPanelHandler:
    """
     (Mixin)
    
    
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 'stopped', 'playing', 'paused'
        self._playback_state = 'stopped'
        
        # UI
        self.history_panel = None
    
    def connectHistoryPanel(self, history_panel):
        """
        
        
        Args:
            history_panel: HistoryPanel
        """
        print(f"[HistoryPanelHandler] ==========  ==========")
        print(f"[HistoryPanelHandler] : {history_panel}")
        
        self.history_panel = history_panel
        
        # //
        if hasattr(history_panel, 'play_pause_button'):
            print(f"[HistoryPanelHandler]  play_pause_button: {history_panel.play_pause_button}")
            history_panel.play_pause_button.clicked.connect(self._onPlayPauseClicked)
            print(f"[HistoryPanelHandler]  ")
        else:
            print(f"[HistoryPanelHandler]  :  play_pause_button")
        
        # 
        if hasattr(history_panel, '_media_player'):
            print(f"[HistoryPanelHandler]  _media_player: {history_panel._media_player}")
            history_panel._media_player.stateChanged.connect(self._onPlayerStateChanged)
            print(f"[HistoryPanelHandler]  ")
        else:
            print(f"[HistoryPanelHandler]  :  _media_player")
        
        print(f"[HistoryPanelHandler] ==========  ==========")
    
    def _onPlayPauseClicked(self):
        """播放/暂停/停止按钮点击处理
        
        状态转换：
        - stopped → playing (加载并播放任务文件夹中的avi视频)
        - playing → paused (暂停播放)
        - paused → stopped (停止播放)
        """
        print(f"[HistoryPanelHandler] ========== 播放按钮点击 ==========")
        print(f"[HistoryPanelHandler] 当前状态: {self._playback_state}")
        
        if not self.history_panel:
            print(f"[HistoryPanelHandler] 错误: history_panel 为 None")
            return
            
        if not hasattr(self.history_panel, '_media_player'):
            print(f"[HistoryPanelHandler] 错误: history_panel 没有 _media_player 属性")
            return
        
        import os
        from qtpy.QtMultimedia import QMediaPlayer
        from qtpy import QtWidgets
        
        player = self.history_panel._media_player
        print(f"[HistoryPanelHandler] 播放器: {player}")
        print(f"[HistoryPanelHandler] 播放器状态: {player.state()}")
        print(f"[HistoryPanelHandler] 媒体状态: {player.mediaStatus()}")
        print(f"[HistoryPanelHandler] 当前媒体: {player.currentMedia().canonicalUrl().toString() if player.currentMedia() else 'None'}")
        
        if self._playback_state == 'stopped':
            # 停止状态 → 加载并播放视频
            print(f"\n[播放控制] ========== 开始播放流程 ==========")
            print(f"[播放控制] 当前状态: stopped")
            print(f"[播放控制] 操作: 加载并播放视频")
            
            # 查找任务文件夹中的avi视频文件
            video_path = self._findTaskVideo()
            
            if video_path:
                print(f"\n[播放控制] ========== 视频文件已找到 ==========")
                print(f"[播放控制] 视频路径: {video_path}")
                print(f"[播放控制] 文件存在: {os.path.exists(video_path)}")
                
                # 加载视频
                print(f"[播放控制] 调用loadHistoryVideo加载视频...")
                success = self.loadHistoryVideo(video_path)
                print(f"[播放控制] loadHistoryVideo返回结果: {success}")
                
                if success:
                    # 自动播放
                    print(f"[播放控制] 视频加载成功，开始播放...")
                    print(f"[播放控制] 播放器状态（播放前）: {player.state()}")
                    print(f"[播放控制] 媒体状态（播放前）: {player.mediaStatus()}")
                    print(f"[播放控制] 当前媒体: {player.currentMedia().canonicalUrl().toString() if player.currentMedia() else 'None'}")
                    
                    player.play()
                    
                    print(f"[播放控制] play()已调用")
                    print(f"[播放控制] 播放器状态（播放后）: {player.state()}")
                    print(f"[播放控制] 媒体状态（播放后）: {player.mediaStatus()}")
                    print(f"[播放控制] ========== 播放流程完成 ==========")
                else:
                    print(f"\n[播放控制] ========== 视频加载失败 ==========")
                    print(f"[播放控制] loadHistoryVideo返回False")
                    QtWidgets.QMessageBox.warning(
                        self.history_panel,
                        "加载失败",
                        f"无法加载视频文件:\n{video_path}"
                    )
            else:
                print(f"\n[播放控制] ========== 未找到视频文件 ==========")
                QtWidgets.QMessageBox.information(
                    self.history_panel,
                    "未找到视频",
                    "当前任务文件夹中没有找到avi视频文件"
                )
            
        elif self._playback_state == 'playing':
            # 播放中 → 暂停
            print(f"[HistoryPanelHandler] 操作: 暂停播放")
            player.pause()
            self._playback_state = 'paused'
            print(f"[HistoryPanelHandler] 状态转换: playing → paused")
            
        elif self._playback_state == 'paused':
            # 暂停 → 停止
            print(f"[HistoryPanelHandler] 操作: 停止播放")
            player.stop()
            self._playback_state = 'stopped'
            print(f"[HistoryPanelHandler] 状态转换: paused → stopped")
        
        print(f"[HistoryPanelHandler] ========== 处理完成 ==========")
    
    def _onPlayerStateChanged(self, state):
        """播放器状态变化处理"""
        if not self.history_panel or not hasattr(self.history_panel, 'play_pause_button'):
            return
        
        from qtpy.QtMultimedia import QMediaPlayer
        from widgets.style_manager import newIcon
        
        button = self.history_panel.play_pause_button
        
        if state == QMediaPlayer.PlayingState:
            # 播放中 -> 显示停止图标
            button.setIcon(newIcon('停止1'))
            button.setToolTip('停止')
            self._playback_state = 'playing'
            print(f"[HistoryPanelHandler] 播放器状态: 播放中 (显示停止图标)")
            
        elif state == QMediaPlayer.PausedState:
            # 暂停 -> 显示开始图标
            button.setIcon(newIcon('开始'))
            button.setToolTip('播放')
            self._playback_state = 'paused'
            print(f"[HistoryPanelHandler] 播放器状态: 暂停 (显示开始图标)")
            
        else:  # StoppedState
            # 停止 -> 显示开始图标
            button.setIcon(newIcon('开始'))
            button.setToolTip('播放')
            self._playback_state = 'stopped'
            print(f"[HistoryPanelHandler] 播放器状态: 停止 (显示开始图标)")
    
    def _findTaskVideo(self):
        """查找当前任务文件夹中的avi视频文件
        
        Returns:
            str: 视频文件的绝对路径，如果未找到则返回None
        """
        import os
        import sys
        
        print(f"\n[视频查找] ========== 开始查找任务视频 ==========")
        
        try:
            # 获取项目根目录
            if getattr(sys, 'frozen', False):
                project_root = os.path.dirname(sys.executable)
                print(f"[视频查找] 运行模式: 打包模式")
            else:
                try:
                    from database.config import get_project_root
                    project_root = get_project_root()
                    print(f"[视频查找] 运行模式: 开发模式（使用get_project_root）")
                except ImportError:
                    project_root = os.getcwd()
                    print(f"[视频查找] 运行模式: 开发模式（使用os.getcwd）")
            
            print(f"[视频查找] 项目根目录: {project_root}")
            
            # 获取当前选中的任务
            current_mission = None
            print(f"[视频查找] 检查curvemission属性: {hasattr(self, 'curvemission')}")
            
            if hasattr(self, 'curvemission'):
                current_mission = self.curvemission.currentText()
                print(f"[视频查找] 从curvemission获取任务: '{current_mission}'")
            else:
                print(f"[视频查找] 错误: 没有curvemission属性")
                print(f"[视频查找] 当前对象属性: {dir(self)}")
            
            if not current_mission or current_mission == "请选择任务":
                print(f"[视频查找] 错误: 未选择有效任务")
                return None
            
            # 构建任务结果文件夹路径
            mission_result_folder = os.path.join(
                project_root,
                'database',
                'mission_result',
                current_mission
            )
            
            print(f"[视频查找] 任务文件夹路径: {mission_result_folder}")
            print(f"[视频查找] 文件夹是否存在: {os.path.exists(mission_result_folder)}")
            
            if not os.path.exists(mission_result_folder):
                print(f"[视频查找] 错误: 任务文件夹不存在")
                return None
            
            # 列出文件夹中的所有文件
            all_files = os.listdir(mission_result_folder)
            print(f"[视频查找] 文件夹中的所有文件 ({len(all_files)}个): {all_files}")
            
            # 查找avi视频文件
            avi_files = []
            for filename in all_files:
                print(f"[视频查找] 检查文件: {filename}")
                if filename.lower().endswith('.avi'):
                    video_path = os.path.join(mission_result_folder, filename)
                    file_size = os.path.getsize(video_path)
                    print(f"[视频查找] ✓ 找到avi视频: {filename} (大小: {file_size} 字节)")
                    avi_files.append((filename, video_path, file_size))
            
            if avi_files:
                # 返回第一个找到的avi文件
                filename, video_path, file_size = avi_files[0]
                print(f"[视频查找] ========== 查找成功 ==========")
                print(f"[视频查找] 视频文件: {filename}")
                print(f"[视频查找] 完整路径: {video_path}")
                print(f"[视频查找] 文件大小: {file_size} 字节")
                return video_path
            else:
                print(f"[视频查找] ========== 查找失败 ==========")
                print(f"[视频查找] 错误: 未找到avi视频文件")
                return None
            
        except Exception as e:
            print(f"[视频查找] ========== 查找异常 ==========")
            print(f"[视频查找] 错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def loadHistoryVideo(self, video_path, info_text=None):
        """加载历史视频到播放器
        
        Args:
            video_path: 视频文件路径
            info_text: 信息文本
        
        Returns:
            bool: 加载是否成功
        """
        print(f"\n[视频加载] ========== 开始加载视频 ==========")
        print(f"[视频加载] 视频路径: {video_path}")
        print(f"[视频加载] 信息文本: {info_text}")
        
        import os
        print(f"[视频加载] 文件存在: {os.path.exists(video_path)}")
        if os.path.exists(video_path):
            print(f"[视频加载] 文件大小: {os.path.getsize(video_path)} 字节")
        else:
            print(f"[视频加载] 错误: 文件不存在！")
            return False
        
        if not self.history_panel:
            print(f"[视频加载] 错误: history_panel为None")
            return False
        
        print(f"[视频加载] history_panel对象: {self.history_panel}")
        print(f"[视频加载] history_panel类型: {type(self.history_panel)}")
        
        # 检查loadVideo方法是否存在
        if not hasattr(self.history_panel, 'loadVideo'):
            print(f"[视频加载] 错误: history_panel没有loadVideo方法")
            print(f"[视频加载] history_panel的方法: {[m for m in dir(self.history_panel) if not m.startswith('_')]}")
            return False
        
        # 调用loadVideo
        print(f"[视频加载] 调用 history_panel.loadVideo()...")
        try:
            success = self.history_panel.loadVideo(video_path, info_text=info_text)
            print(f"[视频加载] loadVideo返回结果: {success}")
        except Exception as e:
            print(f"[视频加载] loadVideo调用异常: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        if success:
            print(f"[视频加载] ========== 视频加载成功 ==========")
            
            # 检查播放器状态
            if hasattr(self.history_panel, '_media_player'):
                player = self.history_panel._media_player
                print(f"[视频加载] 播放器对象: {player}")
                print(f"[视频加载] 播放器状态: {player.state()}")
                print(f"[视频加载] 媒体状态: {player.mediaStatus()}")
                print(f"[视频加载] 当前媒体: {player.currentMedia().canonicalUrl().toString() if player.currentMedia() else 'None'}")
                
                # 同步播放器状态
                print(f"[视频加载] 同步播放器状态...")
                self._onPlayerStateChanged(player.state())
                print(f"[视频加载] 当前播放状态: {self._playback_state}")
            else:
                print(f"[视频加载] 警告: history_panel没有_media_player属性")
        else:
            print(f"[视频加载] ========== 视频加载失败 ==========")
        
        return success
    
    def playHistoryVideo(self):
        """"""
        if self.history_panel and hasattr(self.history_panel, 'play'):
            self.history_panel.play()
    
    def pauseHistoryVideo(self):
        """"""
        if self.history_panel and hasattr(self.history_panel, 'pause'):
            self.history_panel.pause()
    
    def stopHistoryVideo(self):
        """"""
        if self.history_panel and hasattr(self.history_panel, 'stop'):
            self.history_panel.stop()
