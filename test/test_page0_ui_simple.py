#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import xml.etree.ElementTree as ET

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def parse_ui_file(ui_file):
    """解析UI文件并显示结构"""
    print(f"\n{'='*60}")
    print(f"UI文件: {ui_file}")
    print(f"{'='*60}\n")

    if not os.path.exists(ui_file):
        print(f"错误: UI文件不存在!")
        return

    try:
        tree = ET.parse(ui_file)
        root = tree.getroot()

        print(f"UI版本: {root.get('version')}")
        print(f"主类名: {root.find('class').text if root.find('class') is not None else 'N/A'}")

        # 查找主widget
        main_widget = root.find('widget')
        if main_widget is not None:
            print(f"\n主窗口:")
            print(f"  类型: {main_widget.get('class')}")
            print(f"  名称: {main_widget.get('name')}")

            # 查找geometry
            geometry = main_widget.find('.//property[@name="geometry"]/rect')
            if geometry is not None:
                width = geometry.find('width').text
                height = geometry.find('height').text
                print(f"  尺寸: {width}x{height}")

        # 递归显示widget结构
        print(f"\n{'='*60}")
        print("UI结构树:")
        print(f"{'='*60}\n")
        display_widget_tree(main_widget, 0)

    except Exception as e:
        print(f"解析UI文件失败: {e}")
        import traceback
        traceback.print_exc()

def display_widget_tree(widget, level=0):
    """递归显示widget树结构"""
    if widget is None:
        return

    indent = "  " * level
    widget_class = widget.get('class', 'Unknown')
    widget_name = widget.get('name', 'unnamed')

    # 获取objectName属性
    object_name_prop = widget.find('.//property[@name="objectName"]/string')
    if object_name_prop is not None:
        object_name = object_name_prop.text
        print(f"{indent}├─ {widget_class} [{widget_name}] (objectName: {object_name})")
    else:
        print(f"{indent}├─ {widget_class} [{widget_name}]")

    # 显示一些重要属性
    if widget_class == 'QStackedWidget':
        current_index = widget.find('.//property[@name="currentIndex"]/number')
        if current_index is not None:
            print(f"{indent}│  └─ 当前索引: {current_index.text}")

    if widget_class in ['QScrollArea', 'QWidget']:
        min_size = widget.find('.//property[@name="minimumSize"]/size')
        if min_size is not None:
            width = min_size.find('width')
            height = min_size.find('height')
            if width is not None and height is not None:
                print(f"{indent}│  └─ 最小尺寸: {width.text}x{height.text}")

    # 递归处理子widget
    for child_widget in widget.findall('widget'):
        display_widget_tree(child_widget, level + 1)

    # 处理layout中的widget
    for layout in widget.findall('.//layout'):
        for item in layout.findall('item'):
            child_widget = item.find('widget')
            if child_widget is not None:
                display_widget_tree(child_widget, level + 1)

def main():
    ui_file = os.path.join(project_root, 'client', 'ui', 'page0_video.ui')
    parse_ui_file(ui_file)

    print(f"\n{'='*60}")
    print("UI文件说明:")
    print(f"{'='*60}\n")
    print("Page0 - 视频监控页面包含两种显示模式:")
    print("\n模式1 - 默认布局 (索引0):")
    print("  ├─ 左侧: 任务表格面板 (MissionPanel)")
    print("  └─ 右侧: 2x8通道面板网格 (16个通道, 带滚动条)")
    print("      └─ 每个通道: 620x465像素")
    print("\n模式2 - 曲线模式布局 (索引1):")
    print("  ├─ 左侧: 子布局栈 (宽度660px)")
    print("  │   ├─ 子布局0: 实时检测曲线布局 (垂直通道列表)")
    print("  │   └─ 子布局1: 历史回放曲线布局")
    print("  └─ 右侧: 曲线面板 (CurvePanel, 共用)")
    print("\n通过 videoLayoutStack.setCurrentIndex(0/1) 切换模式")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
