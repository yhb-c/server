# -*- coding: utf-8 -*-

"""
测试labelme集成功能

运行此脚本验证labelme是否正确嵌入到AnnotationTool中
"""

import sys
import os
import os.path as osp

# 添加项目根目录到路径
project_root = osp.dirname(osp.dirname(osp.dirname(osp.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from qtpy import QtWidgets, QtCore
from qtpy.QtCore import Qt

# 导入标注工具
from annotationtool import AnnotationTool


def test_labelme_integration():
    """测试labelme集成"""
    # 创建应用
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Labelme集成测试 - AnnotationTool")
    window.resize(1600, 900)
    
    # 创建标注工具
    annotation_tool = AnnotationTool()
    window.setCentralWidget(annotation_tool)
    
    # 添加测试数据
    test_images = [
        {
            "name": "sample_001.jpg",
            "path": osp.join(project_root, "test_images", "sample_001.jpg"),
            "size": "2.5 MB",
            "resolution": "1920x1080",
            "json": "不存在",
            "objects": "0 个对象",
            "time": "--"
        },
        {
            "name": "sample_002.jpg",
            "path": osp.join(project_root, "test_images", "sample_002.jpg"),
            "size": "1.8 MB",
            "resolution": "1280x720",
            "json": "不存在",
            "objects": "0 个对象",
            "time": "--"
        },
    ]
    
    for img_data in test_images:
        item = QtWidgets.QListWidgetItem(annotation_tool.annotation_list)
        icon = annotation_tool.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        item.setIcon(icon)
        item.setText(f" {img_data['name']}\n{img_data['resolution']}")
        item.setData(Qt.UserRole, img_data)
    
    # 更新统计
    annotation_tool.lbl_total_stats.setText(f"总数: {len(test_images)}")
    annotation_tool.lbl_annotated_stats.setText("已标注: 0")
    
    # 连接列表点击事件（演示如何加载图片）
    def on_item_clicked(item):
        data = item.data(Qt.UserRole)
        
        # 更新详细信息
        annotation_tool.lbl_image_name.setText(data["name"])
        annotation_tool.lbl_image_size.setText(data["size"])
        annotation_tool.lbl_image_resolution.setText(data["resolution"])
        annotation_tool.lbl_json_status.setText(data["json"])
        annotation_tool.lbl_objects_count.setText(data["objects"])
        annotation_tool.lbl_annotation_time.setText(data["time"])
        
        # 如果图片存在，加载到labelme
        if osp.exists(data["path"]):
            annotation_tool.loadImageForAnnotation(data["path"])
    
    annotation_tool.annotation_list.itemClicked.connect(on_item_clicked)
    
    # 显示窗口
    window.show()
    
    # 如果labelme初始化成功，显示成功消息
    if annotation_tool.labelme_widget is not None:
        QtWidgets.QMessageBox.information(
            window,
            " 测试成功",
            "Labelme已成功嵌入到AnnotationTool！\n\n"
            "您可以：\n"
            "1. 在右侧labelme中点击'打开'加载图片\n"
            "2. 使用labelme的所有标注功能\n"
            "3. 测试工具栏按钮\n\n"
            "更多信息请查看控制台输出。"
        )
    else:
        QtWidgets.QMessageBox.warning(
            window,
            " 初始化失败",
            "Labelme未能成功初始化。\n\n"
            "请确保已安装labelme：\n"
            "pip install labelme\n\n"
            "详细错误信息请查看控制台。"
        )
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    test_labelme_integration()

