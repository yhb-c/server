# flake8: noqa

from .menubar import MenuBar

# UI界面模块
from .login import LoginWindow
from .system_window import SystemWindow

# 视频页面组件（从 videopage 子模块导入）
from .videopage import (
    ChannelPanel,
    CurvePanel,
    MissionPanel,
    ModelSettingDialog,
)

# 数据集页面组件（从 datasetpage 子模块导入）
from .datasetpage import (
    DataCollectionPanel,
    DataPreprocessPanel,
    AnnotationTool,
    CropConfigDialog,
)

# 模型页面组件（从 modelpage 子模块导入）
from .modelpage import (
    ModelSetPage,
    TrainingPage,
)



from .datasetpage.videobrowser import VideoBrowser

from .datasetpage.videoclipper import VideoClipper

from .style_manager import newIcon

