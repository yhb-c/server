#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试测试
"""

import sys
from pathlib import Path

client_path = Path(__file__).parent / 'client'
sys.path.insert(0, str(client_path))

from qtpy import QtWidgets

def test_debug():
    app = QtWidgets.QApplication(sys.argv)

    from widgets.videopage.channelpanel import ChannelPanel

    # 创建主窗口
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("调试测试")
    main_window.resize(800, 600)

    # 创建滚动区域
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)

    # 创建容器
    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)

    print("=" * 80)
    print("开始创建 ChannelPanel")
    print("=" * 80)

    # 只创建3个面板用于测试
    for i in range(1, 4):
        print(f"\n{'='*80}")
        print(f"创建通道{i}")
        print(f"{'='*80}")
        panel = ChannelPanel(title=f"通道{i}")
        layout.addWidget(panel)

        print(f"\n调用 setHwndRenderMode for 通道{i}")
        panel.setHwndRenderMode(True)

        print(f"\n调用 updateOverlayInfo for 通道{i}")
        panel.updateOverlayInfo(
            channel_name=f"通道{i}",
            task_name=f"任务{i}",
            fps=25.0,
            resolution="1920x1080"
        )
        print(f"\n通道{i} 创建完成\n")

    scroll_area.setWidget(container)
    main_window.setCentralWidget(scroll_area)
    main_window.show()

    print("\n" + "=" * 80)
    print("所有面板创建完成，窗口已显示")
    print("=" * 80)

    sys.exit(app.exec_())

if __name__ == '__main__':
    test_debug()
