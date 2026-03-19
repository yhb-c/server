# -*- coding: utf-8 -*-

"""
菜单栏配置处理器 (Mixin类)

职责：
- 配置和管理应用的所有菜单项
- 设置菜单回调函数
- 管理菜单的启用/禁用状态
"""


class MenuBarHandler:
    """
    菜单栏配置处理器 (Mixin类)
    
    处理菜单栏的配置和信号连接
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def setupMenuBar(self, menubar):
        """
        配置菜单栏的所有菜单项
        
        Args:
            menubar: MenuBar组件实例
        """
        self.menubar = menubar
        
        # 配置各个菜单
        self._setupFileMenu()
        self._setupEditMenu()
        self._setupViewMenu()
        self._setupHelpMenu()
        
        # 设置菜单标题点击回调
        self._setupMenuCallbacks()
    
    def _setupFileMenu(self):
        """配置文件菜单（实时检测管理）"""
        # 实时检测管理菜单 - 无下拉菜单项，仅用于页面切换
        pass
    
    def _setupEditMenu(self):
        """配置编辑菜单（模型管理）"""
        # 添加分隔符分组
        self.menubar.addSeparator('edit')
        
        # 1. 模型升级
        self.menubar.addEditAction(
            'upgrade_model',
            self.tr("模型升级"),
            slot=self._showTestModelTab,
            tip=self.tr("模型管理 - 模型升级")
        )
        
        # 2. 模型集管理
        self.menubar.addEditAction(
            'model_sets',
            self.tr("模型集管理"),
            slot=self._showModelSetsTab,
            tip=self.tr("模型管理 - 模型集管理")
        )
        
        # 3. 模型设置 (已隐藏，无实际作用)
        # self.menubar.addEditAction(
        #     'model_settings',
        #     self.tr("模型设置"),
        #     slot=self.openModelSettings,
        #     tip=self.tr("模型管理 - 模型设置")
        # )
    
    def _setupViewMenu(self):
        """配置视图菜单（数据集管理）"""
        # 添加分隔符分组
        self.menubar.addSeparator('view')
        
        # 1. 数据采集
        self.menubar.addViewAction(
            'page_data_collection',
            self.tr("数据采集"),
            slot=self.showDataCollectionPage,
            tip=self.tr("数据集管理 - 数据采集")
        )
        
        # 2. 数据预处理
        self.menubar.addViewAction(
            'page_data_preprocess',
            self.tr("数据预处理"),
            slot=self.showDataPreprocessPage,
            tip=self.tr("数据集管理 - 数据预处理")
        )
        
        # 3. 数据标注
        self.menubar.addViewAction(
            'page_annotation',
            self.tr("数据标注"),
            slot=self.showAnnotationPage,
            tip=self.tr("数据集管理 - 数据标注")
        )
        
        # self.menubar.addSeparator('view')
        
        # 添加面板显示选项（已隐藏）
        # self.menubar.addViewAction(
        #     'show_toolbar',
        #     self.tr("显示工具栏"),
        #     slot=self.toggleToolBar,
        #     checkable=True,
        #     tip=self.tr("显示/隐藏工具栏")
        # )
        
        # self.menubar.addViewAction(
        #     'show_statusbar',
        #     self.tr("显示状态栏"),
        #     slot=self.toggleStatusBar,
        #     checkable=True,
        #     tip=self.tr("显示/隐藏状态栏")
        # )
        
        # 默认勾选
        # self.menubar.checkAction('show_toolbar', True)
        # self.menubar.checkAction('show_statusbar', True)
        
        # self.menubar.addSeparator('view')
        
        # self.menubar.addViewAction(
        #     'fullscreen',
        #     self.tr("全屏"),
        #     slot=self.toggleFullScreen,
        #     checkable=True,
        #     tip=self.tr("切换全屏模式")
        # )
    
    
    def _setupHelpMenu(self):
        """配置帮助菜单"""
        # 添加用户手册
        self.menubar.addHelpAction(
            'user_manual',
            self.tr("用户手册"),
            slot=self.showDocumentation,
            tip=self.tr("查看用户手册")
        )
        
        self.menubar.addSeparator('help')
        
        # 添加关于
        self.menubar.addHelpAction(
            'about',
            self.tr("关于"),
            slot=self.showAbout,
            tip=self.tr("关于本软件")
        )
    
    def _setupMenuCallbacks(self):
        """设置菜单标题点击回调（点击菜单标题切换页面）"""
        self.menubar.setMenuClickCallback('file', self.showVideoPage)      # 实时检测管理 -> 视频监控页面
        self.menubar.setMenuClickCallback('edit', self.showModelPage)      # 模型管理 -> 模型管理页面
        self.menubar.setMenuClickCallback('view', self.showDatasetPage)    # 数据集管理 -> 数据集管理页面

