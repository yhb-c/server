# -*- coding: utf-8 -*-

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui

# 导入图标工具（支持相对导入和独立运行）
try:
    # 优先使用相对导入（作为包的一部分时）
    from .style_manager import newIcon
except (ImportError, ValueError):
    # 独立运行时的处理
    import sys
    import os.path as osp
    # 将当前目录添加到路径
    sys.path.insert(0, osp.dirname(__file__))
    from style_manager import newIcon


class MenuBar(QtWidgets.QMenuBar):
    """
    自定义菜单栏组件
    
    模仿labelme设计，提供统一的菜单管理接口
    """
    
    # 自定义信号
    fileMenuTriggered = QtCore.Signal(str)  # 文件菜单触发
    editMenuTriggered = QtCore.Signal(str)  # 编辑菜单触发
    viewMenuTriggered = QtCore.Signal(str)  # 视图菜单触发
    toolsMenuTriggered = QtCore.Signal(str)  # 工具菜单触发
    helpMenuTriggered = QtCore.Signal(str)  # 帮助菜单触发
    
    def __init__(self, parent=None):
        super(MenuBar, self).__init__(parent)
        self._parent = parent
        self._actions = {}
        self._menus = {}
        
        self._initMenus()
    
    def _initMenus(self):
        """初始化菜单结构"""
        # 菜单点击回调字典
        self._menu_callbacks = {}
        
        # 文件菜单 - 实时检测管理（对应视频监控页面）
        self._menus['file'] = self.addMenu(self.tr("实时检测管理"))
        
        # 编辑菜单 - 模型管理（对应模型管理页面 page1）
        self._menus['edit'] = self.addMenu(self.tr("模型管理"))
        
        # 视图菜单 - 数据集管理（对应数据集管理页面 page2）
        self._menus['view'] = self.addMenu(self.tr("数据集管理"))
        
        # 帮助菜单
        self._menus['help'] = self.addMenu(self.tr("帮助"))
    
    def setMenuClickCallback(self, menu_name, callback):
        """
        设置菜单点击时的回调函数
        
        Args:
            menu_name: 菜单名称 ('file', 'edit', 'view', 'tools', 'help')
            callback: 回调函数
        """
        if menu_name in self._menus:
            self._menu_callbacks[menu_name] = callback
            # 连接菜单的aboutToShow信号到回调
            self._menus[menu_name].aboutToShow.connect(callback)
    
    def addFileAction(self, action_name, text, slot=None, shortcut=None, 
                      icon=None, tip=None, checkable=False):
        """
        添加文件菜单项
        
        Args:
            action_name: 动作名称（用于标识）
            text: 显示文本
            slot: 槽函数
            shortcut: 快捷键
            icon: 图标
            tip: 提示信息
            checkable: 是否可勾选
        """
        action = self._createAction(text, slot, shortcut, icon, tip, checkable)
        self._menus['file'].addAction(action)
        self._actions[action_name] = action
        return action
    
    def addEditAction(self, action_name, text, slot=None, shortcut=None,
                      icon=None, tip=None, checkable=False):
        """添加编辑菜单项"""
        action = self._createAction(text, slot, shortcut, icon, tip, checkable)
        self._menus['edit'].addAction(action)
        self._actions[action_name] = action
        return action
    
    def addViewAction(self, action_name, text, slot=None, shortcut=None,
                      icon=None, tip=None, checkable=False):
        """添加视图菜单项"""
        action = self._createAction(text, slot, shortcut, icon, tip, checkable)
        self._menus['view'].addAction(action)
        self._actions[action_name] = action
        return action
    
    def addToolsAction(self, action_name, text, slot=None, shortcut=None,
                       icon=None, tip=None, checkable=False):
        """添加工具菜单项"""
        action = self._createAction(text, slot, shortcut, icon, tip, checkable)
        self._menus['tools'].addAction(action)
        self._actions[action_name] = action
        return action
    
    def addHelpAction(self, action_name, text, slot=None, shortcut=None,
                      icon=None, tip=None, checkable=False):
        """添加帮助菜单项"""
        action = self._createAction(text, slot, shortcut, icon, tip, checkable)
        self._menus['help'].addAction(action)
        self._actions[action_name] = action
        return action
    
    def addSeparator(self, menu_name):
        """
        添加分隔符
        
        Args:
            menu_name: 菜单名称 ('file', 'edit', 'view', 'tools', 'help')
        """
        if menu_name in self._menus:
            self._menus[menu_name].addSeparator()
    
    def getAction(self, action_name):
        """获取指定的动作"""
        return self._actions.get(action_name)
    
    def getMenu(self, menu_name):
        """获取指定的菜单"""
        return self._menus.get(menu_name)
    
    def _createAction(self, text, slot=None, shortcut=None, icon=None,
                      tip=None, checkable=False):
        """
        创建动作的内部方法
        
        模仿labelme的utils.newAction设计
        
        Args:
            icon: 图标名称（字符串）或 QtGui.QIcon 对象
        """
        action = QtWidgets.QAction(text, self)
        
        if icon is not None:
            # 如果是字符串，使用 newIcon 加载；如果已经是 QIcon，直接使用
            if isinstance(icon, str):
                action.setIcon(newIcon(icon))
            else:
                action.setIcon(icon)
        
        if shortcut is not None:
            if isinstance(shortcut, (list, tuple)):
                action.setShortcuts(shortcut)
            else:
                action.setShortcut(shortcut)
        
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        
        if slot is not None:
            action.triggered.connect(slot)
        
        if checkable:
            action.setCheckable(True)
        
        return action
    
    def enableAction(self, action_name, enabled=True):
        """启用/禁用指定动作"""
        if action_name in self._actions:
            self._actions[action_name].setEnabled(enabled)
    
    def checkAction(self, action_name, checked=True):
        """勾选/取消勾选指定动作"""
        if action_name in self._actions:
            action = self._actions[action_name]
            if action.isCheckable():
                action.setChecked(checked)


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口作为容器
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("MenuBar 组件测试")
    main_window.resize(800, 600)
    
    # 创建并设置菜单栏
    menubar = MenuBar(main_window)
    main_window.setMenuBar(menubar)
    
    menubar.addFileAction(
        "open", "打开", 
        lambda: print("打开文件"), 
        "Ctrl+O",
        icon="文件夹",  # 使用图标名称
        tip="打开图像或视频文件"
    )
    menubar.addFileAction(
        "save", "保存", 
        lambda: print("保存文件"), 
        "Ctrl+S",
        icon="add",  # 使用图标名称
        tip="保存检测结果"
    )
    menubar.addSeparator('file')
    menubar.addFileAction(
        "exit", "退出", 
        app.quit, 
        "Ctrl+Q",
        icon="关闭",  # 使用图标名称
        tip="退出应用程序"
    )
    
    menubar.addEditAction(
        "undo", "撤销", 
        lambda: print("撤销"), 
        "Ctrl+Z",
        tip="撤销上一步操作"
    )
    menubar.addEditAction(
        "redo", "重做", 
        lambda: print("重做"), 
        "Ctrl+Y",
        tip="重做上一步操作"
    )
    
    menubar.addViewAction(
        "channel_panel", "通道面板", 
        lambda: print("切换通道面板"), 
        "F1",
        checkable=True,
        tip="显示/隐藏通道管理面板"
    )
    
    # 创建中央部件
    central_widget = QtWidgets.QWidget()
    label = QtWidgets.QLabel("MenuBar 组件独立调试\n\n请测试菜单功能\n图标已集成")
    label.setAlignment(QtCore.Qt.AlignCenter)
    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(label)
    central_widget.setLayout(layout)
    main_window.setCentralWidget(central_widget)
    
    main_window.show()
    sys.exit(app.exec_())

