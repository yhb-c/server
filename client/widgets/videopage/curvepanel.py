# -*- coding: utf-8 -*-

"""
高性能曲线面板 - PyQtGraph实现

只负责UI控件设计和发送信号，业务逻辑由handler处理
提供实时曲线绘制、多通道管理等功能
"""

import datetime
import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

import pyqtgraph as pg

# 导入全局字体管理器和响应式布局
from ..style_manager import FontManager
from ..responsive_layout import ResponsiveLayout, scale_w, scale_h


# ============================================================================
# 自定义按钮类：返回按钮（任何情况不得禁用）
# ============================================================================

class AlwaysEnabledBackButton(QtWidgets.QPushButton):
    """
    始终启用的返回按钮
    
    重写 setEnabled 和 setDisabled 方法，确保按钮始终处于启用状态
    无论外部代码如何调用 setEnabled(False) 或 setDisabled(True)，按钮都会保持启用
    """
    
    def __init__(self, parent=None):
        """初始化按钮，确保始终启用"""
        super().__init__(parent)
        # 初始状态设置为启用
        super(AlwaysEnabledBackButton, self).setEnabled(True)
    
    def setEnabled(self, enabled):
        """
        重写 setEnabled 方法，强制保持启用状态
        
        Args:
            enabled: 是否启用（此参数会被忽略，按钮始终启用）
        """
        # 🔥 强制始终启用，忽略传入的参数
        # 直接调用父类的 setEnabled(True)，绕过重写
        super(AlwaysEnabledBackButton, self).setEnabled(True)
    
    def setDisabled(self, disabled):
        """
        重写 setDisabled 方法，确保按钮不会被禁用
        
        Args:
            disabled: 是否禁用（此参数会被忽略，按钮始终启用）
        """
        # 🔥 即使调用 setDisabled(True)，也保持启用
        # 直接调用父类的 setEnabled(True)，绕过重写
        super(AlwaysEnabledBackButton, self).setEnabled(True)


# 导入图标工具（支持相对导入和独立运行）
try:
    # 从父目录（widgets）导入
    from ..style_manager import newIcon
except (ImportError, ValueError):
    # 独立运行时的处理
    import sys
    import os.path as osp
    # 添加父目录到路径
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    try:
        from style_manager import newIcon
    except ImportError:
        def newIcon(icon): 
            return QtGui.QIcon()


