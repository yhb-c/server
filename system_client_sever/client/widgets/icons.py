# -*- coding: utf-8 -*-
"""
图标和按钮工具模块
"""

from qtpy import QtGui, QtWidgets, QtCore


def newIcon(icon):
    """
    创建图标
    
    Args:
        icon: 图标路径或名称
        
    Returns:
        QIcon对象
    """
    if isinstance(icon, str):
        return QtGui.QIcon(icon)
    return QtGui.QIcon()


def newButton(text, icon=None, slot=None):
    """
    创建按钮
    
    Args:
        text: 按钮文本
        icon: 图标（可选）
        slot: 点击槽函数（可选）
        
    Returns:
        QPushButton对象
    """
    button = QtWidgets.QPushButton(text)
    
    if icon:
        if isinstance(icon, str):
            button.setIcon(QtGui.QIcon(icon))
        else:
            button.setIcon(icon)
    
    if slot:
        button.clicked.connect(slot)
    
    return button
