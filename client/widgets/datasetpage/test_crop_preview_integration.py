#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
裁剪图片预览面板集成测试

演示如何将 CropPreviewPanel 与 DataPreprocessPanel 集成
"""

import sys
import os
import os.path as osp

# 添加项目根目录到路径
current_dir = osp.dirname(osp.abspath(__file__))
project_root = osp.dirname(osp.dirname(current_dir))
sys.path.insert(0, project_root)

from qtpy import QtWidgets, QtCore
from widgets.datasetpage import DataPreprocessPanel, CropPreviewPanel
from handlers.datasetpage import DataPreprocessHandler, CropPreviewHandler


class IntegratedDatasetPage(QtWidgets.QWidget):
    """
    集成的数据集管理页面
    
    左侧：数据预处理面板（视频预览、裁剪配置）
    右侧：裁剪图片预览面板（实时显示裁剪结果）
    """
    
    def __init__(self, parent=None):
        super(IntegratedDatasetPage, self).__init__(parent)
        self._initUI()
        self._initHandlers()
        self._connectSignals()
    
    def _initUI(self):
        """初始化UI"""
        # 主布局：左右分割
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # 创建分割器（可调整大小）
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # 左侧：数据预处理面板
        self.preprocess_panel = DataPreprocessPanel()
        splitter.addWidget(self.preprocess_panel)
        
        # 右侧：裁剪图片预览面板
        self.preview_panel = CropPreviewPanel()
        splitter.addWidget(self.preview_panel)
        
        # 设置分割比例（左:右 = 2:1）
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QWidget {
                font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
            }
        """)
    
    def _initHandlers(self):
        """初始化处理器"""
        # 数据预处理处理器
        self.preprocess_handler = DataPreprocessHandler(self.preprocess_panel)
        
        # 裁剪预览处理器
        self.preview_handler = CropPreviewHandler(self.preview_panel)
    
    def _connectSignals(self):
        """连接信号"""
        # === 预处理面板信号 ===
        
        # 文件夹被选中
        self.preprocess_panel.folderSelected.connect(self._onFolderSelected)
        
        # 视频被选中
        self.preprocess_panel.videoSelected.connect(self._onVideoSelected)
        
        # === 预处理处理器信号 ===
        
        # 裁剪任务开始
        self.preprocess_handler.cropStarted.connect(self._onCropStarted)
        
        # 裁剪进度更新
        self.preprocess_handler.cropProgress.connect(self._onCropProgress)
        
        # 裁剪任务完成
        self.preprocess_handler.cropFinished.connect(self._onCropFinished)
        
        # 裁剪错误
        self.preprocess_handler.cropError.connect(self._onCropError)
        
        # === 预览处理器信号 ===
        
        # 检测到新图片
        self.preview_handler.newImageDetected.connect(self._onNewImageDetected)
        
        # 文件夹变化
        self.preview_handler.folderChanged.connect(self._onFolderChanged)
        
        # === 预览面板信号 ===
        
        # 图片被选中
        self.preview_panel.imageSelected.connect(self._onImageSelected)
        
        # 切换区域
        self.preview_panel.regionChanged.connect(self._onRegionChanged)
    
    # ========== 数据预处理面板槽函数 ==========
    
    def _onFolderSelected(self, folder_path):
        """文件夹被选中"""
        pass
    
    def _onVideoSelected(self, video_path):
        """视频被选中"""
        pass
    
    # ========== 数据预处理处理器槽函数 ==========
    
    def _onCropStarted(self, config):
        """裁剪任务开始"""
        save_liquid_data_path = config.get('save_liquid_data_path', '')
        
        # 启动预览监控
        self.preview_handler.startMonitoring(save_liquid_data_path)
        
        # 切换到预览面板所在的标签页（如果使用标签页布局）
        # 这里我们直接显示即可
    
    def _onCropProgress(self, progress):
        """裁剪进度更新"""
        pass
    
    def _onCropFinished(self, save_liquid_data_path):
        """裁剪任务完成"""
        # 刷新预览显示
        self.preview_handler.refreshPanel()
        
        # 显示完成提示
        QtWidgets.QMessageBox.information(
            self, "裁剪完成", 
            f"视频裁剪任务已完成！\n\n保存路径:\n{save_liquid_data_path}\n\n"
            f"您可以在右侧预览面板查看裁剪后的图片。"
        )
    
    def _onCropError(self, error_msg):
        """裁剪错误"""
        # 显示错误提示
        QtWidgets.QMessageBox.critical(
            self, "裁剪失败", 
            f"裁剪任务执行失败：\n\n{error_msg}"
        )
    
    # ========== 预览处理器槽函数 ==========
    
    def _onNewImageDetected(self, region_index, image_path):
        """检测到新图片"""
        pass
    
    def _onFolderChanged(self, folder_path):
        """监控文件夹变化"""
        pass
    
    # ========== 预览面板槽函数 ==========
    
    def _onImageSelected(self, image_path):
        """图片被选中"""
        pass
    
    def _onRegionChanged(self, region_index):
        """切换区域"""
        pass


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("数据集管理 - 裁剪预览集成测试")
    window.resize(1800, 900)
    
    # 创建集成页面
    page = IntegratedDatasetPage()
    window.setCentralWidget(page)
    
    # 设置窗口图标（如果有）
    try:
        from widgets.style_manager import newIcon
        icon = newIcon("apple")
        if not icon.isNull():
            window.setWindowIcon(icon)
    except:
        pass
    
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

