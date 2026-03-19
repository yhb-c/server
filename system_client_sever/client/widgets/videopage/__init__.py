# flake8: noqa

"""
视频页面相关组件

包含视频监控页面所需的所有专用组件
"""

from .channelpanel import ChannelPanel
from .curvepanel import CurvePanel
from .missionpanel import MissionPanel
from .modelsetting_dialogue import ModelSettingDialog
from .historyvideopanel import HistoryVideoPanel


from .general_set import GeneralSetPanel, GeneralSetDialog

__all__ = [
    'ChannelPanel',
    'CurvePanel',
    'MissionPanel',
    'ModelSettingDialog',
    'HistoryVideoPanel',
    'RtspDialog',
    'GeneralSetPanel',
    'GeneralSetDialog',
]

