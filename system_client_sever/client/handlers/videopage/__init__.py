# -*- coding: utf-8 -*-

"""
视频页面相关的处理器

命名规范：组件名_handler.py → 组件名Handler 类

每个组件对应一个Handler类：
- ChannelPanelHandler (channelpanel_handler.py): 通道面板 - 通道连接、视频流、配置管理
- CurvePanelHandler (curvepanel_handler.py): 曲线面板 - 曲线数据、导出
- MissionPanelHandler (missionpanel_handler.py): 任务面板 - 任务管理、分页
- ModelSettingHandler (modelsetting_handler.py): 模型设置对话框
"""

from .channelpanel_handler import ChannelPanelHandler
from .curvepanel_handler import CurvePanelHandler
from .missionpanel_handler import MissionPanelHandler
from .modelsetting_handler import ModelSettingHandler
from .general_set_handler import GeneralSetPanelHandler
from .historypanel_handler import HistoryPanelHandler  #  历史回放面板处理器

__all__ = [
    'ChannelPanelHandler',
    'CurvePanelHandler',
    'MissionPanelHandler',
    'ModelSettingHandler',
    'GeneralSetPanelHandler',
    'HistoryPanelHandler',  #  导出历史回放面板处理器
]

