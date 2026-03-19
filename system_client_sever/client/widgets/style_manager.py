# -*- coding: utf-8 -*-

"""
统一样式管理器
整合字体管理器、对话框管理器和按钮样式管理器

包含三个主要管理器：
1. FontManager - 字体管理器
2. DialogManager - 对话框管理器  
3. ButtonStyleManager - 按钮样式管理器

对话框文本对齐方式使用示例：
-----------------------------
from widgets.style_manager import DialogManager

# 1. 左对齐（默认，适用于多行列表或详细说明）
DialogManager.show_warning(
    self, "警告", 
    "请检查以下问题：\n1. 相机是否开机\n2. 网络是否连接\n3. IP地址是否正确"
    # text_alignment=DialogManager.ALIGN_LEFT  # 默认值，可省略
)

# 2. 居中对齐（适用于简短消息）
DialogManager.show_information(
    self, "提示", 
    "操作成功完成",
    text_alignment=DialogManager.ALIGN_CENTER
)

# 3. 右对齐（较少使用，特殊场景）
DialogManager.show_critical(
    self, "错误", 
    "系统错误\n错误代码: 500",
    text_alignment=DialogManager.ALIGN_RIGHT
)
"""

import os
import os.path as osp
import sys

try:
    from qtpy import QtGui, QtWidgets, QtCore
except ImportError as e:
    raise

try:
    from qtpy import QtCore as QtCore_qtpy
except ImportError as e:
    raise


# ============================================================================
# 字体管理器 (Font Manager)
# ============================================================================

class FontManager:
    """全局字体管理器"""
    
    # 默认字体配置
    DEFAULT_FONT_FAMILY = 'Microsoft YaHei'
    DEFAULT_FONT_SIZE = 12
    DEFAULT_FONT_WEIGHT = 50  # Normal
    
    # 预定义字体大小
    FONT_SIZE_SMALL = 10
    FONT_SIZE_MEDIUM = 12
    FONT_SIZE_LARGE = 14
    FONT_SIZE_TITLE = 16
    
    # 预定义字体粗细
    WEIGHT_LIGHT = 25
    WEIGHT_NORMAL = 50
    WEIGHT_DEMIBOLD = 63
    WEIGHT_BOLD = 75
    WEIGHT_BLACK = 87
    
    @staticmethod
    def getDefaultFont():
        """获取默认字体"""
        return FontManager.getFont(
            size=FontManager.DEFAULT_FONT_SIZE,
            weight=FontManager.DEFAULT_FONT_WEIGHT,
            family=FontManager.DEFAULT_FONT_FAMILY
        )
    
    @staticmethod
    def getFont(size=None, weight=None, italic=False, underline=False, family=None):
        """获取自定义字体"""
        if family is None:
            family = FontManager.DEFAULT_FONT_FAMILY
        if size is None:
            size = FontManager.DEFAULT_FONT_SIZE
        if weight is None:
            weight = FontManager.DEFAULT_FONT_WEIGHT
            
        font = QtGui.QFont(family, size)
        
        # PySide6兼容性：将整数权重转换为QFont.Weight枚举
        try:
            # 尝试使用PySide6的Weight枚举
            if hasattr(QtGui.QFont, 'Weight'):
                if weight <= 25:
                    font.setWeight(QtGui.QFont.Weight.Light)
                elif weight <= 50:
                    font.setWeight(QtGui.QFont.Weight.Normal)
                elif weight <= 63:
                    font.setWeight(QtGui.QFont.Weight.DemiBold)
                elif weight <= 75:
                    font.setWeight(QtGui.QFont.Weight.Bold)
                else:
                    font.setWeight(QtGui.QFont.Weight.Black)
            else:
                # 回退到旧的整数方式（PyQt5）
                font.setWeight(weight)
        except (AttributeError, TypeError):
            # 如果出现任何错误，使用默认权重
            try:
                font.setWeight(QtGui.QFont.Weight.Normal)
            except:
                pass
                
        font.setItalic(italic)
        font.setUnderline(underline)
        return font
    
    @staticmethod
    def getSmallFont():
        """获取小字体 (10pt)"""
        return FontManager.getFont(size=FontManager.FONT_SIZE_SMALL)
    
    @staticmethod
    def getMediumFont():
        """获取中字体 (12pt)"""
        return FontManager.getFont(size=FontManager.FONT_SIZE_MEDIUM)
    
    @staticmethod
    def getLargeFont():
        """获取大字体 (14pt)"""
        return FontManager.getFont(size=FontManager.FONT_SIZE_LARGE)
    
    @staticmethod
    def getTitleFont():
        """获取标题字体 (16pt, DemiBold)"""
        return FontManager.getFont(
            size=FontManager.FONT_SIZE_TITLE,
            weight=FontManager.WEIGHT_DEMIBOLD
        )
    
    @staticmethod
    def getBoldFont(size=None):
        """获取粗体字体"""
        return FontManager.getFont(
            size=size if size else FontManager.DEFAULT_FONT_SIZE,
            weight=FontManager.WEIGHT_BOLD
        )
    
    @staticmethod
    def applyToWidget(widget, size=None, weight=None, italic=False, underline=False):
        """应用字体到控件"""
        widget_type = type(widget).__name__
        widget_text = getattr(widget, 'text', lambda: 'N/A')()
        old_font = widget.font()
        
        font = FontManager.getFont(size, weight, italic, underline)
        
        # 只在字体真正不同时才设置，避免重复设置
        if (old_font.family() != font.family() or 
            old_font.pointSize() != font.pointSize() or 
            old_font.weight() != font.weight() or
            old_font.italic() != font.italic() or
            old_font.underline() != font.underline()):
            
            widget.setFont(font)
            
            new_font = widget.font()
        else:
            pass
    
    @staticmethod
    def applyToApplication(app):
        """应用默认字体到整个应用程序"""
        try:
            # 确保使用当前 Qt 后端创建字体对象
            from qtpy import QtGui
            font = QtGui.QFont(
                FontManager.DEFAULT_FONT_FAMILY,
                FontManager.DEFAULT_FONT_SIZE
            )
            font.setWeight(FontManager.DEFAULT_FONT_WEIGHT)
            app.setFont(font)
        except Exception as e:
            print(f"字体设置失败，使用默认字体: {e}")
    
    @staticmethod
    def applyToWidgetRecursive(widget, size=None, weight=None):
        """递归应用字体到控件及其所有子控件"""
        # 应用字体到当前控件
        FontManager.applyToWidget(widget, size, weight)
        
        # 递归应用到所有子控件
        children = widget.findChildren(QtWidgets.QWidget)
        
        for child in children:
            child_type = type(child).__name__
            child_text = getattr(child, 'text', lambda: 'N/A')()
            FontManager.applyToWidget(child, size, weight)
    
    @staticmethod
    def setDefaultFontConfig(family=None, size=None, weight=None):
        """设置默认字体配置"""
        if family is not None:
            FontManager.DEFAULT_FONT_FAMILY = family
        if size is not None:
            FontManager.DEFAULT_FONT_SIZE = size
        if weight is not None:
            FontManager.DEFAULT_FONT_WEIGHT = weight
    
    @staticmethod
    def applyToDialog(dialog):
        """专门为对话框和页面应用字体管理器"""
        try:
            # 应用到对话框本身
            FontManager.applyToWidget(dialog)
            
            # 递归应用到所有子控件
            FontManager.applyToWidgetRecursive(dialog)
            
        except Exception as e:
            pass


