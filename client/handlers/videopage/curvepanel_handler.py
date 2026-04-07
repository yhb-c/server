# -*- coding: utf-8 -*-

"""
曲线面板处理器 (Mixin类)

对应组件：widgets/videopage/curvepanel.py (CurvePanel)

职责：
- 管理曲线数据存储和处理
- 处理曲线面板的业务逻辑
- 响应UI信号并处理业务逻辑
- 管理自动保存和数据导出
"""

import os
import csv
import datetime
import numpy as np
from qtpy import QtWidgets, QtCore
from qtpy.QtCore import QThread, Signal as pyqtSignal

# 导入图标工具
try:
    from widgets.style_manager import newIcon
except ImportError:
    try:
        from style_manager import newIcon
    except ImportError:
        def newIcon(icon):
            from qtpy import QtGui
            return QtGui.QIcon()


class CurveDataLoadThread(QThread):
    """后台曲线数据加载线程（支持分批加载大文件）"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, str)  # (进度值0-100, 提示文本)
    file_loaded = pyqtSignal(str, str, str, str, list)  # (channel_id, channel_name, window_name, color, data_points)
    load_finished = pyqtSignal(bool, int)  # (是否成功, 加载文件数)
    
    # 分批加载配置
    BATCH_SIZE = 50000  # 每批处理5万个数据点
    
    def __init__(self, data_directory, csv_files, handler):
        super().__init__()
        self.data_directory = data_directory
        self.csv_files = csv_files
        self.handler = handler
        self.loaded_count = 0
    
    def run(self):
        """后台线程执行的加载任务"""
        try:
            total_files = len(self.csv_files)
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            
            for idx, csv_file in enumerate(self.csv_files):
                csv_path = os.path.join(self.data_directory, csv_file)
                
                # 解析文件名获取区域名称
                file_base = os.path.splitext(csv_file)[0]
                parts = file_base.split('_')
                
                # 去掉日期后缀（如果有）
                if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 8:
                    area_name = '_'.join(parts[:-1])
                else:
                    area_name = file_base
                
                # 生成通道ID
                curve_channel_id = f"historical_{area_name}"
                
                # 分配颜色
                color_index = self.loaded_count % len(colors)
                color = colors[color_index]
                
                # 提取通道名称和窗口名称
                channel_name = area_name.split('_')[0] if '_' in area_name else area_name
                window_name = area_name
                
                # 🔥 分批读取CSV文件
                batch_count = 0
                total_points = 0
                
                for batch_data in self._readCSVInBatches(csv_path, csv_file, idx, total_files):
                    if not batch_data:
                        continue
                    
                    batch_count += 1
                    total_points += len(batch_data)
                    
                    # 发射批次数据加载完成信号
                    self.file_loaded.emit(curve_channel_id, channel_name, window_name, color, batch_data)
                
                if total_points > 0:
                    self.loaded_count += 1
            
            # 完成进度
            self.progress_updated.emit(100, f"加载完成！共 {self.loaded_count} 个文件")
            
            # 发射加载完成信号
            self.load_finished.emit(True, self.loaded_count)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.load_finished.emit(False, 0)
    
    def _readCSVInBatches(self, csv_path, csv_file, file_idx, total_files):
        """
        分批读取CSV文件
        
        Args:
            csv_path: CSV文件完整路径
            csv_file: CSV文件名
            file_idx: 当前文件索引
            total_files: 总文件数
            
        Yields:
            list: 每批数据点列表
        """
        try:
            batch = []
            line_count = 0
            batch_count = 0
            
            # 🔥 先获取文件总行数（用于精确进度计算）
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    total_lines = sum(1 for _ in f)
            except:
                total_lines = 0
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    line_count += 1
                    
                    # 解析CSV行：时间戳 高度值
                    parts = line.split()
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        height_str = parts[1]
                        
                        try:
                            # 解析时间戳
                            timestamp = datetime.datetime.strptime(
                                timestamp_str, "%Y-%m-%d-%H:%M:%S.%f"
                            ).timestamp()
                            
                            # 解析高度（支持小数，精度0.1mm）
                            height_mm = float(height_str)
                            
                            # 创建数据点
                            point = {
                                'timestamp': timestamp,
                                'height_mm': height_mm
                            }
                            
                            batch.append(point)
                            
                            # 🔥 达到批次大小，发送一批数据
                            if len(batch) >= self.BATCH_SIZE:
                                batch_count += 1
                                
                                # 🔥 计算精确进度：文件进度 + 文件内进度
                                file_base_progress = (file_idx / total_files) * 100
                                if total_lines > 0:
                                    file_internal_progress = (line_count / total_lines) * (100 / total_files)
                                    total_progress = int(file_base_progress + file_internal_progress)
                                else:
                                    total_progress = int(file_base_progress)
                                
                                # 限制进度在0-99之间（100%留给完成信号）
                                total_progress = min(99, max(0, total_progress))
                                
                                self.progress_updated.emit(
                                    total_progress, 
                                    f"加载: {csv_file} ({line_count:,}/{total_lines:,}行, 批次{batch_count}) [{file_idx+1}/{total_files}]"
                                )
                                
                                yield batch
                                batch = []
                            
                        except ValueError:
                            pass  # 忽略解析错误的行
            
            # 发送最后一批数据
            if batch:
                batch_count += 1
                # 文件读取完成，进度设为该文件的100%
                file_complete_progress = int(((file_idx + 1) / total_files) * 100)
                file_complete_progress = min(99, file_complete_progress)
                self.progress_updated.emit(
                    file_complete_progress,
                    f"完成: {csv_file} (共{line_count:,}行, {batch_count}批次) [{file_idx+1}/{total_files}]"
                )
                yield batch
                
        except Exception as e:
            yield []


class CurvePanelHandler:
    """
    曲线面板处理器 (Mixin类)
    
    处理曲线面板相关的业务逻辑和数据管理
    """
    
    # 定义信号：曲线数据更新（线程安全）
    # 参数：(curve_id: str, area_idx: int, new_points: list)
    curveDataReceived = QtCore.Signal(str, int, list)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        #  业务数据管理（从Widget层移动到Handler层）
        self.channel_data = {}  # {channel_id: {'channel_name': str, 'window_name': str, 'time': [], 'value': []}}
        self.channel_start_times = {}  # 每个通道的起始时间
        # 每条曲线历史模式下单次绘制的最大点数（根据X轴显示范围做采样）
        # 注意：原始数据全部保存在 channel_data 中，仅在送往UI前做抽样
        # self.max_points = 3000  # 旧字段，保留以兼容旧逻辑（实时模式用）
        self.max_points_per_view = 800  # 新字段：单视图最大显示点数，用于采样
        
        # 🔥 曲线加载模式：'realtime' 或 'history'
        # - 'realtime'：实时检测模式，限制数据点为3000个（滚动窗口）
        # - 'history'：历史回放模式，加载所有数据点，不做限制
        self.curve_load_mode = 'realtime'
        
        # 🔥 历史数据加载标志（避免重复加载）
        self._history_data_loaded = False
        
        # UI组件引用
        self.curve_panel = None
    
    def connectCurvePanel(self, curve_panel):
        """
        连接曲线面板信号
        
        Args:
            curve_panel: CurvePanel实例
        """
        self.curve_panel = curve_panel
        
        # 连接信号
        curve_panel.missionFolderChanged.connect(self._handleMissionFolderChanged)
        curve_panel.refreshMissionListRequested.connect(self.loadMissionFolders)
        # 时间轴范围变化信号：用于缩放/拖动时根据当前范围重新采样
        if hasattr(curve_panel, "timeAxisRangeChanged"):
            curve_panel.timeAxisRangeChanged.connect(self._onTimeAxisRangeChanged)
        
        # 连接安全限值变化信号
        curve_panel.spn_upper_limit.valueChanged.connect(self._handleSafetyLimitsChanged)
        curve_panel.spn_lower_limit.valueChanged.connect(self._handleSafetyLimitsChanged)
        
        # 连接线程安全的信号到主线程槽函数
        self.curveDataReceived.connect(
            self._processCurveDataInMainThread,
            QtCore.Qt.QueuedConnection  # 关键：确保跨线程调用安全
        )
        
        # 🔥 设置曲线线程回调（如果thread_manager存在）
        if hasattr(self, 'thread_manager'):
            self.thread_manager.on_curve_updated = self._onCurveDataUpdated

        else:
            pass

        # 设置默认保存目录
        self._setDefaultSaveDirectory()
        
        # 加载任务文件夹列表
        self.loadMissionFolders()
        
        # 加载安全限值配置
        self._loadSafetyLimitsFromConfig()
    
    def _setDefaultSaveDirectory(self):
        """设置默认保存目录（已废弃，数据由存储线程自动保存）"""
        pass
    
    # ========== 业务逻辑方法 ==========
    
    def addChannelData(self, channel_id, channel_name=None, window_name=None, color=None):
        """
        添加通道数据（业务逻辑）
        
        Args:
            channel_id: 通道ID
            channel_name: 通道名称
            window_name: 窗口名称
            color: 曲线颜色
        """
        if channel_id in self.channel_data:
            return
        
        # 默认名称
        if channel_name is None:
            channel_name = channel_id
        
        if window_name is None:
            window_name = "默认窗口"
        
        # 初始化数据存储
        self.channel_data[channel_id] = {
            'channel_name': channel_name,
            'window_name': window_name,
            'time': [],
            'value': []
        }
        
        # 记录起始时间
        self.channel_start_times[channel_id] = datetime.datetime.now()
        
        # 通知UI创建通道
        if self.curve_panel:
            self.curve_panel.addChannel(channel_id, channel_name, window_name, color)
    
    def updateCurveData(self, channel_id, data_points):
        """
        更新曲线数据（业务逻辑：批量处理）
        
        Args:
            channel_id: 通道ID
            data_points: 数据点列表 [{'timestamp': float, 'height_mm': float}, ...]
                        height_mm精度为0.1mm（保留1位小数）
        """
        if not data_points:
            return
        
        if channel_id not in self.channel_data:
            self.addChannelData(channel_id)
        
        channel = self.channel_data[channel_id]
        
        # 批量添加数据（原始数据全部保留在 channel_data 中）
        added_count = 0
        for point in data_points:
            timestamp = point['timestamp']
            height_mm = point['height_mm']
            
            #  数据验证：过滤无效值（NaN、Inf）
            if not np.isfinite(timestamp) or not np.isfinite(height_mm):
                continue  # 跳过无效数据点
            
            channel['time'].append(timestamp)
            channel['value'].append(height_mm)
            added_count += 1
        
        # ===== 根据当前X轴显示范围进行采样（显示层抽点，不影响原始数据） =====
        processed_time, processed_value = self._getSampledDataForChannel(channel_id)
        
        # 🔥 数据验证：确保有数据才更新UI
        if not processed_time or not processed_value:
            # print(f"   - ⚠️ 处理后数据为空，跳过UI更新")
            return
        
        if len(processed_time) != len(processed_value):
            # print(f"   - ⚠️ 处理后数据长度不匹配: time={len(processed_time)}, value={len(processed_value)}")
            return
        
        # 🔥 检查是否有有效数据点（至少有一个非NaN值）
        has_valid_data = False
        for i in range(len(processed_value)):
            if np.isfinite(processed_value[i]) and np.isfinite(processed_time[i]):
                has_valid_data = True
                break
        
        if not has_valid_data:
            # print(f"   - ⚠️ 没有有效数据点（全是NaN/Inf），跳过UI更新")
            return
        
        #  更新UI显示（只更新一次）
        if self.curve_panel:
            self.curve_panel.updateCurveDisplay(
                channel_id,
                processed_time,
                processed_value
            )
            
            # 🔥 根据加载模式决定X轴范围设置
            if channel['time']:
                min_time = min(channel['time'])
                max_time = max(channel['time'])
                
                if self.curve_load_mode == 'history':
                    # 历史模式：显示全部数据范围
                    if channel['value']:
                        max_value = max(channel['value'])
                    else:
                        max_value = 23
                    self.curve_panel.setViewAll(min_time, max_time, max_value)
                else:
                    # 实时模式：只显示最后几分钟（自动跟随）
                    self.curve_panel.setXRangeAuto(max_time)
            
            # 更新Y轴范围（仅在实时模式下）
            if self.curve_load_mode == 'realtime' and channel['value']:
                max_value = max(channel['value'])
                self.curve_panel.setYRangeAuto(max_value)
        else:
            pass

    def _processTimeGaps(self, time_data, value_data, max_gap_seconds=10):
        """
        处理时间间隔断点：在超过指定时间间隔的数据点之间插入NaN值
        
        Args:
            time_data: 时间戳列表
            value_data: 数值列表
            max_gap_seconds: 最大允许的时间间隔（秒），默认10秒
        
        Returns:
            tuple: (处理后的时间列表, 处理后的数值列表)
        """
        # 🔥 处理空数据情况
        if not time_data or not value_data:
            return [], []
        
        if len(time_data) != len(value_data):
            # print(f"⚠️ [时间间隔处理] 数据长度不匹配: time={len(time_data)}, value={len(value_data)}")
            return time_data, value_data
        
        if len(time_data) <= 1:
            return time_data, value_data
        
        processed_time = []
        processed_value = []
        
        for i in range(len(time_data)):
            # 添加当前数据点
            processed_time.append(time_data[i])
            processed_value.append(value_data[i])
            
            # 检查与下一个数据点的时间间隔
            if i < len(time_data) - 1:
                time_gap = time_data[i + 1] - time_data[i]
                
                # 如果时间间隔超过阈值，插入NaN断点
                if time_gap > max_gap_seconds:
                    # 在间隔中间插入一个NaN点来断开连接
                    mid_time = (time_data[i] + time_data[i + 1]) / 2
                    processed_time.append(mid_time)
                    processed_value.append(np.nan)
        
        return processed_time, processed_value

    def _getSampledDataForChannel(self, channel_id, starttime=None, endtime=None):
        """
        根据给定的时间范围对指定通道的数据进行抽样，并处理时间间隔断点。

        Args:
            channel_id (str): 通道ID
            starttime (float|None): 可见范围起始时间戳；None 时自动取通道最小时间
            endtime (float|None): 可见范围结束时间戳；None 时自动取通道最大时间

        Returns:
            tuple: (processed_time, processed_value)
        """
        if channel_id not in self.channel_data:
            return [], []

        channel = self.channel_data[channel_id]
        full_time = channel.get("time", [])
        full_value = channel.get("value", [])

        if not full_time or not full_value:
            return [], []

        # 如果外部没有指定范围，则使用当前CurvePanel中的范围
        if starttime is None or endtime is None:
            try:
                starttime, endtime = self.getTimeAxisRange()
            except Exception:
                starttime, endtime = None, None

        # 如果仍然没有有效范围，则使用该通道的整体时间范围
        if starttime is None or endtime is None or not np.isfinite(starttime) or not np.isfinite(endtime):
            starttime = min(full_time)
            endtime = max(full_time)

        # 选出当前显示范围内的数据点
        visible_indices = [i for i, t in enumerate(full_time) if starttime <= t <= endtime]

        if visible_indices:
            visible_time = [full_time[i] for i in visible_indices]
            visible_value = [full_value[i] for i in visible_indices]
        else:
            # 如果当前显示范围内没有点，则退回到全量数据
            visible_time = full_time
            visible_value = full_value

        visible_count = len(visible_time)
        max_points_per_view = getattr(self, "max_points_per_view", 5000)

        if visible_count > max_points_per_view:
            # 计算采样步长，保证单次绘制点数不超过 max_points_per_view
            step = int(np.ceil(visible_count / max_points_per_view))
            sampled_time = visible_time[::step]
            sampled_value = visible_value[::step]
        else:
            sampled_time = visible_time
            sampled_value = visible_value

        # 处理时间间隔断点：超过10秒的数据点之间插入NaN断开连接
        processed_time, processed_value = self._processTimeGaps(
            sampled_time, sampled_value, max_gap_seconds=10  # 10秒
        )
        return processed_time, processed_value

    def _onTimeAxisRangeChanged(self, starttime, endtime):
        """
        曲线面板时间轴范围变化回调（由CurvePanel触发）

        每次缩放/拖动X轴时，按照当前显示范围对所有通道重新采样并刷新UI。
        """
        if not self.curve_panel:
            return

        for channel_id, channel in self.channel_data.items():
            processed_time, processed_value = self._getSampledDataForChannel(
                channel_id, starttime=starttime, endtime=endtime
            )

            # 数据验证：与 updateCurveData 中保持一致
            if not processed_time or not processed_value:
                continue
            if len(processed_time) != len(processed_value):
                continue

            has_valid_data = any(
                np.isfinite(v) and np.isfinite(t)
                for t, v in zip(processed_time, processed_value)
            )
            if not has_valid_data:
                continue

            self.curve_panel.updateCurveDisplay(
                channel_id,
                processed_time,
                processed_value
            )
    
    def _exportChannelDataToCSV(self, channel_id, file_path=None):
        """
        导出通道数据到CSV文件（手动导出功能）
        
        注意：数据已由存储线程自动保存，此方法仅用于手动导出数据副本
        
        Args:
            channel_id: 通道ID
            file_path: 保存路径（必需）
        
        Returns:
            bool: 是否成功
        """
        if channel_id not in self.channel_data:
            return False
        
        channel = self.channel_data[channel_id]
        
        if len(channel['time']) == 0:
            return False
        
        if file_path is None:
            return False
        
        try:
            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=' ')
                for time_val, height_val in zip(channel['time'], channel['value']):
                    # 转换时间戳为格式化字符串
                    dt = datetime.datetime.fromtimestamp(time_val)
                    time_str = dt.strftime("%Y-%m-%d-%H:%M:%S.%f")[:-3]  # 保留3位小数
                    # 保留1位小数，精度0.1mm
                    writer.writerow([time_str, f"{height_val:.1f}"])
            
            return True
        except Exception as e:
            return False
    
    # ========== 信号处理方法 ==========
    
    def _handleExportData(self, channel_id):
        """
        处理导出数据请求（业务逻辑）
        
        Args:
            channel_id: 通道ID
        """
        # 弹出文件选择对话框
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.curve_panel,
            "导出数据",
            f"{self.channel_data[channel_id]['channel_name']}_{self.channel_data[channel_id]['window_name']}.csv",
            "CSV文件 (*.csv)"
        )
        
        if file_path:
            success = self._exportChannelDataToCSV(channel_id, file_path)
            if success:
                QtWidgets.QMessageBox.information(
                    self.curve_panel,
                    "成功",
                    f"数据已导出到:\n{file_path}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self.curve_panel,
                    "失败",
                    "数据导出失败"
                )
    
    def _handleSaveImage(self):
        """处理保存图片请求（业务逻辑）"""
        
        # 弹出文件选择对话框
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.curve_panel,
            "保存图片",
            f"curve_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG图片 (*.png)"
        )
        
        if file_path:
            try:
                # 使用PyQtGraph的导出功能
                from pyqtgraph.exporters import ImageExporter
                exporter = ImageExporter(self.curve_panel.plot_widget.plotItem)
                exporter.export(file_path)
                
                QtWidgets.QMessageBox.information(
                    self.curve_panel,
                    "成功",
                    f"图片已保存到:\n{file_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self.curve_panel,
                    "失败",
                    f"图片保存失败: {e}"
                )
    
    def _handleMissionFolderChanged(self, folder_path_or_name):
        """
        处理任务文件夹选择变化
        
        Args:
            folder_path_or_name: 选中的任务文件夹完整路径或任务名称
