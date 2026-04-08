# -*- coding: utf-8 -*-

"""
模型集管理页面

提供模型集列表显示、参数查看和管理功能
"""

import os
import yaml
from pathlib import Path

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt

# 导入字体管理器和响应式布局
try:
    from ..style_manager import FontManager
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    try:
        from widgets.style_manager import FontManager
        from widgets.responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        # 后备方案
        class FontManager:
            @staticmethod
            def applyToWidget(widget, **kwargs):
                pass
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x

# 导入消息框工具
try:
    from ...utils.message_box_utils import showWarning, showInformation, showCritical
except (ImportError, ValueError):
    try:
        from utils.message_box_utils import showWarning, showInformation, showCritical
    except ImportError:
        # 后备方案
        showWarning = lambda parent, title, msg: QtWidgets.QMessageBox.warning(parent, title, msg)
        showInformation = lambda parent, title, msg: QtWidgets.QMessageBox.information(parent, title, msg)
        showCritical = lambda parent, title, msg: QtWidgets.QMessageBox.critical(parent, title, msg)

# 导入图标工具函数
try:
    from ..icons import newIcon, newButton
except (ImportError, ValueError):
    try:
        from widgets.icons import newIcon, newButton
    except ImportError:
        # 后备方案：如果导入失败，定义空函数
        def newIcon(icon):
            from qtpy import QtGui
            return QtGui.QIcon()
        def newButton(text, icon=None, slot=None):
            btn = QtWidgets.QPushButton(text)
            if slot:
                btn.clicked.connect(slot)
            return btn


