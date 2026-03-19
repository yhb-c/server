# -*- coding: utf-8 -*-

"""
模型加载进度条对话框

提供PyQt5风格的进度条UI，用于显示模型加载进度
"""

from qtpy.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from qtpy.QtCore import Qt, QTimer, Signal, QThread
from qtpy.QtGui import QFont

# 导入样式管理器
try:
    from widgets.style_manager import newIcon, FontManager
except ImportError:
    try:
        from style_manager import newIcon, FontManager
    except ImportError:
        def newIcon(icon):
            from qtpy.QtGui import QIcon
            return QIcon()
        
        class FontManager:
            @staticmethod
            def getTitleFont():
                font = QFont()
                font.setPointSize(12)
                font.setBold(True)
                return font
            
            @staticmethod
            def getMediumFont():
                font = QFont()
                font.setPointSize(10)
                return font
            
            @staticmethod
            def getSmallFont():
                font = QFont()
                font.setPointSize(9)
                return font


class ModelLoadingProgressDialog(QDialog):
    """模型加载进度条对话框"""
    
    # 🔥 添加取消信号
    cancelRequested = Signal()  # 用户点击关闭按钮时发出
    
    def __init__(self, parent=None, total_models: int = 1):
        """
        初始化进度条对话框
        
        Args:
            parent: 父窗口
            total_models: 总模型数
        """
        super().__init__(parent)
        self.total_models = total_models
        self.current_model = 0
        self._user_cancelled = False  # 标记用户是否取消
        
        self.setupUI()
        
    def setupUI(self):
        """设置UI"""
        self.setWindowTitle("模型加载中...")
        self.setGeometry(100, 100, 500, 180)  # 增加宽度和高度以显示更多信息
        self.setModal(True)
        
        # 设置左上角图标为逻辑图标
        self.setWindowIcon(newIcon("逻辑"))
        
        # 🔥 只移除帮助按钮，保留关闭按钮（用户可以点击关闭按钮取消加载）
        self.setWindowFlags(
            self.windowFlags() & 
            ~Qt.WindowContextHelpButtonHint  # 移除帮助按钮
        )
        
        # 居中显示
        self._center_window()
        
        # 主布局
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 主标题标签（合并模型信息）
        self.title_label = QLabel("正在初始化检测引擎...")
        FontManager.applyToWidget(self.title_label)  # 应用全局字体管理
        self.title_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        layout.addWidget(self.title_label)
        
        # 当前步骤详情标签
        self.step_label = QLabel("")
        FontManager.applyToWidget(self.step_label)  # 应用全局字体管理
        self.step_label.setStyleSheet("padding: 2px 0;")
        layout.addWidget(self.step_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(self.total_models * 100)  # 使用100倍精度支持子步骤
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #4CAF50, stop:1 #45a049);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 统计信息标签
        self.stats_label = QLabel("模型: 0/0")
        FontManager.applyToWidget(self.stats_label)  # 应用全局字体管理
        layout.addWidget(self.stats_label)
        
        self.setLayout(layout)
    
    def _center_window(self):
        """将窗口居中显示"""
        try:
            from qtpy.QtWidgets import QApplication
            from qtpy.QtGui import QScreen
            
            # 获取应用实例
            app = QApplication.instance()
            if not app:
                return
            
            # 获取主屏幕
            screen = app.primaryScreen()
            if not screen:
                return
            
            # 获取屏幕几何信息
            screen_geometry = screen.geometry()
            
            # 计算窗口应该显示的位置（居中）
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            
            # 设置窗口位置
            self.move(x, y)
            
        except Exception as e:
            # 如果出错，使用默认位置
            pass
    
    def update_progress(self, current: int, model_id: str = "", step: str = "", sub_progress: int = 0):
        """
        更新进度（线程安全）
        
        Args:
            current: 当前模型序号（1-based）
            model_id: 当前模型ID
            step: 当前步骤描述
            sub_progress: 子步骤进度（0-100）
        """
        self.current_model = current
        
        # 计算总进度：(已完成模型数 * 100 + 当前模型子进度)
        total_progress = (current - 1) * 100 + sub_progress
        self.progress_bar.setValue(total_progress)
        
        # 更新标题（合并模型信息）
        if current > self.total_models:
            self.title_label.setText("检测引擎初始化完成")
            self.title_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        else:
            if model_id:
                self.title_label.setText(f"正在加载模型: {model_id} ({current}/{self.total_models})")
            else:
                self.title_label.setText(f"正在加载模型 ({current}/{self.total_models})")
            self.title_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        
        # 更新步骤信息
        if step:
            self.step_label.setText(step)
        else:
            self.step_label.setText("")
        
        # 更新统计信息
        completed = current - 1 if current <= self.total_models else self.total_models
        self.stats_label.setText(f"已完成: {completed}/{self.total_models} 模型")
        
        # 注意：不再调用 processEvents()，因为我们已经在后台线程中
    
    def set_complete(self):
        """设置为完成状态"""
        self.progress_bar.setValue(self.total_models * 100)
        self.title_label.setText(f"检测引擎初始化完成 - 成功加载 {self.total_models} 个模型")
        self.title_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        self.step_label.setText("所有模型已就绪，可以开始检测")
        self.stats_label.setText(f"已完成: {self.total_models}/{self.total_models} 模型")
        
        # 自动关闭（延迟800ms）
        QTimer.singleShot(800, self.accept)
    
    def set_error(self, error_msg: str = ""):
        """设置为错误状态"""
        if error_msg:
            self.title_label.setText(f"模型加载失败: {error_msg}")
        else:
            self.title_label.setText("模型加载失败")
        self.title_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        self.step_label.setText("请检查模型文件和配置")
    
    def closeEvent(self, event):
        """
        处理关闭事件（用户点击右上角关闭按钮）
        
        发出取消信号，通知外部停止加载线程
        """
        if not self._user_cancelled:
            self._user_cancelled = True
            print(f"⚠️ [模型加载] 用户取消加载，发出取消信号")
            self.cancelRequested.emit()
        
        # 接受关闭事件
        event.accept()
