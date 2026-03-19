# -*- coding: utf-8 -*-

"""
数据标注处理器

负责处理数据标注相关的业务逻辑：
- 文件扫描和管理
- JSON标注文件解析
- 标注状态管理
- 文件信息统计
- 实时文件系统监控
"""

import os
import os.path as osp
import json
from datetime import datetime
from qtpy import QtCore, QtGui


class AnnotationHandler(QtCore.QObject):
    """
    数据标注业务逻辑处理器
    
    职责：
    1. 扫描和管理图片文件
    2. 解析JSON标注文件
    3. 统计标注状态
    4. 提供文件信息查询
    5. 实时监控文件系统变化
    """
    
    # 自定义信号
    directoryChanged = QtCore.Signal(str)  # 目录变化
    fileListUpdated = QtCore.Signal(list)  # 文件列表更新
    currentFileChanged = QtCore.Signal(str)  # 当前文件变化
    statisticsUpdated = QtCore.Signal(dict)  # 统计信息更新
    fileAdded = QtCore.Signal(str)  # 新文件添加
    fileRemoved = QtCore.Signal(str)  # 文件删除
    fileModified = QtCore.Signal(str)  # 文件修改
    
    def __init__(self, parent=None):
        super(AnnotationHandler, self).__init__(parent)
        
        # 当前工作目录
        self.current_dir = None
        
        # 文件列表
        self.image_files = []  # 所有图片文件路径
        self.file_info_dict = {}  # 文件信息字典 {image_path: info_dict}
        
        # 统计信息
        self.statistics = {
            'total': 0,
            'annotated': 0,
            'unannotated': 0
        }
        
        # 支持的图片格式
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff']
        
        # 文件系统监控器
        self.file_watcher = QtCore.QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self._onDirectoryChanged)
        self.file_watcher.fileChanged.connect(self._onFileChanged)
        
        # 定时刷新器（用于定期检查JSON文件变化）
        self.refresh_timer = QtCore.QTimer()
        self.refresh_timer.timeout.connect(self._onRefreshTimer)
        self.refresh_interval = 2000  # 默认2秒刷新一次
        
        # 监控状态
        self.monitoring_enabled = False
    
    def setDirectory(self, dir_path):
        """
        设置工作目录并扫描文件
        
        Args:
            dir_path: 目录路径
        
        Returns:
            bool: 是否成功
        """
        if not dir_path or not osp.exists(dir_path):
            return False
        
        # 停止之前的监控
        self.stopMonitoring()
        
        self.current_dir = dir_path
        self.directoryChanged.emit(dir_path)
        
        # 扫描文件
        success = self.scanImageFiles()
        
        if success:
            # 加载文件信息
            self.loadFileInfoList()
            
            # 更新统计
            self.updateStatistics()
            
            # 启动监控
            self.startMonitoring()
        
        return success
    
    def startMonitoring(self):
        """启动文件系统监控"""
        if not self.current_dir:
            return False
        
        try:
            # 添加目录到监控列表
            if self.current_dir not in self.file_watcher.directories():
                self.file_watcher.addPath(self.current_dir)
            
            # 启动定时刷新
            if not self.refresh_timer.isActive():
                self.refresh_timer.start(self.refresh_interval)
            
            self.monitoring_enabled = True
            return True
            
        except Exception as e:
            return False
    
    def stopMonitoring(self):
        """停止文件系统监控"""
        try:
            # 移除所有监控路径
            directories = self.file_watcher.directories()
            if directories:
                self.file_watcher.removePaths(directories)
            
            files = self.file_watcher.files()
            if files:
                self.file_watcher.removePaths(files)
            
            # 停止定时器
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()
            
            self.monitoring_enabled = False
            
        except Exception as e:
            pass
    
    def _onDirectoryChanged(self, path):
        """目录内容变化回调"""
        
        # 重新扫描文件
        old_files = set(self.image_files)
        self.scanImageFiles()
        new_files = set(self.image_files)
        
        # 检测新增文件
        added_files = new_files - old_files
        for file_path in added_files:
            self.fileAdded.emit(file_path)
        
        # 检测删除文件
        removed_files = old_files - new_files
        for file_path in removed_files:
            if file_path in self.file_info_dict:
                del self.file_info_dict[file_path]
            self.fileRemoved.emit(file_path)
        
        # 重新加载文件信息
        self.loadFileInfoList()
        
        # 更新统计
        self.updateStatistics()
    
    def _onFileChanged(self, path):
        """文件变化回调"""
        
        # 刷新该文件的信息
        if path in self.file_info_dict:
            self.refreshFileInfo(path)
            self.fileModified.emit(path)
    
    def _onRefreshTimer(self):
        """定时刷新回调 - 检查JSON文件变化"""
        if not self.monitoring_enabled or not self.current_dir:
            return
        
        try:
            # 检查每个图片文件对应的JSON文件
            has_changes = False
            
            for image_path in list(self.image_files):
                if image_path not in self.file_info_dict:
                    continue
                
                old_info = self.file_info_dict[image_path]
                json_path = old_info['json_path']
                
                # 检查JSON文件状态是否变化
                json_exists_now = osp.exists(json_path)
                json_existed_before = old_info['has_json']
                
                if json_exists_now != json_existed_before:
                    # JSON文件状态发生变化
                    self.refreshFileInfo(image_path)
                    has_changes = True
                elif json_exists_now:
                    # 检查JSON文件是否被修改
                    try:
                        current_mtime = osp.getmtime(json_path)
                        # 重新获取JSON信息来检查
                        json_info = self.getJsonInfo(json_path)
                        if json_info['shapes_count'] != old_info['shapes_count']:
                            self.refreshFileInfo(image_path)
                            has_changes = True
                    except Exception as e:
                        pass
            
            # 如果有变化，更新统计
            if has_changes:
                self.updateStatistics()
                # 重新发送文件列表更新信号
                self.fileListUpdated.emit(self.getAllFileInfoList())
                
        except Exception as e:
            pass
    
    def setRefreshInterval(self, interval_ms):
        """
        设置刷新间隔
        
        Args:
            interval_ms: 刷新间隔（毫秒）
        """
        self.refresh_interval = interval_ms
        
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            self.refresh_timer.start(self.refresh_interval)
    
    def scanImageFiles(self):
        """
        扫描目录中的图片文件
        
        Returns:
            bool: 是否成功
        """
        if not self.current_dir:
            return False
        
        self.image_files = []
        
        try:
            for root, dirs, files in os.walk(self.current_dir):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in self.image_extensions):
                        full_path = osp.join(root, file)
                        self.image_files.append(full_path)
            
            # 排序
            self.image_files.sort()
            
            return True
            
        except Exception as e:
            return False
    
    def loadFileInfoList(self):
        """加载所有文件的信息"""
        self.file_info_dict = {}
        file_info_list = []
        
        for image_path in self.image_files:
            info = self.getFileInfo(image_path)
            self.file_info_dict[image_path] = info
            file_info_list.append(info)
        
        self.fileListUpdated.emit(file_info_list)
    
    def getFileInfo(self, image_path):
        """
        获取单个文件的完整信息
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            dict: 文件信息字典
        """
        info = {
            'image_path': image_path,
            'file_name': osp.basename(image_path),
            'json_path': osp.splitext(image_path)[0] + ".json",
            'has_json': False,
            'file_size': 0,
            'file_size_str': '--',
            'resolution': '--',
            'resolution_width': 0,
            'resolution_height': 0,
            'shapes_count': 0,
            'modified_time': '--',
            'thumbnail': None
        }
        
        # 检查JSON文件
        info['has_json'] = osp.exists(info['json_path'])
        
        # 获取文件大小
        try:
            file_size = osp.getsize(image_path)
            info['file_size'] = file_size
            
            if file_size < 1024:
                info['file_size_str'] = f"{file_size} B"
            elif file_size < 1024 * 1024:
                info['file_size_str'] = f"{file_size / 1024:.1f} KB"
            else:
                info['file_size_str'] = f"{file_size / (1024 * 1024):.1f} MB"
        except Exception as e:
            pass
        
        # 获取分辨率
        try:
            pixmap = QtGui.QPixmap(image_path)
            if not pixmap.isNull():
                info['resolution_width'] = pixmap.width()
                info['resolution_height'] = pixmap.height()
                info['resolution'] = f"{pixmap.width()}x{pixmap.height()}"
                
                # 生成缩略图
                info['thumbnail'] = pixmap.scaled(
                    80, 80,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
        except Exception as e:
            pass
        
        # 如果有JSON文件，获取JSON信息
        if info['has_json']:
            json_info = self.getJsonInfo(info['json_path'])
            info['shapes_count'] = json_info['shapes_count']
            info['modified_time'] = json_info['modified_time']
        
        return info
    
    def getJsonInfo(self, json_path):
        """
        获取JSON文件信息
        
        Args:
            json_path: JSON文件路径
        
        Returns:
            dict: JSON信息
        """
        info = {
            'shapes_count': 0,
            'modified_time': '--',
            'labels': []
        }
        
        try:
            # 读取JSON文件
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                shapes = data.get('shapes', [])
                info['shapes_count'] = len(shapes)
                
                # 获取所有标签
                info['labels'] = list(set([shape.get('label', '') for shape in shapes]))
            
            # 获取修改时间
            mtime = osp.getmtime(json_path)
            info['modified_time'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            pass
        
        return info
    
    def updateStatistics(self):
        """更新统计信息"""
        total = len(self.image_files)
        annotated = sum(1 for info in self.file_info_dict.values() if info['has_json'])
        
        self.statistics = {
            'total': total,
            'annotated': annotated,
            'unannotated': total - annotated
        }
        
        self.statisticsUpdated.emit(self.statistics)
    
    def filterFiles(self, filter_type='all', search_text=''):
        """
        筛选文件
        
        Args:
            filter_type: 筛选类型 ('all', 'annotated', 'unannotated', 'review')
            search_text: 搜索文本
        
        Returns:
            list: 筛选后的文件信息列表
        """
        filtered_list = []
        
        for info in self.file_info_dict.values():
            # 按状态筛选
            if filter_type == 'annotated' and not info['has_json']:
                continue
            elif filter_type == 'unannotated' and info['has_json']:
                continue
            # 'all' 和 'review' 显示全部
            
            # 按搜索文本筛选
            if search_text:
                if search_text.lower() not in info['file_name'].lower():
                    continue
            
            filtered_list.append(info)
        
        return filtered_list
    
    def getFileInfoByPath(self, image_path):
        """
        根据路径获取文件信息
        
        Args:
            image_path: 图片路径
        
        Returns:
            dict: 文件信息，如果不存在返回None
        """
        return self.file_info_dict.get(image_path)
    
    def refreshFileInfo(self, image_path):
        """
        刷新单个文件的信息（用于标注后更新）
        
        Args:
            image_path: 图片路径
        """
        if image_path in self.file_info_dict:
            # 重新获取文件信息
            new_info = self.getFileInfo(image_path)
            self.file_info_dict[image_path] = new_info
            
            # 更新统计
            self.updateStatistics()
            
            return new_info
        
        return None
    
    def getAllFileInfoList(self):
        """
        获取所有文件信息列表
        
        Returns:
            list: 文件信息列表
        """
        return list(self.file_info_dict.values())
    
    def getCurrentDirectory(self):
        """获取当前目录"""
        return self.current_dir
    
    def getStatistics(self):
        """获取统计信息"""
        return self.statistics
    
    def getTotalCount(self):
        """获取文件总数"""
        return self.statistics['total']
    
    def getAnnotatedCount(self):
        """获取已标注数量"""
        return self.statistics['annotated']
    
    def getUnannotatedCount(self):
        """获取未标注数量"""
        return self.statistics['unannotated']
    
    def exportStatistics(self, output_path=None):
        """
        导出统计信息到JSON文件
        
        Args:
            output_path: 输出文件路径，如果为None则使用默认路径
        
        Returns:
            bool: 是否成功
        """
        if output_path is None:
            if not self.current_dir:
                return False
            output_path = osp.join(self.current_dir, 'annotation_statistics.json')
        
        try:
            export_data = {
                'directory': self.current_dir,
                'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'statistics': self.statistics,
                'files': []
            }
            
            # 添加每个文件的信息
            for info in self.file_info_dict.values():
                export_data['files'].append({
                    'file_name': info['file_name'],
                    'has_json': info['has_json'],
                    'shapes_count': info['shapes_count'],
                    'file_size': info['file_size'],
                    'resolution': info['resolution']
                })
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            return False


# 单例模式（可选）
_annotation_handler_instance = None

def get_annotation_handler():
    """获取AnnotationHandler的单例实例"""
    global _annotation_handler_instance
    if _annotation_handler_instance is None:
        _annotation_handler_instance = AnnotationHandler()
    return _annotation_handler_instance




