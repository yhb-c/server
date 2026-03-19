# -*- coding: utf-8 -*-

"""
响应式布局管理器
根据屏幕分辨率自动调整UI尺寸
"""

from qtpy import QtWidgets, QtCore


class ResponsiveLayout:
    """响应式布局管理器 - 根据屏幕分辨率自动计算尺寸"""
    
    # 基准分辨率 (1920x1080)
    BASE_WIDTH = 1920
    BASE_HEIGHT = 1080
    
    # 缩放因子限制（避免极端缩放）
    MIN_SCALE_FACTOR = 0.5  # 最小50%
    MAX_SCALE_FACTOR = 2.0  # 最大200%
    
    # 当前屏幕信息
    _screen_width = None
    _screen_height = None
    _scale_factor_w = 1.0
    _scale_factor_h = 1.0
    _scale_factor = 1.0  # 统一缩放因子
    
    @classmethod
    def initialize(cls, app=None):
        """
        初始化响应式布局系统
        
        Args:
            app: QApplication实例,如果为None则自动获取
        """
        if app is None:
            app = QtWidgets.QApplication.instance()
        
        if app is None:
            return
        
        # 获取主屏幕
        screen = app.primaryScreen()
        if screen is None:
            return
        
        # 获取屏幕几何信息
        geometry = screen.geometry()
        cls._screen_width = geometry.width()
        cls._screen_height = geometry.height()
        
        # 计算缩放因子
        raw_scale_w = cls._screen_width / cls.BASE_WIDTH
        raw_scale_h = cls._screen_height / cls.BASE_HEIGHT
        
        # 使用较小的缩放因子，保持宽高比一致性
        raw_scale = min(raw_scale_w, raw_scale_h)
        
        # 限制缩放因子范围
        cls._scale_factor = max(cls.MIN_SCALE_FACTOR, min(cls.MAX_SCALE_FACTOR, raw_scale))
        cls._scale_factor_w = cls._scale_factor
        cls._scale_factor_h = cls._scale_factor
    
    @classmethod
    def scale_width(cls, base_width):
        """
        根据屏幕宽度缩放
        
        Args:
            base_width: 基准宽度(1920分辨率下的像素值)
        
        Returns:
            缩放后的宽度
        """
        return int(base_width * cls._scale_factor_w)
    
    @classmethod
    def scale_height(cls, base_height):
        """
        根据屏幕高度缩放
        
        Args:
            base_height: 基准高度(1080分辨率下的像素值)
        
        Returns:
            缩放后的高度
        """
        return int(base_height * cls._scale_factor_h)
    
    @classmethod
    def scale_size(cls, base_width, base_height):
        """
        同时缩放宽度和高度
        
        Args:
            base_width: 基准宽度
            base_height: 基准高度
        
        Returns:
            (缩放后的宽度, 缩放后的高度)
        """
        return cls.scale_width(base_width), cls.scale_height(base_height)
    
    @classmethod
    def get_scale_factor(cls):
        """
        获取统一缩放因子
        
        Returns:
            统一缩放因子
        """
        return cls._scale_factor
    
    @classmethod
    def scale_spacing(cls, base_spacing):
        """
        缩放布局间距
        
        Args:
            base_spacing: 基准间距
        
        Returns:
            缩放后的间距
        """
        return int(base_spacing * cls._scale_factor)
    
    @classmethod
    def scale_margin(cls, base_margin):
        """
        缩放边距
        
        Args:
            base_margin: 基准边距
        
        Returns:
            缩放后的边距
        """
        return int(base_margin * cls._scale_factor)
    
    @classmethod
    def scale_font_size(cls, base_font_size):
        """
        缩放字体大小
        
        Args:
            base_font_size: 基准字体大小(pt)
        
        Returns:
            缩放后的字体大小
        """
        return int(base_font_size * cls._scale_factor)
    
    @classmethod
    def apply_to_widget(cls, widget, base_width=None, base_height=None, 
                       min_width=None, max_width=None, 
                       min_height=None, max_height=None):
        """
        为控件应用响应式尺寸
        
        Args:
            widget: Qt控件
            base_width: 基准宽度(如果设置,将应用setMinimumWidth)
            base_height: 基准高度(如果设置,将应用setMinimumHeight)
            min_width: 基准最小宽度
            max_width: 基准最大宽度
            min_height: 基准最小高度
            max_height: 基准最大高度
        """
        if min_width is not None:
            widget.setMinimumWidth(cls.scale_width(min_width))
        
        if max_width is not None:
            widget.setMaximumWidth(cls.scale_width(max_width))
        
        if min_height is not None:
            widget.setMinimumHeight(cls.scale_height(min_height))
        
        if max_height is not None:
            widget.setMaximumHeight(cls.scale_height(max_height))
        
        if base_width is not None and min_width is None:
            widget.setMinimumWidth(cls.scale_width(base_width))
        
        if base_height is not None and min_height is None:
            widget.setMinimumHeight(cls.scale_height(base_height))
    
    @classmethod
    def apply_to_layout(cls, layout, base_spacing=None, base_margins=None):
        """
        为布局应用响应式间距和边距
        
        Args:
            layout: Qt布局对象
            base_spacing: 基准间距(如果为None则不修改)
            base_margins: 基准边距,可以是:
                - 单个数字: 四周相同边距
                - 元组(left, top, right, bottom): 分别设置四个边距
        """
        if base_spacing is not None:
            layout.setSpacing(cls.scale_spacing(base_spacing))
        
        if base_margins is not None:
            if isinstance(base_margins, (int, float)):
                # 四周相同边距
                margin = cls.scale_margin(base_margins)
                layout.setContentsMargins(margin, margin, margin, margin)
            elif isinstance(base_margins, (tuple, list)) and len(base_margins) == 4:
                # 分别设置四个边距
                margins = [cls.scale_margin(m) for m in base_margins]
                layout.setContentsMargins(*margins)
    
    @classmethod
    def get_screen_info(cls):
        """
        获取屏幕信息
        
        Returns:
            字典包含屏幕宽度、高度和缩放因子
        """
        return {
            'width': cls._screen_width,
            'height': cls._screen_height,
            'scale_w': cls._scale_factor_w,
            'scale_h': cls._scale_factor_h,
            'scale': cls._scale_factor,
            'base_width': cls.BASE_WIDTH,
            'base_height': cls.BASE_HEIGHT
        }


# 便捷函数
def scale_w(base_width):
    """缩放宽度的快捷函数"""
    return ResponsiveLayout.scale_width(base_width)


def scale_h(base_height):
    """缩放高度的快捷函数"""
    return ResponsiveLayout.scale_height(base_height)


def scale_size(base_width, base_height):
    """缩放尺寸的快捷函数"""
    return ResponsiveLayout.scale_size(base_width, base_height)


def scale_spacing(base_spacing):
    """缩放间距的快捷函数"""
    return ResponsiveLayout.scale_spacing(base_spacing)


def scale_margin(base_margin):
    """缩放边距的快捷函数"""
    return ResponsiveLayout.scale_margin(base_margin)


def scale_font(base_font_size):
    """缩放字体的快捷函数"""
    return ResponsiveLayout.scale_font_size(base_font_size)


def get_scale():
    """获取当前缩放因子的快捷函数"""
    return ResponsiveLayout.get_scale_factor()