# 字体管理器便捷函数
def applyDefaultFont(widget):
    """应用默认字体到控件"""
    FontManager.applyToWidget(widget)

def applySmallFont(widget):
    """应用小字体到控件"""
    widget.setFont(FontManager.getSmallFont())

def applyMediumFont(widget):
    """应用中字体到控件"""
    widget.setFont(FontManager.getMediumFont())

def applyLargeFont(widget):
    """应用大字体到控件"""
    widget.setFont(FontManager.getLargeFont())

def applyTitleFont(widget):
    """应用标题字体到控件"""
    widget.setFont(FontManager.getTitleFont())

def applyBoldFont(widget, size=None):
    """应用粗体字体到控件"""
    widget.setFont(FontManager.getBoldFont(size))

def applyDialogFont(dialog):
    """应用字体到对话框或页面的便捷函数"""
    FontManager.applyToDialog(dialog)


# ============================================================================
# 对话框管理器 (Dialog Manager)
# ============================================================================

class DialogManager:
    """全局对话框管理器"""
    
    # 默认样式（使用Qt5默认按钮样式）
    # 🔥 移除了font-size设置，改用FontManager统一管理字体
    # 🔥 移除了固定高度限制，改为根据内容自适应
    # 🔥 移除了固定对齐方式，改为通过参数动态设置
    DEFAULT_STYLE = """
        QMessageBox {
            min-width: 400px;
        }
        QMessageBox QLabel {
            border: none;
            background: transparent;
        }
    """
    
    # 文本对齐方式常量
    ALIGN_LEFT = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
    ALIGN_CENTER = QtCore.Qt.AlignCenter
    ALIGN_RIGHT = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
    
    @staticmethod
    def _create_base_dialog(parent, title, message, icon_type, text_alignment=None):
        """创建基础对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            message: 消息文本
            icon_type: 图标类型
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认为左对齐
        """
        msg_box = QtWidgets.QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)  # 不显示内容区域图标
        
        # 设置左上角图标
        if icon_type:
            msg_box.setWindowIcon(
                msg_box.style().standardIcon(icon_type)
            )
        
        # 移除帮助按钮
        msg_box.setWindowFlags(
            msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        # 应用统一样式（使用Qt5默认按钮样式）
        msg_box.setStyleSheet(DialogManager.DEFAULT_STYLE)
        
        # 🔥 应用全局字体管理器到对话框及其所有子控件
        FontManager.applyToWidgetRecursive(msg_box)
        
        # 🔥 设置文本对齐方式（默认左对齐）
        if text_alignment is None:
            text_alignment = DialogManager.ALIGN_LEFT
        DialogManager._set_text_alignment(msg_box, text_alignment)
        
        # 🔥 根据文本内容自动调整对话框大小
        DialogManager._adjust_dialog_size(msg_box, message)
        
        # 🔥 应用统一按钮样式到对话框的所有按钮
        DialogManager._apply_button_styles(msg_box)
        
        return msg_box
    
    @staticmethod
    def _set_text_alignment(msg_box, alignment):
        """设置对话框文本对齐方式
        
        Args:
            msg_box: QMessageBox对象
            alignment: Qt对齐方式（Qt.AlignLeft, Qt.AlignCenter, Qt.AlignRight）
        """
        try:
            # 查找对话框中的QLabel（消息文本标签）
            for label in msg_box.findChildren(QtWidgets.QLabel):
                # 只设置消息文本标签的对齐方式，不影响其他标签
                if label.text() and not label.pixmap():
                    label.setAlignment(alignment)
                    # 移除任何边框样式
                    label.setFrameStyle(QtWidgets.QFrame.NoFrame)
                    label.setStyleSheet("border: none; background: transparent;")
        except Exception as e:
            pass
    
    @staticmethod
    def _adjust_dialog_size(msg_box, message):
        """根据文本内容自动调整对话框大小
        
        Args:
            msg_box: QMessageBox对象
            message: 消息文本
        """
        try:
            # 计算文本行数
            lines = message.split('\n')
            line_count = len(lines)
            
            # 计算最长行的字符数（考虑HTML标签）
            import re
            max_chars = 0
            for line in lines:
                # 移除HTML标签来计算实际字符数
                clean_line = re.sub(r'<[^>]+>', '', line)
                max_chars = max(max_chars, len(clean_line))
            
            # 根据行数和字符数动态计算宽度和高度
            # 基础宽度400px，每个字符约12px
            base_width = 400
            char_width = 12
            calculated_width = max(base_width, min(max_chars * char_width + 100, 800))
            
            # 基础高度150px，每行约30px
            base_height = 150
            line_height = 30
            calculated_height = base_height + (line_count * line_height)
            
            # 设置最小尺寸（让对话框至少有这么大）
            msg_box.setMinimumSize(calculated_width, calculated_height)
            
        except Exception as e:
            # 如果计算失败，使用默认尺寸
            pass
    
    @staticmethod
    def _apply_button_styles(msg_box):
        """应用统一按钮样式到对话框的所有按钮
        
        Args:
            msg_box: QMessageBox对象
        """
        try:
            # 查找对话框中的所有QPushButton
            buttons = msg_box.findChildren(QtWidgets.QPushButton)
            
            for button in buttons:
                # 应用TextButtonStyleManager样式
                TextButtonStyleManager.applyToButton(button)
                
        except Exception as e:
            pass
    
    @staticmethod
    def _set_chinese_button_texts(msg_box, button_texts=None):
        """设置按钮为中文文本"""
        # 默认中文按钮文本映射
        default_texts = {
            QtWidgets.QMessageBox.Ok: "确定",
            QtWidgets.QMessageBox.Cancel: "取消",
            QtWidgets.QMessageBox.Yes: "是",
            QtWidgets.QMessageBox.No: "否",
            QtWidgets.QMessageBox.Apply: "应用",
            QtWidgets.QMessageBox.Reset: "重置",
            QtWidgets.QMessageBox.Close: "关闭",
            QtWidgets.QMessageBox.Save: "保存",
            QtWidgets.QMessageBox.Discard: "丢弃",
            QtWidgets.QMessageBox.Open: "打开",
            QtWidgets.QMessageBox.Retry: "重试",
            QtWidgets.QMessageBox.Ignore: "忽略",
            QtWidgets.QMessageBox.Abort: "中止"
        }
        
        # 使用自定义文本或默认中文文本
        texts_to_use = button_texts if button_texts else default_texts
        
        # 设置按钮文本
        for button_type, text in texts_to_use.items():
            btn = msg_box.button(button_type)
            if btn:
                btn.setText(text)
    
    @staticmethod
    def show_warning(parent, title, message, text_alignment=None):
        """显示警告对话框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message, 
            QtWidgets.QStyle.SP_MessageBoxCritical,
            text_alignment
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        DialogManager._set_chinese_button_texts(msg_box)
        # 🔥 确保OK按钮文本为"确定"
        ok_btn = msg_box.button(QtWidgets.QMessageBox.Ok)
        if ok_btn:
            ok_btn.setText("确定")
        msg_box.exec_()
    
    @staticmethod
    def show_information(parent, title, message, text_alignment=None):
        """显示信息对话框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxInformation,
            text_alignment
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        DialogManager._set_chinese_button_texts(msg_box)
        # 🔥 确保OK按钮文本为"确定"
        ok_btn = msg_box.button(QtWidgets.QMessageBox.Ok)
        if ok_btn:
            ok_btn.setText("确定")
        msg_box.exec_()
    
    @staticmethod
    def show_critical(parent, title, message, text_alignment=None):
        """显示错误对话框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxCritical,
            text_alignment
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        DialogManager._set_chinese_button_texts(msg_box)
        # 🔥 确保OK按钮文本为"确定"
        ok_btn = msg_box.button(QtWidgets.QMessageBox.Ok)
        if ok_btn:
            ok_btn.setText("确定")
        msg_box.exec_()
    
    @staticmethod
    def show_question(parent, title, message, yes_text="是", no_text="否", text_alignment=None):
        """显示询问对话框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            yes_text: "是"按钮文本
            no_text: "否"按钮文本
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxQuestion,
            text_alignment
        )
        
        # 设置按钮
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        # 设置中文按钮文本
        button_texts = {
            QtWidgets.QMessageBox.Yes: yes_text,
            QtWidgets.QMessageBox.No: no_text
        }
        DialogManager._set_chinese_button_texts(msg_box, button_texts)
        
        result = msg_box.exec_()
        return result == QtWidgets.QMessageBox.Yes
    
    @staticmethod
    def show_question_warning(parent, title, message, yes_text="是", no_text="否", text_alignment=None):
        """显示警告询问对话框（用于删除确认等危险操作）
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            yes_text: "是"按钮文本
            no_text: "否"按钮文本
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxWarning,
            text_alignment
        )
        
        # 设置按钮
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        # 设置中文按钮文本
        button_texts = {
            QtWidgets.QMessageBox.Yes: yes_text,
            QtWidgets.QMessageBox.No: no_text
        }
        DialogManager._set_chinese_button_texts(msg_box, button_texts)
        
        result = msg_box.exec_()
        return result == QtWidgets.QMessageBox.Yes
    
    @staticmethod
    def show_custom(parent, title, message, icon_type=None, buttons=None, button_texts=None, default_button=None, text_alignment=None):
        """显示自定义对话框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息文本
            icon_type: 图标类型
            buttons: 按钮组合
            button_texts: 按钮文本字典
            default_button: 默认按钮
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(parent, title, message, icon_type, text_alignment)
        
        # 设置按钮
        if buttons:
            msg_box.setStandardButtons(buttons)
            if default_button:
                msg_box.setDefaultButton(default_button)
        else:
            # 默认使用确定按钮
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        
        # 设置中文按钮文本
        DialogManager._set_chinese_button_texts(msg_box, button_texts)
        
        return msg_box.exec_()
    
    @staticmethod
    def show_about(parent, title, message, text_alignment=None):
        """显示关于对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            message: 关于信息（支持HTML格式）
            text_alignment: 文本对齐方式（ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT），默认左对齐
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxInformation,
            text_alignment
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        DialogManager._set_chinese_button_texts(msg_box)
        # 确保OK按钮文本为"确定"
        ok_btn = msg_box.button(QtWidgets.QMessageBox.Ok)
        if ok_btn:
            ok_btn.setText("确定")
        
        # 设置文本格式为富文本（支持HTML）
        msg_box.setTextFormat(QtCore.Qt.RichText)
        
        msg_box.exec_()
    
    @staticmethod
    def show_information_with_details(parent, title, message, detail_info="", custom_buttons=None):
        """显示带详细信息和自定义按钮的信息对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            message: 主要消息文本
            detail_info: 详细信息文本
            custom_buttons: 自定义按钮列表，格式为 [(按钮文本, 按钮角色), ...]
                          例如: [("打开文件夹", QtWidgets.QMessageBox.ActionRole)]
        
        Returns:
            str: 被点击的按钮文本，如果是标准按钮则返回None
        """
        msg_box = DialogManager._create_base_dialog(
            parent, title, message,
            QtWidgets.QStyle.SP_MessageBoxInformation
        )
        
        # 设置详细信息
        if detail_info:
            msg_box.setInformativeText(detail_info)
        
        # 添加自定义按钮
        custom_button_widgets = {}
        if custom_buttons:
            for button_text, button_role in custom_buttons:
                btn = msg_box.addButton(button_text, button_role)
                custom_button_widgets[btn] = button_text
        
        # 添加标准"确定"按钮
        ok_btn = msg_box.addButton("确定", QtWidgets.QMessageBox.AcceptRole)
        
        # 执行对话框
        msg_box.exec_()
        
        # 获取被点击的按钮
        clicked_button = msg_box.clickedButton()
        
        # 如果是自定义按钮，返回按钮文本
        if clicked_button in custom_button_widgets:
            return custom_button_widgets[clicked_button]
        
        return None
    
    @staticmethod
    def create_progress_dialog(parent, title, label_text, icon_name=None, cancelable=True):
        """创建进度对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            label_text: 进度标签文本
            icon_name: 图标名称（从icons目录加载），如"裁剪"、"动态曲线"等
            cancelable: 是否显示取消按钮
        
        Returns:
            QProgressDialog: 配置好的进度对话框
        """
        # 创建进度对话框
        cancel_text = "取消" if cancelable else None
        progress_dialog = QtWidgets.QProgressDialog(
            label_text, cancel_text, 0, 100, parent
        )
        
        # 设置标题
        progress_dialog.setWindowTitle(title)
        
        # 设置模态
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        
        # 立即显示
        progress_dialog.setMinimumDuration(0)
        
        # 设置初始值
        progress_dialog.setValue(0)
        
        # 🔥 移除帮助按钮
        progress_dialog.setWindowFlags(
            progress_dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )
        
        # 🔥 设置左上角图标（使用icons目录中的图标）
        if icon_name:
            icon = newIcon(icon_name)
            if not icon.isNull():
                progress_dialog.setWindowIcon(icon)
        
        # 如果不可取消，移除取消按钮
        if not cancelable:
            progress_dialog.setCancelButton(None)
        
        # 🔥 应用全局字体管理器
        FontManager.applyToWidgetRecursive(progress_dialog)
        
        return progress_dialog
    
    @staticmethod
    def set_default_style(style_sheet):
        """设置默认样式"""
        DialogManager.DEFAULT_STYLE = style_sheet
    
    @staticmethod
    def applyButtonStylesToDialog(dialog):
        """应用统一按钮样式到对话框的所有按钮
        
        Args:
            dialog: QDialog或QInputDialog对象
        """
        try:
            # 查找对话框中的所有QPushButton
            buttons = dialog.findChildren(QtWidgets.QPushButton)
            
            for button in buttons:
                # 应用TextButtonStyleManager样式
                from widgets.style_manager import TextButtonStyleManager
                TextButtonStyleManager.applyToButton(button)
                
        except Exception as e:
            pass


# 对话框管理器便捷函数
def show_warning(parent, title, message):
    """显示警告对话框（中文按钮）"""
    return DialogManager.show_warning(parent, title, message)

def show_information(parent, title, message):
    """显示信息对话框（中文按钮）"""
    return DialogManager.show_information(parent, title, message)

def show_critical(parent, title, message):
    """显示错误对话框（中文按钮）"""
    return DialogManager.show_critical(parent, title, message)

def show_question(parent, title, message, yes_text="是", no_text="否"):
    """显示询问对话框（中文按钮）"""
    return DialogManager.show_question(parent, title, message, yes_text, no_text)

def show_question_warning(parent, title, message, yes_text="是", no_text="否"):
    """显示警告询问对话框（中文按钮）"""
    return DialogManager.show_question_warning(parent, title, message, yes_text, no_text)

def show_about(parent, title, message):
    """显示关于对话框（中文按钮）"""
    return DialogManager.show_about(parent, title, message)


# ============================================================================
# 按钮样式管理器 (Button Style Manager)
# ============================================================================

def get_project_root():
    """动态获取项目根目录"""
    # 从当前文件位置开始向上查找
    current_dir = osp.dirname(osp.abspath(__file__))
    
    # 标志性文件列表（用于识别项目根目录）
    # 客户端项目的标志文件
    marker_files = ['run_client.bat', 'requirements.txt', 'README.md', 'build_client.py']
    
    # 最多向上查找5层
    for i in range(5):
        # 检查当前目录是否包含标志性文件
        for marker in marker_files:
            marker_path = osp.join(current_dir, marker)
            if osp.exists(marker_path):
                return current_dir
        
        # 向上移动一层
        parent_dir = osp.dirname(current_dir)
        if parent_dir == current_dir:  # 已到达根目录
            break
        current_dir = parent_dir
    
    # 如果找不到，返回当前文件的上级目录作为后备方案
    fallback = osp.dirname(osp.dirname(osp.abspath(__file__)))
    return fallback

def get_icons_dir():
    """获取图标目录的绝对路径，兼容开发环境和PyInstaller打包后的环境"""
    # PyInstaller创建临时文件夹，并把路径存储在_MEIPASS中
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe运行
        base_path = sys._MEIPASS
        icons_path = osp.join(base_path, 'icons')
        return icons_path
    else:
        # 如果是开发环境运行，基于项目根目录动态构建路径
        project_root = get_project_root()
        icons_path = osp.join(project_root, 'client', 'icons')
        return icons_path

# 向后兼容：保留 here 变量
here = osp.dirname(osp.abspath(__file__))

def newIcon(icon):
    """创建图标对象"""
    icons_dir = get_icons_dir()
    
    # 尝试不同的图片格式
    for ext in ['.png', '.svg', '.ico']:
        icon_path = osp.join(icons_dir, f"{icon}{ext}")
        if osp.exists(icon_path):
            return QtGui.QIcon(icon_path)
    
    # 如果找不到图标文件，返回空图标（避免程序崩溃）
    return QtGui.QIcon()

def newButton(text, icon=None, slot=None):
    """创建带图标的按钮"""
    b = QtWidgets.QPushButton(text)
    if icon is not None:
        b.setIcon(newIcon(icon))
    if slot is not None:
        b.clicked.connect(slot)
    return b

def newAction(parent, text, slot=None, shortcut=None, icon=None, tip=None, 
              checkable=False, enabled=True, checked=False):
    """创建新的动作（用于菜单项和工具栏按钮）"""
    a = QtWidgets.QAction(text, parent)
    
    if icon is not None:
        a.setIconText(text.replace(" ", "\n"))
        a.setIcon(newIcon(icon))
    
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    
    if tip is not None:
        a.setToolTip(tip)
        a.setStatusTip(tip)
    
    if slot is not None:
        a.triggered.connect(slot)
    
    if checkable:
        a.setCheckable(True)
    
    a.setEnabled(enabled)
    a.setChecked(checked)
    
    return a

def addActions(widget, actions):
    """批量添加动作到部件（菜单或工具栏）"""
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QtWidgets.QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)

class TextButtonStyleManager:
    """全局文本按钮样式管理器"""
    
    # 按钮大小配置
    BASE_WIDTH = 60      # 基础宽度
    BASE_HEIGHT = 30     # 固定高度
    CHAR_WIDTH = 12      # 每个字符的平均宽度（像素）
    MIN_PADDING = 20     # 最小内边距（左右各10像素）
    
    @classmethod
    def calculateButtonWidth(cls, text):
        """根据文本长度计算按钮宽度"""
        if not text:
            return cls.BASE_WIDTH
        
        # 计算文本宽度：字符数 * 每字符宽度 + 内边距
        text_width = len(text) * cls.CHAR_WIDTH + cls.MIN_PADDING
        

        return max(cls.BASE_WIDTH, text_width)
    
    @classmethod
    def applyToButton(cls, button, text=None):
        """应用标准样式到文本按钮"""
        if text is None:
            text = button.text()
        
        # 计算并设置按钮大小
        width = cls.calculateButtonWidth(text)
        button.setFixedSize(width, cls.BASE_HEIGHT)
        
        # 清除任何自定义样式表，使用Qt默认样式
        button.setStyleSheet("")
        
        # 设置文本对齐方式
        button.setDefault(False)
        button.setAutoDefault(False)
    
    @classmethod
    def createStandardButton(cls, text, parent=None, slot=None):
        """创建标准样式的文本按钮"""
        # 修复 PySide6 兼容性问题 - 分步创建
        try:
            button = QtWidgets.QPushButton(text)
            if parent is not None:
                button.setParent(parent)
        except Exception as e:
            print(f"按钮创建失败: {e}")
            button = QtWidgets.QPushButton("按钮")
        
        # 应用标准样式
        cls.applyToButton(button, text)
        
        # 连接槽函数
        if slot is not None:
            button.clicked.connect(slot)
        
        return button
    
    @classmethod
    def updateButtonText(cls, button, new_text):
        """更新按钮文本并重新调整大小"""
        button.setText(new_text)
        cls.applyToButton(button, new_text)
    
    @classmethod
    def applyDangerStyle(cls, button):
        """应用危险按钮样式（红色）"""
        button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
    
    @classmethod
    def applyStandardStyle(cls, button):
        """应用标准按钮样式"""
        # 重新应用标准样式
        cls.applyToButton(button)
    
    @classmethod
    def createSuccessButton(cls, text, parent=None, slot=None):
        """创建成功样式按钮（绿色）"""
        button = cls.createStandardButton(text, parent, slot)
        width = cls.calculateButtonWidth(text)
        button.setFixedSize(width, cls.BASE_HEIGHT)
        button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        return button
    
    @classmethod
    def createPrimaryButton(cls, text, parent=None, slot=None):
        """创建主要样式按钮（蓝色）"""
        button = cls.createStandardButton(text, parent, slot)
        width = cls.calculateButtonWidth(text)
        button.setFixedSize(width, cls.BASE_HEIGHT)
        button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
            QPushButton:pressed {
                background-color: #0062cc;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        return button

class BackgroundStyleManager:
    """全局背景颜色管理器"""
    
    # 全局背景颜色配置
    GLOBAL_BACKGROUND_COLOR = "#f8f9fa"  # 统一浅灰色背景，消除纯白色
    GLOBAL_BACKGROUND_STYLE = "background-color: #f8f9fa;"
    
    @classmethod
    def applyToWidget(cls, widget):
        """应用统一背景色到控件"""
        if isinstance(widget, QtWidgets.QWidget):
            widget.setStyleSheet(cls.GLOBAL_BACKGROUND_STYLE)
    
    @classmethod
    def applyToWidgets(cls, *widgets):
        """批量应用统一背景色到多个控件"""
        for widget in widgets:
            cls.applyToWidget(widget)
    
    @classmethod
    def createStandardContainer(cls, parent=None):
        """创建标准背景色的容器控件"""
        container = QtWidgets.QWidget(parent)
        cls.applyToWidget(container)
        return container
    
    @classmethod
    def getBackgroundStyle(cls):
        """获取标准背景样式字符串"""
        return cls.GLOBAL_BACKGROUND_STYLE


# 按钮样式管理器便捷函数
def createTextButton(text, parent=None, slot=None):
    """创建标准文本按钮的便捷函数"""
    return TextButtonStyleManager.createStandardButton(text, parent, slot)

def applyTextButtonStyle(button, text=None):
    """应用标准文本按钮样式的便捷函数"""
    TextButtonStyleManager.applyToButton(button, text)

def updateTextButtonText(button, new_text):
    """更新按钮文本并重新调整大小的便捷函数"""
    TextButtonStyleManager.updateButtonText(button, new_text)

def applyGlobalBackground(widget):
    """应用全局背景色的便捷函数"""
    BackgroundStyleManager.applyToWidget(widget)

def createStandardContainer(parent=None):
    """创建标准背景容器的便捷函数"""
    return BackgroundStyleManager.createStandardContainer(parent)

def getGlobalBackgroundStyle():
    """获取全局背景样式的便捷函数"""
    return BackgroundStyleManager.getBackgroundStyle()


# ============================================================================
# 标题文本框样式管理器 (Title TextBox Style Manager)
# ============================================================================

class TitleTextBoxStyleManager:
    """全局标题文本框样式管理器"""
    
    # 默认样式配置
    DEFAULT_TEXTBOX_STYLE = """
        QTextEdit {
            background-color: transparent;
            border: none;
            padding: 5px;
        }
    """
    
    DEFAULT_GROUPBOX_STYLE = """
        QGroupBox {
            font-weight: normal;
            border: 1px solid #CCCCCC;
            border-radius: 3px;
            margin-top: 0.5em;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
    """
    
    @classmethod
    def createTitleTextBox(cls, parent, title, placeholder_text="", max_height=100, read_only=True):
        """
        创建标准的标题文本框组合
        
        Args:
            parent: 父控件
            title (str): 标题文本
            placeholder_text (str): 占位符文本
            max_height (int): 文本框最大高度
            read_only (bool): 是否只读
            
        Returns:
            tuple: (QGroupBox, QTextEdit) 返回组框和文本框
        """
        # 创建组框
        group_box = QtWidgets.QGroupBox(title, parent)
        group_box.setStyleSheet(cls.DEFAULT_GROUPBOX_STYLE)
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout()
        
        # 创建文本框
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(read_only)
        text_edit.setMaximumHeight(max_height)
        if placeholder_text:
            text_edit.setPlaceholderText(placeholder_text)
        text_edit.setStyleSheet(cls.DEFAULT_TEXTBOX_STYLE)
        
        # 应用字体管理器
        FontManager.applyToWidget(text_edit)
        
        # 组装布局
        layout.addWidget(text_edit)
        group_box.setLayout(layout)
        
        return group_box, text_edit
    
    @classmethod
    def applyToTextBox(cls, text_edit):
        """应用标准文本框样式到现有文本框"""
        text_edit.setStyleSheet(cls.DEFAULT_TEXTBOX_STYLE)
        FontManager.applyToWidget(text_edit)
    
    @classmethod
    def applyToGroupBox(cls, group_box):
        """应用标准组框样式到现有组框"""
        group_box.setStyleSheet(cls.DEFAULT_GROUPBOX_STYLE)
    
    @classmethod
    def applyToTitleTextBox(cls, group_box, text_edit):
        """应用标准样式到标题文本框组合"""
        cls.applyToGroupBox(group_box)
        cls.applyToTextBox(text_edit)
    
    @classmethod
    def setDefaultTextBoxStyle(cls, style_sheet):
        """设置默认文本框样式"""
        cls.DEFAULT_TEXTBOX_STYLE = style_sheet
    
    @classmethod
    def setDefaultGroupBoxStyle(cls, style_sheet):
        """设置默认组框样式"""
        cls.DEFAULT_GROUPBOX_STYLE = style_sheet
    
    @classmethod
    def getDefaultTextBoxStyle(cls):
        """获取默认文本框样式"""
        return cls.DEFAULT_TEXTBOX_STYLE
    
    @classmethod
    def getDefaultGroupBoxStyle(cls):
        """获取默认组框样式"""
        return cls.DEFAULT_GROUPBOX_STYLE


# 标题文本框样式管理器便捷函数
def createTitleTextBox(parent, title, placeholder_text="", max_height=100, read_only=True):
    """创建标准标题文本框的便捷函数"""
    return TitleTextBoxStyleManager.createTitleTextBox(
        parent, title, placeholder_text, max_height, read_only
    )

def applyTitleTextBoxStyle(group_box, text_edit):
    """应用标题文本框样式的便捷函数"""
    TitleTextBoxStyleManager.applyToTitleTextBox(group_box, text_edit)

def applyTextBoxStyle(text_edit):
    """应用文本框样式的便捷函数"""
    TitleTextBoxStyleManager.applyToTextBox(text_edit)

def applyGroupBoxStyle(group_box):
    """应用组框样式的便捷函数"""
    TitleTextBoxStyleManager.applyToGroupBox(group_box)


# ============================================================================
# 菜单栏样式管理器 (MenuBar Style Manager)
# ============================================================================

class MenuBarStyleManager:
    """全局菜单栏样式管理器"""
    
    # 默认菜单栏样式配置
    DEFAULT_MENUBAR_STYLE = """
        QMenuBar {
            background-color: #F0F0F0;
            border-bottom: 1px solid #D0D0D0;
            padding: 2px;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
            margin: 1px;
            border-radius: 3px;
        }
        QMenuBar::item:selected {
            background-color: #B0B0B0;  /* 加深的悬停颜色 */
            color: black;
        }
        QMenuBar::item:pressed {
            background-color: #A0A0A0;  /* 按下时更深的颜色 */
            color: black;
        }
        QMenu {
            background-color: white;
            border: 1px solid #CCCCCC;
            padding: 2px;
        }
        QMenu::item {
            background-color: transparent;
            padding: 6px 20px;
            margin: 1px;
        }
        QMenu::item:selected {
            background-color: #0078D4;
            color: white;
        }
        QMenu::separator {
            height: 1px;
            background-color: #E0E0E0;
            margin: 2px 0px;
        }
    """
    
    @classmethod
    def applyToMenuBar(cls, menubar):
        """应用标准菜单栏样式到菜单栏控件"""
        menubar.setStyleSheet(cls.DEFAULT_MENUBAR_STYLE)
    
    @classmethod
    def setDefaultMenuBarStyle(cls, style_sheet):
        """设置默认菜单栏样式"""
        cls.DEFAULT_MENUBAR_STYLE = style_sheet
    
    @classmethod
    def getDefaultMenuBarStyle(cls):
        """获取默认菜单栏样式"""
        return cls.DEFAULT_MENUBAR_STYLE
    
    @classmethod
    def setHoverColor(cls, color):
        """设置菜单栏悬停颜色"""
        # 更新样式中的悬停颜色
        cls.DEFAULT_MENUBAR_STYLE = cls.DEFAULT_MENUBAR_STYLE.replace(
            "background-color: #B0B0B0;",
            f"background-color: {color};"
        )


# 菜单栏样式管理器便捷函数
def applyMenuBarStyle(menubar):
    """应用菜单栏样式的便捷函数"""
    MenuBarStyleManager.applyToMenuBar(menubar)

def setMenuBarHoverColor(color):
    """设置菜单栏悬停颜色的便捷函数"""
    MenuBarStyleManager.setHoverColor(color)


# ============================================================================
# 曲线显示样式管理器 (Curve Display Style Manager)
# ============================================================================

class CurveDisplayStyleManager:
    """曲线显示样式管理器"""
    
    # 统一的颜色配置
    BACKGROUND_COLOR = "#f8f9fa"  # 统一背景色
    PLOT_BACKGROUND_COLOR = "#f8f9fa"  # 图表背景色
    CONTAINER_BACKGROUND_COLOR = "#ffffff"  # 容器背景色
    BORDER_COLOR = "#dee2e6"  # 边框颜色
    TEXT_COLOR = "#333333"  # 文本颜色
    
    # 图表尺寸配置
    CHART_WIDTH = 600
    CHART_HEIGHT = 350
    CHART_DPI = 100
    
    @classmethod
    def getBackgroundColor(cls):
        """获取统一背景色"""
        return cls.BACKGROUND_COLOR
    
    @classmethod
    def getPlotBackgroundColor(cls):
        """获取图表背景色"""
        return cls.PLOT_BACKGROUND_COLOR
    
    @classmethod
    def getContainerBackgroundColor(cls):
        """获取容器背景色"""
        return cls.CONTAINER_BACKGROUND_COLOR
    
    @classmethod
    def getBorderColor(cls):
        """获取边框颜色"""
        return cls.BORDER_COLOR
    
    @classmethod
    def getTextColor(cls):
        """获取文本颜色"""
        return cls.TEXT_COLOR
    
    @classmethod
    def getChartSize(cls):
        """获取图表尺寸"""
        return cls.CHART_WIDTH, cls.CHART_HEIGHT
    
    @classmethod
    def getChartDPI(cls):
        """获取图表DPI"""
        return cls.CHART_DPI
    
    @classmethod
    def generateCurveHTML(cls, curve_image_path, stats_html=""):
        """生成统一样式的曲线HTML"""
        return f"""
        <div style="font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif; padding: 20px; background: {cls.BACKGROUND_COLOR}; color: {cls.TEXT_COLOR};">
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 15px 0; color: {cls.TEXT_COLOR}; font-size: 18px; font-weight: 600;">液位检测曲线结果</h3>
            </div>
            
            {stats_html}
            
            <div style="text-align: center; margin-bottom: 15px; background: {cls.CONTAINER_BACKGROUND_COLOR}; padding: 8px; border-radius: 6px; border: 1px solid {cls.BORDER_COLOR};">
                <img src="file:///{curve_image_path.replace(chr(92), '/')}" style="max-width: 100%; height: auto; border-radius: 4px;">
            </div>
            
            <div style="padding: 10px; background: {cls.CONTAINER_BACKGROUND_COLOR}; border: 1px solid {cls.BORDER_COLOR}; border-radius: 5px; font-size: 12px; color: #666;">
                <p style="margin: 0;"><strong>说明:</strong> 曲线显示了液位检测的结果变化趋势。X轴表示帧序号，Y轴表示液位高度（毫米）。</p>
            </div>
        </div>
        """
    
    @classmethod
    def setBackgroundColor(cls, color):
        """设置背景颜色"""
        cls.BACKGROUND_COLOR = color
        cls.PLOT_BACKGROUND_COLOR = color
    
    @classmethod
    def setChartSize(cls, width, height):
        """设置图表尺寸"""
        cls.CHART_WIDTH = width
        cls.CHART_HEIGHT = height


# 曲线显示样式管理器便捷函数
def getCurveBackgroundColor():
    """获取曲线背景色的便捷函数"""
    return CurveDisplayStyleManager.getBackgroundColor()

def getCurvePlotBackgroundColor():
    """获取曲线图表背景色的便捷函数"""
    return CurveDisplayStyleManager.getPlotBackgroundColor()

def getCurveChartSize():
    """获取曲线图表尺寸的便捷函数"""
    return CurveDisplayStyleManager.getChartSize()

def generateCurveHTML(curve_image_path, stats_html=""):
    """生成曲线HTML的便捷函数"""
    return CurveDisplayStyleManager.generateCurveHTML(curve_image_path, stats_html)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 应用全局字体
    FontManager.applyToApplication(app)
    
    window = QtWidgets.QWidget()
    window.setWindowTitle("统一样式管理器测试")
    layout = QtWidgets.QVBoxLayout()
    
    label1 = QtWidgets.QLabel("默认字体 - Microsoft YaHei 12pt Normal")
    applyDefaultFont(label1)
    layout.addWidget(label1)
    
    label2 = QtWidgets.QLabel("标题字体 - Microsoft YaHei 16pt DemiBold")
    applyTitleFont(label2)
    layout.addWidget(label2)
    
    button1 = createTextButton("确认", parent=window)
    layout.addWidget(button1)
    
    button2 = createTextButton("这是一个很长的按钮文本", parent=window)
    layout.addWidget(button2)
    
    title_group, title_text = createTitleTextBox(
        window, 
        "模型描述", 
        "这是最新版综合液位推理模型，满足了绝大多数任务的检测需求。",
        max_height=80
    )
    layout.addWidget(title_group)
    
    def test_dialog():
        result = show_question(window, "确认", "确定要执行此操作吗？")
        if result:
            show_information(window, "信息", "操作已确认")
        else:
            show_warning(window, "警告", "操作已取消")
    
    button3 = createTextButton("测试对话框", parent=window, slot=test_dialog)
    layout.addWidget(button3)
    
    window.setLayout(layout)
    window.show()
    
    sys.exit(app.exec_())