"""
        
        # 🔥 处理两种输入格式：完整路径或任务名称
        if folder_path_or_name and folder_path_or_name != "请选择任务" and folder_path_or_name != "0000":
            # 如果输入是任务名称（不是完整路径），需要构建完整路径
            if os.path.sep not in str(folder_path_or_name):
                # 输入是任务名称，构建完整路径
                mission_name = folder_path_or_name
                folder_path = self._buildMissionFolderPath(mission_name)
            else:
                # 输入是完整路径
                folder_path = folder_path_or_name
                mission_name = os.path.basename(folder_path) if folder_path else None
        else:
            # 无效输入或默认选项
            folder_path = None
            mission_name = None
        
        # 清除当前数据
        self.clearAllData()
        
        # 🔥 只在曲线模式布局时才启动曲线线程
        # 检查是否在曲线模式（_video_layout_mode == 1）
        is_curve_mode = hasattr(self, '_video_layout_mode') and self._video_layout_mode == 1
        
        if not is_curve_mode:
            return
        
        # 🔥 重新启动曲线线程以监控新任务的CSV文件变化
        if hasattr(self, 'thread_manager') and folder_path:
            # 先停止旧的曲线线程
            self.thread_manager.stop_all_curve_threads()
            
            # 启动新的曲线线程监控新任务
            import time
            time.sleep(0.1)  # 短暂延迟确保线程完全停止
            self.thread_manager.start_all_curve_threads()
    
    def _handleClearData(self, channel_id):
        """
        处理清空通道数据请求（业务逻辑）
        
        Args:
            channel_id: 通道ID
        """
        if channel_id not in self.channel_data:
            return
        
        # 清空数据
        channel = self.channel_data[channel_id]
        channel['time'].clear()
        channel['value'].clear()
        
        # 重置起始时间
        self.channel_start_times[channel_id] = datetime.datetime.now()
        
        # 更新UI
        if self.curve_panel:
            self.curve_panel.updateCurveDisplay(channel_id, [], [])
    
    def _handleViewAll(self):
        """处理查看全部数据请求（业务逻辑）"""
        # 找出所有通道的最小和最大时间值、最大数值
        min_time = None
        max_time = None
        max_value = 23
        
        for channel_id, channel in self.channel_data.items():
            if len(channel['time']) > 0:
                channel_min_time = min(channel['time'])
                channel_max_time = max(channel['time'])
                if min_time is None or channel_min_time < min_time:
                    min_time = channel_min_time
                if max_time is None or channel_max_time > max_time:
                    max_time = channel_max_time
            
            if len(channel['value']) > 0:
                channel_max_value = max(channel['value'])
                max_value = max(max_value, channel_max_value)
        
        # 更新UI显示
        if self.curve_panel:
            self.curve_panel.setViewAll(min_time, max_time, max_value)
    
    def _onAutoSaveTimer(self):
        """自动保存定时器（业务逻辑）"""
        for channel_id in self.channel_data.keys():
            self._checkAutoSave(channel_id)
    
    def _loadSafetyLimitsFromConfig(self):
        """从配置文件加载安全限值"""
        try:
            # 尝试从全局配置中读取安全限值
            if hasattr(self, 'config'):
                upper_limit = self.config.get('safety_limit', {}).get('upper_limit', 20.0)
                lower_limit = self.config.get('safety_limit', {}).get('lower_limit', 0.0)
            else:
                # 默认值
                upper_limit = 20.0
                lower_limit = 0.0
            
            # 设置到UI
            if self.curve_panel:
                self.curve_panel.setSafetyLimits(upper_limit, lower_limit)
        except Exception as e:
            pass
    
    def _handleSafetyLimitsChanged(self, value):
        """处理安全限值变化（保存到配置）"""
        try:
            if not self.curve_panel:
                return
            
            # 获取当前限值
            upper_limit, lower_limit = self.curve_panel.getSafetyLimits()
            
            # 保存到配置
            if hasattr(self, 'config'):
                if 'safety_limit' not in self.config:
                    self.config['safety_limit'] = {}
                self.config['safety_limit']['upper_limit'] = upper_limit
                self.config['safety_limit']['lower_limit'] = lower_limit
                
                # 如果有保存配置的方法，调用它
                if hasattr(self, 'save_config'):
                    self.save_config()
        except Exception as e:
            pass
    
    def getTimeAxisRange(self):
        """
        获取曲线面板时间轴显示范围
        
        Returns:
            tuple: (starttime, endtime) - 时间轴起始时刻和结束时刻（Unix时间戳）
        """
        if self.curve_panel:
            result = self.curve_panel.getTimeAxisRange()
            # 🔥 调试信息：输出handler获取的结果
            import datetime
            start_time, end_time = result
            start_str = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S') if start_time else 'None'
            end_str = datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S') if end_time else 'None'
           
            return result
        
        return (None, None)
    
    # ========== 数据管理方法 ==========
    
    def clearAllData(self):
        """
        清除所有曲线数据（业务逻辑）
        
        用于任务切换时清空当前显示的所有曲线数据
        """
        try:
            # 清除业务数据
            self.channel_data.clear()
            self.channel_start_times.clear()
            
            # 调用UI组件的清除方法
            if self.curve_panel:
                self.curve_panel.clearAllChannels()
            
            return True
        except Exception as e:
            return False
    
    def _buildMissionFolderPath(self, mission_name):
        """
        根据任务名称构建完整的任务文件夹路径
        
        Args:
            mission_name: 任务名称（如 "1_1", "2_3" 等）
        
        Returns:
            str: 完整的任务文件夹路径，如果构建失败返回None
        """
        try:
            import sys
            
            # 🔥 动态获取数据目录（与storage_thread保持一致）
            if getattr(sys, 'frozen', False):
                # 打包后：使用 sys._MEIPASS 指向 _internal 目录
                data_root = sys._MEIPASS
            else:
                # 开发环境：基于配置模块获取
                try:
                    from database.config import get_project_root
                    data_root = get_project_root()
                except ImportError:
                    # 后备方案：当前工作目录
                    data_root = os.getcwd()
            
            # 构建完整路径
            mission_folder_path = os.path.join(data_root, 'database', 'mission_result', mission_name)
            # print(f"🔍 [路径构建] 任务名称: {mission_name}")
            # print(f"🔍 [路径构建] 数据根目录: {data_root}")
            # print(f"🔍 [路径构建] 完整路径: {mission_folder_path}")
            # print(f"🔍 [路径构建] 路径是否存在: {os.path.exists(mission_folder_path)}")
            
            # 检查路径是否存在
            if os.path.exists(mission_folder_path):
                return mission_folder_path
            else:
                # print(f"❌ [路径构建] 路径不存在: {mission_folder_path}")
                return None
                
        except Exception as e:
            return None
    
    # ========== 外部调用方法 ==========
    
    def clearCurvePanelOnLayoutSwitch(self):
        """
        切换回默认模式时清除曲线面板（业务逻辑）
        
        业务规则：
        - 切换回默认模式时需要清除所有曲线数据
        - 避免下次进入曲线模式时出现重复曲线
        - 重置曲线面板到初始状态
        """
        if not self.curve_panel:
            return False
        
        try:
            # 清除业务数据
            self.channel_data.clear()
            self.channel_start_times.clear()
            
            # 调用UI组件的清除方法
            self.curve_panel.clearAllChannels()
            
            return True
        except Exception as e:
            return False
    
    def setCurvePanelSaveDirectory(self, directory):
        """
        设置曲线面板保存目录（已废弃，数据由存储线程自动保存）
        
        Args:
            directory: 目录路径
        """
        # 此方法已废弃，保留仅为向后兼容
        pass
    
    def loadMissionFolders(self):
        """
        加载任务文件夹列表（业务逻辑）
        
        从 database/mission_result 目录读取所有任务文件夹
        """
        import sys
        
        try:
            # 🔥 动态获取数据目录（与storage_thread保持一致）
            if getattr(sys, 'frozen', False):
                # 打包后：使用 sys._MEIPASS 指向 _internal 目录
                data_root = sys._MEIPASS
            else:
                # 开发环境：基于配置模块获取
                try:
                    from database.config import get_project_root
                    data_root = get_project_root()
                except ImportError:
                    # 后备方案：当前工作目录
                    data_root = os.getcwd()
            
            # 构建 mission_result 目录路径
            mission_result_dir = os.path.join(data_root, 'database', 'mission_result')
            
            if not os.path.exists(mission_result_dir):
                # 通知UI显示空列表
                if self.curve_panel:
                    self.curve_panel.updateMissionFolderList([])
                return
            
            # 扫描所有子文件夹
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
            
            # 通知UI更新下拉框
            if self.curve_panel:
                self.curve_panel.updateMissionFolderList(mission_folders)
            
        except Exception as e:
            pass
            # 通知UI显示空列表
            if self.curve_panel:
                self.curve_panel.updateMissionFolderList([])
    
    def loadHistoricalCurveData(self, data_directory=None):
        """
        一次性加载历史曲线数据（用于无检测线程的历史回放场景）
        使用后台线程加载，避免UI冻结
        
        业务场景：
        - 切换到曲线模式时，如果没有检测线程运行
        - 不需要启动曲线线程去监控文件变化
        - 只需要一次性读取当前任务文件夹下的所有CSV文件并显示
        
        Args:
            data_directory: 数据目录路径（通常从 curvemission 获取）
        
        Returns:
            bool: 是否成功启动加载任务
        """
        try:
            if not data_directory or not os.path.exists(data_directory):
                return False
            
            # 切换到历史模式（不限制数据点数量）
            self.setCurveLoadMode('history')
            
            # 查找所有CSV文件
            # print(f"\n🔍 [曲线加载] ==================== 开始加载 ====================")
            # print(f"🔍 [曲线加载] 扫描目录: {data_directory}")
            # print(f"🔍 [曲线加载] 目录是否存在: {os.path.exists(data_directory)}")
            
            if not os.path.exists(data_directory):
                # print(f"❌ [曲线加载] 目录不存在: {data_directory}")
                return False
            
            # 列出目录中的所有文件
            all_files = os.listdir(data_directory)
            # print(f"🔍 [曲线加载] 目录中所有文件: {all_files}")
            
            csv_files = [f for f in all_files if f.endswith('.csv')]
            # print(f"🔍 [曲线加载] 找到 {len(csv_files)} 个CSV文件: {csv_files}")
            
            if not csv_files:
                # print(f"⚠️ [曲线加载] 未找到CSV文件")
                return False
            
            # 检查是否需要显示进度条
            # 触发条件：CSV文件数量 > 1 或 单个CSV文件大小 > 8MB
            show_progress = False
            
            if len(csv_files) > 1:
                # 条件1：多个CSV文件
                show_progress = True
            else:
                # 条件2：单个CSV文件大小超过8MB
                csv_path = os.path.join(data_directory, csv_files[0])
                file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
                if file_size_mb > 8:
                    show_progress = True
            
            # 🔥 使用全局DialogManager创建进度对话框（仅在需要时）
            progress_dialog = None
            if show_progress:
                from widgets.style_manager import DialogManager
                progress_dialog = DialogManager.create_progress_dialog(
                    parent=None,  # 全局进度条，无父窗口
                    title="曲线数据加载进度",
                    label_text="正在加载曲线数据...",
                    icon_name="动态曲线",
                    cancelable=False  # 不可取消
                )
                progress_dialog.setWindowModality(QtCore.Qt.ApplicationModal)
                progress_dialog.setMinimumWidth(400)
                progress_dialog.show()
                # 🔥 强制刷新UI，确保进度条立即显示
                QtWidgets.QApplication.processEvents()
                # print(f"✅ [进度条] 已显示进度对话框")
            
            # 创建并启动后台加载线程
            # print(f"🧵 [曲线加载] 创建后台加载线程...")
            self._load_thread = CurveDataLoadThread(
                data_directory=data_directory,
                csv_files=csv_files,
                handler=self
            )
            # print(f"🧵 [曲线加载] 后台线程已创建")
            
            # 连接信号（使用Qt.QueuedConnection确保跨线程安全）
            self._load_thread.progress_updated.connect(
                lambda value, text: self._onLoadProgress(progress_dialog, value, text),
                QtCore.Qt.QueuedConnection
            )
            self._load_thread.file_loaded.connect(
                lambda channel_id, channel_name, window_name, color, data_points: 
                    self._onFileLoaded(channel_id, channel_name, window_name, color, data_points),
                QtCore.Qt.QueuedConnection
            )
            self._load_thread.load_finished.connect(
                lambda success, count: self._onLoadFinished(progress_dialog, success, count),
                QtCore.Qt.QueuedConnection
            )
            
            # 启动线程
            # print(f"🚀 [曲线加载] 启动后台线程...")
            self._load_thread.start()
            # print(f"✅ [曲线数据加载] 后台加载线程已启动")
            # print(f"🔍 [曲线加载] ==================== 加载流程启动完成 ====================\n")
            
            return True
            
        except Exception as e:
            # print(f"⚠️ [曲线数据加载] 启动失败: {e}")
            return False
    
    def _onLoadProgress(self, progress_dialog, value, text):
        """处理加载进度更新"""
        if progress_dialog:
            progress_dialog.setValue(value)
            progress_dialog.setLabelText(text)
            QtWidgets.QApplication.processEvents()
    
    def _onFileLoaded(self, channel_id, channel_name, window_name, color, data_points):
        """处理单个文件加载完成"""
        # print(f"📥 [文件加载] 收到文件数据:")
        # print(f"   - channel_id: {channel_id}")
        # print(f"   - channel_name: {channel_name}")
        # print(f"   - window_name: {window_name}")
        # print(f"   - 数据点数量: {len(data_points)}")
        
        # 添加通道（如果不存在）
        if channel_id not in self.channel_data:
            # print(f"   - 添加新通道: {channel_id}")
            self.addChannelData(
                channel_id=channel_id,
                channel_name=channel_name,
                window_name=window_name,
                color=color
            )
        else:
            pass

        # 批量更新曲线数据
        self.updateCurveData(channel_id, data_points)
    
    def _onLoadFinished(self, progress_dialog, success, count):
        """处理加载完成"""
        if progress_dialog:
            # 🔥 设置进度为100%，确保用户看到完成状态
            progress_dialog.setValue(100)
            QtWidgets.QApplication.processEvents()
            
            # 🔥 延迟关闭进度条，确保用户能看到（至少显示500ms）
            from qtpy.QtCore import QTimer
            QTimer.singleShot(500, progress_dialog.close)
            # print(f"✅ [进度条] 将在500ms后关闭")
        
        if success:
            # print(f"✅ [曲线数据加载] 成功加载 {count} 个文件")
            # 🔥 设置历史数据已加载标志
            self._history_data_loaded = True
            
            # 🔥 历史数据加载完成后，确保显示全部数据范围
            if self.curve_load_mode == 'history' and self.curve_panel:
                # 找出所有通道的最小和最大时间值、最大数值
                min_time = None
                max_time = None
                max_value = 0
                
                for channel_id, channel in self.channel_data.items():
                    if len(channel['time']) > 0:
                        channel_min_time = min(channel['time'])
                        channel_max_time = max(channel['time'])
                        if min_time is None or channel_min_time < min_time:
                            min_time = channel_min_time
                        if max_time is None or channel_max_time > max_time:
                            max_time = channel_max_time
                    
                    if len(channel['value']) > 0:
                        channel_max_value = max(channel['value'])
                        max_value = max(max_value, channel_max_value)
                
                # 如果有数据，设置视图显示全部范围
                if min_time is not None and max_time is not None:
                    self.curve_panel.setViewAll(min_time, max_time, max_value)
        else:
            pass

    def _readCSVFile(self, csv_path):
        """
        读取CSV文件并解析为数据点列表
        
        Args:
            csv_path: CSV文件路径
        
        Returns:
            list: 数据点列表 [{'timestamp': float, 'height_mm': float}, ...]
        """
        data_points = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析CSV行：时间戳 高度值
                    parts = line.split()
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        height_str = parts[1]
                        
                        try:
                            # 解析时间戳
                            timestamp = datetime.datetime.strptime(
                                timestamp_str, "%Y-%m-%d-%H:%M:%S.%f"
                            ).timestamp()
                            
                            # 解析高度（支持小数，精度0.1mm）
                            height_mm = float(height_str)
                            
                            # 创建数据点
                            point = {
                                'timestamp': timestamp,
                                'height_mm': height_mm
                            }
                            
                            data_points.append(point)
                            
                        except ValueError:
                            pass  # 忽略解析错误的行
            
            return data_points
            
        except Exception as e:
            return []
    
    # ==================== 曲线数据回调 ====================
    
    def _onCurveDataUpdated(self, csv_filepath: str, area_name: str, area_idx: int, new_points: list):
        """
        曲线数据更新回调（从曲线线程接收CSV文件中的新数据）
        
        ⚠️ 注意：此方法在工作线程中调用，不能直接操作UI对象！
        
        Args:
            csv_filepath: CSV文件的完整路径
            area_name: CSV文件名（不含扩展名），如 "侧门液位检测_区域1"（直接作为曲线标识）
            area_idx: ROI索引（0, 1, 2...）
            new_points: 新增的数据点列表
                [
                    {'timestamp': 1730123456.123, 'height_mm': 145, 'area_name': '侧门液位检测_区域1', ...},
                    {'timestamp': 1730123456.223, 'height_mm': 146, 'area_name': '侧门液位检测_区域1', ...},
                    ...
                ]
        """
        try:
            # 直接使用 area_name 作为曲线标识（不需要推断 channel_id）
            # 曲线标签就是CSV文件名
            curve_id = area_name
            
            # 🔥 发射线程安全的信号，让主线程处理UI更新
            self.curveDataReceived.emit(curve_id, area_idx, new_points)
        except Exception as e:
            import traceback
            # print(f"⚠️ [曲线数据回调] 发射信号失败: {e}")
            traceback.print_exc()
    
    def _processCurveDataInMainThread(self, curve_id: str, area_idx: int, new_points: list):
        """
        在主线程中处理曲线数据更新（线程安全）
        
        ✅ 此方法在主线程（UI线程）中调用，可以安全地操作UI对象
        
        Args:
            curve_id: 曲线标识（CSV文件名，如 "侧门液位检测_区域1"）
            area_idx: ROI索引（0, 1, 2...）
            new_points: 新增的数据点列表
        """
        try:
            # 🔥 检查是否在曲线模式（防止UI对象生命周期问题）
            if hasattr(self, 'is_curve_mode_active'):
                if not self.is_curve_mode_active:
                    # 当前不是曲线模式，不更新UI（静默跳过）
                    return
            
            # 🔥 检查全局曲线线程是否运行中
            if hasattr(self, 'thread_manager'):
                try:
                    from handlers.videopage.thread_manager.threads.curve_thread import CurveThread as CT
                    if not CT.is_running():
                        # 全局曲线线程已停止，不更新UI（静默跳过）
                        return
                except ImportError:
                    # 如果导入失败，继续处理
                    pass
            
            # 检查曲线面板是否存在（兼容两种命名方式）
            curve_panel_obj = getattr(self, 'curvePanel', None) or getattr(self, 'curve_panel', None)
            if curve_panel_obj is None:
                # print(f"⚠️ [曲线数据处理-主线程] 曲线面板不存在，跳过更新")
                return
            
            # 如果没有数据点，直接返回
            if not new_points:
                # print(f"⚠️ [曲线数据处理-主线程] 数据点为空，跳过更新")
                return
            
            # 从第一个数据点获取区域名称（作为曲线标签）
            first_point = new_points[0]
            area_name = first_point.get('area_name', curve_id)
            
            # 直接使用 curve_id（CSV文件名）作为曲线标识
            # 曲线标签就是CSV文件名，不需要推断channel_id
            
            # 🔥 使用新架构：通过 CurvePanelHandler 管理数据
            # 自动添加通道（如果不存在）
            if curve_id not in self.channel_data:
                # 分配颜色（循环使用预设颜色）
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                         '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                color_index = len(self.channel_data) % len(colors)
                color = colors[color_index]
                
                # 🔥 在主线程中安全地添加通道（通过Handler）
                # 使用 area_name 作为通道名称和窗口名称（曲线标签就是CSV文件名）
                self.addChannelData(
                    channel_id=curve_id,  # 使用CSV文件名作为曲线标识
                    channel_name=area_name,  # 曲线标签（CSV文件名）
                    window_name=area_name,  # 窗口名称（CSV文件名）
                    color=color
                )
            
            # 🔥 批量更新曲线（通过Handler处理业务逻辑）
            # 注意：new_points 已经是正确的格式 [{'timestamp': float, 'height_mm': int}, ...]
            if new_points:
                self.updateCurveData(curve_id, new_points)
            
        except Exception as e:
            # 静默处理错误，避免干扰主线程
            import traceback
            # print(f"⚠️ [曲线数据更新-主线程] 错误: {e}")
            traceback.print_exc()
    
    def setCurveLoadMode(self, mode: str):
        """
        设置曲线加载模式
        
        Args:
            mode: 加载模式
                - 'realtime'：实时检测模式，限制数据点为3000个（滚动窗口）
                - 'history'：历史回放模式，加载所有数据点，不做限制
        """
        if mode not in ('realtime', 'history'):
            # print(f"⚠️ [曲线加载模式] 无效的模式: {mode}，使用默认模式 'realtime'")
            mode = 'realtime'
        
        self.curve_load_mode = mode
        # 🔥 切换模式时重置历史数据加载标志
        self._history_data_loaded = False
        # print(f"✅ [曲线加载模式] 已切换到: {mode}")
    
    def getCurveLoadMode(self) -> str:
        """
        获取当前曲线加载模式
        
        Returns:
            str: 当前加载模式 ('realtime' 或 'history')
        """
        return self.curve_load_mode
            
    def isHistoryDataLoaded(self) -> bool:
        """
        检查历史数据是否已加载
        
        Returns:
            bool: True 如果已加载，False 否则
        """
        return self._history_data_loaded