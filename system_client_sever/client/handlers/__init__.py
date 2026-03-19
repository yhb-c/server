# -*- coding: utf-8 -*-

"""
信号槽处理方法模块

按功能模块分离，使用Mixin模式组织代码
模仿labelme设计，但采用更清晰的文件结构
"""

# 视频页面处理器（从 videopage 子模块导入）
from .videopage import (
    ChannelPanelHandler,
    CurvePanelHandler,
    MissionPanelHandler,
    ModelSettingHandler,
    GeneralSetPanelHandler
)

from .file_handler import FileHandler
from .view_handler import ViewHandler
from .settings_handler import SettingsHandler
from .menubar_handler import MenuBarHandler
from .modelpage import (
    ModelSyncHandler,
    ModelSignalHandler,
    ModelSetHandler,
    ModelLoadHandler,
    ModelSettingsHandler,
    ModelTrainingHandler
)

__all__ = [
    'ChannelPanelHandler',
    'CurvePanelHandler',
    'MissionPanelHandler',
    'ModelSettingHandler',
    'GeneralSetPanelHandler',
    'FileHandler',
    'ViewHandler',
    'SettingsHandler',
    'MenuBarHandler',
    'ModelSyncHandler',
    'ModelSignalHandler',
    'ModelSetHandler',
    'ModelLoadHandler',
    'ModelSettingsHandler',
    'ModelTrainingHandler',
]

