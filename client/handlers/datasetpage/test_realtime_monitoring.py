# -*- coding: utf-8 -*-

"""
AnnotationHandler 实时监控功能测试脚本

测试实时文件监控、JSON文件检测和自动更新功能
"""

import sys
import os
import os.path as osp
import json
import time
import shutil
from qtpy import QtWidgets, QtCore

# 添加项目路径
project_root = osp.abspath(osp.join(osp.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from handlers.datasetpage.annotation_handler import AnnotationHandler


class TestWindow(QtWidgets.QWidget):
    """测试窗口"""
    
    def __init__(self):
        super(TestWindow, self).__init__()
        
        # 创建测试目录
        self.test_dir = osp.join(osp.expanduser("~"), "test_annotation_monitoring")
        os.makedirs(self.test_dir, exist_ok=True)
        
        # 创建handler
        self.handler = AnnotationHandler()
        
        # 连接信号
        self._connectSignals()
        
        # 初始化UI
        self._initUI()
        
        # 设置目录
        self.handler.setDirectory(self.test_dir)
        
        print(f"\n{'='*70}")
        print(f"测试目录: {self.test_dir}")
        print(f"{'='*70}\n")
    
    def _initUI(self):
        """初始化UI"""
        self.setWindowTitle("AnnotationHandler 实时监控测试")
        self.resize(800, 600)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题
        title = QtWidgets.QLabel("AnnotationHandler 实时监控测试")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # 测试目录显示
        dir_layout = QtWidgets.QHBoxLayout()
        dir_layout.addWidget(QtWidgets.QLabel("测试目录:"))
        self.lbl_dir = QtWidgets.QLabel(self.test_dir)
        self.lbl_dir.setStyleSheet("color: #0078d7; font-weight: bold;")
        dir_layout.addWidget(self.lbl_dir, stretch=1)
        layout.addLayout(dir_layout)
        
        # 统计信息
        stats_group = QtWidgets.QGroupBox("统计信息")
        stats_layout = QtWidgets.QFormLayout()
        
        self.lbl_total = QtWidgets.QLabel("0")
        self.lbl_annotated = QtWidgets.QLabel("0")
        self.lbl_unannotated = QtWidgets.QLabel("0")
        
        stats_layout.addRow("总文件数:", self.lbl_total)
        stats_layout.addRow("已标注:", self.lbl_annotated)
        stats_layout.addRow("未标注:", self.lbl_unannotated)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 文件列表
        list_group = QtWidgets.QGroupBox("文件列表")
        list_layout = QtWidgets.QVBoxLayout()
        
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setAlternatingRowColors(True)
        list_layout.addWidget(self.file_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 日志输出
        log_group = QtWidgets.QGroupBox("监控日志")
        log_layout = QtWidgets.QVBoxLayout()
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 测试按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_add_image = QtWidgets.QPushButton("添加测试图片")
        self.btn_add_image.clicked.connect(self._onAddImage)
        button_layout.addWidget(self.btn_add_image)
        
        self.btn_add_json = QtWidgets.QPushButton("添加标注JSON")
        self.btn_add_json.clicked.connect(self._onAddJson)
        button_layout.addWidget(self.btn_add_json)
        
        self.btn_modify_json = QtWidgets.QPushButton("修改标注")
        self.btn_modify_json.clicked.connect(self._onModifyJson)
        button_layout.addWidget(self.btn_modify_json)
        
        self.btn_delete_file = QtWidgets.QPushButton("删除文件")
        self.btn_delete_file.clicked.connect(self._onDeleteFile)
        button_layout.addWidget(self.btn_delete_file)
        
        self.btn_clear = QtWidgets.QPushButton("清空测试目录")
        self.btn_clear.clicked.connect(self._onClear)
        button_layout.addWidget(self.btn_clear)
        
        layout.addLayout(button_layout)
        
        # 说明
        info = QtWidgets.QLabel(
            "说明：点击按钮执行测试操作，观察列表和统计信息是否自动更新（2秒内）"
        )
        info.setStyleSheet("color: #666; padding: 10px; font-style: italic;")
        info.setWordWrap(True)
        layout.addWidget(info)
    
    def _connectSignals(self):
        """连接信号"""
        self.handler.directoryChanged.connect(self._onDirectoryChanged)
        self.handler.fileListUpdated.connect(self._onFileListUpdated)
        self.handler.statisticsUpdated.connect(self._onStatisticsUpdated)
        self.handler.fileAdded.connect(self._onFileAdded)
        self.handler.fileRemoved.connect(self._onFileRemoved)
        self.handler.fileModified.connect(self._onFileModified)
    
    def _onDirectoryChanged(self, dir_path):
        """目录变化"""
        self._log(f"[目录变化] {dir_path}")
    
    def _onFileListUpdated(self, file_list):
        """文件列表更新"""
        self._log(f"[列表更新] 共 {len(file_list)} 个文件")
        
        # 更新UI列表
        self.file_list.clear()
        for info in file_list:
            status = "✓" if info['has_json'] else "○"
            shapes = f"({info['shapes_count']}个对象)" if info['has_json'] else ""
            text = f"{status} {info['file_name']} {shapes}"
            
            item = QtWidgets.QListWidgetItem(text)
            if info['has_json']:
                item.setForeground(QtCore.Qt.darkGreen)
            self.file_list.addItem(item)
    
    def _onStatisticsUpdated(self, stats):
        """统计信息更新"""
        self._log(f"[统计更新] 总:{stats['total']} 已标注:{stats['annotated']} 未标注:{stats['unannotated']}")
        
        self.lbl_total.setText(str(stats['total']))
        self.lbl_annotated.setText(str(stats['annotated']))
        self.lbl_annotated.setStyleSheet("color: #2ca02c; font-weight: bold;")
        self.lbl_unannotated.setText(str(stats['unannotated']))
    
    def _onFileAdded(self, path):
        """文件添加"""
        self._log(f"[新增文件] {osp.basename(path)}", color="green")
    
    def _onFileRemoved(self, path):
        """文件删除"""
        self._log(f"[删除文件] {osp.basename(path)}", color="red")
    
    def _onFileModified(self, path):
        """文件修改"""
        self._log(f"[修改文件] {osp.basename(path)}", color="blue")
    
    def _log(self, message, color="black"):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        color_map = {
            "black": "black",
            "green": "#2ca02c",
            "red": "#d62728",
            "blue": "#1f77b4"
        }
        
        html = f'<span style="color: {color_map.get(color, "black")};">[{timestamp}] {message}</span><br>'
        self.log_text.insertHtml(html)
        self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def _onAddImage(self):
        """添加测试图片"""
        # 生成一个简单的测试图片
        from qtpy import QtGui
        
        count = len([f for f in os.listdir(self.test_dir) if f.endswith('.jpg')])
        filename = f"test_image_{count+1:03d}.jpg"
        filepath = osp.join(self.test_dir, filename)
        
        # 创建一个简单的图片
        pixmap = QtGui.QPixmap(640, 480)
        pixmap.fill(QtCore.Qt.white)
        pixmap.save(filepath, "JPG")
        
        self._log(f"[操作] 添加图片: {filename}", color="blue")
        QtWidgets.QMessageBox.information(self, "提示", f"已添加图片: {filename}\n请观察列表是否自动更新")
    
    def _onAddJson(self):
        """添加标注JSON"""
        # 获取未标注的图片
        files = self.handler.getAllFileInfoList()
        unannotated = [f for f in files if not f['has_json']]
        
        if not unannotated:
            QtWidgets.QMessageBox.warning(self, "提示", "没有未标注的图片！\n请先添加测试图片")
            return
        
        # 为第一个未标注的图片创建JSON
        info = unannotated[0]
        json_path = info['json_path']
        
        # 创建labelme格式的JSON
        json_data = {
            "version": "5.0.0",
            "flags": {},
            "shapes": [
                {
                    "label": "test_object",
                    "points": [[100, 100], [200, 200]],
                    "group_id": None,
                    "shape_type": "rectangle",
                    "flags": {}
                }
            ],
            "imagePath": info['file_name'],
            "imageData": None,
            "imageHeight": 480,
            "imageWidth": 640
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        self._log(f"[操作] 添加标注: {info['file_name']}", color="blue")
        QtWidgets.QMessageBox.information(
            self, "提示", 
            f"已为 {info['file_name']} 添加标注\n请在2秒内观察列表是否显示✓标记"
        )
    
    def _onModifyJson(self):
        """修改标注"""
        # 获取已标注的图片
        files = self.handler.getAllFileInfoList()
        annotated = [f for f in files if f['has_json']]
        
        if not annotated:
            QtWidgets.QMessageBox.warning(self, "提示", "没有已标注的图片！\n请先添加标注")
            return
        
        # 修改第一个标注
        info = annotated[0]
        json_path = info['json_path']
        
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # 添加一个新的对象
        json_data['shapes'].append({
            "label": "new_object",
            "points": [[300, 300], [400, 400]],
            "group_id": None,
            "shape_type": "rectangle",
            "flags": {}
        })
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        self._log(f"[操作] 修改标注: {info['file_name']}", color="blue")
        QtWidgets.QMessageBox.information(
            self, "提示", 
            f"已修改 {info['file_name']} 的标注\n请在2秒内观察对象数量是否更新"
        )
    
    def _onDeleteFile(self):
        """删除文件"""
        files = self.handler.getAllFileInfoList()
        
        if not files:
            QtWidgets.QMessageBox.warning(self, "提示", "没有文件可删除！")
            return
        
        # 删除最后一个文件
        info = files[-1]
        image_path = info['image_path']
        json_path = info['json_path']
        
        try:
            if osp.exists(image_path):
                os.remove(image_path)
            if osp.exists(json_path):
                os.remove(json_path)
            
            self._log(f"[操作] 删除文件: {info['file_name']}", color="blue")
            QtWidgets.QMessageBox.information(
                self, "提示", 
                f"已删除 {info['file_name']}\n请观察列表是否自动移除该文件"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"删除失败: {e}")
    
    def _onClear(self):
        """清空测试目录"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认", 
            "确定要清空测试目录吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for file in os.listdir(self.test_dir):
                    file_path = osp.join(self.test_dir, file)
                    if osp.isfile(file_path):
                        os.remove(file_path)
                
                self._log("[操作] 清空测试目录", color="blue")
                QtWidgets.QMessageBox.information(self, "提示", "测试目录已清空\n请观察列表是否自动清空")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"清空失败: {e}")
    
    def closeEvent(self, event):
        """关闭窗口时停止监控"""
        self.handler.stopMonitoring()
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    print("\n" + "="*70)
    print(" AnnotationHandler 实时监控功能测试")
    print("="*70)
    print("\n测试说明:")
    print("  1. 点击'添加测试图片'按钮 - 列表应立即显示新图片")
    print("  2. 点击'添加标注JSON'按钮 - 2秒内列表应显示✓标记")
    print("  3. 点击'修改标注'按钮 - 2秒内对象数量应更新")
    print("  4. 点击'删除文件'按钮 - 列表应立即移除文件")
    print("  5. 点击'清空测试目录'按钮 - 列表应立即清空")
    print("\n观察要点:")
    print("  - 监控日志中的时间戳")
    print("  - 统计信息的变化")
    print("  - 文件列表的实时更新")
    print("="*70 + "\n")
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec_())


