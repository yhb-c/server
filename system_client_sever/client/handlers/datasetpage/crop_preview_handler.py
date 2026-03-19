# -*- coding: utf-8 -*-

"""
裁剪图片预览处理器

功能：
1. 监控裁剪任务的输出文件夹
2. 实时检测新增的图片
3. 自动更新预览面板
4. 提供图片统计信息
"""

from qtpy import QtCore
from qtpy.QtCore import Signal, QTimer, QFileSystemWatcher
import os
import os.path as osp


class CropPreviewHandler(QtCore.QObject):
    """
    裁剪图片预览处理器
    
    负责监控裁剪任务的输出文件夹，实时更新预览面板
    """
    
    # 信号
    newImageDetected = Signal(int, str)  # 检测到新图片 (区域索引, 图片路径)
    folderChanged = Signal(str)          # 监控文件夹变化
    
    def __init__(self, panel=None):
        """
        Args:
            panel: CropPreviewPanel 实例
        """
        super(CropPreviewHandler, self).__init__()
        
        self._panel = panel
        
        # 文件系统监控器
        self._file_watcher = None
        
        # 监控的区域文件夹路径
        self._monitored_paths = []
        
        # 已知的图片列表（用于检测新增）
        self._known_images = {}  # {region_index: set(image_paths)}
        
        # 定时器（用于轮询检测，作为文件监控的补充）
        self._poll_timer = None
        self._poll_interval = 500  # 500毫秒轮询一次（提高实时性）
        
        # 是否启用自动监控
        self._auto_monitor_enabled = False
        
        # 是否正在重置状态（避免在清空期间检测旧图片）
        self._is_resetting = False
        
        if self._panel:
            self._initPanel()
    
    def _initPanel(self):
        """初始化面板"""
        # 连接面板信号
        pass
    
    def startMonitoring(self, save_liquid_data_path, clear_first=False, video_name=None):
        """
        开始监控指定的保存路径
        
        Args:
            save_liquid_data_path: 裁剪图片保存的根路径
            clear_first: 是否先清空显示（默认False）
            video_name: 当前裁剪的视频名称（用于只监控本次任务的区域文件夹）
        """
        print(f"[CropPreviewHandler] === 启动新监控 ===")
        print(f"[CropPreviewHandler] 目标路径: {save_liquid_data_path}")
        print(f"[CropPreviewHandler] 清空显示: {clear_first}")
        print(f"[CropPreviewHandler] 视频名称: {video_name}")
        
        # 保存监控参数（用于后续动态添加新文件夹）
        self._save_liquid_data_path = save_liquid_data_path
        self._video_name = video_name
        
        # 设置重置标志（避免在清空期间检测旧图片）
        self._is_resetting = True
        
        # 停止之前的监控
        self.stopMonitoring()
        
        # 如果需要，先清空显示
        if clear_first and self._panel:
            print(f"[CropPreviewHandler] 正在清空面板显示...")
            self._panel.clearImages()
            print(f"[CropPreviewHandler] 面板已清空")
        
        # 设置面板的保存路径（不自动刷新）
        if self._panel:
            print(f"[CropPreviewHandler] 设置保存路径（不自动刷新）")
            self._panel.setSavePath(save_liquid_data_path, auto_refresh=False, video_name=video_name)
        
        # 初始化已知图片列表
        if clear_first:
            # 如果清空显示，则不扫描现有图片，所有图片都视为新增
            print(f"[CropPreviewHandler] 清空模式：不扫描现有图片，所有图片将被视为新增")
            self._known_images.clear()
        else:
            # 否则扫描现有图片，避免重复显示
            print(f"[CropPreviewHandler] 扫描现有图片...")
            self._initKnownImages(save_liquid_data_path, video_name)
        
        # 设置文件系统监控
        self._setupFileWatcher(save_liquid_data_path, video_name)
        
        # 启动定时器轮询
        self._startPolling()
        
        self._auto_monitor_enabled = True
        
        # 清除重置标志
        self._is_resetting = False
        
        # 如果是清空模式，立即执行一次检查，显示所有现有图片
        if clear_first:
            print(f"[CropPreviewHandler] 清空模式：立即检查并显示所有现有图片")
            for i, region_path in enumerate(self._monitored_paths):
                if region_path and osp.exists(region_path):
                    self._checkRegionForNewImages(i, region_path)
        
        print(f"[CropPreviewHandler] === 监控已启动 ===")
    
    def stopMonitoring(self):
        """停止监控"""
        # 停止文件监控
        if self._file_watcher:
            self._file_watcher.removePaths(self._file_watcher.files())
            self._file_watcher.removePaths(self._file_watcher.directories())
            self._file_watcher = None
        
        # 停止轮询定时器
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        
        # 清空监控路径
        self._monitored_paths.clear()
        self._known_images.clear()
        
        self._auto_monitor_enabled = False
        
        print(f"[CropPreviewHandler] 停止监控")
    
    def _initKnownImages(self, save_liquid_data_path, video_name=None):
        """
        初始化已知图片列表
        
        Args:
            save_liquid_data_path: 保存路径
            video_name: 视频名称，如果提供则只扫描该视频的区域文件夹
        """
        self._known_images.clear()
        
        # 支持的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        # 自动扫描所有区域文件夹（支持中文命名：视频名_区域X 或 regionX）
        if not osp.exists(save_liquid_data_path):
            print(f"[CropPreviewHandler] 保存路径不存在: {save_liquid_data_path}")
            return
        
        try:
            # 获取保存路径下的所有子文件夹
            subdirs = [d for d in os.listdir(save_liquid_data_path) 
                      if osp.isdir(osp.join(save_liquid_data_path, d))]
            
            # 筛选出区域文件夹
            region_folders = []
            for subdir in subdirs:
                # 如果指定了视频名称，只扫描该视频的区域文件夹
                if video_name:
                    # 匹配格式：视频名_区域X
                    if subdir.startswith(f"{video_name}_") and '区域' in subdir:
                        region_folders.append(subdir)
                else:
                    # 未指定视频名称时，扫描所有区域文件夹
                    if '区域' in subdir or 'region' in subdir.lower():
                        region_folders.append(subdir)
            
            # 按文件夹名排序
            region_folders.sort()
            
            if video_name:
                print(f"[CropPreviewHandler] 只扫描视频 '{video_name}' 的区域文件夹")
            print(f"[CropPreviewHandler] 发现 {len(region_folders)} 个区域文件夹: {region_folders}")
            
            # 扫描每个区域文件夹
            for i, folder_name in enumerate(region_folders):
                region_path = osp.join(save_liquid_data_path, folder_name)
                
                try:
                    files = [f for f in os.listdir(region_path) 
                            if osp.isfile(osp.join(region_path, f)) and 
                            osp.splitext(f)[1].lower() in image_extensions]
                    
                    image_paths = {osp.join(region_path, f) for f in files}
                    self._known_images[i] = image_paths
                    
                    print(f"[CropPreviewHandler] {folder_name} 初始图片数: {len(image_paths)}")
                    
                except Exception as e:
                    print(f"[CropPreviewHandler] 扫描 {folder_name} 失败: {e}")
                    self._known_images[i] = set()
                    
        except Exception as e:
            print(f"[CropPreviewHandler] 扫描保存路径失败: {e}")
    
    def _setupFileWatcher(self, save_liquid_data_path, video_name=None):
        """
        设置文件系统监控器
        
        Args:
            save_liquid_data_path: 保存路径
            video_name: 视频名称，如果提供则只监控该视频的区域文件夹
        """
        # 创建文件系统监控器
        self._file_watcher = QFileSystemWatcher()
        
        # 监控所有区域文件夹
        self._monitored_paths.clear()
        
        # 首先监控保存路径本身（以便检测新创建的区域文件夹）
        if osp.exists(save_liquid_data_path):
            self._file_watcher.addPath(save_liquid_data_path)
            print(f"[CropPreviewHandler] 监控保存路径: {save_liquid_data_path}")
        
        # 获取所有区域文件夹
        if osp.exists(save_liquid_data_path):
            try:
                subdirs = [d for d in os.listdir(save_liquid_data_path) 
                          if osp.isdir(osp.join(save_liquid_data_path, d))]
                
                region_folders = []
                for subdir in subdirs:
                    # 如果指定了视频名称，只监控该视频的区域文件夹
                    if video_name:
                        # 匹配格式：视频名_区域X
                        if subdir.startswith(f"{video_name}_") and '区域' in subdir:
                            region_folders.append(subdir)
                    else:
                        # 未指定视频名称时，监控所有区域文件夹
                        if '区域' in subdir or 'region' in subdir.lower():
                            region_folders.append(subdir)
                
                region_folders.sort()
                
                if video_name:
                    print(f"[CropPreviewHandler] 只监控视频 '{video_name}' 的区域文件夹")
                print(f"[CropPreviewHandler] 发现 {len(region_folders)} 个区域文件夹: {region_folders}")
                
                # 监控每个区域文件夹
                for i, folder_name in enumerate(region_folders):
                    region_path = osp.join(save_liquid_data_path, folder_name)
                    
                    # 添加到监控列表
                    if self._file_watcher.addPath(region_path):
                        self._monitored_paths.append(region_path)
                        print(f"[CropPreviewHandler] 开始监控: {folder_name}")
                    else:
                        print(f"[CropPreviewHandler] 无法监控文件夹: {folder_name}")
                        
            except Exception as e:
                print(f"[CropPreviewHandler] 设置监控失败: {e}")
        
        # 连接信号
        self._file_watcher.directoryChanged.connect(self._onDirectoryChanged)
    
    def _startPolling(self):
        """启动轮询定时器"""
        if not self._poll_timer:
            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self._checkForNewImages)
        
        self._poll_timer.start(self._poll_interval)
        print(f"[CropPreviewHandler] 启动轮询 (间隔: {self._poll_interval}ms)")
    
    def _onDirectoryChanged(self, path):
        """
        文件夹变化回调（处理新文件夹创建和文件变化）
        
        Args:
            path: 变化的文件夹路径
        """
        print(f"[CropPreviewHandler] 检测到文件夹变化: {path}")
        
        # 如果是根目录变化，可能是新创建了区域文件夹
        if hasattr(self, '_save_liquid_data_path') and path == self._save_liquid_data_path:
            print(f"[CropPreviewHandler] 根目录变化，检查是否有新区域文件夹...")
            self._scanAndAddNewRegionFolders()
        
        # 检查是哪个区域的文件夹（文件变化）
        for i, monitored_path in enumerate(self._monitored_paths):
            if monitored_path and osp.exists(monitored_path):
                try:
                    if osp.samefile(path, monitored_path):
                        self._checkRegionForNewImages(i, monitored_path)
                        break
                except (OSError, ValueError):
                    # 文件路径无效
                    continue
        
        # 发射文件夹变化信号
        self.folderChanged.emit(path)
    
    def _scanAndAddNewRegionFolders(self):
        """扫描并添加新创建的区域文件夹到监控列表"""
        if not hasattr(self, '_save_liquid_data_path') or not osp.exists(self._save_liquid_data_path):
            return
        
        # 获取当前视频名称（如果有的话）
        video_name = getattr(self, '_video_name', None)
        
        try:
            # 扫描所有子文件夹
            subdirs = [d for d in os.listdir(self._save_liquid_data_path) 
                      if osp.isdir(osp.join(self._save_liquid_data_path, d))]
            
            # 筛选出区域文件夹
            region_folders = []
            for subdir in subdirs:
                if video_name:
                    if subdir.startswith(f"{video_name}_") and '区域' in subdir:
                        region_folders.append(subdir)
                else:
                    if '区域' in subdir or 'region' in subdir.lower():
                        region_folders.append(subdir)
            
            region_folders.sort()
            
            # 检查每个区域文件夹，如果不在监控列表中则添加
            for i, folder_name in enumerate(region_folders):
                if i >= 3:  # 最多支持3个区域
                    break
                
                region_path = osp.join(self._save_liquid_data_path, folder_name)
                
                # 检查是否已在监控列表中
                if i < len(self._monitored_paths) and self._monitored_paths[i] == region_path:
                    continue  # 已经在监控中
                
                # 扩展监控列表
                while len(self._monitored_paths) <= i:
                    self._monitored_paths.append(None)
                
                # 添加新的监控路径
                if self._file_watcher and self._file_watcher.addPath(region_path):
                    self._monitored_paths[i] = region_path
                    
                    # 初始化该区域的已知图片列表
                    if i not in self._known_images:
                        self._known_images[i] = set()
                    
                    print(f"[CropPreviewHandler] 添加新区域监控: {folder_name}")
                    
                    # 更新面板的区域路径
                    if self._panel:
                        self._panel._findRegionPaths()
                else:
                    print(f"[CropPreviewHandler] 无法添加监控: {folder_name}")
                    
        except Exception as e:
            print(f"[CropPreviewHandler] 扫描新区域文件夹失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _checkForNewImages(self):
        """定时检查所有区域是否有新图片"""
        if not self._auto_monitor_enabled or self._is_resetting:
            return
        
        for i, region_path in enumerate(self._monitored_paths):
            if region_path and osp.exists(region_path):
                self._checkRegionForNewImages(i, region_path)
    
    def _checkRegionForNewImages(self, region_index, region_path):
        """
        检查指定区域是否有新图片
        
        Args:
            region_index: 区域索引 (0, 1, 2)
            region_path: 区域文件夹路径
        """
        # 支持的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        try:
            # 获取当前所有图片
            files = [f for f in os.listdir(region_path) 
                    if osp.isfile(osp.join(region_path, f)) and 
                    osp.splitext(f)[1].lower() in image_extensions]
            
            current_images = {osp.join(region_path, f) for f in files}
            
            # 获取已知图片集合
            known_images = self._known_images.get(region_index, set())
            
            # 找出新增的图片
            new_images = current_images - known_images
            
            if new_images:
                # 排序（按文件名）
                new_images_sorted = sorted(new_images)
                
                print(f"[CropPreviewHandler] 区域{region_index+1} 检测到 {len(new_images)} 张新图片")
                
                # 逐个添加到面板
                for image_path in new_images_sorted:
                    if self._panel:
                        self._panel.addImage(region_index, image_path)
                    
                    # 发射信号
                    self.newImageDetected.emit(region_index, image_path)
                
                # 更新已知图片列表
                self._known_images[region_index] = current_images
                
                # 检测到新图片后，立即触发一次额外检查（提高响应速度）
                if self._poll_timer and self._poll_timer.isActive():
                    # 重启定时器，立即进行下一次检查
                    self._poll_timer.stop()
                    self._poll_timer.start(self._poll_interval)
                
        except Exception as e:
            print(f"[CropPreviewHandler] 检查区域{region_index+1}新图片失败: {e}")
    
    def refreshPanel(self):
        """刷新面板显示"""
        if self._panel:
            self._panel.refreshImages()
    
    def forceRefresh(self):
        """
        强制立即检查所有区域的新图片
        
        用于在裁剪过程中手动触发检查，确保实时更新
        """
        if not self._auto_monitor_enabled or self._is_resetting:
            return
        
        print(f"[CropPreviewHandler] 强制刷新检查")
        for i, region_path in enumerate(self._monitored_paths):
            if region_path and osp.exists(region_path):
                self._checkRegionForNewImages(i, region_path)
    
    def clearPanel(self):
        """清空面板显示"""
        if self._panel:
            self._panel.clearImages()
    
    def setAutoMonitorEnabled(self, enabled):
        """
        设置是否启用自动监控
        
        Args:
            enabled: 是否启用
        """
        self._auto_monitor_enabled = enabled
        print(f"[CropPreviewHandler] 自动监控: {'启用' if enabled else '禁用'}")
    
    def loadExistingImages(self, save_liquid_data_path, video_name=None):
        """
        加载已有的裁剪图片（不启动监控）
        
        Args:
            save_liquid_data_path: 裁剪图片保存的根路径
            video_name: 视频名称（用于只加载该视频的区域文件夹）
        """
        print(f"[CropPreviewHandler] === 加载已有图片 ===")
        print(f"[CropPreviewHandler] 目标路径: {save_liquid_data_path}")
        print(f"[CropPreviewHandler] 视频名称: {video_name}")
        
        # 停止之前的监控
        self.stopMonitoring()
        
        # 清空面板显示
        if self._panel:
            self._panel.clearImages()
        
        # 设置面板的保存路径（不自动刷新）
        if self._panel:
            self._panel.setSavePath(save_liquid_data_path, auto_refresh=False, video_name=video_name)
        
        # 支持的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        # 扫描并加载区域文件夹中的图片
        if not osp.exists(save_liquid_data_path):
            print(f"[CropPreviewHandler] 保存路径不存在: {save_liquid_data_path}")
            return
        
        try:
            # 获取所有子文件夹
            subdirs = [d for d in os.listdir(save_liquid_data_path) 
                      if osp.isdir(osp.join(save_liquid_data_path, d))]
            
            # 筛选出区域文件夹
            region_folders = []
            for subdir in subdirs:
                if video_name:
                    # 匹配格式：视频名_区域X
                    if subdir.startswith(f"{video_name}_") and '区域' in subdir:
                        region_folders.append(subdir)
                else:
                    # 未指定视频名称时，加载所有区域文件夹
                    if '区域' in subdir or 'region' in subdir.lower():
                        region_folders.append(subdir)
            
            # 按文件夹名排序
            region_folders.sort()
            
            if video_name:
                print(f"[CropPreviewHandler] 只加载视频 '{video_name}' 的区域文件夹")
            print(f"[CropPreviewHandler] 发现 {len(region_folders)} 个区域文件夹: {region_folders}")
            
            # 加载每个区域的图片
            for i, folder_name in enumerate(region_folders):
                if i >= 3:  # 最多支持3个区域
                    break
                
                region_path = osp.join(save_liquid_data_path, folder_name)
                
                try:
                    # 获取该区域的所有图片
                    files = [f for f in os.listdir(region_path) 
                            if osp.isfile(osp.join(region_path, f)) and 
                            osp.splitext(f)[1].lower() in image_extensions]
                    
                    # 按文件名排序
                    files.sort()
                    
                    print(f"[CropPreviewHandler] {folder_name} 包含 {len(files)} 张图片")
                    
                    # 加载图片到面板（只加载最新的几张，避免加载过多）
                    max_images_to_load = 50  # 每个区域最多加载50张
                    images_to_load = files[-max_images_to_load:] if len(files) > max_images_to_load else files
                    
                    for filename in images_to_load:
                        image_path = osp.join(region_path, filename)
                        if self._panel:
                            self._panel.addImage(i, image_path)
                    
                    if len(files) > max_images_to_load:
                        print(f"[CropPreviewHandler] {folder_name} 只加载最新的 {max_images_to_load} 张图片")
                    
                except Exception as e:
                    print(f"[CropPreviewHandler] 加载 {folder_name} 失败: {e}")
            
            print(f"[CropPreviewHandler] === 图片加载完成 ===")
            
        except Exception as e:
            print(f"[CropPreviewHandler] 加载图片失败: {e}")
            import traceback
            traceback.print_exc()
    
    def clearDisplay(self):
        """清空显示"""
        print(f"[CropPreviewHandler] 清空显示")
        
        # 停止监控
        self.stopMonitoring()
        
        # 清空面板
        if self._panel:
            self._panel.clearImages()


def get_crop_preview_handler(panel=None):
    """
    获取裁剪预览处理器实例（单例模式）
    
    Args:
        panel: CropPreviewPanel 实例
        
    Returns:
        CropPreviewHandler 实例
    """
    if not hasattr(get_crop_preview_handler, '_instance'):
        get_crop_preview_handler._instance = CropPreviewHandler(panel)
    elif panel is not None:
        # 如果提供了新的panel，更新处理器的panel引用
        get_crop_preview_handler._instance._panel = panel
        get_crop_preview_handler._instance._initPanel()
    
    return get_crop_preview_handler._instance


if __name__ == "__main__":
    """测试入口"""
    import sys
    from qtpy import QtWidgets
    
    # 导入面板
    sys.path.insert(0, osp.join(osp.dirname(__file__), '..', '..'))
    from widgets.datasetpage.crop_preview_panel import CropPreviewPanel
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("裁剪预览处理器测试")
    window.resize(1000, 700)
    
    # 创建面板
    panel = CropPreviewPanel()
    window.setCentralWidget(panel)
    
    # 创建处理器
    handler = CropPreviewHandler(panel)
    
    # 连接信号
    def on_new_image(region_index, image_path):
        print(f"[SIGNAL] 新图片: 区域{region_index+1} - {osp.basename(image_path)}")
    
    handler.newImageDetected.connect(on_new_image)
    
    # 创建测试目录并开始监控
    def setup_test():
        import tempfile
        test_dir = osp.join(tempfile.gettempdir(), "crop_monitor_test")
        
        # 创建测试目录结构
        for i in range(3):
            region_dir = osp.join(test_dir, f"region{i+1}")
            os.makedirs(region_dir, exist_ok=True)
        
        # 开始监控
        handler.startMonitoring(test_dir)
        
        print(f"\n[TEST] 监控目录: {test_dir}")
        print("[TEST] 你可以手动向该目录的 region1/region2/region3 文件夹添加图片")
        print("[TEST] 处理器会自动检测并更新显示\n")
        
        # 模拟添加图片（每5秒添加一张）
        def add_test_image():
            try:
                import cv2
                import numpy as np
                import time
                
                region_index = int(time.time()) % 3
                region_dir = osp.join(test_dir, f"region{region_index+1}")
                
                img_count = len([f for f in os.listdir(region_dir) if f.endswith('.jpg')])
                img_path = osp.join(region_dir, f"test_{img_count+1:06d}.jpg")
                
                # 创建随机颜色图片
                color = np.random.randint(0, 255, 3, dtype=np.uint8)
                img = np.full((480, 640, 3), color, dtype=np.uint8)
                
                cv2.putText(img, f"Auto Generated {img_count+1}", 
                           (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 
                           1.5, (255, 255, 255), 3)
                
                cv2.imwrite(img_path, img)
                
                print(f"[TEST] 自动生成测试图片: 区域{region_index+1} - {osp.basename(img_path)}")
                
            except Exception as e:
                print(f"[TEST] 生成测试图片失败: {e}")
        
        # 定时器：每5秒自动生成一张图片
        timer = QtCore.QTimer()
        timer.timeout.connect(add_test_image)
        timer.start(5000)
        
        # 保持定时器引用，避免被垃圾回收
        window._test_timer = timer
    
    # 延迟启动测试
    QtCore.QTimer.singleShot(500, setup_test)
    
    print("\n" + "="*70)
    print(" 裁剪预览处理器测试程序")
    print("="*70)
    print("\n功能:")
    print("  - 自动监控指定文件夹的变化")
    print("  - 实时检测新增的图片文件")
    print("  - 自动更新预览面板显示")
    print("  - 每5秒自动生成一张测试图片")
    print("\n操作:")
    print("  1. 程序会自动创建临时测试目录")
    print("  2. 每5秒自动向随机区域添加一张测试图片")
    print("  3. 观察面板自动更新")
    print("  4. 也可以手动添加图片到测试目录")
    print("="*70 + "\n")
    
    window.show()
    sys.exit(app.exec_())