class CurvePanel(QtWidgets.QWidget):
    """
    高性能曲线面板
    
    基于PyQtGraph实现的实时曲线显示组件
    只负责UI控件设计和发送信号，业务逻辑由handler处理
    支持多通道、数据保存、自动刷新等功能
    """
    
    # 自定义信号 - 用于与handler交互
    backClicked = QtCore.Signal()  # 返回按钮点击信号
    missionFolderChanged = QtCore.Signal(str)  # 任务文件夹选择变化信号（传递完整路径）
    refreshMissionListRequested = QtCore.Signal()  # 刷新任务列表请求信号
    # 时间轴范围变化信号：(starttime, endtime) - Unix时间戳
    timeAxisRangeChanged = QtCore.Signal(float, float)
    
    def __init__(self, parent=None):
        super(CurvePanel, self).__init__(parent)
        self._parent = parent
        
        # 检查PyQtGraph是否可用
        if pg is None:
            raise ImportError("PyQtGraph is required for CurvePanel")
        
        #  UI状态数据（只用于UI显示，不存储业务数据）
        self.current_channel = None  # 当前显示的通道ID
        self.curve_items = {}  # {channel_id: PlotDataItem} - 只存储曲线UI对象
        
        # 时间轴显示范围变量
        self.starttime = None  # 时间轴起始时刻（Unix时间戳）
        self.endtime = None    # 时间轴结束时刻（Unix时间戳）
        
        # 颜色配置
        self.channel_colors = [
            '#1f77b4',  # 蓝色
            '#ff7f0e',  # 橙色
            '#2ca02c',  # 绿色
            '#d62728',  # 红色
            '#9467bd',  # 紫色
            '#8c564b',  # 棕色
            '#e377c2',  # 粉色
            '#7f7f7f',  # 灰色
        ]
        
        # X轴位置修复的节流计数器（避免频繁调用）
        self._fix_x_counter = 0
        
        self._initUI()
        self._connectSignals()
        
        # 初始化后固定X轴位置
        QtCore.QTimer.singleShot(100, self._fixXAxisPosition)
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # === 顶部工具栏 ===
        self._createToolbar()
        main_layout.addWidget(self.toolbar)
        
        # === 中间：绘图区域 ===
        self._createPlotArea()
        main_layout.addWidget(self.plot_widget, stretch=1)
        
    
    def _createToolbar(self):
        """创建顶部工具栏"""
        self.toolbar = QtWidgets.QWidget()
        toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        
        # 按钮样式（与通道面板一致）
        button_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: palette(light);
                border: 1px solid palette(mid);
            }
            QPushButton:pressed {
                background-color: palette(midlight);
            }
            QPushButton:disabled {
                opacity: 0.5;
            }
        """
        
        # 返回按钮（左侧，使用"返回"图标）
        # 🔥 返回按钮任何情况不得禁用，始终保持启用状态
        # 使用自定义的 AlwaysEnabledBackButton 类，确保按钮始终启用
        self.btn_back = AlwaysEnabledBackButton()
        self.btn_back.setIcon(newIcon("返回"))
        # 🔥 响应式按钮尺寸
        icon_size = scale_w(24)
        btn_size = scale_w(35)
        
        self.btn_back.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.btn_back.setToolTip("返回视频监控")
        self.btn_back.setStyleSheet(button_style)
        self.btn_back.setFixedSize(btn_size, btn_size)
        self.btn_back.setEnabled(True)  # 确保始终启用（即使调用也会保持启用）
        self.btn_back.setObjectName("btn_back")  # 设置对象名称，便于事件过滤器识别
        toolbar_layout.addWidget(self.btn_back)
        
        toolbar_layout.addSpacing(10)
        
        # 🔥 模式标签已隐藏（用户要求删除左侧布局索引文本标签）
        # 保留变量以避免其他代码引用错误，但不添加到布局中
        self.mode_label = QtWidgets.QLabel("历史回放")
        self.mode_label.setStyleSheet("font-weight: bold; padding: 2px 8px;")
        
        # 应用全局字体管理
        try:
            from widgets.style_manager import FontManager
            if FontManager:
                FontManager.applyToWidget(self.mode_label)
        except ImportError:
            pass
        
        # toolbar_layout.addWidget(self.mode_label)  # 🔥 已注释，不显示模式标签
        
        # 任务文件夹选择（下拉选项框）- 响应式布局
        self.curvemission = QtWidgets.QComboBox()
        ResponsiveLayout.apply_to_widget(self.curvemission, min_width=250, max_width=350)
        self.curvemission.setPlaceholderText("请选择任务")
        self.curvemission.setToolTip("选择要查看曲线的任务")
        toolbar_layout.addWidget(self.curvemission)
        
        toolbar_layout.addSpacing(10)
        
        # 重置视图按钮
        self.btn_reset_view = QtWidgets.QPushButton("重置视图")
        toolbar_layout.addWidget(self.btn_reset_view)
        
        toolbar_layout.addSpacing(20)
        
        # 自动跟随开关
        self.chk_auto_follow = QtWidgets.QCheckBox("自动跟随")
        self.chk_auto_follow.setChecked(True)
        self.chk_auto_follow.setToolTip("自动滚动显示最新数据")
        toolbar_layout.addWidget(self.chk_auto_follow)
        
        # 自动调整Y轴
        self.chk_auto_y = QtWidgets.QCheckBox("自动Y轴")
        self.chk_auto_y.setChecked(False)
        self.chk_auto_y.setToolTip("自动调整Y轴范围以适应数据")
        toolbar_layout.addWidget(self.chk_auto_y)
        
        toolbar_layout.addSpacing(20)
        
        # 安全上限输入框
        toolbar_layout.addWidget(QtWidgets.QLabel("安全上限:"))
        self.spn_upper_limit = QtWidgets.QDoubleSpinBox()
        self.spn_upper_limit.setRange(0.0, 23.0)
        self.spn_upper_limit.setValue(20.0)
        self.spn_upper_limit.setSuffix("mm")
        self.spn_upper_limit.setDecimals(1)
        self.spn_upper_limit.setSingleStep(0.5)  # 设置步长为0.5mm
        self.spn_upper_limit.setFixedWidth(scale_w(85))  # 🔥 响应式宽度
        self.spn_upper_limit.setToolTip("设置安全上限")
        toolbar_layout.addWidget(self.spn_upper_limit)
        
        toolbar_layout.addSpacing(10)
        
        # 安全下限输入框
        toolbar_layout.addWidget(QtWidgets.QLabel("安全下限:"))
        self.spn_lower_limit = QtWidgets.QDoubleSpinBox()
        self.spn_lower_limit.setRange(0.0, 23.0)
        self.spn_lower_limit.setValue(0.0)
        self.spn_lower_limit.setSuffix("mm")
        self.spn_lower_limit.setDecimals(1)
        self.spn_lower_limit.setSingleStep(0.5)  # 设置步长为0.5mm
        self.spn_lower_limit.setFixedWidth(scale_w(85))  # 🔥 响应式宽度
        self.spn_lower_limit.setToolTip("设置安全下限")
        toolbar_layout.addWidget(self.spn_lower_limit)
        
        toolbar_layout.addStretch()
    
    def _createPlotArea(self):
        """创建绘图区域"""
        #  配置PyQtGraph全局设置（启用GPU加速）
        pg.setConfigOptions(
            antialias=True,      # 抗锯齿（GPU加速）
            useOpenGL=True,      # 全局启用OpenGL
            enableExperimental=False  # 使用稳定版本
        )
        
        # 创建绘图窗口
        self.plot_widget = pg.PlotWidget()
        
        # 设置绘图区域的布局边距（消除左侧空白）
        self.plot_widget.getPlotItem().getViewBox().setContentsMargins(0, 0, 0, 0)
        
        # 设置背景和网格
        self.plot_widget.setBackground('w')  # 白色背景
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 设置坐标轴标签（黑色字体）
        # 左侧Y轴不显示标签（标签将显示在顶部）
        self.plot_widget.setLabel('bottom', '时间', color='k')
        
        # 在左上角添加"液位高度(mm)"标签
        self.height_label = pg.TextItem(text='液位高度(mm)', color='k', anchor=(0, 0))
        self.plot_widget.addItem(self.height_label)
        # 标签位置将在视图范围改变时自动更新到左上角
        
        # 设置X轴为时间轴（自定义格式：时:分:秒）
        class CustomDateAxis(pg.DateAxisItem):
            def tickStrings(self, values, scale, spacing):
                """自定义时间格式显示：根据时间跨度选择合适的格式"""
                strings = []
                for value in values:
                    try:
                        if value <= 0:
                            strings.append('')
                            continue
                        dt = datetime.datetime.fromtimestamp(value)
                        # 根据时间跨度（spacing）选择不同的显示格式
                        # spacing 单位是秒
                        if spacing < 1:  # 小于1秒，显示毫秒
                            strings.append(dt.strftime('%H:%M:%S.%f')[:-3])
                        elif spacing < 60:  # 小于1分钟，显示时分秒
                            strings.append(dt.strftime('%H:%M:%S'))
                        elif spacing < 3600:  # 小于1小时，显示时分
                            strings.append(dt.strftime('%H:%M'))
                        elif spacing < 86400:  # 小于24小时，显示时分
                            strings.append(dt.strftime('%H:%M'))
                        else:  # 24小时或更长，显示月日时分
                            strings.append(dt.strftime('%m-%d %H:%M'))
                    except (ValueError, OSError, OverflowError) as e:
                        strings.append('')
                return strings
        
        axis = CustomDateAxis(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': axis})
        
        # ====== 固定原点位置方案 ======
        # 获取PlotItem，用于设置固定布局
        plot_item = self.plot_widget.getPlotItem()
        
        # 设置固定的坐标轴高度和宽度，防止自动调整
        bottom_axis = plot_item.getAxis('bottom')
        left_axis = plot_item.getAxis('left')
        
        # 固定X轴（底部）的高度为40像素，减少5像素使其上移
        bottom_axis.setHeight(35)  # 默认是40，减少到35使其上移5像素
        
        # 固定Y轴（左侧）的宽度，减小宽度以消除左下角空白
        left_axis.setWidth(38)  # 设置为38像素，刚好容纳两位数字和刻度线
        
        # 设置坐标轴颜色为黑色
        bottom_axis.setPen(pg.mkPen(color='k', width=1))
        left_axis.setPen(pg.mkPen(color='k', width=1))
        bottom_axis.setTextPen(pg.mkPen(color='k'))
        left_axis.setTextPen(pg.mkPen(color='k'))
        
        # 禁用坐标轴的自动调整
        bottom_axis.setStyle(autoExpandTextSpace=False, tickTextOffset=-5)
        left_axis.setStyle(autoExpandTextSpace=False)
        
        # 添加图例（右上角）
        # offset: 相对于绘图区域右上角的偏移 (x, y)
        # 负数x向左偏移，正数y向下偏移
        self.legend = self.plot_widget.addLegend(offset=(-10, 10))
        
        # 设置图例样式
        self.legend.setParentItem(self.plot_widget.getPlotItem())
        # 设置图例位置锚点为右上角
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))
        
        # 🔥 应用全局字体管理
        self._legend_font = FontManager.getMediumFont()  # 使用中等字体 (12pt)
        
        # 设置图例标签颜色和字体
        try:
            self.legend.setLabelTextColor(pg.mkColor('k'))
        except AttributeError:
            self.legend.opts['labelTextColor'] = pg.mkColor('k')
        
        # 🔥 设置图例的字体大小和对齐方式
        # PyQtGraph 图例使用 LabelItem，需要设置其样式
        try:
            # 设置图例标签的字体
            self.legend.opts['labelTextSize'] = f'{self._legend_font.pointSize()}pt'
            # 设置图例项的垂直对齐和间距
            self.legend.setColumnSpacing(10)  # 图例符号和文本之间的间距
            self.legend.setRowSpacing(5)      # 图例行之间的间距
        except:
            pass
        
        # 添加安全上下限水平虚线
        self.upper_limit_line = pg.InfiniteLine(
            pos=20.0, 
            angle=0,  # 水平线
            pen=pg.mkPen(color='r', width=2, style=Qt.DashLine),
            movable=False
        )
        self.plot_widget.addItem(self.upper_limit_line)
        
        self.lower_limit_line = pg.InfiniteLine(
            pos=0.0, 
            angle=0,  # 水平线
            pen=pg.mkPen(color='r', width=2, style=Qt.DashLine),
            movable=False
        )
        self.plot_widget.addItem(self.lower_limit_line)
        
        # 启用鼠标交互（X轴和Y轴都允许）
        self.plot_widget.setMouseEnabled(x=True, y=True)
        
        # 设置Y轴初始范围从0到23
        self.plot_widget.setYRange(0, 23, padding=0)
        
        # 禁用自动范围的padding
        self.plot_widget.getViewBox().setDefaultPadding(0)
        
        # 固定X轴位置（需要在后续设置完成后再调用，所以这里先不调用）
        
        # 获取ViewBox以便后续控制
        self.view_box = self.plot_widget.getViewBox()
        
        # 设置ViewBox的拖动和缩放模式
        self.view_box.setMouseMode(pg.ViewBox.PanMode)  # 设置为平移模式
        
        # 限制Y轴范围：最小值0，最大值23
        self.view_box.setLimits(yMin=0, yMax=23)
        
        # 连接视图范围改变信号
        self.view_box.sigRangeChanged.connect(self._onViewRangeChanged)
        
        # 立即应用固定设置（确保初始化时就生效）
        QtCore.QTimer.singleShot(0, self._fixXAxisPosition)
        
        # 初始化"液位高度(mm)"标签位置
        QtCore.QTimer.singleShot(100, self._updateHeightLabelPosition)
        
        # #  显式启用OpenGL并记录日志
        # try:
        #     self.plot_widget.useOpenGL(True)
        #     print(" [曲线面板] GPU加速已启用 (OpenGL)")
        #     print("   - GPU型号: RTX 4070")
        #     print("   - 预期性能提升: 2-4x")
            
        #     # 验证OpenGL视口
        #     try:
        #         from PyQt5.QtOpenGL import QGLWidget
        #         viewport = self.plot_widget.viewport()
        #         if isinstance(viewport, QGLWidget):
        #             print("   - OpenGL视口:  已激活")
        #         else:
        #             print(f"   - OpenGL视口: ️ 未激活（当前: {type(viewport).__name__}）")
        #     except ImportError:
        #         print("   - OpenGL验证: ️ PyQt5.QtOpenGL未安装")
                
        # except Exception as e:
        #     print(f" [曲线面板] GPU加速启用失败: {e}")
        #     print("️ [曲线面板] 回退到CPU软件渲染")
    
    def _connectSignals(self):
        """连接信号槽"""
        self.btn_back.clicked.connect(self._onBackClicked)
        self.btn_reset_view.clicked.connect(self._onResetView)
        
        # 连接任务选择下拉框的信号
        self.curvemission.currentTextChanged.connect(self._onMissionSelectionChanged)

        self.chk_auto_follow.stateChanged.connect(self._onAutoFollowToggled)
        self.chk_auto_y.stateChanged.connect(self._onAutoYToggled)
        self.spn_upper_limit.valueChanged.connect(self._onUpperLimitChanged)
        self.spn_lower_limit.valueChanged.connect(self._onLowerLimitChanged)
    
    # ========== 公共方法 ==========
    
    def updateMissionFolderList(self, mission_folders):
        """
        更新任务文件夹列表到下拉框
        
        Args:
            mission_folders: 任务文件夹列表 [{'name': str, 'path': str}, ...]
        """
        # 保存当前选中的任务
        current_text = self.curvemission.currentText()
        
        # 清空下拉框
        self.curvemission.clear()
        
        # 添加默认选项
        self.curvemission.addItem("请选择任务")
        
        # 添加任务文件夹到下拉框
        for folder in mission_folders:
            self.curvemission.addItem(folder['name'])
        
        # 恢复之前的选择（如果存在）
        if current_text and current_text != "请选择任务":
            index = self.curvemission.findText(current_text)
            if index >= 0:
                self.curvemission.setCurrentIndex(index)
    
    def setFolderName(self, folder_path):
        """
        设置当前任务文件夹（在下拉框中选中对应的任务）
        
        Args:
            folder_path: 文件夹完整路径
        """
        import os
        
        if not folder_path or folder_path == "0000":
            # 选中默认选项
            self.curvemission.setCurrentIndex(0)
            return
        
        # 只显示文件夹名称（路径的最后一部分）
        folder_name = os.path.basename(os.path.normpath(str(folder_path)))
        
        # 如果提取的名称为空，使用原始路径
        if not folder_name:
            folder_name = str(folder_path)
        
        # 在下拉框中查找并选中对应的任务
        index = self.curvemission.findText(folder_name)
        if index >= 0:
            self.curvemission.setCurrentIndex(index)
        else:
            # 如果找不到，选中默认选项
            self.curvemission.setCurrentIndex(0)
    
    def setMissionFromTaskName(self, task_name):
        """
        从任务名称设置 curvemission（来源1和来源2使用）
        
        Args:
            task_name: 任务名称（如 "1_1", "32_23"）
        """
        if not task_name or task_name == "未分配任务" or task_name == "None":
            # 选中默认选项
            self.curvemission.setCurrentIndex(0)
            return False
        
        # 在下拉框中查找并选中对应的任务
        index = self.curvemission.findText(task_name)
        if index >= 0:
            self.curvemission.setCurrentIndex(index)
            return True
        else:
            # 如果找不到，选中默认选项
            self.curvemission.setCurrentIndex(0)
            return False
    
    def addChannel(self, channel_id, channel_name=None, window_name=None, color=None):
        """
        添加一个通道（UI创建）
        
        Args:
            channel_id: 通道唯一ID
            channel_name: 通道名称（可选）
            window_name: 检测窗口名称（可选）
            color: 曲线颜色（可选）
        """
        if channel_id in self.curve_items:
            return
        
        # 默认名称
        if channel_name is None:
            channel_name = channel_id
        
        if window_name is None:
            window_name = "默认窗口"
        
        # 图例显示：仅显示检测窗口名
        legend_name = window_name
        
        # 分配颜色
        if color is None:
            color_index = len(self.curve_items) % len(self.channel_colors)
            color = self.channel_colors[color_index]
        
        # 创建曲线UI对象（圆润样式）
        pen = pg.mkPen(
            color=color, 
            width=1,
            style=Qt.SolidLine,
            capStyle=Qt.RoundCap,   # 圆形端点
            joinStyle=Qt.RoundJoin  # 圆角连接
        )
        curve = self.plot_widget.plot(
            name=legend_name,
            pen=pen,
            symbol=None,        #  禁用散点符号（避免ScatterPlotItem错误，提升性能）
            antialias=True,     # 启用抗锯齿（GPU加速）
            connect='finite',   # 跳过NaN/Inf值，只连接有效数据点（避免形成填充区域）
            clipToView=True,    #  只渲染可见区域（GPU优化）
            skipFiniteCheck=False  # 启用有限性检查
        )
        
        # 🔥 应用全局字体到新添加的图例项，并设置垂直对齐
        try:
            # 获取刚添加的图例项
            for sample, label in self.legend.items:
                if label is not None and hasattr(label, 'setText'):
                    # 设置字体
                    label_text = label.toPlainText() if hasattr(label, 'toPlainText') else str(label.text)
                    # 使用 HTML 格式设置字体
                    html_text = f'<span style="font-family: {self._legend_font.family()}; font-size: {self._legend_font.pointSize()}pt;">{label_text}</span>'
                    label.setHtml(html_text)
                    
                # 设置图例项的垂直对齐（sample是线条符号，label是文本）
                if sample is not None and hasattr(sample, 'setParentItem'):
                    # 调整sample（线条符号）的垂直位置，使其与文本居中对齐
                    try:
                        # 获取label的高度
                        if label is not None and hasattr(label, 'boundingRect'):
                            label_height = label.boundingRect().height()
                            # 将sample垂直居中
                            sample.setPos(sample.pos().x(), label_height / 2 - 5)
                    except:
                        pass
        except Exception as e:
            # 如果设置失败，静默忽略
            pass
        
        # 只存储UI对象
        self.curve_items[channel_id] = curve
        
        # 如果是第一个通道，自动选中
        if len(self.curve_items) == 1:
            self.current_channel = channel_id
    
    def updateCurveDisplay(self, channel_id, time_data, value_data):
        """
        更新曲线显示（UI更新）
        
        Args:
            channel_id: 通道ID
            time_data: 时间数组（已处理的Unix时间戳列表）
            value_data: 数值数组
        
        注意：此方法只负责UI更新，数据处理由handler完成
        """
        if channel_id not in self.curve_items:
            print(f"⚠️ [UI更新] 通道不存在: {channel_id}")
            return
        
        # 🔥 数据验证和调试
        if not time_data or not value_data:
            print(f"⚠️ [UI更新] 数据为空: channel_id={channel_id}, time_data长度={len(time_data) if time_data else 0}, value_data长度={len(value_data) if value_data else 0}")
            # 即使数据为空，也调用setData清空显示
            curve = self.curve_items[channel_id]
            curve.setData([], [])
            return
        
        if len(time_data) != len(value_data):
            print(f"⚠️ [UI更新] 数据长度不匹配: channel_id={channel_id}, time_data长度={len(time_data)}, value_data长度={len(value_data)}")
            return
        
        # 🔥 转换为numpy数组（PyQtGraph需要numpy数组）
        try:
            time_array = np.array(time_data, dtype=np.float64)
            value_array = np.array(value_data, dtype=np.float64)
            
            # 🔥 关键修复：按时间排序，避免曲线头尾相连
            # 如果时间戳不是严格递增的，PyQtGraph会按数组顺序连接点
            # 导致最后一个点连回到早期的点，形成闭环
            sort_indices = np.argsort(time_array)
            time_array = time_array[sort_indices]
            value_array = value_array[sort_indices]
            
        except Exception as e:
            print(f"⚠️ [UI更新] 数据转换失败: channel_id={channel_id}, 错误={e}")
            return
        
        # 🔥 检查有效数据点数量（排除NaN和Inf）
        valid_mask = np.isfinite(time_array) & np.isfinite(value_array)
        valid_count = np.sum(valid_mask)
        
        if valid_count == 0:
            print(f"⚠️ [UI更新] 没有有效数据点: channel_id={channel_id}, 总数据点={len(time_array)}, 有效数据点=0")
            # 即使没有有效数据，也调用setData清空显示
            curve = self.curve_items[channel_id]
            curve.setData([], [])
            return
        
        #  只更新UI显示
        curve = self.curve_items[channel_id]
        curve.setData(time_array, value_array)
        
        # 动态调整X轴范围
        self._updateXRange()
        
        # 如果启用了自动Y轴，检查是否需要调整Y轴范围
        if self.chk_auto_y.isChecked():
            self._updateYRange()
        
        # 固定X轴位置（使用节流：每10次更新才调用一次）
        self._fix_x_counter += 1
        if self._fix_x_counter >= 10:
            self._fixXAxisPosition()
            self._fix_x_counter = 0
    
    def removeChannel(self, channel_id):
        """移除通道（UI移除）"""
        if channel_id not in self.curve_items:
            return
        
        # 移除曲线UI对象
        curve = self.curve_items[channel_id]
        self.plot_widget.removeItem(curve)
        
        # 移除UI对象引用
        del self.curve_items[channel_id]
    
    def clearAllChannels(self):
        """
        清除所有通道和数据（用于切换回默认模式时重置曲线面板）
        """
        # 移除所有曲线UI对象
        for channel_id, curve in list(self.curve_items.items()):
            self.plot_widget.removeItem(curve)
        
        # 清空所有UI对象
        self.curve_items.clear()
        
        # 重置当前通道
        self.current_channel = None
        
        # 重置文本框显示
        self.txt_folder_name.setText("未选择任务")
    
    
    def setYRange(self, min_value, max_value):
        """
        设置Y轴范围
        
        Args:
            min_value: Y轴最小值（会被限制为>=0）
            max_value: Y轴最大值
        """
        # 确保最小值不小于0
        min_value = max(0, min_value)
        self.plot_widget.setYRange(min_value, max_value, padding=0)
        # 固定X轴位置
        self._fixXAxisPosition()
    
    def setSafetyLimits(self, upper_limit, lower_limit):
        """
        设置安全上下限
        
        Args:
            upper_limit: 安全上限值（mm）
            lower_limit: 安全下限值（mm）
        """
        # 阻止信号触发
        self.spn_upper_limit.blockSignals(True)
        self.spn_lower_limit.blockSignals(True)
        
        # 设置输入框的值
        self.spn_upper_limit.setValue(upper_limit)
        self.spn_lower_limit.setValue(lower_limit)
        
        # 更新限值线位置
        if hasattr(self, 'upper_limit_line'):
            self.upper_limit_line.setValue(upper_limit)
        if hasattr(self, 'lower_limit_line'):
            self.lower_limit_line.setValue(lower_limit)
        
        # 恢复信号
        self.spn_upper_limit.blockSignals(False)
        self.spn_lower_limit.blockSignals(False)
    
    def getSafetyLimits(self):
        """
        获取当前安全上下限
        
        Returns:
            tuple: (upper_limit, lower_limit)
        """
        return (self.spn_upper_limit.value(), self.spn_lower_limit.value())
    
    def getTimeAxisRange(self):
        """
        获取当前时间轴显示范围
        
        Returns:
            tuple: (starttime, endtime) - 时间轴起始时刻和结束时刻（Unix时间戳）
        """
        return (self.starttime, self.endtime)
    
    
    # ========== 私有方法 ==========
    
    def _updateHeightLabelPosition(self):
        """更新"液位高度(mm)"标签位置到左上角"""
        try:
            if hasattr(self, 'height_label'):
                # 获取当前视图范围
                view_range = self.view_box.viewRange()
                x_range, y_range = view_range
                x_min, x_max = x_range
                y_min, y_max = y_range
                
                # 设置标签位置：X轴左边缘，Y轴顶部（稍微下移一点避免贴边）
                self.height_label.setPos(x_min, y_max - (y_max - y_min) * 0.02)
        except Exception as e:
            # 静默处理异常，避免影响主流程
            pass
    
    def _fixXAxisPosition(self):
        """固定X轴位置（固定原点位置方案）- 在任何可能影响布局的操作后调用"""
        try:
            plot_item = self.plot_widget.getPlotItem()
            bottom_axis = plot_item.getAxis('bottom')
            left_axis = plot_item.getAxis('left')
            
            # 重新设置固定的坐标轴尺寸
            bottom_axis.setHeight(35)  # 固定X轴高度（比默认40减少5像素）
            left_axis.setWidth(38)      # 固定Y轴宽度（减小宽度以消除左下角空白）
            
            # 重新设置坐标轴颜色为黑色
            bottom_axis.setPen(pg.mkPen(color='k', width=1))
            left_axis.setPen(pg.mkPen(color='k', width=1))
            bottom_axis.setTextPen(pg.mkPen(color='k'))
            left_axis.setTextPen(pg.mkPen(color='k'))
            
            # 重新禁用自动调整
            bottom_axis.setStyle(autoExpandTextSpace=False, tickTextOffset=-5)
            left_axis.setStyle(autoExpandTextSpace=False)
        except Exception as e:
            # 静默处理异常，避免影响主流程
            pass
    
    def _updateXRange(self):
        """更新X轴范围，自动滚动显示最新数据（由handler触发）"""
        if not self.chk_auto_follow.isChecked():
            return
        
        #  由于数据由handler管理，这里只保留UI逻辑
        # handler会在需要时调用 setXRangeAuto 方法
    
    def _updateYRange(self):
        """自动调整Y轴范围（由handler触发）"""
        #  由于数据由handler管理，这里只保留UI逻辑
        # handler会在需要时调用 setYRangeAuto 方法
    
    def setXRangeAuto(self, max_time, view_width=120):
        """
        自动设置X轴范围（由handler调用）
        
        Args:
            max_time: 最大时间戳
            view_width: 显示宽度（秒），默认120秒（2分钟）
        """
        if self.chk_auto_follow.isChecked():
            min_time = max_time - view_width
            self.plot_widget.setXRange(min_time, max_time, padding=0)
    
    def setViewAll(self, min_time, max_time, max_value):
        """
        显示全部数据范围（用于历史数据加载）
        
        Args:
            min_time: 最小时间戳
            max_time: 最大时间戳
            max_value: 最大数值
        """
        # 设置X轴显示全部时间范围（留出5%的边距）
        time_span = max_time - min_time
        if time_span > 0:
            padding = time_span * 0.05  # 5%边距
            self.plot_widget.setXRange(min_time - padding, max_time + padding, padding=0)
        
        # 设置Y轴范围（留出10%的边距）
        if max_value > 0:
            y_max = min(23, max_value * 1.1)  # 不超过23
            self.plot_widget.setYRange(0, y_max, padding=0)
        
        # 固定X轴位置
        self._fixXAxisPosition()
    
    def setYRangeAuto(self, max_value):
        """
        自动设置Y轴范围（由handler调用）
        
        Args:
            max_value: 最大数值
        """
        if self.chk_auto_y.isChecked():
            # 获取当前Y轴范围
            current_range = self.view_box.viewRange()
            current_y_min, current_y_max = current_range[1]
            
            # 如果数据超出当前范围，扩展Y轴（留出10%余量）
            if max_value > current_y_max * 0.9:  # 超过90%时扩展
                new_max = min(23, max_value * 1.1)  # 不超过23
                self.plot_widget.setYRange(0, new_max, padding=0)
                # 固定X轴位置
                self._fixXAxisPosition()
    
    def _onViewRangeChanged(self, view_box, ranges):
        """视图范围改变回调，确保Y轴范围在0-23之间，并保持X轴位置固定"""
        # 获取当前范围
        x_range, y_range = ranges
        y_min, y_max = y_range
        x_min, x_max = x_range
        
        # 更新时间轴显示范围变量
        self.starttime = x_min  # 时间轴起始时刻（Unix时间戳）
        self.endtime = x_max    # 时间轴结束时刻（Unix时间戳）
        
        # 🔥 调试信息：输出时间轴范围变化（安全处理时间戳转换）
        import datetime
        try:
            if x_min and np.isfinite(x_min):
                start_str = datetime.datetime.fromtimestamp(x_min).strftime('%Y-%m-%d %H:%M:%S')
            else:
                start_str = 'None'
        except (OSError, ValueError, OverflowError):
            start_str = f'Invalid({x_min})'
        
        try:
            if x_max and np.isfinite(x_max):
                end_str = datetime.datetime.fromtimestamp(x_max).strftime('%Y-%m-%d %H:%M:%S')
            else:
                end_str = 'None'
        except (OSError, ValueError, OverflowError):
            end_str = f'Invalid({x_max})'
        
        # 发送时间轴范围变化信号，通知Handler根据新的范围重新采样
        try:
            self.timeAxisRangeChanged.emit(float(self.starttime), float(self.endtime))
        except Exception:
            # 静默处理，避免因为范围无效导致崩溃
            pass
        
        # 确保Y轴范围在0-23之间
        if y_min < 0 or y_max > 23:
            # 调整到合法范围
            y_min = max(0, y_min)
            y_max = min(23, y_max)
            # 如果范围太小，至少保持一定的高度
            if y_max - y_min < 1:
                if y_max == 23:
                    y_min = 22
                else:
                    y_max = y_min + 1
            self.plot_widget.setYRange(y_min, y_max, padding=0)
        
        # 更新"液位高度(mm)"标签位置到左上角
        if hasattr(self, 'height_label'):
            # 设置标签位置：X轴左边缘，Y轴顶部（稍微下移一点避免贴边）
            self.height_label.setPos(x_min, y_max - (y_max - y_min) * 0.02)
        
        # 固定X轴位置（每次视图范围改变都重新应用）
        self._fixXAxisPosition()
    
    
    # ========== 槽函数 ==========
    
    def _onBackClicked(self):
        """返回按钮点击"""
        self.backClicked.emit()
    
    def _onResetView(self):
        """重置视图，显示最新10秒数据"""
        # 重置Y轴范围为0-23
        self.plot_widget.setYRange(0, 23, padding=0)
        
        # 固定X轴位置
        self._fixXAxisPosition()
        
        # 启用自动跟随
        self.chk_auto_follow.setChecked(True)
        
        # 自动调整X轴范围到最新数据
        self._updateXRange()
    
    def _onAutoFollowToggled(self, state):
        """自动跟随开关"""
        is_enabled = (state == Qt.Checked)
        
        if is_enabled:
            # 立即更新到最新数据
            self._updateXRange()
    
    def _onAutoYToggled(self, state):
        """自动Y轴开关"""
        is_enabled = (state == Qt.Checked)
        
        if is_enabled:
            # 立即更新Y轴范围
            self._updateYRange()
    
    def _onRefreshMissionList(self):
        """刷新任务列表按钮点击（发送信号）"""
        self.refreshMissionListRequested.emit()
    
    def _onMissionSelectionChanged(self, mission_name):
        """任务选择变化（发送信号给handler）"""
        # 如果选择的是默认选项，不发送信号
        if not mission_name or mission_name == "请选择任务":
            return
        
        # 构建完整路径并发送信号
        import os
        import sys
        
        # 动态获取项目根目录
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            try:
                from client.config import get_project_root
                project_root = get_project_root()
            except ImportError:
                project_root = os.getcwd()
        
        # 构建完整路径
        mission_path = os.path.join(project_root, 'database', 'mission_result', mission_name)
        
        # 发送信号给handler
        self.missionFolderChanged.emit(mission_path)
    
    def _onUpperLimitChanged(self, value):
        """安全上限值变化"""
        # 更新上限线位置
        if hasattr(self, 'upper_limit_line'):
            self.upper_limit_line.setValue(value)
    
    def _onLowerLimitChanged(self, value):
        """安全下限值变化"""
        # 更新下限线位置
        if hasattr(self, 'lower_limit_line'):
            self.lower_limit_line.setValue(value)


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    import time
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("CurvePanel 高性能曲线面板测试")
    window.resize(1200, 700)
    
    # 创建曲线面板
    curve_panel = CurvePanel()
    window.setCentralWidget(curve_panel)
    
    curve_panel.addChannel("channel1", "通道1", "1", "#1f77b4")
    curve_panel.addChannel("channel2", "通道2", "2", "#ff7f0e")
    curve_panel.addChannel("channel3", "通道3", "3", "#2ca02c")
    
    # 模拟实时数据更新
    start_time = datetime.datetime.now()
    def update_test_data():
        """模拟实时数据（按照CSV格式：时间戳 数值）"""
        # 当前时间戳
        current_time = datetime.datetime.now()
        
        # 计算经过的秒数（用于生成波形）
        elapsed = (current_time - start_time).total_seconds()
        
        value1 = int(16 + 3 * np.sin(elapsed * 0.1) + np.random.randn() * 1.5)
        value2 = int(15 + 2 * np.cos(elapsed * 0.15) + np.random.randn() * 1.2)
        value3 = int(14 + 3 * np.sin(elapsed * 0.08 + 1) + np.random.randn() * 1.0)
        
        # 确保数值在0-23范围内
        value1 = np.clip(value1, 0, 23)
        value2 = np.clip(value2, 0, 23)
        value3 = np.clip(value3, 0, 23)
        
        # 更新曲线（传入datetime对象）
        curve_panel.updateCurve("channel1", current_time, value1)
        curve_panel.updateCurve("channel2", current_time, value2)
        curve_panel.updateCurve("channel3", current_time, value3)
    
    # 创建定时器模拟实时更新
    timer = QtCore.QTimer()
    timer.timeout.connect(update_test_data)
    timer.start(100)  # 100ms更新一次，10Hz刷新率
    
    def on_curve_updated(channel_id, t, v):
        pass  # 静默处理，避免打印过多
    
    def on_channel_switched(channel_id):
        pass
    
    def on_data_exported(channel_id, file_path):
        pass
    
    curve_panel.curveDataUpdated.connect(on_curve_updated)
    curve_panel.channelSwitched.connect(on_channel_switched)
    curve_panel.dataExported.connect(on_data_exported)
    
    
    window.show()
    sys.exit(app.exec_())

