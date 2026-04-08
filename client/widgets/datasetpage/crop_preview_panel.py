# -*- coding: utf-8 -*-

"""
裁剪图片预览面板

功能：
1. 实时预览视频裁剪后生成的图片
2. 支持多区域图片预览（区域1、区域2、区域3）
3. 网格模式显示图片缩略图
4. 点击图片可查看大图
5. 显示裁剪进度和统计信息
"""

from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
import os
import os.path as osp

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..style_manager import newIcon, TextButtonStyleManager, DialogManager, FontManager
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, osp.join(osp.dirname(__file__), '..'))
    try:
        from style_manager import newIcon, TextButtonStyleManager, DialogManager, FontManager
        from responsive_layout import ResponsiveLayout, scale_w, scale_h
    except ImportError:
        def newIcon(icon):
            return QtGui.QIcon()
        TextButtonStyleManager = None
        DialogManager = None
        FontManager = None
        ResponsiveLayout = None
        scale_w = lambda x: x
        scale_h = lambda x: x

# 导入回收站工具
try:
    from utils.recycle_bin_utils import delete_file_to_recycle_bin, delete_folder_to_recycle_bin
except ImportError:
    delete_file_to_recycle_bin = None
    delete_folder_to_recycle_bin = None


class CropPreviewPanel(QtWidgets.QWidget):
    """
    裁剪图片预览面板
    
    布局：
    - 顶部：标题和控制按钮
    - 中部：区域选择标签页
    - 底部：统计信息
    """
    
    # 自定义信号
    imageSelected = QtCore.Signal(str)  # 图片被选中
    regionChanged = QtCore.Signal(int)  # 切换区域
    
    def __init__(self, parent=None):
        """
        Args:
            parent: 父窗口
        """
        super(CropPreviewPanel, self).__init__(parent)
        self._parent = parent
        
        # 当前监控的保存路径
        self._save_liquid_data_path = None
        
        # 当前监控的视频名称（用于过滤区域文件夹）
        self._video_name = None
        
        # 区域路径列表
        self._region_paths = []
        
        # 当前选中的区域索引
        self._current_region = 0
        
        # 图片列表缓存（每个区域一个列表）
        self._region_images = {}  # {region_index: [image_paths]}
        
        self._initUI()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)  # 减少内边距
        main_layout.setSpacing(5)  # 减少间距
        
        # 🔥 设置固定宽度 - 响应式布局
        ResponsiveLayout.apply_to_widget(self, min_width=300, max_width=300)
        
        # 标题栏
        title_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("裁剪图片预览")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #333;")  # 缩小字体
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 刷新按钮 - 更小更紧凑
        self.btn_refresh = QtWidgets.QPushButton("刷新")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(self.btn_refresh, "刷新")
        else:
            self.btn_refresh.setFixedSize(scale_w(50), scale_h(25))  # 🔥 响应式尺寸
        title_layout.addWidget(self.btn_refresh)
        
        # 删除按钮 - 更小更紧凑
        self.btn_delete = QtWidgets.QPushButton("删除")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(self.btn_delete, "删除")
        else:
            self.btn_delete.setFixedSize(scale_w(50), scale_h(25))  # 🔥 响应式尺寸
        title_layout.addWidget(self.btn_delete)
        
        main_layout.addLayout(title_layout)
        
        # 保存路径显示 - 更紧凑
        self.lbl_save_liquid_data_path = QtWidgets.QLabel("未设置保存路径")
        self.lbl_save_liquid_data_path.setStyleSheet("""
            QLabel {
                padding: 4px;
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                color: #666;
                font-size: 10pt;
            }
        """)
        self.lbl_save_liquid_data_path.setWordWrap(True)
        main_layout.addWidget(self.lbl_save_liquid_data_path)
        
        # 区域标签页
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                padding: 4px 12px;
                margin-right: 2px;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #0078d7;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
        """)
        
        # 创建3个区域的标签页
        self.image_grids = []
        for i in range(3):
            grid = self._createImageGrid()
            self.image_grids.append(grid)
            self.tab_widget.addTab(grid, f"区域 {i+1}")
        
        main_layout.addWidget(self.tab_widget, stretch=1)
        
        # 底部统计信息
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.lbl_total_images = QtWidgets.QLabel("总图片数: 0")
        self.lbl_total_images.setStyleSheet("color: #666; padding: 2px; font-size: 9pt;")
        stats_layout.addWidget(self.lbl_total_images)
        
        stats_layout.addStretch()
        
        self.lbl_current_region_images = QtWidgets.QLabel("当前区域: 0")
        self.lbl_current_region_images.setStyleSheet("color: #666; padding: 2px; font-size: 9pt;")
        stats_layout.addWidget(self.lbl_current_region_images)
        
        main_layout.addLayout(stats_layout)
        
        # 设置面板样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
            }
        """)
    
    def _createImageGrid(self):
        """创建图片网格"""
        grid = QtWidgets.QListWidget()
        grid.setViewMode(QtWidgets.QListWidget.IconMode)
        grid.setIconSize(QtCore.QSize(80, 60))  # 图片缩略图尺寸
        grid.setGridSize(QtCore.QSize(130, 160))  # 调整网格宽度为130px，保持两列显示
        grid.setResizeMode(QtWidgets.QListWidget.Adjust)  # 改为自动调整，允许自适应
        grid.setMovement(QtWidgets.QListWidget.Static)
        grid.setSpacing(15)  # 增加图片间隔从5到15
        grid.setWordWrap(True)
        grid.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: white;
            }
            QListWidget::item {
                border: 2px solid transparent;
                border-radius: 5px;
                background-color: white;
                padding: 8px;    /* 增加内边距 */
                margin: 5px;     /* 增加外边距 */
                color: #333;
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 2px solid #0078d7;
                color: #000;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                border: 2px solid #c0c0c0;
            }
        """)
        
        # 连接双击事件
        grid.itemDoubleClicked.connect(self._onImageDoubleClicked)
        
        return grid
    
    def _connectSignals(self):
        """连接信号槽"""
        self.btn_refresh.clicked.connect(self.refreshImages)
        self.btn_delete.clicked.connect(self._onDeleteCurrentRegion)
        self.tab_widget.currentChanged.connect(self._onTabChanged)
    
    # ========== 公共方法 ==========
    
    def setSavePath(self, save_liquid_data_path, auto_refresh=True, video_name=None):
        """
        设置保存路径
        
        Args:
            save_liquid_data_path: 裁剪图片保存的根路径
            auto_refresh: 是否自动刷新图片列表（默认True）
            video_name: 视频名称，如果提供则只显示该视频的区域文件夹
        """
        
        self._save_liquid_data_path = save_liquid_data_path
        self._video_name = video_name  # 保存视频名称
        
        # 更新显示
        if video_name:
            self.lbl_save_liquid_data_path.setText(f"监控中: (视频: {video_name})")
        else:
            self.lbl_save_liquid_data_path.setText(f"监控中: {save_liquid_data_path}")
        
        self.lbl_save_liquid_data_path.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: transparent;
                border: 1px solid #4caf50;
                border-radius: 3px;
                color: #2e7d32;
                font-weight: bold;
            }
        """)
        
        # 查找所有区域文件夹
        self._findRegionPaths()
        
        # 只在需要时加载图片
        if auto_refresh:
            self.refreshImages()
    
    def _findRegionPaths(self):
        """查找所有区域文件夹（支持新旧命名格式，可根据视频名 称过滤）"""
        self._region_paths = []
        
        if not self._save_liquid_data_path or not osp.exists(self._save_liquid_data_path):
            return
        
        try:
            # 获取保存路径下的所有子文件夹
            subdirs = [d for d in os.listdir(self._save_liquid_data_path) 
                      if osp.isdir(osp.join(self._save_liquid_data_path, d))]
            
            # 筛选出区域文件夹
            region_folders = []
            for subdir in subdirs:
                # 如果指定了视频名称，只查找该视频的区域文件夹
                if self._video_name:
                    # 匹配格式：视频名_区域X
                    if subdir.startswith(f"{self._video_name}_") and '区域' in subdir:
                        region_folders.append(subdir)
                else:
                    # 未指定视频名称时，查找所有区域文件夹
                    if '区域' in subdir or 'region' in subdir.lower():
                        region_folders.append(subdir)
            
            # 按文件夹名排序
            region_folders.sort()
            
            # 初始化所有区域为None
            for i in range(3):
                self._region_paths.append(None)
            
            # 根据文件夹名称中的区域编号映射到对应的索引
            import re
            for folder in region_folders:
                # 提取区域编号（支持中文和英文）
                # 匹配格式：“区域1”、“区域 1”、“region1”、“region 1”
                match = re.search(r'[区域|region]\s*(\d+)', folder, re.IGNORECASE)
                if match:
                    region_num = int(match.group(1))
                    # 区域编号从1开始，索引从0开始
                    region_index = region_num - 1
                    if 0 <= region_index < 3:
                        region_path = osp.join(self._save_liquid_data_path, folder)
                        self._region_paths[region_index] = region_path
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 降级到旧的查找方式
            for i in range(3):
                region_path = osp.join(self._save_liquid_data_path, f"region{i+1}")
                if osp.exists(region_path):
                    self._region_paths.append(region_path)
                else:
                    self._region_paths.append(None)
    
    def refreshImages(self):
        """刷新所有区域的图片列表"""
        if not self._save_liquid_data_path:
            return
        
        # 保存当前的视频名称（clearImages会清空它）
        current_video_name = self._video_name
        
        # 如果没有视频名称上下文，说明当前没有选中有效的裁剪视频，不应该刷新
        if not current_video_name:
            return
        
        # 先清空所有图片
        self.clearImages()
        
        # 恢复视频名称
        self._video_name = current_video_name
        
        # 重新查找区域文件夹
        self._findRegionPaths()
        
        # 加载每个区域的图片
        for i, region_path in enumerate(self._region_paths):
            if region_path and osp.exists(region_path):
                self._loadRegionImages(i, region_path)
        
        # 更新统计
        self._updateStats()
    
    def _loadRegionImages(self, region_index, region_path):
        """
        加载指定区域的图片
        
        Args:
            region_index: 区域索引 (0, 1, 2)
            region_path: 区域文件夹路径
        """
        # 获取该区域的图片列表控件
        grid = self.image_grids[region_index]
        grid.clear()
        
        # 支持的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        # 获取所有图片文件
        try:
            files = [f for f in os.listdir(region_path) 
                    if osp.isfile(osp.join(region_path, f)) and 
                    osp.splitext(f)[1].lower() in image_extensions]
            files.sort()
            
            # 缓存图片路径列表
            image_paths = [osp.join(region_path, f) for f in files]
            self._region_images[region_index] = image_paths
            
            if len(files) == 0:
                # 如果没有图片，显示等待提示
                placeholder_item = QtWidgets.QListWidgetItem(grid)
                placeholder_item.setText("\n\n等待裁剪任务生成图片...\n\n监控已启动，图片生成后会自动显示")
                placeholder_item.setTextAlignment(Qt.AlignCenter)
                placeholder_item.setFlags(Qt.NoItemFlags)  # 不可选择
                
                # 🔥 应用全局字体管理器
                if FontManager:
                    # 使用全局字体管理器设置字体
                    font = FontManager.getFont()
                    placeholder_item.setFont(font)
                else:
                    # 备用方案：手动设置字体
                    font = placeholder_item.font()
                    font.setPointSize(10)
                    placeholder_item.setFont(font)
                return
            
            # 添加到网格（只显示最新的100张，避免加载过多）
            display_files = files[-100:] if len(files) > 100 else files
            
            for file in display_files:
                item = QtWidgets.QListWidgetItem(grid)
                file_path = osp.join(region_path, file)
                
                # 显示完整文件名（不带路径）
                display_name = file
                
                # 在图片下方显示文件名，使用换行符确保文件名在图片下方
                item.setText(display_name)
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file)
                
                # 生成缩略图
                thumbnail = self._generateThumbnail(file_path)
                if thumbnail:
                    item.setIcon(QtGui.QIcon(thumbnail))
                else:
                    # 使用默认图标
                    icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
                    item.setIcon(icon)
                
                # 设置文本居中对齐
                item.setTextAlignment(Qt.AlignCenter)
            
        except Exception as e:
            pass
    
    def _generateThumbnail(self, image_path):
        """
        生成图片缩略图
        
        Args:
            image_path: 图片路径
            
        Returns:
            QPixmap: 缩略图
        """
        try:
            # 直接使用QPixmap加载
            pixmap = QtGui.QPixmap(image_path)
            
            if pixmap.isNull():
                return None
            
            # 缩放到缩略图尺寸
            scaled_pixmap = pixmap.scaled(
                160, 120,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            return scaled_pixmap
            
        except Exception as e:
            return None
    
    def clearImages(self):
        """清空所有图片显示"""
        # 清空所有网格
        for i, grid in enumerate(self.image_grids):
            grid.clear()
            
            # 添加等待提示
            placeholder_item = QtWidgets.QListWidgetItem(grid)
            placeholder_item.setTextAlignment(Qt.AlignCenter)
            placeholder_item.setFlags(Qt.NoItemFlags)  # 不可选择
            
            # 🔥 应用全局字体管理器
            if FontManager:
                # 使用全局字体管理器设置字体
                font = FontManager.getFont()
                placeholder_item.setFont(font)
            else:
                # 备用方案：手动设置字体
                font = placeholder_item.font()
                font.setPointSize(10)
                placeholder_item.setFont(font)
        
        # 清空缓存数据
        self._region_images.clear()
        self._region_paths = []
        self._video_name = None  # 清空视频名称，防止刷新时显示其他视频的图片
        
        # 更新统计
        self._updateStats()
    
    def addImage(self, region_index, image_path):
        """
        添加单张图片到指定区域（用于实时更新）
        
        Args:
            region_index: 区域索引 (0, 1, 2)
            image_path: 图片路径
        """
        if region_index < 0 or region_index >= 3:
            return
        
        # 获取该区域的图片列表控件
        grid = self.image_grids[region_index]
        
        # 如果是第一张图片，清除等待提示
        if grid.count() == 1:
            first_item = grid.item(0)
            if first_item and first_item.flags() == Qt.NoItemFlags:
                # 这是占位符，清除它
                grid.clear()
        
        # 创建列表项
        item = QtWidgets.QListWidgetItem(grid)
        
        # 显示完整文件名
        file_name = osp.basename(image_path)
        display_name = file_name
        
        # 在图片下方显示文件名
        item.setText(display_name)
        item.setData(Qt.UserRole, image_path)
        item.setToolTip(file_name)
        
        # 生成缩略图
        thumbnail = self._generateThumbnail(image_path)
        if thumbnail:
            item.setIcon(QtGui.QIcon(thumbnail))
        else:
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
            item.setIcon(icon)
        
        item.setTextAlignment(Qt.AlignCenter)
        
        # 更新缓存
        if region_index not in self._region_images:
            self._region_images[region_index] = []
        self._region_images[region_index].append(image_path)
        
        # 更新统计
        self._updateStats()
        
        # 自动滚动到底部
        grid.scrollToBottom()
    
    def _updateStats(self):
        """更新统计信息"""
        # 计算总图片数
        total = sum(len(images) for images in self._region_images.values())
        self.lbl_total_images.setText(f"总图片数: {total}")
        
        # 当前区域图片数
        current_region = self.tab_widget.currentIndex()
        current_count = len(self._region_images.get(current_region, []))
        self.lbl_current_region_images.setText(f"当前区域: {current_count}")
    
    # ========== 槽函数 ==========
    
    def _onTabChanged(self, index):
        """标签页切换"""
        self._current_region = index
        self._updateStats()
        self.regionChanged.emit(index)
    
    def _onImageDoubleClicked(self, item):
        """图片被双击 - 显示大图"""
        image_path = item.data(Qt.UserRole)
        
        # 创建图片查看对话框
        dialog = ImageViewDialog(self, image_path)
        dialog.exec_()
    
    def _onDeleteCurrentRegion(self):
        """删除当前区域的所有文件"""
        # 获取当前选中的区域索引
        current_region = self.tab_widget.currentIndex()
        
        # 检查是否有区域路径
        if current_region < 0 or current_region >= len(self._region_paths):
            if DialogManager:
                DialogManager.show_warning(self, "警告", "无法获取当前区域信息")
            else:
                QtWidgets.QMessageBox.warning(self, "警告", "无法获取当前区域信息")
            return
        
        region_path = self._region_paths[current_region]
        
        if not region_path or not osp.exists(region_path):
            if DialogManager:
                DialogManager.show_warning(self, "警告", f"区域 {current_region + 1} 的文件夹不存在")
            else:
                QtWidgets.QMessageBox.warning(self, "警告", f"区域 {current_region + 1} 的文件夹不存在")
            return
        
        # 获取区域中的图片数量
        image_count = len(self._region_images.get(current_region, []))
        
        # 显示确认对话框
        if DialogManager:
            reply = DialogManager.show_question_warning(
                self, 
                "确认删除", 
                f"确定要删除区域 {current_region + 1} 的所有文件吗？\n"
                f"当前区域共有 {image_count} 张图片"
                f"文件夹将被移动到回收站"
            )
        else:
            reply = QtWidgets.QMessageBox.question(
                self, 
                "确认删除", 
                f"确定要删除区域 {current_region + 1} 的所有文件吗？\n"
                f"当前区域共有 {image_count} 张图片"
                f"文件夹将被移动到回收站",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            reply = (reply == QtWidgets.QMessageBox.Yes)
        
        if not reply:
            return
        
        # 删除文件夹
        try:
            if delete_folder_to_recycle_bin:
                # 使用回收站工具删除
                success = delete_folder_to_recycle_bin(region_path)
                if success:
                    if DialogManager:
                        DialogManager.show_information(self, "成功", f"区域 {current_region + 1} 的文件已移动到回收站")
                    else:
                        QtWidgets.QMessageBox.information(self, "成功", f"区域 {current_region + 1} 的文件已移动到回收站")
                else:
                    if DialogManager:
                        DialogManager.show_warning(self, "错误", f"无法删除文件夹: {region_path}")
                    else:
                        QtWidgets.QMessageBox.warning(self, "错误", f"无法删除文件夹: {region_path}")
                    return
            else:
                # 回收站工具不可用，使用直接删除
                import shutil
                shutil.rmtree(region_path)
                if DialogManager:
                    DialogManager.show_information(self, "成功", f"区域 {current_region + 1} 的文件已删除")
                else:
                    QtWidgets.QMessageBox.information(self, "成功", f"区域 {current_region + 1} 的文件已删除")
            
            # 清空当前区域的显示
            grid = self.image_grids[current_region]
            grid.clear()
            
            # 添加等待提示
            placeholder_item = QtWidgets.QListWidgetItem(grid)
            placeholder_item.setText("\n\n区域已删除\n\n")
            placeholder_item.setTextAlignment(Qt.AlignCenter)
            placeholder_item.setFlags(Qt.NoItemFlags)
            
            # 🔥 应用全局字体管理器
            if FontManager:
                # 使用全局字体管理器设置字体
                font = FontManager.getFont()
                placeholder_item.setFont(font)
            else:
                # 备用方案：手动设置字体
                font = placeholder_item.font()
                font.setPointSize(10)
                placeholder_item.setFont(font)
            
            # 清空缓存
            if current_region in self._region_images:
                del self._region_images[current_region]
            self._region_paths[current_region] = None
            
            # 更新统计
            self._updateStats()
            
        except Exception as e:
            if DialogManager:
                DialogManager.show_critical(self, "错误", f"删除失败: {str(e)}")
            else:
                QtWidgets.QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")
            import traceback
            traceback.print_exc()


class ImageViewDialog(QtWidgets.QDialog):
    """图片查看对话框"""
    
    def __init__(self, parent=None, image_path=None):
        super(ImageViewDialog, self).__init__(parent)
        
        self._image_path = image_path
        
        self.setWindowTitle("图片查看")
        self.resize(800, 600)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 图片显示区域（使用滚动区域）
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        # 图片标签
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        
        scroll_area.setWidget(self.image_label)
        layout.addWidget(scroll_area)
        
        # 底部信息栏
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setContentsMargins(10, 5, 10, 5)
        
        self.lbl_info = QtWidgets.QLabel()
        self.lbl_info.setStyleSheet("color: #666;")
        info_layout.addWidget(self.lbl_info)
        
        info_layout.addStretch()
        
        # 关闭按钮
        btn_close = QtWidgets.QPushButton("关闭")
        if TextButtonStyleManager:
            TextButtonStyleManager.applyToButton(btn_close, "关闭")
        btn_close.clicked.connect(self.close)
        info_layout.addWidget(btn_close)
        
        layout.addLayout(info_layout)
        
        # 加载图片
        self._loadImage()
    
    def _loadImage(self):
        """加载图片"""
        if not self._image_path or not osp.exists(self._image_path):
            self.image_label.setText("图片不存在")
            return
        
        try:
            pixmap = QtGui.QPixmap(self._image_path)
            
            if pixmap.isNull():
                self.image_label.setText("无法加载图片")
                return
            
            # 显示原始大小（可滚动）
            self.image_label.setPixmap(pixmap)
            
            # 更新信息
            file_name = osp.basename(self._image_path)
            file_size = osp.getsize(self._image_path) / 1024  # KB
            image_size = f"{pixmap.width()} × {pixmap.height()}"
            
            self.lbl_info.setText(
                f"文件: {file_name}  |  尺寸: {image_size}  |  大小: {file_size:.1f} KB"
            )
            
        except Exception as e:
            self.image_label.setText(f"加载失败: {e}")


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("裁剪图片预览面板测试")
    window.resize(1000, 700)
    
    # 创建预览面板
    panel = CropPreviewPanel()
    window.setCentralWidget(panel)
    
    # 测试数据
    def setup_test_data():
        """创建测试数据"""
        import tempfile
        test_dir = osp.join(tempfile.gettempdir(), "crop_preview_test")
        
        # 创建测试目录结构
        for i in range(3):
            region_dir = osp.join(test_dir, f"region{i+1}")
            os.makedirs(region_dir, exist_ok=True)
            
            # 创建一些测试图片（使用纯色图片）
            for j in range(5):
                img_path = osp.join(region_dir, f"test_image_{j+1:06d}.jpg")
                
                # 创建纯色图片
                try:
                    import cv2
                    import numpy as np
                    
                    # 随机颜色
                    color = np.random.randint(0, 255, 3, dtype=np.uint8)
                    img = np.full((480, 640, 3), color, dtype=np.uint8)
                    
                    # 添加文字
                    cv2.putText(img, f"Region {i+1} - Image {j+1}", 
                               (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 
                               1.5, (255, 255, 255), 3)
                    
                    cv2.imwrite(img_path, img)
                except:
                    pass
        
        panel.setSavePath(test_dir)
        print(f"\n[TEST] 测试目录: {test_dir}")
    
    # 延迟创建测试数据
    QtCore.QTimer.singleShot(500, setup_test_data)
    
    # 打印测试说明
    print("\n" + "="*70)
    print(" 裁剪图片预览面板测试程序")
    print("="*70)
    print("\n功能:")
    print("  - 顶部：刷新和清空按钮")
    print("  - 中部：3个区域的标签页，每个显示该区域的裁剪图片")
    print("  - 底部：统计信息（总图片数、当前区域图片数）")
    print("  - 双击图片：查看大图")
    print("\n操作:")
    print("  1. 面板会自动加载测试图片")
    print("  2. 切换标签页查看不同区域的图片")
    print("  3. 双击图片查看大图")
    print("  4. 点击刷新按钮重新加载")
    print("  5. 点击清空按钮清除所有显示")
    print("="*70 + "\n")
    
    window.show()
    sys.exit(app.exec_())

