# -*- coding: utf-8 -*-

"""
==================== app.py 文件说明 ====================

职责概述
----------
本文件是应用程序的主入口和UI框架层，负责：
1. 定义主窗口类 MainWindow
2. 管理应用程序的整体布局和页面结构
3. 初始化和组织各个UI组件
4. 连接UI组件与业务逻辑处理器（Handlers）

架构设计
-----------
采用 Mixin 模式 + Handler 模式实现关注点分离：
- app.py：UI框架层，仅负责UI组件的创建、布局和信号连接
- handlers/：业务逻辑层，处理所有的事件响应和业务逻辑

页面结构（3个主页面）
------------------------
1. PAGE_VIDEO (0)：视频监控页面
   - 子页面0：实时检测（任务表格 + 2x8通道面板，带垂直滚动条，共16通道）
   - 子页面1：曲线分析（垂直通道 + 曲线面板）

2. PAGE_MODEL (1)：模型管理中心
   - modelStackWidget（堆叠容器）
     - 索引0：ModelSetPage（模型集管理）
       - 模型列表和参数显示
     - 索引1：TrainingPage（模型升级）★ 默认页面
       - 训练参数配置 + 日志显示

3. PAGE_DATASET (2)：数据集管理页面
   - 子页面0：数据采集
   - 子页面1：数据预处理
   - 子页面2：数据标注
   - 子页面3：模型训练

Handler 组织（通过Mixin继承）
---------------------------------
- ChannelPanelHandler：通道面板事件处理
- MissionPanelHandler：任务管理事件处理
- FileHandler：文件菜单事件处理
- ViewHandler：视图菜单事件处理
- SettingsHandler：设置菜单事件处理
- MenuBarHandler：菜单栏初始化
- GeneralSetPanelHandler：通用设置面板处理
- ModelSettingHandler：模型设置处理
- TestHandler：测试调试处理
- CurvePanelHandler：曲线面板业务逻辑
- DataCollectionChannelHandler：数据采集通道处理
- ModelSyncHandler：模型同步处理
- ModelSignalHandler：模型信号处理
- ModelSetHandler：模型集管理处理
- ModelLoadHandler：模型加载处理
- ModelSettingsHandler：模型设置处理
- ModelTrainingHandler：模型训练处理

核心方法
-----------
初始化相关：
- _initUI()：初始化UI组件
- _createPages()：创建所有主页面
- _createVideoPage()：创建视频监控页面及其子页面
- _createModelPage()：创建模型管理页面
- _createDatasetPage()：创建数据集管理页面
- _connectSignals()：连接所有信号槽
- _initMenuBar()：初始化菜单栏

页面切换相关：
- showVideoPage()：显示视频监控页面
- showModelPage()：显示模型管理页面
- showDatasetPage()：显示数据集管理页面
- toggleVideoPageCurveLayout()：切换视频页面子页面

设计原则
-----------
1. 单一职责：app.py 仅负责UI框架，不包含业务逻辑
2. 委托模式：所有事件处理委托给对应的 Handler
3. 组件封装：通道面板通过移动在不同布局之间切换
4. 信号驱动：UI组件通过信号与Handler通信

编码规范
-----------
禁止事项：
1. 不要在 app.py 中添加业务逻辑
   - 所有业务逻辑应添加到对应的 handler 中
   - app.py 仅负责UI组件的创建和信号连接

2. 不要在 app.py 中处理事件回调
   - 事件回调应在对应的 Handler 中实现
   - app.py 仅负责连接信号到 Handler 方法

新增功能指南：

新增页面时需要：
1. 在 _createPages() 中创建页面
2. 添加对应的 show*Page() 方法
3. 在 PAGE_* 常量中定义页面索引

新增 Handler 时需要：
1. 在文件开头导入 Handler 类
2. 在 MainWindow 的继承列表中添加
3. 必要时在 __init__ 中初始化 Handler

新增 UI 组件时需要：
1. 在对应的 _create*Page() 方法中创建组件
2. 在 _connectSignals() 中连接信号
3. 将业务逻辑实现在对应的 Handler 中

 相关文件
-----------
- handlers/：所有业务逻辑处理器
- widgets/：UI组件定义
- config/：配置文件

 代码审查检查项
-----------------
在修改 app.py 时，请确保：
- [ ] 没有在 app.py 中添加业务逻辑
- [ ] 所有事件处理都委托给了 Handler
- [ ] 新增的信号都已正确连接
- [ ] 代码遵循单一职责原则
- [ ] 使用了合适的 Handler，而不是直接实现

========================================================
"""

import functools
import os
import os.path as osp
import sys
import time

from qtpy import QtCore
from qtpy.QtCore import Qt
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import QObject, QEvent

# 支持相对导入（作为模块运行）和绝对导入（独立运行）
try:
    from ..widgets import MenuBar
    
    # 导入所有处理器 (Mixin类)
    from ..handlers import (
        ChannelPanelHandler,
        FileHandler,
        ViewHandler,
        SettingsHandler,
        MenuBarHandler,
    )
    from ..handlers.datasetpage import DataCollectionChannelHandler
    from ..handlers.videopage import GeneralSetPanelHandler, ModelSettingHandler, CurvePanelHandler, MissionPanelHandler
    from ..handlers.modelpage import (
        ModelSyncHandler,
        ModelSignalHandler,
        ModelSetHandler,
        ModelLoadHandler,
        ModelSettingsHandler,
        ModelTrainingHandler
    )
    
    # 导入远程配置管理器
    from utils.config import RemoteConfigManager
    
except ImportError:
    # 独立运行时使用绝对导入
    import sys
    import os
    # 添加client到Python路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.dirname(current_dir)
    if client_dir not in sys.path:
        sys.path.insert(0, client_dir)
    
    from widgets.menubar import MenuBar
    from widgets.style_manager import FontManager
    from handlers import (
        ChannelPanelHandler,
        FileHandler,
        ViewHandler,
        SettingsHandler,
        MenuBarHandler,
    )
    from handlers.datasetpage import DataCollectionChannelHandler
    from handlers.videopage import GeneralSetPanelHandler, ModelSettingHandler, CurvePanelHandler, MissionPanelHandler
    from handlers.modelpage import (
        ModelSyncHandler,
        ModelSignalHandler,
        ModelSetHandler,
        ModelLoadHandler,
        ModelSettingsHandler,
        ModelTrainingHandler
    )
    
    # 导入远程配置管理器
    from utils.config import RemoteConfigManager


