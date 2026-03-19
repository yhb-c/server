# -*- coding: utf-8 -*-

"""
逻辑设置对话框组件

用于配置业务逻辑参数：
- 检测模式
- 报警设置
- 数据处理
- 通信设置
"""

from qtpy import QtWidgets, QtCore
from qtpy.QtCore import Qt

# 导入图标工具和响应式布局（支持相对导入和独立运行）
try:
    from ..style_manager import newIcon
    from ..responsive_layout import ResponsiveLayout, scale_w, scale_h
except (ImportError, ValueError):
    import sys
    import os.path as osp
    parent_dir = osp.dirname(osp.dirname(__file__))
    sys.path.insert(0, parent_dir)
    from style_manager import newIcon
    from responsive_layout import ResponsiveLayout, scale_w, scale_h


class LogicSettingDialog(QtWidgets.QDialog):
    """
    逻辑设置对话框
    
    用于配置业务逻辑参数（功能开发中）
    """
    
    def __init__(self, parent=None, logic_config=None, channel_id=None):
        """
        Args:
            parent: 父窗口
            logic_config: 逻辑配置字典
            channel_id: 通道ID（如 'channel1'），用于显示通道特定的逻辑配置
        """
        super(LogicSettingDialog, self).__init__(parent)
        self._logic_config = logic_config or {}
        self._channel_id = channel_id
        
        # 设置窗口标题（包含通道信息）
        title = "逻辑设置"
        if self._channel_id:
            title += f" - {self._channel_id}"
        self.setWindowTitle(title)
        self.setMinimumSize(scale_w(600), scale_h(550))  # 🔥 响应式尺寸
        
        self._initUI()
    
    def _initUI(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 添加垂直伸展
        layout.addStretch()
        
        # 提示信息
        info_label = QtWidgets.QLabel("业务逻辑功能开发中...")
        info_label.setStyleSheet("""
            QLabel {
                font-size: 18pt;
                font-weight: bold;
                color: #666666;
                padding: 20px;
            }
        """)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 详细说明
        detail_label = QtWidgets.QLabel("敬请期待")
        detail_label.setStyleSheet("""
            QLabel {
                font-size: 12pt;
                color: #999999;
                padding: 10px;
            }
        """)
        detail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(detail_label)
        
        # 添加垂直伸展
        layout.addStretch()
        
        # 按钮组
        buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
        )
        buttonBox.accepted.connect(self.accept)
        layout.addWidget(buttonBox)
        
        self.setLayout(layout)
    
    
    def getLogicConfig(self):
        """
        获取逻辑配置
        
        Returns:
            dict: 逻辑配置字典（当前返回空字典，功能开发中）
        """
        return {}


if __name__ == "__main__":
    """独立调试入口"""
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    test_config = {
        'detection_mode': 'continuous',
        'high_threshold': 80.0,
        'low_threshold': 20.0,
        'sound_alarm': True,
        'email_alarm': False,
        'sms_alarm': False,
        'enable_smooth': True,
        'smooth_window': 5,
        'save_interval': '10秒',
        'protocol': 'HTTP/REST',
        'comm_address': '192.168.1.100:8080',
    }
    
    dialog = LogicSettingDialog(logic_config=test_config, channel_id='channel1')
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        config = dialog.getLogicConfig()
    
    sys.exit(0)

