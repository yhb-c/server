# -*- coding: utf-8 -*-
"""
登录窗口 - 参考User Registration设计
"""

import logging
import sys
import os
from pathlib import Path
from qtpy import QtWidgets, QtCore, QtGui

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from network.api.auth_api import AuthAPI


class LoginWindow(QtWidgets.QWidget):
    """登录窗口"""
    
    def __init__(self, config):
        """
        初始化登录窗口
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        self._initUI()
        self._applyStyles()
    
    def _initUI(self):
        """初始化UI - 参考User Registration设计"""
        self.setWindowTitle('液位检测系统')
        self.setFixedSize(450, 350)
        
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 背景容器 (灰色背景)
        bg_widget = QtWidgets.QWidget()
        bg_widget.setStyleSheet('background-color: #f9fafb;')
        bg_layout = QtWidgets.QVBoxLayout(bg_widget)
        bg_layout.setContentsMargins(16, 16, 16, 16)
        
        # 卡片容器 (白色卡片)
        card_widget = QtWidgets.QWidget()
        card_widget.setStyleSheet('''
            QWidget {
                background-color: white;
                border-radius: 8px;
            }
        ''')
        card_layout = QtWidgets.QVBoxLayout(card_widget)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # 标题
        title = QtWidgets.QLabel('液位检测系统')
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet('font-size: 20px; font-weight: bold; color: #111827;')
        card_layout.addWidget(title)
        
        # 用户名输入
        username_layout = QtWidgets.QVBoxLayout()
        username_layout.setSpacing(8)
        
        username_label = QtWidgets.QLabel('用户名')
        username_label.setStyleSheet('font-size: 14px; font-weight: 500; color: #374151;')
        username_layout.addWidget(username_label)
        
        self.username_input = QtWidgets.QLineEdit()
        self.username_input.setPlaceholderText('请输入用户名')
        self.username_input.setText('user')  # 默认填充用户名
        self.username_input.setMinimumHeight(40)
        username_layout.addWidget(self.username_input)
        
        self.username_error = QtWidgets.QLabel()
        self.username_error.setStyleSheet('color: #dc2626; font-size: 12px;')
        self.username_error.hide()
        username_layout.addWidget(self.username_error)
        
        card_layout.addLayout(username_layout)
        
        # 密码输入
        password_layout = QtWidgets.QVBoxLayout()
        password_layout.setSpacing(8)
        
        password_label = QtWidgets.QLabel('密码')
        password_label.setStyleSheet('font-size: 14px; font-weight: 500; color: #374151;')
        password_layout.addWidget(password_label)
        
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setPlaceholderText('请输入密码(可为空)')
        self.password_input.setText('')  # 密码为空
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        password_layout.addWidget(self.password_input)
        
        self.password_error = QtWidgets.QLabel()
        self.password_error.setStyleSheet('color: #dc2626; font-size: 12px;')
        self.password_error.hide()
        password_layout.addWidget(self.password_error)
        
        card_layout.addLayout(password_layout)
        
        # 状态提示标签
        self.status_label = QtWidgets.QLabel()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet('font-size: 13px; padding: 8px;')
        self.status_label.hide()
        card_layout.addWidget(self.status_label)
        
        # 按钮布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(16)
        
        # 取消按钮
        self.cancel_button = QtWidgets.QPushButton('取消')
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self._onCancel)
        button_layout.addWidget(self.cancel_button)
        
        # 登录按钮
        self.login_button = QtWidgets.QPushButton('登录')
        self.login_button.setMinimumHeight(40)
        self.login_button.clicked.connect(self._onLogin)
        button_layout.addWidget(self.login_button)
        
        card_layout.addLayout(button_layout)
        
        # 添加卡片到背景
        bg_layout.addWidget(card_widget)
        main_layout.addWidget(bg_widget)
        
        # 回车键登录
        self.password_input.returnPressed.connect(self._onLogin)
    
    def _applyStyles(self):
        """应用样式"""
        # 输入框样式
        input_style = '''
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
                outline: none;
            }
        '''
        self.username_input.setStyleSheet(input_style)
        self.password_input.setStyleSheet(input_style)
        
        # 取消按钮样式 (outline)
        self.cancel_button.setStyleSheet('''
            QPushButton {
                background-color: white;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                color: #374151;
                font-size: 14px;
                font-weight: 500;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f9fafb;
            }
            QPushButton:pressed {
                background-color: #f3f4f6;
            }
        ''')
        
        # 登录按钮样式 (primary)
        self.login_button.setStyleSheet('''
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #93c5fd;
            }
        ''')
    
    def _validateForm(self):
        """验证表单"""
        is_valid = True
        
        # 验证用户名
        username = self.username_input.text().strip()
        if not username:
            self.username_error.setText('请输入用户名')
            self.username_error.show()
            is_valid = False
        else:
            self.username_error.hide()
        
        # 密码可以为空,不需要验证
        self.password_error.hide()
        
        return is_valid
    
    def _onLogin(self):
        """登录按钮点击"""
        # 验证表单
        if not self._validateForm():
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # 调用登录API
        api_url = self.config.get('server', {}).get('api_url', 'http://localhost:8084')
        auth_api = AuthAPI(api_url)
        
        # 显示加载状态
        self.login_button.setEnabled(False)
        self.login_button.setText('登录中...')
        self._showStatus('正在连接服务器...', 'info')
        
        result = auth_api.login(username, password)
        
        self.login_button.setEnabled(True)
        self.login_button.setText('登录')
        
        if result['success']:
            self.logger.info(f"登录成功: {username}")
            
            # 显示成功提示
            self._showStatus('登录成功！正在打开系统...', 'success')
            
            # 打开系统主窗口
            try:
                self.logger.info("准备导入SystemWindow...")
                from .system_window import SystemWindow
                self.logger.info("SystemWindow导入成功，准备创建窗口...")
                self.system_window = SystemWindow(self.config, auth_api, result.get('user', {}))
                self.logger.info("SystemWindow创建成功，准备显示...")
                self.system_window.show()
                self.close()
            except Exception as e:
                self.logger.error(f"打开系统窗口失败: {e}", exc_info=True)
                self._showStatus(f'打开系统窗口失败: {str(e)}', 'error')
        else:
            # 显示错误提示
            self._showStatus(result['message'], 'error')
    
    def _onCancel(self):
        """取消按钮点击"""
        # 清空输入
        self.username_input.clear()
        self.password_input.clear()
        self.username_error.hide()
        self.password_error.hide()
        self.status_label.hide()
    
    def _showStatus(self, message, status_type='info'):
        """
        在界面上显示状态消息
        
        Args:
            message: 消息内容
            status_type: 消息类型 (success, error, info)
        """
        self.status_label.setText(message)
        self.status_label.show()
        
        # 根据类型设置不同的样式
        if status_type == 'success':
            self.status_label.setStyleSheet('''
                font-size: 13px; 
                padding: 8px;
                color: #059669;
                background-color: #d1fae5;
                border-radius: 4px;
            ''')
        elif status_type == 'error':
            self.status_label.setStyleSheet('''
                font-size: 13px; 
                padding: 8px;
                color: #dc2626;
                background-color: #fee2e2;
                border-radius: 4px;
            ''')
        else:  # info
            self.status_label.setStyleSheet('''
                font-size: 13px; 
                padding: 8px;
                color: #2563eb;
                background-color: #dbeafe;
                border-radius: 4px;
            ''')