class SystemWindow(
    ChannelPanelHandler,
    FileHandler,
    ViewHandler,
    SettingsHandler,
    MenuBarHandler,
    GeneralSetPanelHandler,
    ModelSettingHandler,
    CurvePanelHandler,
    DataCollectionChannelHandler,
    ModelSyncHandler,
    ModelSignalHandler,
    ModelSetHandler,
    ModelLoadHandler,
    ModelSettingsHandler,
    ModelTrainingHandler,
    MissionPanelHandler,
    QtWidgets.QMainWindow
):
    """
    系统主窗口 - 登录后的主界面
    """
    
    # 页面索引常量
    PAGE_VIDEO = 0
    PAGE_MODEL = 1
    PAGE_DATASET = 2
    
    def __init__(
        self,
        config,
        auth_api,
        user_info,
    ):
        super(SystemWindow, self).__init__()
        
        # 保存认证信息
        self.config = config
        self.auth_api = auth_api
        self.user_info = user_info
        
        # 使用传入的配置，不再从database目录读取
        self._config = config if config else {}
        
        # 设置窗口标题
        self.setWindowTitle(self.tr("帕特智能油液位检测"))
       
        
        # 设置窗口图标（用于左上角和任务栏）
        self._setWindowIcon()
        
        # 初始化通道资源（必须在UI初始化之前）
        self._initChannelResources()
        
        # 初始化数据采集通道资源
        self._initDataCollectionChannelResources()
        
        # 测试调试资源已移除
        
        # 初始化模型管理处理器
        ModelSyncHandler._set_main_window(self, self)
        ModelSignalHandler._set_main_window(self, self)
        ModelSetHandler._set_main_window(self, self)
        ModelLoadHandler._set_main_window(self, self)
        ModelSettingsHandler._set_main_window(self, self)
        ModelTrainingHandler._set_main_window(self, self)
        
        # 创建 handler 属性别名（用于 Mixin 模式）
        # 因为 MainWindow 通过 Mixin 继承了这些 handler，所以让属性指向 self
        self.model_set_handler = self
        self.model_load_handler = self
        self.model_signal_handler = self
        self.model_settings_handler = self
        self.model_training_handler = self
        self.model_sync_handler = self
        
        # 初始化WebSocket客户端
        self._initWebSocketClient()
        
        # 初始化UI
        self._initUI()
        
        # 初始化菜单
        self._initMenuBar()
        
        # 连接信号槽
        self._connectSignals()
        
        # 恢复窗口状态
        self._restoreSettings()
        
        # 显示默认页面
        self.showVideoPage()
    
    def _setWindowIcon(self):
        """设置窗口图标（用于左上角和任务栏）"""
        try:
            # 获取项目根目录
            project_root = get_project_root()
            icon_path = os.path.join(project_root, 'resources', 'icons', 'apple.png')
            
            # 检查图标文件是否存在
            if os.path.exists(icon_path):
                icon = QtGui.QIcon(icon_path)
                self.setWindowIcon(icon)
            else:
                pass
        except Exception as e:
            pass
    
    def _loadDefaultConfig(self):
        """从服务端加载配置"""
        try:
            print("[DEBUG] 开始从服务端加载配置")
            
            # 初始化远程配置管理器
            if not hasattr(self, '_remote_config_manager'):
                self._remote_config_manager = RemoteConfigManager()
            
            # 从服务端加载配置
            channel_config = self._remote_config_manager.load_channel_config()
            default_config = self._remote_config_manager.load_default_config()
            
            # 合并配置
            config = {**default_config, **channel_config}
            
            if config:
                print(f"[DEBUG] 成功从服务端加载配置")
                print(f"[DEBUG] 配置的通道: {[k for k in config.keys() if k.startswith('channel')]}")
                return config
            else:
                print("[DEBUG] 服务端配置为空，使用备用配置")
                return self._getFallbackConfig()
                
        except Exception as e:
            print(f"[ERROR] 从服务端加载配置失败: {e}")
            import traceback
            traceback.print_exc()
            return self._getFallbackConfig()
    
    def _getFallbackConfig(self):
        """获取备用配置"""
        return {
            'channel1': {
                'name': '通道1',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel2': {
                'name': '通道2',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel3': {
                'name': '通道3',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            },
            'channel4': {
                'name': '通道4',
                'address': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
            }
        }
    
    def _initUI(self):
        """初始化UI组件 - 使用 QStackedWidget 管理多页面"""
        # 创建 QStackedWidget 作为中央控件
        self.stackedWidget = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stackedWidget)
        
        # 创建不同的页面
        self._createPages()
        
        # 创建状态栏
        self.statusBar().showMessage(self.tr("就绪"))
        self.statusBar().show()
    def _initWebSocketClient(self):
        """初始化网络命令管理器"""
        try:
            # 检查是否为离线模式
            import sys

            # 尝试从__main__模块获取OFFLINE_MODE (因为main.py是作为主程序运行的)
            offline_mode = False
            try:
                if '__main__' in sys.modules:
                    offline_mode = getattr(sys.modules['__main__'], 'OFFLINE_MODE', False)
                    print(f"[SystemWindow] 检测到离线模式设置: {offline_mode}")
            except Exception as e:
                print(f"[SystemWindow] 检查离线模式失败: {e}")
                pass

            if offline_mode:
                print(f"[SystemWindow] 离线模式 - 跳过WebSocket连接")
                self.command_manager = None
                self.ws_client = None
                return

            # 创建网络命令管理器 - 连接到远程服务端
            from client.network.command_manager import NetworkCommandManager

            self.command_manager = NetworkCommandManager('ws://192.168.0.121:8085', self)

            # 连接状态信号
            self.command_manager.connectionStatusChanged.connect(self._onWebSocketStatus)
            self.command_manager.detectionResultReceived.connect(self._onDetectionResult)

            # 启动连接
            self.command_manager.start_connection()

            # 为了向后兼容，保留ws_client属性
            self.ws_client = self.command_manager

            print(f"[SystemWindow] 网络命令管理器已初始化并启动")
            
        except Exception as e:
            print(f"[SystemWindow] 网络命令管理器初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self.command_manager = None
            self.ws_client = None
    
    def _onWebSocketStatus(self, is_connected, message):
        """WebSocket连接状态变化回调
        
        Args:
            is_connected: 是否已连接
            message: 状态消息
        """
        status_text = "已连接" if is_connected else "未连接"
        print(f"[WebSocket] 连接状态: {status_text} - {message}")
        
        # 更新状态栏
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"WebSocket: {status_text} - {message}")
    
    def _onDetectionResult(self, data):
        """检测结果回调

        Args:
            data: 检测结果数据
        """
        print(f"[SystemWindow] 收到检测结果: {data}")

        # 转发给ChannelPanelHandler处理液位线显示
        if hasattr(self, '_onWebSocketDetectionResult'):
            print(f"[SystemWindow] 转发检测结果给ChannelPanelHandler...")
            self._onWebSocketDetectionResult(data)
        else:
            print(f"[SystemWindow] [WARN] _onWebSocketDetectionResult方法不存在")
    
    def _createPages(self):
        """创建不同的页面"""
        # 页面0：实时检测管理页面（实时检测管理）
        self.videoPage = self._createVideoPage()
        self.stackedWidget.addWidget(self.videoPage)
        
        # 页面1：模型管理页面
        self.modelPage = self._createModelPage()
        self.stackedWidget.addWidget(self.modelPage)
        
        # 页面2：数据集管理页面（包含多个子页面）
        self.datasetPage = self._createDatasetPage()
        self.stackedWidget.addWidget(self.datasetPage)
    
    def _createVideoPage(self):
        """创建实时检测管理页面 - 支持两种布局模式切换"""
        try:
            from widgets import ChannelPanel, MissionPanel, CurvePanel
        except ImportError:
            from widgets import ChannelPanel, MissionPanel, CurvePanel
        
        # 主页面容器
        # 修复：确保 QApplication 完全初始化后再创建 QWidget
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication 未初始化")
        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        
        # 使用 QStackedWidget 管理两种布局模式
        self.videoLayoutStack = QtWidgets.QStackedWidget()
        page_layout.addWidget(self.videoLayoutStack)
        
        # === 模式1：默认布局（任务表格 + 2x2通道面板） ===
        self._createDefaultVideoLayout()
        
        # === 模式2：曲线模式布局（垂直通道面板 + 曲线面板） ===
        self._createCurveVideoLayout()
        
        # 默认显示模式1
        self.videoLayoutStack.setCurrentIndex(0)
        self._video_layout_mode = 0  # 0=默认模式, 1=曲线模式
        
        return page
    
    def _createDefaultVideoLayout(self):
        """创建默认布局：任务表格 + 2x8通道面板（带垂直滚动条）"""
        try:
            from widgets import ChannelPanel, MissionPanel
        except ImportError:
            from widgets import ChannelPanel, MissionPanel
        
        # 确保 QApplication 存在
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication 未初始化")
        layout_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(layout_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # === 左侧：任务表格（自动配置） ===
        self.missionTable = MissionPanel()
        main_layout.addWidget(self.missionTable)
        
        # === 右侧：带滚动条的通道面板区域（2x8网格，共16个通道） ===
        self.default_scroll_area = QtWidgets.QScrollArea()
        self.default_scroll_area.setWidgetResizable(False)
        self.default_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.default_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.default_scroll_area.setMinimumWidth(1310)  # 确保滚动区域有足够宽度
        
        # 通道面板容器
        self.default_channel_container = QtWidgets.QWidget()
        # 2x8布局：2列 x 8行，每个面板620x465，间距20
        # 宽度：30 + 620 + 20 + 620 + 30 = 1320
        # 高度：10 + (465 + 20) * 8 - 20 + 10 = 3880
        container_height = 10 + (465 + 20) * 8 - 20 + 10
        self.default_channel_container.setFixedSize(1320, container_height)
        
        # 创建16个通道面板
        self.channelPanels = []
        
        # 2x8 网格布局的固定位置（4:3比例，620x465）
        self.default_channel_positions = []
        for row in range(8):
            for col in range(2):
                x = 30 + col * (620 + 20)  # 30, 670
                y = 10 + row * (465 + 20)  # 10, 495, 980, ...
                self.default_channel_positions.append((x, y))
        
        for i, (x, y) in enumerate(self.default_channel_positions):
            channel_id = f'channel{i+1}'
            channel_name = self.getChannelDisplayName(channel_id, i+1)
            
            channelPanel = ChannelPanel(channel_name, parent=self.default_channel_container, debug_mode=False)
            channelPanel.setObjectName(f"ChannelPanel_{i+1}")
            
            if hasattr(channelPanel, 'setChannelName'):
                channelPanel.setChannelName(channel_name)
            
            # 为每个通道面板的任务标签设置变量名
            mission_var_name = f'channel{i+1}mission'
            setattr(self, mission_var_name, channelPanel.taskLabel)
            
            if hasattr(self, '_connectChannelPanelSignals'):
                self._connectChannelPanelSignals(channelPanel)
            
            channelPanel.move(x, y)
            self.channelPanels.append(channelPanel)
        
        self.default_scroll_area.setWidget(self.default_channel_container)
        main_layout.addWidget(self.default_scroll_area)
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 1)
        
        # 连接滚动信号，滚动时更新叠加层位置
        self.default_scroll_area.verticalScrollBar().valueChanged.connect(self._updateAllOverlayPositions)
        
        # 保存第一个面板的引用（兼容现有代码）
        self.channelPanel = self.channelPanels[0] if self.channelPanels else None
        
        # 创建16个历史视频面板（用于曲线模式布局的历史回放子布局）
        try:
            from widgets.videopage import HistoryVideoPanel
        except ImportError:
            from widgets.videopage import HistoryVideoPanel
        
        self.historyVideoPanels = []
        for i in range(16):
            channel_id = f'channel{i+1}'
            channel_name = self.getChannelDisplayName(channel_id, i+1)
            
            # 创建历史视频面板，不设置父窗口（避免自动显示），但传入主窗口引用以访问 curvemission
            history_panel = HistoryVideoPanel(title=channel_name, parent=None, debug_mode=False, main_window=self)
            history_panel.setObjectName(f"HistoryVideoPanel_{i+1}")
            self.historyVideoPanels.append(history_panel)
        
        
        # 通过handler初始化通道面板数据
        if hasattr(self, 'initializeChannelPanels'):
            self.initializeChannelPanels(self.channelPanels)
        
        self.videoLayoutStack.addWidget(layout_widget)
    
    def _createCurveVideoLayout(self):
        """创建曲线模式布局：左侧垂直排列通道 + 右侧曲线面板
        
        包含两个子布局：
        - 子布局0：同步布局（带任务选择和底部按钮）
        - 子布局1：历史回放布局（无任务选择和底部按钮）
        
        两个子布局共用同一个CurvePanel（右侧）
        """
        try:
            from widgets import CurvePanel
        except ImportError:
            from widgets import CurvePanel
        
        # 先创建共用的CurvePanel
        self.curvePanel = CurvePanel()
        
        # 设置曲线面板的任务选择下拉框变量名（curvemission）
        self.curvemission = self.curvePanel.curvemission
        
        # 连接任务选择变化信号
        self.curvemission.currentTextChanged.connect(self._onCurveMissionChanged)
        
        # 连接曲线面板到Handler（业务逻辑层）
        self.curve_panel = self.curvePanel
        self.connectCurvePanel(self.curvePanel)
        
        # 创建主容器和布局
        layout_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(layout_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建左侧子布局栈（实时检测 vs 历史回放）
        self.curveLayoutStack = QtWidgets.QStackedWidget()
        self.curveLayoutStack.setFixedWidth(660)
        self._curve_sub_layout_mode = 0  # 0=同步布局, 1=历史回放布局
        
        # === 子布局0：同步布局（左侧通道列表）===
        self._createRealtimeCurveSubLayout()
        
        # === 子布局1：历史回放布局（左侧历史视频面板容器）===
        self._createHistoryCurveSubLayout()
        
        # 布局结构：左侧子布局栈 + 右侧共用CurvePanel
        main_layout.addWidget(self.curveLayoutStack)
        main_layout.addWidget(self.curvePanel, stretch=1)
        
        self.videoLayoutStack.addWidget(layout_widget)
        
    
    def _createRealtimeCurveSubLayout(self):
        """创建实时检测曲线子布局（索引0）- 左侧通道列表"""
        # 保留固定通道容器系统，但改为基于CSV文件动态显示
        # 不再从任务配置读取通道筛选，而是显示所有容器，由CSV文件数量决定实际显示
        
        sublayout_widget = QtWidgets.QWidget()
        sublayout = QtWidgets.QVBoxLayout(sublayout_widget)
        sublayout.setContentsMargins(0, 0, 0, 0)
        sublayout.setSpacing(0)
        
        # === 带滚动条的垂直通道面板区域 ===
        self.curve_scroll_area = QtWidgets.QScrollArea()
        self.curve_scroll_area.setWidgetResizable(False)
        self.curve_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.curve_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        # 创建通道容器
        self.curve_channel_container = QtWidgets.QWidget()
        self.curve_channel_layout = QtWidgets.QVBoxLayout(self.curve_channel_container)
        self.curve_channel_layout.setContentsMargins(5, 5, 5, 5)
        self.curve_channel_layout.setSpacing(10)
        
        # 初始化通道包裹容器列表（同步布局）
        self.channel_widgets_for_curve = []
        
        # 创建16个通道容器（初始隐藏，等待CSV文件加载）
        for i in range(16):
            wrapper = QtWidgets.QWidget()
            wrapper.setFixedSize(620, 465)
            wrapper.setVisible(False)  # 初始隐藏
            
            wrapper_layout = QtWidgets.QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setSpacing(0)
            
            self.channel_widgets_for_curve.append(wrapper)
            self.curve_channel_layout.addWidget(wrapper)
        
        self.curve_scroll_area.setWidget(self.curve_channel_container)
        sublayout.addWidget(self.curve_scroll_area)
        
        # 连接滚动信号，滚动时更新叠加层位置
        self.curve_scroll_area.verticalScrollBar().valueChanged.connect(self._updateAllOverlayPositions)
        
        self.curveLayoutStack.addWidget(sublayout_widget)
    
    def _createHistoryCurveSubLayout(self):
        """创建历史回放曲线子布局（索引1）- 使用历史视频面板容器"""
        sublayout_widget = QtWidgets.QWidget()
        sublayout = QtWidgets.QVBoxLayout(sublayout_widget)
        sublayout.setContentsMargins(0, 0, 0, 0)
        sublayout.setSpacing(0)
        
        # === 带滚动条的垂直历史视频面板区域 ===
        self.history_scroll_area = QtWidgets.QScrollArea()
        self.history_scroll_area.setWidgetResizable(False)
        self.history_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.history_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        # 创建历史视频容器
        self.history_channel_container = QtWidgets.QWidget()
        # 设置容器最小高度，确保能容纳所有wrapper
        # 16个wrapper * 465高度 + 15个间距 * 10 + 上下边距 * 2 * 5 = 7440 + 150 + 10 = 7600
        self.history_channel_container.setMinimumHeight(7600)
        self.history_channel_layout = QtWidgets.QVBoxLayout(self.history_channel_container)
        self.history_channel_layout.setContentsMargins(5, 5, 5, 5)
        self.history_channel_layout.setSpacing(10)
        
        # 初始化历史视频包裹容器列表（历史回放布局）
        self.history_channel_widgets_for_curve = []
        
        # 创建16个历史视频容器（初始隐藏，等待CSV文件加载）
        for i in range(16):
            wrapper = QtWidgets.QWidget()
            wrapper.setFixedSize(620, 465)
            wrapper.setVisible(False)  # 初始隐藏
            
            wrapper_layout = QtWidgets.QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setSpacing(0)
            
            self.history_channel_widgets_for_curve.append(wrapper)
            self.history_channel_layout.addWidget(wrapper)
        
        self.history_scroll_area.setWidget(self.history_channel_container)
        sublayout.addWidget(self.history_scroll_area)
        
        # 连接滚动信号，滚动时更新叠加层位置
        self.history_scroll_area.verticalScrollBar().valueChanged.connect(self._updateAllOverlayPositions)
        
        self.curveLayoutStack.addWidget(sublayout_widget)
    
    def _onChannelCurveClicked(self, task_name):
        """
        处理通道面板的查看曲线按钮点击（来源2）
        
        Args:
            task_name: 通道面板的任务名称
        """
        # 设置 curvemission 的值
        if hasattr(self, 'curvePanel') and self.curvePanel:
            success = self.curvePanel.setMissionFromTaskName(task_name)
        
        # 切换到曲线模式
        self.toggleVideoPageMode()
    
    def _onCurveMissionChanged(self, mission_name):
        """曲线任务选择变化（基于CSV文件动态显示）"""
        if not mission_name or mission_name == "请选择任务":
            self._updateCurveChannelDisplay([])
            return
        
        # 重新检查检测状态并切换布局
        detection_running = False
        if hasattr(self, '_switchCurveSubLayout') and hasattr(self, '_getCurrentDetectionState'):
            detection_running = self._getCurrentDetectionState()
            self._switchCurveSubLayout(detection_running)
        
        # 根据检测状态决定显示逻辑（而不是依赖 getCurveLoadMode）
        if detection_running:
            # 同步布局：只显示任务配置中使用的通道
            selected_channels = self._getTaskChannels(mission_name)
        else:
            # 历史回放布局：显示所有通道容器
            selected_channels = [f'通道{i}' for i in range(1, 17)]
        
        self._updateCurveChannelDisplay(selected_channels)
    
    def _getTaskChannels(self, mission_name):
        """
        从任务配置文件中获取使用的通道列表
        
        Args:
            mission_name: 任务名称
            
        Returns:
            list: 任务使用的通道名称列表，如 ['通道1', '通道2']
        """
        import os
        import yaml
        
        try:
            # 任务配置现在应该从服务端获取，这里暂时使用临时方案
            # TODO: 改为从服务端API获取任务配置
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            
            # 任务配置文件在 database/config/mission/ 目录下（临时保留）
            config_file = os.path.join(project_root, 'database', 'config', 'mission', f"{mission_name}.yaml")
            
            if not os.path.exists(config_file):
                print(f"[通道筛选] 任务配置文件不存在: {config_file}")
                # 如果没有配置文件，返回空列表
                return []
            
            # 读取任务配置
            with open(config_file, 'r', encoding='utf-8') as f:
                task_config = yaml.safe_load(f)
            
            if not task_config:
                print(f"[通道筛选] 任务配置为空: {config_file}")
                return []
            
            #  调试：打印配置文件的所有键
            
            
            # 从配置中提取使用的通道
            # 配置格式可能是：selected_channels: ['通道2', '通道3'] 或 channels: ['channel1', 'channel2']
            used_channels = []
            
            # 优先检查 selected_channels 字段（最常用的格式）
            if 'selected_channels' in task_config:
                # 格式1: selected_channels: ['通道2', '通道3']
                channel_list = task_config['selected_channels']
                if isinstance(channel_list, list):
                    used_channels = [ch for ch in channel_list if isinstance(ch, str) and '通道' in ch]
            
            # 尝试其他可能的配置键名
            elif 'channels' in task_config:
                # 格式2: channels: ['channel1', 'channel2']
                channel_list = task_config['channels']
                if isinstance(channel_list, list):
                    for ch in channel_list:
                        if isinstance(ch, str) and 'channel' in ch.lower():
                            # 提取通道编号
                            ch_num = ''.join(filter(str.isdigit, ch))
                            if ch_num:
                                used_channels.append(f'通道{ch_num}')
                        elif isinstance(ch, int):
                            used_channels.append(f'通道{ch}')
                    print(f"[通道筛选] 从 channels 读取: {used_channels}")
            
            elif 'channel_list' in task_config:
                # 格式3: channel_list: [1, 2, 3]
                channel_list = task_config['channel_list']
                if isinstance(channel_list, list):
                    for ch_num in channel_list:
                        used_channels.append(f'通道{ch_num}')
                    print(f"[通道筛选] 从 channel_list 读取: {used_channels}")
            
            elif 'task_channels' in task_config:
                # 格式4: task_channels: '通道1, 通道2'
                channels_str = task_config['task_channels']
                if isinstance(channels_str, str):
                    used_channels = [ch.strip() for ch in channels_str.split(',')]
                    print(f"[通道筛选] 从 task_channels 读取: {used_channels}")
            
            else:
                # 如果没有明确的通道配置，尝试从其他字段推断
                # 检查是否有 channel1, channel2 等键
                for i in range(1, 17):  # 支持16个通道
                    if f'channel{i}' in task_config:
                        used_channels.append(f'通道{i}')
                if used_channels:
                    print(f"[通道筛选] 从 channel 字段推断: {used_channels}")
            
            # 去重并排序
            used_channels = sorted(list(set(used_channels)))
            
            if used_channels:
                pass
            else:
                pass
                # 如果配置中没有通道信息，返回所有通道
                used_channels = [f'通道{i}' for i in range(1, 17)]
            
            return used_channels
            
        except Exception as e:
            print(f"[通道筛选] 获取通道列表失败: {e}")
            import traceback
            traceback.print_exc()
            # 出错时返回所有通道
            return [f'通道{i}' for i in range(1, 17)]
    
    def _updateCurveChannelDisplay(self, selected_channels):
        """更新曲线布局中显示的通道"""
        # 根据当前曲线子布局模式选择要操作的容器
        if hasattr(self, '_curve_sub_layout_mode'):
            if self._curve_sub_layout_mode == 0:
                # 同步布局：操作channel_widgets_for_curve
                target_widgets = self.channel_widgets_for_curve if hasattr(self, 'channel_widgets_for_curve') else []
                target_container = self.curve_channel_container if hasattr(self, 'curve_channel_container') else None
            else:
                # 历史回放布局：操作history_channel_widgets_for_curve
                target_widgets = self.history_channel_widgets_for_curve if hasattr(self, 'history_channel_widgets_for_curve') else []
                target_container = self.history_channel_container if hasattr(self, 'history_channel_container') else None
        else:
            # 默认使用实时检测容器
            target_widgets = self.channel_widgets_for_curve if hasattr(self, 'channel_widgets_for_curve') else []
            target_container = self.curve_channel_container if hasattr(self, 'curve_channel_container') else None
        
        if not target_widgets:
            return
        
        # 通道名称到索引的映射（支持16个通道）
        channel_name_to_index = {f'通道{i}': i-1 for i in range(1, 17)}
        
        # 首先隐藏所有通道
        for wrapper in target_widgets:
            wrapper.setVisible(False)
        
        # 显示选中的通道
        visible_count = 0
        for channel_name in selected_channels:
            channel_index = channel_name_to_index.get(channel_name)
            if channel_index is not None and channel_index < len(target_widgets):
                target_widgets[channel_index].setVisible(True)
                visible_count += 1
        
        # 调整容器高度
        if visible_count > 0:
            total_height = visible_count * 465 + (visible_count - 1) * 10 + 10
        else:
            total_height = 100  # 最小高度
        
        if target_container:
            target_container.setFixedSize(640, total_height)
        
    
    def _createModelPage(self):
        """创建模型管理页面"""
        try:
            from widgets.modelpage import ModelSetPage, TestModelPage
        except ImportError:
            from widgets.modelpage import ModelSetPage, TrainingPage
        
        # 创建主页面容器（使用堆叠容器管理多个子页面）
        self.modelStackWidget = QtWidgets.QStackedWidget()
        
        # 创建训练处理器
        try:
            from handlers.modelpage.model_training_handler import ModelTrainingHandler
        except ImportError:
            try:
                from handlers.modelpage.model_training_handler import ModelTrainingHandler
            except ImportError:
                ModelTrainingHandler = None
                print("[WARNING] 无法导入ModelTrainingHandler，训练功能将不可用")
        
        if ModelTrainingHandler:
            self.training_handler = ModelTrainingHandler()
            self.training_handler._set_main_window(self)
        else:
            self.training_handler = None
        
        # 子页面0：模型集管理页面
        self.modelSetPage = ModelSetPage(parent=self)
        self.modelStackWidget.addWidget(self.modelSetPage)  # 索引 0
        
        # 创建模型升级（训练）页面
        self.trainingPage = TrainingPage(parent=self)
        self.modelStackWidget.addWidget(self.trainingPage)  # 索引 1
        
        # 连接训练页面到训练处理器
        if self.training_handler:
            self.training_handler.connectToTrainingPanel(self.trainingPage)
        
        # 建立组件间的连接（委托给ModelSignalHandler处理）
        self.setupModelPageConnections()
        
        return self.modelStackWidget
    
    
    def _createDatasetPage(self):
        """创建数据集管理页面（包含多个子页面）"""
        try:
            from widgets import DataCollectionPanel, DataPreprocessPanel, AnnotationTool
            from widgets.datasetpage import TrainingPanel
            from handlers.datasetpage import DataPreprocessHandler, TrainingHandler
        except ImportError:
            from widgets import DataCollectionPanel, DataPreprocessPanel, AnnotationTool
            from widgets.datasetpage import TrainingPanel
            from handlers.datasetpage import DataPreprocessHandler, TrainingHandler
        
        # 创建主页面容器
        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(10, 10, 10, 10)
        page_layout.setSpacing(10)
        
        # 创建堆叠容器管理子页面
        self.datasetStackWidget = QtWidgets.QStackedWidget()
        
        # 子页面0：数据采集
        self.dataCollectionPanel = DataCollectionPanel(parent=self)
        self.datasetStackWidget.addWidget(self.dataCollectionPanel)
        
        # 子页面1：数据预处理
        self.dataPreprocessPanel = DataPreprocessPanel()
        self.dataPreprocessHandler = DataPreprocessHandler(self.dataPreprocessPanel)
        self.datasetStackWidget.addWidget(self.dataPreprocessPanel)
        
        # 子页面2：数据标注
        self.annotationTool = AnnotationTool()
        self.datasetStackWidget.addWidget(self.annotationTool)
        
        # 子页面3：模型训练
        self.trainingPanel = TrainingPanel(parent=self)
        self.trainingHandler = TrainingHandler(self.trainingPanel)
        self.datasetStackWidget.addWidget(self.trainingPanel)
        
        # 默认显示第一个子页面（数据采集）
        self.datasetStackWidget.setCurrentIndex(0)
        
        # 连接切换信号，实现切换时刷新文件列表
        self.datasetStackWidget.currentChanged.connect(self._onDatasetSubPageChanged)
        
        page_layout.addWidget(self.datasetStackWidget)
        
        return page
    
    
    def _connectSignals(self):
        """连接信号槽"""
        # ========== 任务面板Handler信号（新建任务流程）==========
        # 所有任务表格的信号连接都在 MissionPanelHandler.connectMissionPanel 中处理
        self.connectMissionPanel(self.missionTable)
        
        # 测试调试信号已移除
        
        # ========== 通道管理按钮信号 ==========
        # 已改为内嵌显示，由 MissionPanelHandler 处理，不再使用弹窗
        # self.missionTable.channelManageClicked.connect(self.onChannelManage)  # 旧的弹窗方式
        
        # ========== 通道面板信号（为所有面板连接） ==========
        #  注意：channelConnected, channelDisconnected, channelEdited, amplifyClicked, channelNameChanged
        # 已经在 _connectChannelPanelSignals 中连接，不要重复连接！
        for panel in self.channelPanels:
            panel.channelSelected.connect(self.onChannelSelected)
            # panel.channelConnected.connect(self.onChannelConnected)  #  已在 _connectChannelPanelSignals 中连接
            # panel.channelDisconnected.connect(self.onChannelDisconnected)  #  已在 _connectChannelPanelSignals 中连接
            panel.channelAdded.connect(self.onChannelAdded)
            panel.channelRemoved.connect(self.onChannelRemoved)
            # panel.channelEdited.connect(self.onChannelEdited)  #  已在 _connectChannelPanelSignals 中连接
            
            # ========== 通道面板按钮信号 ==========
            panel.curveClicked.connect(self._onChannelCurveClicked)  # 通道面板查看曲线按钮
            # amplifyClicked 信号在 ChannelPanelHandler._connectChannelPanelSignals 中已连接
        
        # ========== 曲线面板信号 ==========
        self.curvePanel.backClicked.connect(self.switchToRealTimeDetectionPage)  # 返回实时检测管理页面
    
    def _initMenuBar(self):
        """初始化菜单栏（委托给MenuBarHandler处理）"""
        # 创建菜单栏组件
        menubar = MenuBar(self)
        self.setMenuBar(menubar)
        
        #  菜单配置逻辑已移至 MenuBarHandler.setupMenuBar()
        # 这里只调用 handler 方法，保持 app.py 职责单一
        self.setupMenuBar(menubar)
    
    def _restoreSettings(self):
        """恢复窗口设置"""
        self.settings = QtCore.QSettings("Detection", "detection")
        
        # 恢复窗口大小和位置
        size = self.settings.value("window/size", QtCore.QSize(1200, 800))
        position = self.settings.value("window/position", QtCore.QPoint(100, 100))
        state = self.settings.value("window/state", QtCore.QByteArray())
        
        self.resize(size)
        
        # 检查位置是否在可见屏幕范围内
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            # 如果窗口位置在屏幕外，重置到屏幕中心
            if (position.x() < screen_geometry.left() - 100 or 
                position.x() > screen_geometry.right() or
                position.y() < screen_geometry.top() - 100 or 
                position.y() > screen_geometry.bottom()):
                # 居中显示
                x = screen_geometry.left() + (screen_geometry.width() - size.width()) // 2
                y = screen_geometry.top() + (screen_geometry.height() - size.height()) // 2
                position = QtCore.QPoint(max(0, x), max(0, y))
                print(f"[DEBUG] 窗口位置超出屏幕，重置到: ({position.x()}, {position.y()})")
        
        self.move(position)
        
        if state:
            self.restoreState(state)
        
        # 恢复最后打开的页面
        last_page = self.settings.value("window/last_page", 0, type=int)
        if 0 <= last_page < self.stackedWidget.count():
            self.stackedWidget.setCurrentIndex(last_page)
    
    # ===== 页面切换方法 =====
    
    def showVideoPage(self):
        """显示实时检测管理页面"""
        self.stackedWidget.setCurrentWidget(self.videoPage)
        
        # 确保切换到默认布局（videoLayoutStack 索引0）
        if hasattr(self, 'videoLayoutStack'):
            self.videoLayoutStack.setCurrentIndex(0)
            self._video_layout_mode = 0
        
        # 确保所有通道面板在默认布局中可见
        if hasattr(self, 'channelPanels'):
            for i, channel_panel in enumerate(self.channelPanels):
                if hasattr(self, 'default_channel_positions') and i < len(self.default_channel_positions):
                    # 确保通道面板在正确的父容器中
                    if hasattr(self, 'default_channel_container'):
                        channel_panel.setParent(self.default_channel_container)
                        x, y = self.default_channel_positions[i]
                        channel_panel.move(x, y)
                    
                    # 显示通道面板
                    channel_panel.show()
        
        self.statusBar().showMessage(self.tr("当前页面: 实时检测管理"))
    
    def showModelPage(self):
        """显示模型管理页面"""
        self.stackedWidget.setCurrentWidget(self.modelPage)
        # 显示模型升级页面（索引1）
        if hasattr(self, 'modelStackWidget'):
            self.modelStackWidget.setCurrentIndex(1)  # 切换到TrainingPage（模型升级）
            self.statusBar().showMessage(self.tr("当前页面: 模型管理 - 模型升级"))
        else:
            self.statusBar().showMessage(self.tr("当前页面: 模型管理"))
    
    def showDatasetPage(self):
        """显示数据集管理页面（默认显示数据采集）"""
        self.stackedWidget.setCurrentWidget(self.datasetPage)
        self.statusBar().showMessage(self.tr("当前页面: 数据集管理"))
    
    def showDataCollectionPage(self):
        """显示数据采集页面"""
        self.showDatasetPage()  # 先切换到数据集管理页面
        if hasattr(self, 'datasetStackWidget'):
            self.datasetStackWidget.setCurrentIndex(0)  # 切换到数据采集子页面
            self.statusBar().showMessage(self.tr("当前页面: 数据集管理 - 数据采集"))
    
    def showDataPreprocessPage(self):
        """显示数据预处理页面"""
        self.showDatasetPage()  # 先切换到数据集管理页面
        if hasattr(self, 'datasetStackWidget'):
            self.datasetStackWidget.setCurrentIndex(1)  # 切换到数据预处理子页面
            self.statusBar().showMessage(self.tr("当前页面: 数据集管理 - 数据预处理"))
    
    def showAnnotationPage(self):
        """显示数据标注页面"""
        self.showDatasetPage()  # 先切换到数据集管理页面
        if hasattr(self, 'datasetStackWidget'):
            self.datasetStackWidget.setCurrentIndex(2)  # 切换到数据标注子页面
            self.statusBar().showMessage(self.tr("当前页面: 数据集管理 - 数据标注"))
    
    def _onDatasetSubPageChanged(self, index):
        """
        数据集子页面切换时的回调
        
        Args:
            index: 当前子页面索引（0=数据采集, 1=数据预处理, 2=数据标注, 3=模型训练）
        """
        # 刷新数据采集和数据预处理页面的左侧文件列表
        if index == 0:  # 数据采集
            if hasattr(self, 'dataCollectionPanel') and self.dataCollectionPanel:
                self.dataCollectionPanel.refreshFolders()
        elif index == 1:  # 数据预处理
            if hasattr(self, 'dataPreprocessPanel') and self.dataPreprocessPanel:
                self.dataPreprocessPanel.refreshFolders()
    
    def _showModelSetsTab(self):
        """显示模型集管理选项卡"""
        self.showModelPage()  # 先切换到模型管理页面
        if hasattr(self, 'modelStackWidget'):
            self.modelStackWidget.setCurrentIndex(0)  # 切换到ModelSetPage
    
    
    def _showTestModelTab(self):
        """显示模型升级页面"""
        self.showModelPage()  # 先切换到模型管理页面
        
        # 切换到 TrainingPage（索引 1）
        if hasattr(self, 'modelStackWidget'):
            self.modelStackWidget.setCurrentIndex(1)
        
        self.statusBar().showMessage(self.tr("当前页面: 模型管理 - 模型升级"))
    
    def switchToPage(self, page_index):
        """根据索引切换页面"""
        page_names = {
            self.PAGE_VIDEO: "实时检测管理",
            self.PAGE_MODEL: "模型管理",
            self.PAGE_DATASET: "数据集管理"
        }
        
        if 0 <= page_index < self.stackedWidget.count():
            self.stackedWidget.setCurrentIndex(page_index)
            page_name = page_names.get(page_index, "未知页面")
            self.statusBar().showMessage(f"当前页面: {page_name}")
    
    def getCurrentPageIndex(self):
        """获取当前页面索引"""
        return self.stackedWidget.currentIndex()
    
    def _updateChannelColumnColor(self):
        """
        更新任务面板中通道列的颜色
        
        当通道的检测状态改变时调用此方法，更新任务面板中对应通道列的背景色
        调用 MissionPanelHandler 的方法（MainWindow 继承了 MissionPanelHandler）
        """

        try:
            # MainWindow 继承了 MissionPanelHandler，直接调用父类方法
            from handlers.videopage import MissionPanelHandler
            MissionPanelHandler._updateChannelColumnColor(self)
        except Exception as e:
            print(f"[更新通道列颜色] 失败: {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== 叠加层位置同步事件 ====================
    
    def _updateAllOverlayPositions(self):
        """更新所有通道面板的叠加层位置"""
        if hasattr(self, 'channelPanels'):
            for panel in self.channelPanels:
                if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                    panel._infoOverlay.update_position()
    
    def moveEvent(self, event):
        """窗口移动时更新所有叠加层位置"""
        super(SystemWindow, self).moveEvent(event)
        self._updateAllOverlayPositions()
    
    def resizeEvent(self, event):
        """窗口大小改变时更新所有叠加层位置"""
        super(SystemWindow, self).resizeEvent(event)
        self._updateAllOverlayPositions()
    
    def changeEvent(self, event):
        """窗口状态改变时处理叠加层显示/隐藏"""
        super(SystemWindow, self).changeEvent(event)
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.windowState() & QtCore.Qt.WindowMinimized:
                # 窗口最小化，隐藏所有叠加层
                if hasattr(self, 'channelPanels'):
                    for panel in self.channelPanels:
                        if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                            panel._infoOverlay.hide()
            else:
                # 窗口恢复，显示所有叠加层并更新位置
                if hasattr(self, 'channelPanels'):
                    for panel in self.channelPanels:
                        if hasattr(panel, '_hwnd_render_mode') and panel._hwnd_render_mode:
                            if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                                panel._infoOverlay.show()
                                panel._infoOverlay.update_position()
    
    def hideEvent(self, event):
        """窗口隐藏时隐藏所有叠加层"""
        super(SystemWindow, self).hideEvent(event)
        if hasattr(self, 'channelPanels'):
            for panel in self.channelPanels:
                if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                    panel._infoOverlay.hide()
    
    def showEvent(self, event):
        """窗口显示时显示所有叠加层并更新位置"""
        super(SystemWindow, self).showEvent(event)
        if hasattr(self, 'channelPanels'):
            for panel in self.channelPanels:
                if hasattr(panel, '_hwnd_render_mode') and panel._hwnd_render_mode:
                    if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                        panel._infoOverlay.show()
                        panel._infoOverlay.update_position()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 关闭所有通道面板的叠加层
            if hasattr(self, 'channelPanels'):
                for panel in self.channelPanels:
                    if hasattr(panel, '_infoOverlay') and panel._infoOverlay:
                        panel._infoOverlay.close()
            
            # 程序退出时，停止全局存储线程并将缓冲区数据写入磁盘
            try:
                from handlers.videopage.thread_manager.threads.storage_thread import StorageThread
                StorageThread.stop()  # stop() 内部会调用 flush_all_on_exit()
            except Exception as e:
                print(f"[关闭] 停止存储线程失败: {e}")
            
            # 清理全局检测线程
            if hasattr(self, 'view_handler') and self.view_handler:
                video_handler = getattr(self.view_handler, 'video_handler', None)
                if video_handler:
                    thread_manager = getattr(video_handler, 'thread_manager', None)
                    if thread_manager:
                        thread_manager.cleanup_global_detection_thread()
            
            # 保存窗口状态
            self.settings.setValue("window/size", self.size())
            self.settings.setValue("window/position", self.pos())
            self.settings.setValue("window/state", self.saveState())
            
            # 保存当前页面索引
            self.settings.setValue("window/last_page", self.getCurrentPageIndex())
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        # 直接退出，不显示确认对话框
        event.accept()
    



# ==================== 独立运行入口 ====================

def main():
    """独立运行入口，用于UI预览和调试"""
    import sys
    
    # 创建应用
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Detection')
    app.setOrganizationName('Detection')
    
    # 暂时禁用全局字体配置，测试是否解决重复显示问题
    print(f"[调试] 跳过全局字体应用到应用程序")
    # FontManager.applyToApplication(app)
    
    # 设置应用样式（可选）
    # app.setStyle('Fusion')
    
    # 创建模拟的auth_api和user_info（用于调试）
    class MockAuthAPI:
        def __init__(self):
            pass
        
        def get_user_info(self):
            return {"username": "admin", "role": "admin"}
    
    mock_auth_api = MockAuthAPI()
    mock_user_info = {"username": "admin", "role": "admin", "permissions": ["all"]}
    
    # 创建主窗口
    win = SystemWindow(config={}, auth_api=mock_auth_api, user_info=mock_user_info)
    win.show()
    
    # 启动事件循环
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