class ModelSetPage(QtWidgets.QWidget):
    """
    模型集管理页面（纯UI组件）
    
    提供模型列表显示、参数查看和管理操作
    业务逻辑由 handlers/modelpage/model_set_handler.py 处理
    """
    
    # ========== UI交互信号 ==========
    modelSetClicked = QtCore.Signal(str)        # 模型集被点击
    modelSetDoubleClicked = QtCore.Signal(str)  # 模型集被双击
    addSetClicked = QtCore.Signal()             # 添加模型集
    editSetClicked = QtCore.Signal()            # 编辑模型集
    deleteSetClicked = QtCore.Signal()          # 删除模型集
    loadSetClicked = QtCore.Signal()            # 加载模型集
    modelSettingsClicked = QtCore.Signal()      # 模型设置
    defaultModelChanged = QtCore.Signal(str)    # 默认模型已更改
    createNewModelClicked = QtCore.Signal()     # 创建新模型（用于按钮点击）
    
    # ========== 业务逻辑请求信号（由 handler 处理） ==========
    renameModelRequested = QtCore.Signal(str, str)     # 请求重命名 (old_name, new_name)
    duplicateModelRequested = QtCore.Signal(str, str)  # 请求复制 (model_name, new_name)
    deleteModelDataRequested = QtCore.Signal(str)      # 请求删除数据
    setDefaultRequested = QtCore.Signal(str)           # 请求设为默认
    
    # ========== 全局通知信号（通知所有相关页面） ==========
    modelListChanged = QtCore.Signal()                 # 模型列表已变化（添加/删除/重命名）
    
    def __init__(self, model_params=None, parent=None):
        """
        Args:
            model_params: 模型参数字典
            parent: 父窗口
        """
        super(ModelSetPage, self).__init__(parent)
        self._parent = parent
        self._model_params = model_params or {}
        self._current_default_model = None  # 当前默认模型名称
        self._model_order = []
        
        self._initUI()
        self._connectSignals()
        self._setupShortcuts()
        
        # 标记是否已加载过模型
        self._models_loaded = False
    
    def _initUI(self):
        """初始化UI - 简约labelme风格（三栏充实布局版）"""
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(8)
        
        # ========== 顶部标题栏（带统计信息） ==========
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)
        
        # 标题
        title = QtWidgets.QLabel("模型集管理")
        FontManager.applyToWidget(title, weight=FontManager.WEIGHT_BOLD)  # 使用全局默认字体，加粗
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # ========== 三栏内容区域（左侧统计 + 中间列表 + 右侧提示） ==========
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(15)
        
        # ========== 左侧统计信息面板 ==========
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # 统计标题
        stat_title = QtWidgets.QLabel("模型统计")
        stat_title.setStyleSheet("color: #333;")
        FontManager.applyToWidget(stat_title, weight=FontManager.WEIGHT_BOLD)  # 使用系统默认字体，加粗
        left_layout.addWidget(stat_title)
        
        # 统计信息组
        stat_group = QtWidgets.QGroupBox()
        stat_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                background-color: #fafafa;
            }
        """)
        stat_group_layout = QtWidgets.QVBoxLayout(stat_group)
        stat_group_layout.setSpacing(8)
        
        # 总数统计
        self.total_count_label = QtWidgets.QLabel("总数量: 0")
        self.total_count_label.setStyleSheet("color: #333;")
        FontManager.applyToWidget(self.total_count_label)  # 使用系统默认字体
        stat_group_layout.addWidget(self.total_count_label)
        
        # 默认模型
        self.default_model_label = QtWidgets.QLabel("默认: 无")
        self.default_model_label.setStyleSheet("color: #333;")
        FontManager.applyToWidget(self.default_model_label)  # 使用系统默认字体
        stat_group_layout.addWidget(self.default_model_label)
        
        left_layout.addWidget(stat_group)
        
        # 操作提示组
        tip_group = QtWidgets.QGroupBox()
        tip_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                background-color: #fafafa;
            }
        """)
        tip_group_layout = QtWidgets.QVBoxLayout(tip_group)
        tip_group_layout.setSpacing(8)
        
        tip_title = QtWidgets.QLabel("操作提示")
        tip_title.setStyleSheet("color: #333;")
        FontManager.applyToWidget(tip_title, weight=FontManager.WEIGHT_BOLD)  # 使用系统默认字体，加粗
        tip_group_layout.addWidget(tip_title)
        
        # 提示列表
        tips = [
            "右键模型可进行管理",
            "设为默认模型",
            "重命名模型",
            "复制模型",
            "删除模型"
        ]
        
        for tip in tips:
            tip_label = QtWidgets.QLabel(f"• {tip}")
            tip_label.setStyleSheet("color: #666;")
            FontManager.applyToWidget(tip_label)  # 使用系统默认字体
            tip_label.setWordWrap(True)
            tip_group_layout.addWidget(tip_label)
        
        left_layout.addWidget(tip_group)
        
        # 快捷操作组
        quick_group = QtWidgets.QGroupBox()
        quick_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: #fafafa;
            }
        """)
        quick_layout = QtWidgets.QVBoxLayout(quick_group)
        quick_layout.setSpacing(6)
        
        quick_title = QtWidgets.QLabel("快捷操作")
        quick_title.setStyleSheet("color: #333;")
        FontManager.applyToWidget(quick_title, weight=FontManager.WEIGHT_BOLD)  # 使用系统默认字体，加粗
        quick_layout.addWidget(quick_title)
        
        # 快捷键说明
        shortcuts = [
            "F5：刷新列表",
            "F2：重命名",
            "Del：删除"
        ]
        
        for shortcut in shortcuts:
            shortcut_label = QtWidgets.QLabel(shortcut)
            shortcut_label.setStyleSheet("color: #666;")
            FontManager.applyToWidget(shortcut_label)  # 使用系统默认字体
            quick_layout.addWidget(shortcut_label)
        
        left_layout.addWidget(quick_group)
        left_layout.addStretch()
        
        # 🔥 设置左侧宽度 - 响应式布局
        ResponsiveLayout.apply_to_widget(left_widget, min_width=150, max_width=180)
        
        content_layout.addWidget(left_widget)
        
        # ========== 中间主内容区（左右分栏：模型列表 + 文本显示） ==========
        # 使用QSplitter实现可缩放的分隔符
        center_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        center_splitter.setChildrenCollapsible(False)  # 防止面板被完全折叠
        
        # 设置splitter样式
        center_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
                width: 6px;
                margin: 2px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #d0d0d0;
            }
            QSplitter::handle:pressed {
                background-color: #b0b0b0;
            }
        """)
        
        # ===== 左侧：模型列表区域 =====
        left_list_widget = QtWidgets.QWidget()
        left_list_layout = QtWidgets.QVBoxLayout(left_list_widget)
        left_list_layout.setContentsMargins(0, 0, 0, 0)
        left_list_layout.setSpacing(8)
        
        # 搜索栏（简约样式）
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setSpacing(5)
        
        search_label = QtWidgets.QLabel("搜索:")
        FontManager.applyToWidget(search_label)  # 使用系统默认字体
        search_layout.addWidget(search_label)
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("输入模型名称进行筛选...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 8px;
                border: 1px solid #ccc;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
        """)
        FontManager.applyToWidget(self.search_input)  # 使用系统默认字体
        self.search_input.textChanged.connect(self._filterModels)
        search_layout.addWidget(self.search_input)
        
        left_list_layout.addLayout(search_layout)
        
        # 模型列表（简约labelme样式）
        self.model_set_list = QtWidgets.QListWidget()
        self.model_set_list.setAlternatingRowColors(False)
        self.model_set_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                min-height: 22px;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #e5f3ff;
            }
        """)
        FontManager.applyToWidget(self.model_set_list)  # 使用系统默认字体
        self.model_set_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.model_set_list.setDragEnabled(True)
        self.model_set_list.setAcceptDrops(True)
        self.model_set_list.setDropIndicatorShown(True)
        self.model_set_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        # 启用右键菜单
        self.model_set_list.setContextMenuPolicy(Qt.CustomContextMenu)
        # 安装事件过滤器以捕获空白区域点击
        self.model_set_list.viewport().installEventFilter(self)
        left_list_layout.addWidget(self.model_set_list)
        
        # ===== 右侧：文本显示区域 =====
        right_text_widget = QtWidgets.QWidget()
        right_text_layout = QtWidgets.QVBoxLayout(right_text_widget)
        right_text_layout.setContentsMargins(0, 0, 0, 0)
        right_text_layout.setSpacing(8)
        
        # 文本显示区域标题
        text_title_label = QtWidgets.QLabel("模型信息")
        FontManager.applyToWidget(text_title_label)
        text_title_label.setStyleSheet("font-weight: bold; padding: 4px;")
        right_text_layout.addWidget(text_title_label)
        
        # 文本显示框
        self.model_info_text = QtWidgets.QTextEdit()
        self.model_info_text.setReadOnly(True)
        self.model_info_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                background-color: white;
            }
        """)
        self.model_info_text.setPlaceholderText("选择模型后将显示模型文件夹内的txt文件内容...")
        # 应用全局字体管理
        FontManager.applyToWidget(self.model_info_text)  # 使用全局默认字体
        right_text_layout.addWidget(self.model_info_text)
        
        # 将左右两部分添加到splitter
        center_splitter.addWidget(left_list_widget)
        center_splitter.addWidget(right_text_widget)
        
        # 设置初始比例（1:1）
        center_splitter.setSizes([400, 400])
        center_splitter.setStretchFactor(0, 1)  # 左侧可伸缩
        center_splitter.setStretchFactor(1, 1)  # 右侧可伸缩
        
        # 🔥 设置中间区域的宽度（主要内容区）- 响应式布局
        center_splitter.setMinimumWidth(scale_w(800))
        
        content_layout.addWidget(center_splitter, 3)
        
        main_layout.addLayout(content_layout)
    
    
    def eventFilter(self, obj, event):
        """事件过滤器：捕获列表空白区域的右键点击"""
        if obj == self.model_set_list.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                # 检查是否是右键点击
                if event.button() == Qt.RightButton:
                    # 获取点击位置
                    pos = event.pos()
                    # 检查点击位置是否在某个项目上
                    item = self.model_set_list.itemAt(pos)
                    if item is None:
                        # 右键点击了空白区域，触发刷新
                        self.loadModelsFromConfig()
                        return True
        return super(ModelSetPage, self).eventFilter(obj, event)
    
    def _connectSignals(self):
        """连接信号"""
        self.model_set_list.itemClicked.connect(self._onModelSetClicked)
        self.model_set_list.itemDoubleClicked.connect(self._onModelSetDoubleClicked)
        self.model_set_list.customContextMenuRequested.connect(self._showContextMenu)
        if hasattr(self.model_set_list, "model"):
            try:
                self.model_set_list.model().rowsMoved.connect(self._onListReordered)
            except AttributeError:
                pass

    def _setupShortcuts(self):
        """绑定快捷键操作"""
        self._shortcut_refresh = QtWidgets.QShortcut(QtGui.QKeySequence("F5"), self)
        self._shortcut_refresh.activated.connect(self.loadModelsFromConfig)

        self._shortcut_rename = QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self)
        self._shortcut_rename.activated.connect(self._triggerRenameShortcut)

        self._shortcut_delete = QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self)
        self._shortcut_delete.activated.connect(self._triggerDeleteShortcut)

        self._shortcut_duplicate = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self._shortcut_duplicate.activated.connect(self._triggerDuplicateShortcut)

    def _triggerRenameShortcut(self):
        current_name = self._getCurrentModelName()
        if current_name:
            self.renameModel(current_name)

    def _triggerDeleteShortcut(self):
        current_name = self._getCurrentModelName()
        if current_name:
            self.deleteModel(current_name)

    def _triggerDuplicateShortcut(self):
        current_name = self._getCurrentModelName()
        if current_name:
            self.duplicateModel(current_name)

    def _getCurrentModelName(self):
        item = self.model_set_list.currentItem()
        if not item:
            return None
        return self._stripDecorations(item.text())

    def _stripDecorations(self, display_name):
        """移除显示名称中的装饰标签"""
        name = display_name.replace("（默认）", "")
        name = name.replace("（已加载）", "")
        return name.strip()

    def _getItemByModelName(self, model_name):
        """根据真实模型名获取列表项"""
        for i in range(self.model_set_list.count()):
            item = self.model_set_list.item(i)
            if self._stripDecorations(item.text()) == model_name:
                return item
        return None

    def _onListReordered(self, *args, **kwargs):
        """拖拽调整顺序后刷新内部顺序状态"""
        self._updateModelOrder()
    
    def _filterModels(self, search_text):
        """根据搜索文本过滤模型列表"""
        search_text = search_text.lower().strip()
        
        visible_count = 0
        for i in range(self.model_set_list.count()):
            item = self.model_set_list.item(i)
            item_text = item.text().lower()
            
            # 如果搜索文本为空，或者项目文本包含搜索文本，则显示
            if not search_text or search_text in item_text:
                item.setHidden(False)
                visible_count += 1
            else:
                item.setHidden(True)
        
        # 更新统计信息
        self._updateStats()
    
    def _updateStats(self):
        """更新统计信息（顶部和左侧面板）"""
        total_count = self.model_set_list.count()
        visible_count = sum(1 for i in range(total_count) if not self.model_set_list.item(i).isHidden())
        
        # 查找默认模型
        default_model = None
        for i in range(total_count):
            item = self.model_set_list.item(i)
            if "（默认）" in item.text():
                default_model = item.text().replace("（默认）", "").strip()
                break
        
        # 更新左侧统计面板
        if hasattr(self, 'total_count_label'):
            self.total_count_label.setText(f"总数量: {total_count}")
        
        if hasattr(self, 'default_model_label'):
            if default_model:
                # 截断过长的名称
                if len(default_model) > 18:
                    default_display = default_model[:18] + "..."
                else:
                    default_display = default_model
                self.default_model_label.setText(f"默认: {default_display}")
            else:
                self.default_model_label.setText("默认: 无")

    def _updateModelOrder(self):
        """记录当前列表顺序"""
        self._model_order = []
        for i in range(self.model_set_list.count()):
            display = self.model_set_list.item(i).text()
            self._model_order.append(self._stripDecorations(display))
    
    def _onNewModelCreated(self, model_info):
        """
        处理从NewModelPage创建的新模型
        
        Args:
            model_info: 模型信息字典，包含以下键：
                - name: 模型名称
                - type: 模型类型
                - file: 模型文件路径
                - config: 配置文件路径（可选）
                - classes: 类别文件路径（可选）
                - description: 模型描述（可选）
        """
        try:
            # 1. 验证模型信息
            model_name = model_info.get('name', '').strip()
            model_file = model_info.get('file', '').strip()
            
            if not model_name:
                showWarning(self, "错误", "模型名称不能为空")
                return
            
            if not model_file:
                showWarning(self, "错误", "模型文件不能为空")
                return
            
            # 检查文件是否存在
            if not os.path.exists(model_file):
                showWarning(
                    self, "错误", 
                    f"模型文件不存在:\n{model_file}"
                )
                return
            
            # 2. 检查模型名称是否已存在
            if model_name in self._model_params:
                # 创建无图标的消息框
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle("模型已存在")
                msg_box.setText(f"模型 '{model_name}' 已存在，是否覆盖？")
                msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
                msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
                
                # 设置中文按钮文本
                yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
                no_btn = msg_box.button(QtWidgets.QMessageBox.No)
                if yes_btn:
                    yes_btn.setText("是")
                if no_btn:
                    no_btn.setText("否")
                
                reply = msg_box.exec_()
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            
            # 3. 获取文件大小
            try:
                file_size_bytes = os.path.getsize(model_file)
                file_size_mb = file_size_bytes / (1024 * 1024)
                size_str = f"{file_size_mb:.1f} MB"
            except:
                size_str = "未知"
            
            # 4. 确定模型类型
            model_type = model_info.get('type', '未知')
            if model_file.endswith('.pt'):
                if '预训练模型' not in model_type and model_type == '未知':
                    model_type = "PyTorch"
            elif model_file.endswith('.dat'):
                model_type = ".dat"
            elif model_file.endswith('.onnx'):
                model_type = "ONNX"
            elif model_file.endswith('.engine'):
                model_type = "TensorRT"
            
            # 5. 创建模型参数字典
            model_params = {
                "name": model_name,
                "type": model_type,
                "path": model_file,
                "size": size_str,
                "classes": 80,  # 默认类别数
                "input": "640x640",  # 默认输入尺寸
                "confidence": 0.5,
                "iou": 0.45,
                "device": "CUDA:0 (GPU)",
                "batch_size": 16,
                "blur_training": 100,
                "epochs": 300,
                "workers": 8,
                "config_path": model_info.get('config', ''),
                "classes_file": model_info.get('classes', ''),
                "description": model_info.get('description', '')
            }
            
            # 6. 添加到模型参数字典
            self._model_params[model_name] = model_params
            
            # 7. 添加到列表显示
            # 先检查是否已存在于列表中
            existing_items = []
            for i in range(self.model_set_list.count()):
                item_text = self.model_set_list.item(i).text()
                item_name = item_text.replace("（默认）", "").strip()
                existing_items.append(item_name)
            
            if model_name not in existing_items:
                self.addModelToList(model_name)
            else:
                # 更新现有项
                for i in range(self.model_set_list.count()):
                    item_text = self.model_set_list.item(i).text()
                    item_name = item_text.replace("（默认）", "").strip()
                    if item_name == model_name:
                        # 保留（默认）标记
                        if "（默认）" in item_text:
                            self.model_set_list.item(i).setText(f"{model_name}（默认）")
                        break
            
            # 8. 选中新创建的模型
            for i in range(self.model_set_list.count()):
                item_text = self.model_set_list.item(i).text()
                item_name = item_text.replace("（默认）", "").strip()
                if item_name == model_name:
                    self.model_set_list.setCurrentRow(i)
                    break
            
            # 9. 显示成功消息
            showInformation(
                self, "创建成功",
                f"模型 '{model_name}' 创建成功！\n\n"
                f"类型: {model_type}\n"
                f"大小: {size_str}\n"
                f"文件: {model_file}\n\n"
                f"模型已添加到模型列表中。"
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            showCritical(
                self, "错误",
                f"创建新模型失败:\n{str(e)}"
            )
    
    def _onModelSetClicked(self, item):
        """模型集列表项被点击"""
        display_name = item.text()
        # 移除"（默认）"标记，获取实际的模型名称
        model_name = display_name.replace("（默认）", "").strip()
        
        # 读取并显示模型文件夹内的txt文件
        self._loadModelTxtFiles(model_name)
        
        # 发射信号通知外部模型已被选中
        self.modelSetClicked.emit(display_name)
    
    def _onModelSetDoubleClicked(self, item):
        """模型集列表项被双击"""
        model_set_name = self._stripDecorations(item.text())
        # 出于安全策略，双击不再显示详细信息，仅发射信号
        self.modelSetDoubleClicked.emit(model_set_name)
    
    def _showEditMenu(self):
        """显示编辑菜单（在编辑按钮下方）"""
        # 检查是否有选中的模型
        current_item = self.model_set_list.currentItem()
        if not current_item:
            showWarning(self, "警告", "请先选择一个模型")
            return
        
        # 创建菜单
        menu = QtWidgets.QMenu(self)
        
        # 获取实际模型名称
        display_name = current_item.text()
        model_name = self._stripDecorations(display_name)
        
        # 判断是否已经是默认模型
        is_default = "（默认）" in display_name
        
        # 添加菜单项
        if is_default:
            # 如果已经是默认模型，显示"取消默认"
            action_cancel_default = menu.addAction(" 取消默认")
            action_cancel_default.triggered.connect(lambda: self.cancelDefaultModel(model_name))
        else:
            # 如果不是默认模型，显示"设为默认"
            action_set_default = menu.addAction(" 设为默认")
            action_set_default.triggered.connect(lambda: self.setAsDefaultModel(model_name))
        
        menu.addSeparator()
        
        # 其他编辑选项
        action_rename = menu.addAction(" 重命名")
        action_rename.triggered.connect(lambda: self.renameModel(model_name))
        
        action_duplicate = menu.addAction(" 复制模型")
        action_duplicate.triggered.connect(lambda: self.duplicateModel(model_name))
        
        menu.addSeparator()
        
        action_delete = menu.addAction(" 删除模型")
        action_delete.triggered.connect(lambda: self.deleteModel(model_name))
        
        # 在编辑按钮下方显示菜单
        button_pos = self.btn_edit_set.mapToGlobal(self.btn_edit_set.rect().bottomLeft())
        menu.exec_(button_pos)
    
    def _showContextMenu(self, position):
        """显示右键菜单（只保留有实际功能的选项）"""
        # 获取点击位置的项
        item = self.model_set_list.itemAt(position)
        if not item:
            return
        
        # 创建菜单
        menu = QtWidgets.QMenu(self)
        
        # 获取实际模型名称
        display_name = item.text()
        model_name = self._stripDecorations(display_name)
        
        # 判断是否已经是默认模型
        is_default = "（默认）" in display_name
        
        # 1. 设为默认模型（有实际功能）
        if is_default:
            action_default = menu.addAction("已是默认模型")
            action_default.setEnabled(False)
        else:
            action_set_default = menu.addAction("设为默认模型")
            action_set_default.triggered.connect(lambda: self.setAsDefaultModel(model_name))
        
        menu.addSeparator()
        
        # 2. 重命名模型（有实际功能）
        action_rename = menu.addAction("重命名")
        action_rename.triggered.connect(lambda: self.renameModel(model_name))
        
        # 3. 复制模型（有实际功能）
        action_duplicate = menu.addAction("复制模型")
        action_duplicate.triggered.connect(lambda: self.duplicateModel(model_name))
        
        # 4. 添加至检测模型（新功能）
        action_add_to_detection = menu.addAction("添加至检测模型")
        action_add_to_detection.triggered.connect(lambda: self.addToDetectionModel(model_name))
        
        menu.addSeparator()
        
        # 5. 查看模型信息（新功能）
        action_view_info = menu.addAction("查看模型信息")
        action_view_info.triggered.connect(lambda: self.viewModelInfo(model_name))
        
        menu.addSeparator()
        
        # 6. 删除模型（有实际功能）
        action_delete = menu.addAction("删除模型")
        action_delete.triggered.connect(lambda: self.deleteModel(model_name))
        
        # 显示菜单
        menu.exec_(self.model_set_list.mapToGlobal(position))
    
    
    def setAsDefaultModel(self, model_name):
        """设置指定模型为默认模型"""
        # 移除旧默认标记
        if self._current_default_model:
            old_item = self._getItemByModelName(self._current_default_model)
            if old_item:
                txt = self._stripDecorations(old_item.text())
                loaded = "（已加载）" in old_item.text()
                new_txt = txt + ("（已加载）" if loaded else "")
                old_item.setText(new_txt)
        
        # 设置新默认
        new_item = self._getItemByModelName(model_name)
        if not new_item:
            return
        
        base_txt = self._stripDecorations(new_item.text())
        loaded = "（已加载）" in new_item.text()
        display_txt = f"{base_txt}（默认）"
        if loaded:
            display_txt += "（已加载）"
        new_item.setText(display_txt)
        
        self._current_default_model = model_name
        self.defaultModelChanged.emit(model_name)
        self.setDefaultRequested.emit(model_name)
        self._updateStats()
        
        # 通知训练页面刷新基础模型列表
        self._notifyTrainingPageRefresh()
    
    def updateModelParams(self, model_name):
        """更新模型参数显示（已移除右侧参数显示，保留方法以保持兼容性）"""
        # 方法保留以保持API兼容性，但不再执行任何操作
        pass
    
    def clearModelParams(self):
        """清空模型参数显示（已移除右侧参数显示，保留方法以保持兼容性）"""
        # 方法保留以保持API兼容性，但不再执行任何操作
        pass
    
    # ========== 原有方法 ==========
    
    def addModelToList(self, model_name):
        """添加模型到列表"""
        self.model_set_list.addItem(model_name)
        # 更新统计信息
        self._updateStats()
        self._updateModelOrder()
    
    def refreshModelList(self):
        """刷新模型列表显示"""
        try:
            # 清空现有列表
            self.model_set_list.clear()
            
            # 重新添加所有模型
            for model_name in self._model_params.keys():
                # 构建显示文本
                display_text = model_name
                
                # 如果是默认模型，添加标记（使用统一格式）
                if model_name == self._current_default_model:
                    display_text = f"{model_name}（默认）"
                
                self.model_set_list.addItem(display_text)
            
            # 更新统计信息
            self._updateStats()
            self._updateModelOrder()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def updateModelLoadStatus(self, loaded_models):
        """
        更新模型加载状态显示
        
        Args:
            loaded_models: 已加载的模型字典 {模型名: 状态信息}
        """
        try:
            # 遍历所有模型项，更新显示状态
            for i in range(self.model_set_list.count()):
                item = self.model_set_list.item(i)
                base_name = self._stripDecorations(item.text())
                is_default = "（默认）" in item.text()
                should_mark_loaded = (
                    base_name in loaded_models and
                    loaded_models[base_name].get('status') == 'loaded'
                )

                display = base_name
                if is_default:
                    display += "（默认）"
                if should_mark_loaded:
                    display += "（已加载）"

                if item.text() != display:
                    item.setText(display)
            
        except Exception as e:
            pass
    
    def getModelLoadStatus(self, model_name):
        """
        获取模型的加载状态
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 是否已加载
        """
        try:
            # 检查父窗口是否有加载状态信息
            if hasattr(self._parent, 'isModelLoaded'):
                return self._parent.isModelLoaded(model_name)
            return False
        except Exception as e:
            pass
            return False
    
    def removeModelFromList(self, model_name):
        """从列表移除模型"""
        item = self._getItemByModelName(model_name)
        if item:
            row = self.model_set_list.row(item)
            self.model_set_list.takeItem(row)
        # 更新统计信息
        self._updateStats()
        self._updateModelOrder()
    
    def clearModelList(self):
        """清空模型列表"""
        self.model_set_list.clear()
        # 更新统计信息
        self._updateStats()
        self._model_order = []
    
    def getCurrentModel(self):
        """获取当前选中的模型"""
        current_item = self.model_set_list.currentItem()
        return current_item.text() if current_item else None
    
    def selectModel(self, model_name):
        """选中指定模型"""
        items = self.model_set_list.findItems(model_name, Qt.MatchExactly)
        if items:
            self.model_set_list.setCurrentItem(items[0])
    
    def getAllModels(self):
        """
        获取所有已加载的模型列表
        
        Returns:
            list: 模型名称列表（包含"（默认）"标记）
        """
        models = []
        for i in range(self.model_set_list.count()):
            item = self.model_set_list.item(i)
            models.append(item.text())
        return models
    
    def getAllModelParams(self):
        """
        获取所有模型的参数信息
        
        Returns:
            dict: 模型参数字典 {模型名称: 参数字典}
        """
        return self._model_params.copy()
    
    def getDefaultModel(self):
        """
        获取当前默认模型
        
        Returns:
            str: 默认模型名称，如果没有则返回None
        """
        return self._current_default_model
    
    def cancelDefaultModel(self, model_name):
        """取消默认模型"""
        if self._current_default_model == model_name:
            self._current_default_model = None
            
            # 更新列表显示，移除"（默认）"标记
            item = self._getItemByModelName(model_name)
            if item:
                base = self._stripDecorations(item.text())
                loaded = "（已加载）" in item.text()
                display = base + ("（已加载）" if loaded else "")
                item.setText(display)
            
            # 更新统计信息
            self._updateStats()
            
            pass
            showInformation(self, "操作成功", f"已取消 '{model_name}' 的默认状态")
    
    def renameModel(self, model_name):
        """重命名模型（UI交互，业务逻辑由 handler 处理）"""
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "重命名模型", f"请输入新的模型名称:", 
            text=model_name
        )
        
        if ok and new_name.strip() and new_name.strip() != model_name:
            new_name = new_name.strip()
            
            # 发射信号，由 handler 处理业务逻辑
            self.renameModelRequested.emit(model_name, new_name)
            
            # 更新内部参数
            if model_name in self._model_params:
                params = self._model_params.pop(model_name)
                params['name'] = new_name
                self._model_params[new_name] = params
            
            # UI更新：更新列表显示
            item = self._getItemByModelName(model_name)
            if item:
                was_default = (self._current_default_model == model_name)
                was_loaded = "（已加载）" in item.text()
                
                display_name = new_name
                if was_default:
                    display_name += "（默认）"
                    self._current_default_model = new_name
                if was_loaded:
                    display_name += "（已加载）"
                
                item.setText(display_name)
            
            # 更新统计信息
            self._updateStats()
            self._updateModelOrder()
            
            showInformation(self, "操作成功", f"模型已重命名为 '{new_name}'")
    
    def duplicateModel(self, model_name):
        """复制模型（UI交互，业务逻辑由 handler 处理）"""
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "复制模型", f"请输入新模型的名称:", 
            text=f"{model_name}_副本"
        )
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            
            # 发射信号，由 handler 处理业务逻辑
            self.duplicateModelRequested.emit(model_name, new_name)
            
            # 复制内部参数
            if model_name in self._model_params:
                params = dict(self._model_params[model_name])
                params['name'] = new_name
                self._model_params[new_name] = params
            
            # UI更新：添加到列表
            self.addModelToList(new_name)
            
            showInformation(self, "操作成功", f"模型已复制为 '{new_name}'")
    
    def deleteModel(self, model_name):
        """删除模型（UI交互，业务逻辑由 handler 处理）"""
        # 创建无图标的消息框
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("确认删除")
        msg_box.setText(f"确定要删除模型 '{model_name}' 吗？\n\n此操作不可撤销！")
        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
        msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        # 设置中文按钮文本
        yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
        no_btn = msg_box.button(QtWidgets.QMessageBox.No)
        if yes_btn:
            yes_btn.setText("是")
        if no_btn:
            no_btn.setText("否")
        
        reply = msg_box.exec_()
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # 发射信号，由 handler 处理业务逻辑
                self.deleteModelDataRequested.emit(model_name)
                
                # UI更新：从列表中删除
                self.removeModelFromList(model_name)
                
                # 更新内部状态
                self._model_params.pop(model_name, None)
                if self._current_default_model == model_name:
                    self._current_default_model = None
                    self._updateStats()
                
                self._updateModelOrder()
                
                # 通知训练页面刷新基础模型列表
                self._notifyTrainingPageRefresh()
                
            except Exception as e:
                showCritical(self, "删除失败", f"删除模型时发生错误: {e}")
    
    def addToDetectionModel(self, model_name):
        """将模型添加至检测模型目录"""
        try:
            # 获取模型信息
            if model_name not in self._model_params:
                showWarning(self, "错误", f"未找到模型 '{model_name}' 的信息")
                return
            
            model_info = self._model_params[model_name]
            source_path = model_info.get('path', '')
            
            if not source_path or not os.path.exists(source_path):
                showWarning(self, "错误", f"模型文件不存在: {source_path}")
                return
            
            # 确认对话框 - 使用全局对话框管理器
            from ..style_manager import show_question
            
            message = f"确定要将模型 '{model_name}' 添加至检测模型目录吗？\n模型文件夹将被移动到 detection_model 目录中"
            confirmed = show_question(self, "确认操作", message, "是", "否")
            
            if confirmed:
                self._moveModelToDetection(model_name, source_path)
                
        except Exception as e:
            showCritical(self, "操作失败", f"添加至检测模型时发生错误: {e}")
    
    def viewModelInfo(self, model_name):
        """查看模型信息（来源和训练指标）"""
        try:
            # 获取模型参数
            if model_name not in self._model_params:
                showWarning(self, "错误", f"未找到模型 '{model_name}' 的信息")
                return
            
            model_params = self._model_params[model_name]
            model_path = model_params.get('path', '')
            
            if not model_path or not os.path.exists(model_path):
                showWarning(self, "错误", f"模型文件不存在: {model_path}")
                return
            
            # 读取模型配置和训练指标
            model_info = self._readModelTrainingInfo(model_path, model_name)
            
            # 创建并显示信息对话框
            self._showModelInfoDialog(model_name, model_params, model_info)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            showCritical(self, "错误", f"查看模型信息时发生错误: {e}")
    
    def _readModelTrainingInfo(self, model_path, model_name):
        """读取模型的训练配置和指标信息"""
        info = {
            'config': {},
            'metrics': {},
            'training_date': None,
            'source': '未知'
        }
        
        try:
            from pathlib import Path
            model_file = Path(model_path)
            
            # 1. 确定模型所在目录
            if model_file.is_file():
                model_dir = model_file.parent
            else:
                model_dir = model_file
            
            # 2. 尝试读取config.yaml（训练配置）
            config_file = model_dir / 'config.yaml'
            if not config_file.exists():
                # 尝试上一级目录
                config_file = model_dir.parent / 'config.yaml'
            
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    info['config'] = yaml.safe_load(f) or {}
                    info['training_date'] = info['config'].get('training_date', '未知')
                    info['source'] = '训练生成'
            
            # 3. 尝试读取results.csv（训练指标）
            results_file = model_dir / 'results.csv'
            if not results_file.exists():
                # 尝试train子目录
                results_file = model_dir.parent / 'train' / 'results.csv'
            
            if results_file.exists():
                import pandas as pd
                try:
                    df = pd.read_csv(results_file)
                    if len(df) > 0:
                        # 获取最后一行（最终指标）
                        last_row = df.iloc[-1]
                        info['metrics'] = {
                            'epoch': int(last_row.get('epoch', 0)) if 'epoch' in last_row else len(df),
                            'train_loss': float(last_row.get('train/box_loss', 0)) if 'train/box_loss' in last_row else None,
                            'val_loss': float(last_row.get('val/box_loss', 0)) if 'val/box_loss' in last_row else None,
                            'precision': float(last_row.get('metrics/precision(B)', 0)) if 'metrics/precision(B)' in last_row else None,
                            'recall': float(last_row.get('metrics/recall(B)', 0)) if 'metrics/recall(B)' in last_row else None,
                            'mAP50': float(last_row.get('metrics/mAP50(B)', 0)) if 'metrics/mAP50(B)' in last_row else None,
                            'mAP50-95': float(last_row.get('metrics/mAP50-95(B)', 0)) if 'metrics/mAP50-95(B)' in last_row else None,
                        }
                except Exception as e:
                    print(f"读取results.csv失败: {e}")
            
            # 4. 如果没有配置文件，从文件路径判断来源
            if not info['config']:
                if 'train_model' in str(model_path):
                    info['source'] = '本地训练'
                elif 'detection_model' in str(model_path):
                    info['source'] = '检测模型'
                else:
                    info['source'] = '导入模型'
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"读取模型训练信息失败: {e}")
        
        return info
    
    def _showModelInfoDialog(self, model_name, model_params, model_info):
        """显示模型信息对话框（简化版 - 只显示训练配置）"""
        # 创建对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"模型升级配置 - {model_name}")
        dialog.setMinimumWidth(450)
        dialog.setMinimumHeight(400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QtWidgets.QLabel(f"<h3>{model_name}</h3>")
        layout.addWidget(title_label)
        
        # 创建表单布局显示训练配置
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # 设置表单样式
        form_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLabel {
                padding: 3px;
            }
        """)
        
        # 从配置中提取训练参数
        config = model_info.get('config', {})
        
        # 基础信息
        info_label = QtWidgets.QLabel(f"<b>模型来源：</b>{model_info['source']}")
        form_layout.addRow("", info_label)
        
        if model_info.get('training_date'):
            date_label = QtWidgets.QLabel(f"<b>训练日期：</b>{model_info['training_date']}")
            form_layout.addRow("", date_label)
        
        # 添加分隔线
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.HLine)
        separator1.setFrameShadow(QtWidgets.QFrame.Sunken)
        form_layout.addRow(separator1)
        
        # 训练配置参数（仿照训练页面的格式）
        epochs = config.get('epochs', '未知')
        batch_size = config.get('batch', config.get('batch_size', '未知'))
        imgsz = config.get('imgsz', '未知')
        workers = config.get('workers', '未知')
        device = config.get('device', '未知')
        optimizer = config.get('optimizer', '未知')
        
        form_layout.addRow("训练轮数:", QtWidgets.QLabel(f"<b>{epochs} 轮</b>"))
        form_layout.addRow("批次大小:", QtWidgets.QLabel(f"<b>{batch_size}</b>"))
        form_layout.addRow("图像尺寸:", QtWidgets.QLabel(f"<b>{imgsz} px</b>"))
        form_layout.addRow("Workers:", QtWidgets.QLabel(f"<b>{workers} 线程</b>"))
        form_layout.addRow("训练设备:", QtWidgets.QLabel(f"<b>{device}</b>"))
        form_layout.addRow("优化器:", QtWidgets.QLabel(f"<b>{optimizer}</b>"))
        
        # 如果有训练指标，显示最终性能
        metrics = model_info.get('metrics', {})
        if metrics:
            separator2 = QtWidgets.QFrame()
            separator2.setFrameShape(QtWidgets.QFrame.HLine)
            separator2.setFrameShadow(QtWidgets.QFrame.Sunken)
            form_layout.addRow(separator2)
            
            mAP50 = metrics.get('mAP50')
            mAP5095 = metrics.get('mAP50-95')
            
            if mAP50 is not None:
                form_layout.addRow("mAP@0.5:", QtWidgets.QLabel(f"<b style='color: #28a745;'>{mAP50:.4f}</b>"))
            if mAP5095 is not None:
                form_layout.addRow("mAP@0.5:0.95:", QtWidgets.QLabel(f"<b style='color: #28a745;'>{mAP5095:.4f}</b>"))
        
        layout.addWidget(form_widget)
        
        # 如果没有训练配置，显示提示
        if not config:
            no_config_label = QtWidgets.QLabel(
                "<i>该模型没有训练配置信息<br>"
                "可能是外部导入的模型</i>"
            )
            no_config_label.setAlignment(Qt.AlignCenter)
            no_config_label.setStyleSheet("color: #999; padding: 20px;")
            layout.addWidget(no_config_label)
        
        layout.addStretch()
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 应用全局字体管理器到对话框及其所有子控件
        FontManager.applyToWidgetRecursive(dialog)
        
        # 显示对话框
        dialog.exec_()
    
    def _moveModelToDetection(self, model_name, source_path):
        """执行模型移动操作 - 移动到服务端检测模型目录"""
        try:
            from client.utils.config import RemoteConfigManager
            
            # 使用远程配置管理器
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                showCritical(self, "移动失败", "SSH连接不可用，无法移动模型到服务端")
                return
            
            # 服务端目标目录
            detection_model_dir = "/home/lqj/liquid/server/database/model/detection_model"
            
            # 确保服务端目标目录存在
            mkdir_cmd = f"mkdir -p {detection_model_dir}"
            ssh_manager.execute_remote_command(mkdir_cmd)
            
            # 查找下一个可用的数字目录
            list_cmd = f"find {detection_model_dir} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -n"
            result = ssh_manager.execute_remote_command(list_cmd)
            
            existing_dirs = []
            if result['success'] and result['stdout']:
                for dir_path in result['stdout'].strip().split('\n'):
                    if dir_path:
                        dir_name = os.path.basename(dir_path)
                        if dir_name.isdigit():
                            existing_dirs.append(int(dir_name))
            
            next_id = max(existing_dirs) + 1 if existing_dirs else 1
            target_folder = f"{detection_model_dir}/{next_id}"
            
            # 如果源路径是本地路径，需要先上传到服务端
            if os.path.exists(source_path):
                # 本地文件，需要上传
                source_file = Path(source_path)
                source_folder = source_file.parent
                
                # 创建服务端目标目录
                mkdir_target_cmd = f"mkdir -p {target_folder}"
                ssh_manager.execute_remote_command(mkdir_target_cmd)
                
                # 使用scp上传整个文件夹
                upload_cmd = f"scp -r {source_folder}/* liquid:{target_folder}/"
                import subprocess
                upload_result = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True)
                
                if upload_result.returncode != 0:
                    showCritical(self, "移动失败", f"上传模型到服务端失败: {upload_result.stderr}")
                    return
                
                print(f"[信息] 成功上传模型到服务端: {target_folder}")
            else:
                # 服务端路径，直接移动
                source_folder = os.path.dirname(source_path)
                move_cmd = f"mv {source_folder} {target_folder}"
                move_result = ssh_manager.execute_remote_command(move_cmd)
                
                if not move_result['success']:
                    showCritical(self, "移动失败", f"在服务端移动模型失败: {move_result.get('stderr', '未知错误')}")
                    return
                
                print(f"[信息] 成功在服务端移动模型: {target_folder}")
            
            # 从当前列表中移除模型
            self.removeModelFromList(model_name)
            self._model_params.pop(model_name, None)
            if self._current_default_model == model_name:
                self._current_default_model = None
            
            self._updateStats()
            self._updateModelOrder()
            
            showInformation(self, "移动成功", f"模型已成功移动到服务端检测模型目录: {target_folder}")
            
        except Exception as e:
            showCritical(self, "移动失败", f"移动模型时发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    def showEvent(self, event):
        """页面显示时自动刷新模型列表（与文件系统同步）"""
        super(ModelSetPage, self).showEvent(event)
        
        # 每次显示时都重新加载模型，确保与文件系统同步
        self.loadModelsFromConfig()
        self._models_loaded = True
    
    def loadModelsFromConfig(self):
        """从配置文件和模型目录加载所有模型（委托给 handler）"""
        try:
            # 优先委托给 handler 处理
            if self._parent and hasattr(self._parent, 'model_set_handler'):
                self._parent.model_set_handler.loadModelsFromConfig()
            else:
                # 备用方案：如果 handler 未初始化，使用本地方法加载
                self._loadModelsLocally()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            self._updateModelOrder()
    
    def _loadModelsLocally(self):
        """本地加载模型的备用方法"""
        try:
            # 1. 加载配置文件
            config = self._loadConfigFile()
            if not config:
                return
            
            # 2. 从配置文件提取通道模型
            channel_models = self._extractChannelModels(config)
            
            # 3. 扫描模型目录（使用统一的getDetectionModels方法确保名称一致）
            scanned_models = self.getDetectionModels()
            
            # 4. 合并所有模型信息
            all_models = self._mergeModelInfo(channel_models, scanned_models)
            
            # 5. 为每个模型创建参数信息并添加到列表
            for model_info in all_models:
                model_params = self._createModelParams(model_info, config)
                model_name = model_info['name']
                self._model_params[model_name] = model_params
                
                # 添加到列表（标记默认模型）
                display_name = model_name
                if model_info.get('is_default', False):
                    display_name = f"{model_name}（默认）"
                    self._current_default_model = model_name
                
                self.addModelToList(display_name)
            
            # 自动选择第一个模型
            if len(all_models) > 0:
                self.model_set_list.setCurrentRow(0)
            
            self._updateModelOrder()
            
            # 通知训练页面刷新基础模型列表
            self._notifyTrainingPageRefresh()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _notifyTrainingPageRefresh(self):
        """通知所有页面刷新模型列表（使用全局信号）"""
        try:
            # 发射全局信号，所有监听的页面都会自动刷新
            self.modelListChanged.emit()
            print("[模型集管理] 已发射模型列表变化信号")
        except Exception as e:
            print(f"[模型集管理] 发射信号失败: {e}")
    
    def _loadConfigFile(self):
        """加载配置文件"""
        try:
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "database" / "config" / "default_config.yaml"
            
            if not config_path.exists():
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config
                
        except Exception as e:
            return None
    
    def _extractChannelModels(self, config):
        """从配置文件提取通道模型信息"""
        models = []
        
        # 遍历 channel1-4
        for i in range(1, 5):
            # 尝试多种路径键名（修复：支持多种配置格式）
            model_path = None
            channel_name = None
            
            # 1. 尝试从根级别的 channel{i}_model_path 读取
            channel_model_key = f'channel{i}_model_path'
            if channel_model_key in config:
                model_path = config[channel_model_key]
            
            # 2. 尝试从通道配置字典中的 model_path 读取
            channel_key = f'channel{i}'
            if channel_key in config and isinstance(config[channel_key], dict):
                channel_config = config[channel_key]
                if not model_path:
                    model_path = channel_config.get('model_path')
                channel_name = channel_config.get('name', f'通道{i}')
            else:
                channel_name = f'通道{i}'
            
            # 3. 检查模型路径是否存在
            if model_path and os.path.exists(model_path):
                # 使用统一的命名逻辑：从模型路径推导出标准名称
                model_name = self._getModelNameFromPath(model_path)
                
                models.append({
                    'name': model_name,  # 使用统一的模型名称
                    'path': model_path,
                    'channel': channel_key,
                    'channel_name': channel_name,
                    'source': 'config',
                    'is_default': i == 1  # channel1 作为默认
                })
        
        return models
    
    def _getModelNameFromPath(self, model_path):
        """从模型路径推导出统一的模型名称"""
        try:
            from pathlib import Path
            path = Path(model_path)
            
            # 检查是否在detection_model目录下
            if 'detection_model' in path.parts:
                # 找到detection_model目录的索引
                parts = path.parts
                detection_index = -1
                for i, part in enumerate(parts):
                    if part == 'detection_model':
                        detection_index = i
                        break
                
                if detection_index >= 0 and detection_index + 1 < len(parts):
                    # 获取模型ID目录名
                    model_id = parts[detection_index + 1]
                    
                    # 尝试读取config.yaml获取模型名称
                    model_dir = path.parent
                    config_locations = [
                        model_dir / "training_results" / "config.yaml",
                        model_dir / "config.yaml"
                    ]
                    
                    for config_file in config_locations:
                        if config_file.exists():
                            try:
                                import yaml
                                with open(config_file, 'r', encoding='utf-8') as f:
                                    config_data = yaml.safe_load(f)
                                    return config_data.get('model_name', f"模型_{model_id}")
                            except:
                                continue
                    
                    # 如果没有配置文件，使用默认格式
                    return f"模型_{model_id}"
            
            # 如果不在detection_model目录下，使用文件名
            return path.stem
            
        except Exception:
            # 出错时返回文件名
            return Path(model_path).stem
    
    def _scanModelDirectory(self):
        """扫描模型目录获取所有模型文件（只从detection_model加载）"""
        models = []
        
        try:
            # 获取模型目录路径
            current_dir = Path(__file__).parent.parent.parent
            
            # 只扫描detection_model目录，确保数据一致性
            model_dirs = [
                (current_dir / "database" / "model" / "detection_model", "检测模型", True),  # 唯一数据源
            ]
            
            for model_dir, dir_type, is_primary in model_dirs:
                if not model_dir.exists():
                    continue
                
                # 遍历所有子目录，按数字排序（降序，最新的在前）
                all_subdirs = [d for d in model_dir.iterdir() if d.is_dir()]
                digit_subdirs = [d for d in all_subdirs if d.name.isdigit()]
                sorted_subdirs = sorted(digit_subdirs, key=lambda x: int(x.name), reverse=True)
                
                for subdir in sorted_subdirs:
                    # 检查是否有weights子目录
                    weights_dir = subdir / "weights"
                    search_dir = weights_dir if weights_dir.exists() else subdir
                    
                    # 尝试读取config.yaml获取模型名称
                    config_file = subdir / "config.yaml"
                    model_display_name = None
                    if config_file.exists():
                        try:
                            import yaml
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config_data = yaml.safe_load(f)
                                if config_data and 'name' in config_data:
                                    model_display_name = config_data['name']
                        except Exception:
                            pass
                    
                    # 如果没有配置文件中的名称，使用默认命名
                    if not model_display_name:
                        if is_primary:
                            model_display_name = f"模型-{subdir.name}"
                        else:
                            model_display_name = f"{dir_type}-{subdir.name}"
                    
                    # 按优先级查找模型文件：best > last > epoch1
                    selected_model = None
                    
                    # 优先级1: best模型（.dat优先，然后.engine, .onnx）
                    for ext in ['.dat', '.engine', '.onnx', '']:  # 无扩展名的也考虑
                        for file in search_dir.iterdir():
                            if file.is_file() and file.name.startswith('best.'):
                                if ext == '' and '.' in file.name[5:]:  # 有其他扩展名
                                    continue
                                if ext != '' and not file.name.endswith(ext):
                                    continue
                                if ext == '' or file.name.endswith(ext):
                                    selected_model = file
                                    break
                        if selected_model:
                            break
                    
                    # 优先级2: last模型
                    if not selected_model:
                        for ext in ['.dat', '.engine', '.onnx', '']:
                            for file in search_dir.iterdir():
                                if file.is_file() and file.name.startswith('last.'):
                                    if ext == '' and '.' in file.name[5:]:
                                        continue
                                    if ext != '' and not file.name.endswith(ext):
                                        continue
                                    if ext == '' or file.name.endswith(ext):
                                        selected_model = file
                                        break
                            if selected_model:
                                break
                    
                    # 优先级3: epoch1模型
                    if not selected_model:
                        for ext in ['.dat', '.engine', '.onnx', '']:
                            for file in search_dir.iterdir():
                                if file.is_file() and file.name.startswith('epoch1.'):
                                    if ext == '' and '.' in file.name[7:]:
                                        continue
                                    if ext != '' and not file.name.endswith(ext):
                                        continue
                                    if ext == '' or file.name.endswith(ext):
                                        selected_model = file
                                        break
                            if selected_model:
                                break
                    
                    # 优先级4: 查找任意.engine文件（TensorRT模型）
                    if not selected_model:
                        for file in search_dir.iterdir():
                            if file.is_file() and file.name.endswith('.engine'):
                                selected_model = file
                                break
                    
                    # 优先级5: 查找任意.onnx文件
                    if not selected_model:
                        for file in search_dir.iterdir():
                            if file.is_file() and file.name.endswith('.onnx'):
                                selected_model = file
                                break
                    
                    # 优先级6: 查找任意.dat文件
                    if not selected_model:
                        for file in search_dir.iterdir():
                            if file.is_file() and file.name.endswith('.dat'):
                                selected_model = file
                                break
                    
                    # 如果找到了模型文件，添加到列表
                    if selected_model:
                        # 获取文件格式
                        file_ext = selected_model.suffix.lstrip('.')
                        if not file_ext:
                            # 处理无扩展名的情况
                            if '.' in selected_model.name:
                                file_ext = selected_model.name.split('.')[-1]
                            else:
                                file_ext = 'dat'  # 默认为dat格式
                        
                        models.append({
                            'name': model_display_name,
                            'path': str(selected_model),
                            'subdir': subdir.name,
                            'source': 'scan',
                            'format': file_ext,
                            'model_type': dir_type,
                            'is_primary': is_primary,  # 标记是否为主要模型目录
                            'file_name': selected_model.name
                        })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return models
    
    @staticmethod
    @staticmethod
    def getDetectionModels():
        """静态方法：获取服务端detection_model目录下的所有模型，供其他页面使用"""
        models = []
        
        try:
            # 使用远程配置管理器获取服务端模型
            from client.utils.config import RemoteConfigManager
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                self.logger.error("[错误] SSH连接不可用，无法获取服务端检测模型")
                return models
            
            # 服务端模型目录路径
            detection_model_dir = "/home/lqj/liquid/server/database/model/detection_model"
            
            # 检查服务端目录是否存在
            check_cmd = f"test -d {detection_model_dir} && echo 'exists' || echo 'not_exists'"
            result = ssh_manager.execute_remote_command(check_cmd)
            
            if not result['success'] or 'not_exists' in result['stdout']:
                print(f"[信息] 服务端检测模型目录不存在: {detection_model_dir}")
                return models
            
            # 获取所有子目录
            list_cmd = f"find {detection_model_dir} -maxdepth 1 -type d ! -path {detection_model_dir} 2>/dev/null"
            result = ssh_manager.execute_remote_command(list_cmd)
            
            if not result['success']:
                self.logger.error(f"[错误] 获取服务端模型目录失败: {result.get('stderr', '未知错误')}")
                return models
            
            subdirs = result['stdout'].strip().split('\n') if result['stdout'].strip() else []
            
            for subdir_path in subdirs:
                if not subdir_path:
                    continue
                    
                try:
                    subdir_name = os.path.basename(subdir_path)
                    
                    # 查找模型文件
                    find_cmd = f"find {subdir_path} -name '*.dat' -o -name '*.engine' -o -name '*.onnx' 2>/dev/null"
                    model_result = ssh_manager.execute_remote_command(find_cmd)
                    
                    if not model_result['success']:
                        continue
                        
                    model_files = model_result['stdout'].strip().split('\n') if model_result['stdout'].strip() else []
                    model_files = [f for f in model_files if f]  # 过滤空字符串
                    
                    if not model_files:
                        continue
                    
                    # 优先选择best.*文件
                    model_file = None
                    for mf in model_files:
                        if 'best.' in os.path.basename(mf):
                            model_file = mf
                            break
                    if not model_file:
                        model_file = model_files[0]
                    
                    # 确定模型类型
                    if model_file.endswith('.engine'):
                        model_type = 'TensorRT'
                    elif model_file.endswith('.onnx'):
                        model_type = 'ONNX'
                    else:
                        model_type = '.dat'
                    
                    # 尝试读取config.yaml获取模型名称
                    model_name = None
                    config_locations = [
                        f"{subdir_path}/training_results/config.yaml",
                        f"{subdir_path}/config.yaml"
                    ]
                    
                    for config_file in config_locations:
                        config_cmd = f"test -f {config_file} && cat {config_file} || echo 'not_found'"
                        config_result = ssh_manager.execute_remote_command(config_cmd)
                        
                        if config_result['success'] and 'not_found' not in config_result['stdout']:
                            try:
                                import yaml
                                config_data = yaml.safe_load(config_result['stdout'])
                                model_name = config_data.get('model_name', f"模型_{subdir_name}")
                                break
                            except:
                                continue
                    
                    if not model_name:
                        model_name = f"模型_{subdir_name}"
                    
                    # 获取文件大小
                    size_cmd = f"stat -c %s {model_file} 2>/dev/null || echo '0'"
                    size_result = ssh_manager.execute_remote_command(size_cmd)
                    
                    file_size = "未知"
                    if size_result['success']:
                        try:
                            size_bytes = int(size_result['stdout'].strip())
                            if size_bytes < 1024 * 1024:
                                file_size = f"{size_bytes / 1024:.1f} KB"
                            else:
                                file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                        except:
                            pass
                    
                    models.append({
                        'name': model_name,
                        'path': model_file,
                        'size': file_size,
                        'type': model_type,
                        'source': '服务端检测模型',
                        'model_id': subdir_name,
                        'is_primary': True
                    })
                    
                    print(f"[信息] 找到服务端检测模型: {model_name} ({file_size})")
                    
                except Exception as e:
                    self.logger.error(f"[错误] 处理服务端模型目录 {subdir_path} 时出错: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"[错误] 获取服务端detection_model模型失败: {e}")
        
        return models
    
    def _mergeModelInfo(self, channel_models, scanned_models):
        """合并模型信息，避免重复（优先detection_model）"""
        all_models = []
        seen_paths = set()
        
        # 首先添加detection_model中的主要模型（优先级最高）
        primary_models = [m for m in scanned_models if m.get('is_primary', False)]
        for model in primary_models:
            path = model['path']
            if path not in seen_paths:
                all_models.append(model)
                seen_paths.add(path)
        
        # 然后添加配置文件中的通道模型
        for model in channel_models:
            path = model['path']
            if path not in seen_paths:
                all_models.append(model)
                seen_paths.add(path)
        
        # 最后添加其他扫描到的模型（跳过已存在的）
        other_models = [m for m in scanned_models if not m.get('is_primary', False)]
        for model in other_models:
            path = model['path']
            if path not in seen_paths:
                all_models.append(model)
                seen_paths.add(path)
        
        # 确保有一个默认模型：优先选择detection_model中的第一个模型
        has_default = any(model.get('is_default', False) for model in all_models)
        if not has_default and len(all_models) > 0:
            # 优先选择detection_model中的模型作为默认
            primary_model_found = False
            for model in all_models:
                if model.get('is_primary', False):
                    model['is_default'] = True
                    primary_model_found = True
                    break
            
            # 如果没有detection_model中的模型，选择第一个
            if not primary_model_found:
                all_models[0]['is_default'] = True
        
        return all_models
    
    def _createModelParams(self, model_info, config):
        """为模型创建参数信息"""
        model_path = model_info['path']
        model_name = model_info['name']
        
        # 获取文件大小
        try:
            file_size_bytes = os.path.getsize(model_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            size_str = f"{file_size_mb:.1f} MB"
        except:
            size_str = "未知"
        
        # 从配置文件获取全局模型参数
        model_config = config.get('model', {})
        
        # 确定模型类型
        if model_path.endswith('.pt'):
            model_type = "PyTorch"
        elif model_path.endswith('.dat'):
            model_type = ".dat"
        elif model_path.endswith('.engine'):
            model_type = "TensorRT"
        else:
            model_type = "未知格式"
        
        # 从配置获取设备信息
        performance_config = config.get('performance', {})
        use_gpu = performance_config.get('use_gpu', False)
        gpu_device = performance_config.get('gpu_device', 'cuda:0')
        device_str = f"{gpu_device.upper()} (GPU)" if use_gpu else "CPU"
        
        # 创建参数字典
        params = {
            "name": model_name,
            "type": model_type,
            "size": size_str,
            "classes": model_config.get('max_det', 100),  # 使用 max_det 作为类别数
            "input": f"{model_config.get('input_size', [640, 640])[0]}x{model_config.get('input_size', [640, 640])[1]}",
            "confidence": model_config.get('confidence_threshold', 0.5),
            "iou": model_config.get('iou_threshold', 0.45),
            "device": device_str,
            "batch_size": model_config.get('batch_size', 1),
            "blur_training": 100,  # 默认值
            "epochs": 300,  # 默认值
            "workers": performance_config.get('num_threads', 4),
            "path": model_path,
            "description": self._generateModelDescription(model_info, model_config)
        }
        
        return params
    
    def _generateModelDescription(self, model_info, model_config):
        """生成模型描述"""
        descriptions = []
        
        # 基本信息
        if model_info.get('source') == 'config':
            descriptions.append(f"【{model_info.get('channel_name', '未命名')}】的检测模型")
            descriptions.append(f"通道: {model_info.get('channel', '未知')}")
        else:
            descriptions.append(f"来自模型库的预训练模型")
            descriptions.append(f"子目录: {model_info.get('subdir', '未知')}")
        
        # 配置信息
        descriptions.append(f"")
        descriptions.append(f"配置信息:")
        descriptions.append(f"- 模型类型: {model_config.get('model_type', '深度学习模型')}")
        descriptions.append(f"- 输入尺寸: {model_config.get('input_size', [640, 640])}")
        descriptions.append(f"- 置信度阈值: {model_config.get('confidence_threshold', 0.5)}")
        descriptions.append(f"- IOU阈值: {model_config.get('iou_threshold', 0.45)}")
        descriptions.append(f"- 批次大小: {model_config.get('batch_size', 1)}")
        
        # 模型格式说明
        descriptions.append(f"")
        if model_info['path'].endswith('.dat'):
            descriptions.append(" 这是一个加密的模型文件，需要解密后才能使用。")
        else:
            descriptions.append(" 这是一个标准的PyTorch模型文件，可直接加载使用。")
        
        return "\n".join(descriptions)
    
    def _removeModelFromConfig(self, model_name):
        """从配置文件中删除模型配置"""
        try:
            # 加载当前配置
            config = self._loadConfigFile()
            if not config:
                pass
                return False
            
            # 查找并删除对应的通道配置
            removed = False
            for channel_key in ['channel1', 'channel2', 'channel3', 'channel4']:
                if channel_key in config:
                    channel_config = config[channel_key]
                    # 检查是否是我们要删除的模型
                    if (channel_config.get('name') == model_name or 
                        channel_config.get('model_path', '').endswith(model_name) or
                        model_name in str(channel_config.get('model_path', ''))):
                        
                        # 删除该通道配置
                        del config[channel_key]
                        pass
                        removed = True
                        break
            
            # 如果找到了对应的配置，保存更新后的配置文件
            if removed:
                success = self._saveConfigFile(config)
                if success:
                    pass
                    return True
                else:
                    pass
                    return False
            else:
                pass
                return False
                
        except Exception as e:
            pass
            return False
    
    def _saveConfigFile(self, config):
        """保存配置文件"""
        try:
            # 获取配置文件路径（修复：添加database目录）
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "database" / "config" / "default_config.yaml"
            
            # 备份原配置文件
            backup_path = config_path.with_suffix('.yaml.backup')
            if config_path.exists():
                import shutil
                shutil.copy2(config_path, backup_path)
            
            # 保存新配置
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                return True
                
        except Exception as e:
            return False
    
    def _loadModelTxtFiles(self, model_name):
        """显示模型最近一次升级的参数和训练效果信息"""
        try:
            # 清空文本显示区域
            self.model_info_text.clear()
            
            # 获取模型信息
            if model_name not in self._model_params:
                self.model_info_text.setPlainText(f"未找到模型 '{model_name}' 的信息")
                return
            
            model_info = self._model_params[model_name]
            model_path = model_info.get('path', '')
            
            if not model_path:
                self.model_info_text.setPlainText(f"模型 '{model_name}' 没有路径信息")
                return
            
            # 获取模型所在的目录 - 服务端模型路径，不需要检查本地目录存在性
            model_dir = Path(model_path).parent
            
            # 注意：由于使用服务端模型，这里不检查本地目录存在性
            # 直接构建模型训练信息
            
            # 构建模型训练信息
            content_parts = []
            
            # 首先检查是否有txt文件，如果有则优先显示txt文件内容
            txt_files = []
            
            # 新结构：搜索training_results目录的txt文件
            training_results_dir = model_dir / "training_results"
            if training_results_dir.exists():
                training_results_files = list(training_results_dir.glob("*.txt"))
                txt_files.extend(training_results_files)
            
            # 兼容旧结构：搜索模型同级目录的txt文件
            current_dir_files = list(model_dir.glob("*.txt"))
            txt_files.extend(current_dir_files)
            
            # 兼容旧结构：搜索上一级目录的txt文件
            parent_dir = model_dir.parent
            if parent_dir.exists():
                parent_dir_files = list(parent_dir.glob("*.txt"))
                txt_files.extend(parent_dir_files)
            
            # 如果有txt文件，直接显示txt文件内容（优先显示模型描述文件）
            if txt_files:
                # 优先显示模型描述文件
                description_files = [f for f in txt_files if '模型描述' in f.name]
                other_files = [f for f in txt_files if '模型描述' not in f.name]
                
                # 按优先级排序：模型描述文件在前
                sorted_files = description_files + sorted(other_files)
                
                for txt_file in sorted_files:
                    try:
                        with open(txt_file, 'r', encoding='utf-8') as f:
                            file_content = f.read().strip()
                        if file_content:
                            if txt_file.parent == model_dir:
                                file_label = txt_file.name
                            else:
                                file_label = f"{txt_file.parent.name}/{txt_file.name}"
                            
                            # 如果是模型描述文件，直接显示内容，不加标题
                            if '模型描述' in txt_file.name:
                                content_parts.append(f"{file_content}\n\n")
                            else:
                                content_parts.append(f"=== {file_label} ===\n")
                                content_parts.append(f"{file_content}\n\n")
                    except:
                        try:
                            with open(txt_file, 'r', encoding='gbk') as f:
                                file_content = f.read().strip()
                            if file_content:
                                if txt_file.parent == model_dir:
                                    file_label = txt_file.name
                                else:
                                    file_label = f"{txt_file.parent.name}/{txt_file.name}"
                                
                                # 如果是模型描述文件，直接显示内容，不加标题
                                if '模型描述' in txt_file.name:
                                    content_parts.append(f"{file_content}\n\n")
                                else:
                                    content_parts.append(f"=== {file_label} ===\n")
                                    content_parts.append(f"{file_content}\n\n")
                        except:
                            pass
                
                # 如果找到了txt文件，直接显示，不再添加其他自动生成的信息
                full_content = "".join(content_parts)
                self.model_info_text.setPlainText(full_content)
                
                # 滚动到顶部
                cursor = self.model_info_text.textCursor()
                cursor.movePosition(QtGui.QTextCursor.Start)
                self.model_info_text.setTextCursor(cursor)
                return
            else:
                # 如果没有txt文件，则显示基础信息
                content_parts.append(f"【模型升级信息】 - {model_name}\n")
                content_parts.append("=" * 60 + "\n\n")
                
                content_parts.append("基础信息\n")
                content_parts.append("-" * 30 + "\n")
                content_parts.append(f"模型名称: {model_name}\n")
                content_parts.append(f"模型类型: {model_info.get('type', '未知')}\n")
                content_parts.append(f"模型路径: {model_path}\n")
                content_parts.append(f"文件大小: {model_info.get('size', '未知')}\n")
                
                # 获取文件修改时间
                try:
                    if os.path.exists(model_path):
                        import time
                        mtime = os.path.getmtime(model_path)
                        mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                        content_parts.append(f"最后修改: {mod_time}\n")
                except:
                    pass
                
                content_parts.append("\n")
            
            # 2. 训练参数信息
            training_info = self._getTrainingParameters(model_dir)
            if training_info:
                content_parts.append("训练参数\n")
                content_parts.append("-" * 30 + "\n")
                for key, value in training_info.items():
                    content_parts.append(f"{key}: {value}\n")
                content_parts.append("\n")
            
            # 3. 训练效果信息
            results_info = self._getTrainingResults(model_dir)
            if results_info:
                content_parts.append("训练效果\n")
                content_parts.append("-" * 30 + "\n")
                for key, value in results_info.items():
                    content_parts.append(f"{key}: {value}\n")
                content_parts.append("\n")
            
            # 4. 模型评估
            evaluation = self._evaluateModelPerformance(results_info)
            if evaluation:
                content_parts.append("效果评估\n")
                content_parts.append("-" * 30 + "\n")
                content_parts.append(f"{evaluation}\n\n")
            
            
            # 如果没有找到训练信息，显示基础信息
            if not training_info and not results_info:
                content_parts.append("说明\n")
                content_parts.append("-" * 30 + "\n")
                content_parts.append("未找到详细的训练记录文件。\n")
                content_parts.append("这可能是预训练模型或外部导入的模型。\n\n")
                content_parts.append("模型仍可正常使用，如需查看训练效果，\n")
                content_parts.append("建议重新进行模型升级训练。\n")
            
            # 显示所有内容
            full_content = "".join(content_parts)
            self.model_info_text.setPlainText(full_content)
            
            # 滚动到顶部
            cursor = self.model_info_text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.Start)
            self.model_info_text.setTextCursor(cursor)
            
        except Exception as e:
            self.model_info_text.setPlainText(f"读取模型信息时出错:\n{str(e)}")
    
    def _getTrainingParameters(self, model_dir):
        """获取训练参数信息"""
        training_params = {}
        
        try:
            # 查找 args.yaml 文件（训练参数）
            args_file = model_dir / "args.yaml"
            if args_file.exists():
                with open(args_file, 'r', encoding='utf-8') as f:
                    args_data = yaml.safe_load(f)
                    if args_data:
                        training_params["训练轮数"] = args_data.get('epochs', '未知')
                        training_params["批次大小"] = args_data.get('batch', '未知')
                        training_params["图像尺寸"] = args_data.get('imgsz', '未知')
                        training_params["学习率"] = args_data.get('lr0', '未知')
                        training_params["优化器"] = args_data.get('optimizer', '未知')
                        training_params["数据集"] = args_data.get('data', '未知')
                        training_params["设备"] = args_data.get('device', '未知')
                        training_params["工作进程"] = args_data.get('workers', '未知')
            
            # 查找其他可能的配置文件
            config_files = list(model_dir.glob("*config*.yaml")) + list(model_dir.glob("*config*.yml"))
            for config_file in config_files:
                if config_file.name != "args.yaml":
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config_data = yaml.safe_load(f)
                            if config_data and isinstance(config_data, dict):
                                # 提取一些关键参数
                                if 'epochs' in config_data:
                                    training_params["训练轮数"] = config_data['epochs']
                                if 'batch_size' in config_data:
                                    training_params["批次大小"] = config_data['batch_size']
                    except:
                        continue
        
        except Exception as e:
            pass
        
        return training_params
    
    def _getTrainingResults(self, model_dir):
        """获取训练结果信息"""
        results = {}
        
        try:
            # 查找 results.csv 文件（训练结果）
            results_file = model_dir / "results.csv"
            if results_file.exists():
                import pandas as pd
                try:
                    df = pd.read_csv(results_file)
                    if not df.empty:
                        # 获取最后一行的结果（最终训练结果）
                        last_row = df.iloc[-1]
                        
                        # 提取关键指标
                        if 'metrics/precision(B)' in df.columns:
                            results["精确率"] = f"{last_row['metrics/precision(B)']:.4f}"
                        elif 'precision' in df.columns:
                            results["精确率"] = f"{last_row['precision']:.4f}"
                        
                        if 'metrics/recall(B)' in df.columns:
                            results["召回率"] = f"{last_row['metrics/recall(B)']:.4f}"
                        elif 'recall' in df.columns:
                            results["召回率"] = f"{last_row['recall']:.4f}"
                        
                        if 'metrics/mAP50(B)' in df.columns:
                            results["mAP@0.5"] = f"{last_row['metrics/mAP50(B)']:.4f}"
                        elif 'mAP_0.5' in df.columns:
                            results["mAP@0.5"] = f"{last_row['mAP_0.5']:.4f}"
                        
                        if 'metrics/mAP50-95(B)' in df.columns:
                            results["mAP@0.5:0.95"] = f"{last_row['metrics/mAP50-95(B)']:.4f}"
                        elif 'mAP_0.5:0.95' in df.columns:
                            results["mAP@0.5:0.95"] = f"{last_row['mAP_0.5:0.95']:.4f}"
                        
                        if 'train/box_loss' in df.columns:
                            results["训练损失"] = f"{last_row['train/box_loss']:.4f}"
                        elif 'train_loss' in df.columns:
                            results["训练损失"] = f"{last_row['train_loss']:.4f}"
                        
                        if 'val/box_loss' in df.columns:
                            results["验证损失"] = f"{last_row['val/box_loss']:.4f}"
                        elif 'val_loss' in df.columns:
                            results["验证损失"] = f"{last_row['val_loss']:.4f}"
                        
                        # 训练轮数
                        if 'epoch' in df.columns:
                            results["完成轮数"] = f"{int(last_row['epoch']) + 1}"
                        
                except ImportError:
                    # 如果没有pandas，尝试手动解析CSV
                    with open(results_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if len(lines) > 1:  # 有标题行和数据行
                            headers = lines[0].strip().split(',')
                            last_data = lines[-1].strip().split(',')
                            
                            for i, header in enumerate(headers):
                                if i < len(last_data):
                                    if 'precision' in header.lower():
                                        results["精确率"] = last_data[i]
                                    elif 'recall' in header.lower():
                                        results["召回率"] = last_data[i]
                                    elif 'map50' in header.lower():
                                        results["mAP@0.5"] = last_data[i]
                except Exception as e:
                    pass
            
            # 查找其他结果文件
            log_files = list(model_dir.glob("*.log")) + list(model_dir.glob("*train*.txt"))
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 简单提取一些关键信息
                        if 'Best mAP' in content or 'best map' in content.lower():
                            lines = content.split('\n')
                            for line in lines:
                                if 'map' in line.lower() and ('best' in line.lower() or 'final' in line.lower()):
                                    results["最佳mAP"] = line.strip()
                                    break
                except:
                    continue
        
        except Exception as e:
            pass
        
        return results
    
    def _evaluateModelPerformance(self, results_info):
        """评估模型性能"""
        if not results_info:
            return "暂无训练结果数据，无法评估模型性能。"
        
        evaluation_parts = []
        
        try:
            # 评估mAP指标
            if "mAP@0.5" in results_info:
                map50 = float(results_info["mAP@0.5"])
                if map50 >= 0.9:
                    evaluation_parts.append("检测精度: 优秀 (mAP@0.5 ≥ 0.9)")
                elif map50 >= 0.8:
                    evaluation_parts.append("检测精度: 良好 (mAP@0.5 ≥ 0.8)")
                elif map50 >= 0.7:
                    evaluation_parts.append("检测精度: 一般 (mAP@0.5 ≥ 0.7)")
                else:
                    evaluation_parts.append("检测精度: 较差 (mAP@0.5 < 0.7)")
            
            # 评估精确率和召回率
            if "精确率" in results_info and "召回率" in results_info:
                precision = float(results_info["精确率"])
                recall = float(results_info["召回率"])
                
                if precision >= 0.85 and recall >= 0.85:
                    evaluation_parts.append("平衡性能: 优秀 (精确率和召回率均 ≥ 0.85)")
                elif precision >= 0.75 and recall >= 0.75:
                    evaluation_parts.append("平衡性能: 良好 (精确率和召回率均 ≥ 0.75)")
                else:
                    evaluation_parts.append("平衡性能: 需要改进")
            
            # 评估损失值
            if "训练损失" in results_info and "验证损失" in results_info:
                train_loss = float(results_info["训练损失"])
                val_loss = float(results_info["验证损失"])
                
                if abs(train_loss - val_loss) < 0.1:
                    evaluation_parts.append("模型稳定性: 良好 (训练和验证损失接近)")
                elif abs(train_loss - val_loss) < 0.2:
                    evaluation_parts.append("模型稳定性: 一般")
                else:
                    evaluation_parts.append("模型稳定性: 可能存在过拟合")
            
            # 综合评估
            if len(evaluation_parts) == 0:
                return "数据不足，无法进行详细评估。"
            
            # 添加使用建议
            if any("优秀" in part for part in evaluation_parts):
                evaluation_parts.append("\n建议: 模型表现良好，可以投入使用。")
            elif any("良好" in part for part in evaluation_parts):
                evaluation_parts.append("\n建议: 模型表现尚可，建议在更多数据上测试。")
            else:
                evaluation_parts.append("\n建议: 模型需要进一步训练优化。")
        
        except Exception as e:
            return "评估过程中出现错误，请检查训练结果数据。"
        
        return "\n".join(evaluation_parts)


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    test_model_params = {
        "预训练模型1": {
            "name": "预训练模型1（默认）",
            "type": "预训练模型1",
            "size": "14.1 MB",
            "classes": 80,
            "input": "640x640",
            "confidence": 0.5,
            "iou": 0.45,
            "device": "CUDA:0 (GPU)",
            "path": "D:\\111\\text1.pt",
            "batch_size": 16,
            "blur_training": 100,
            "epochs": 300,
            "workers": 8,
            "description": "预训练模型1是一个轻量级的目标检测模型，适合实时检测场景。\n包含80个COCO数据集类别，速度快，精度适中。"
        },
        "预训练模型2": {
            "name": "预训练模型2",
            "type": "预训练模型2",
            "size": "49.7 MB",
            "classes": 80,
            "input": "640x640",
            "confidence": 0.6,
            "iou": 0.5,
            "device": "CUDA:0 (GPU)",
            "path": "D:\\111\\text2.pt",
            "batch_size": 32,
            "blur_training": 150,
            "epochs": 500,
            "workers": 8,
            "description": "预训练模型2是中等规模的目标检测模型，平衡了速度和精度。\n适用于需要较高准确率的应用场景，支持多种检测任务。"
        },
        "预训练模型3": {
            "name": "预训练模型3",
            "type": "预训练模型3",
            "size": "136.7 MB",
            "classes": 80,
            "input": "1280x1280",
            "confidence": 0.65,
            "iou": 0.5,
            "device": "CUDA:0 (GPU)",
            "path": "D:\\111\\text.3.pt",
            "batch_size": 16,
            "blur_training": 200,
            "epochs": 500,
            "workers": 8,
            "description": "预训练模型3是最大规模的目标检测模型，提供最高的检测精度。\n适合对精度要求极高的应用场景，但推理速度较慢。"
        }
    }
    
    # 创建窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("模型集管理页面测试")
    window.resize(900, 600)
    
    # 创建页面
    page = ModelSetPage(test_model_params)
    window.setCentralWidget(page)
    
    # 添加测试数据
    page.addModelToList("预训练模型1（默认）")
    page.addModelToList("预训练模型2")
    page.addModelToList("预训练模型3")
    
    window.show()
    sys.exit(app.exec_())

