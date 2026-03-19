# -*- coding: utf-8 -*-

import argparse
import os
import sys
import logging

# 添加 detection 目录到 sys.path，确保可以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from qtpy import QtWidgets

from app import MainWindow
from database.config import get_config, get_temp_models_dir
from widgets.font_manager import FontManager


def setup_logging(level: str = "info"):
    """
    初始化全局日志配置（仅控制台输出）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清理已有的 handler，避免重复配置
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    return None


def setup_runtime_directories():
    """
    在打包环境中创建运行时需要的可写目录
    
    打包后的目录结构：
    - _internal/database/  (只读，从这里读取所有配置和模型)
    - exe目录/            (可写，保存运行时数据)
      - recordings/       (录像文件)
      - database/model/temp_models/      (临时解码的模型)
      - database/mission_result/  (任务结果数据)
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：在exe所在目录创建运行时可写目录
        exe_dir = os.path.dirname(sys.executable)
        
        # 只创建需要写入的目录（不再创建顶层 database 及其子目录，database 仅从 _internal 读取）
        runtime_dirs = [
            os.path.join(exe_dir, 'recordings'),
        ]
        
        for dir_path in runtime_dirs:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    pass


def main():
    """主入口函数"""
    try:
        # 在打包环境中创建运行时目录结构
        if getattr(sys, 'frozen', False):
            setup_runtime_directories()
        
        _main()
    except Exception as e:
        import traceback
        from datetime import datetime
        
        error_log = f"""
{'=' * 80}
程序启动失败！
{'=' * 80}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
错误类型: {type(e).__name__}
错误信息: {str(e)}

完整错误堆栈:
{traceback.format_exc()}

环境信息:
- Python版本: {sys.version}
- 当前目录: {os.getcwd()}
- 脚本目录: {current_dir}
- 是否打包: {getattr(sys, 'frozen', False)}
- 可执行文件: {sys.executable}

sys.path:
{chr(10).join(f'  - {p}' for p in sys.path)}
{'=' * 80}
"""
        # 保存错误日志到文件
        log_path = None
        try:
            log_filename = f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            log_path = os.path.join(os.getcwd(), log_filename)
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(error_log)
        except Exception as log_err:
            pass
        
        # 在打包环境中使用更可靠的暂停方法
        if getattr(sys, 'frozen', False):
            # 打包环境：使用 Windows API 显示消息框
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"程序启动失败！\n\n错误类型: {type(e).__name__}\n错误信息: {str(e)}\n\n" +
                    (f"详细信息已保存到:\n{log_path}\n\n" if log_path else "") +
                    "请查看控制台或日志文件获取完整错误信息。",
                    "液位检测系统 - 错误",
                    0x10  # MB_ICONERROR
                )
            except:
                # 如果消息框失败，尝试 pause 命令
                try:
                    os.system('pause')
                except:
                    import time
                    time.sleep(10)  # 至少显示 10 秒
        else:
            # 开发环境：使用 input
            try:
                input("\n按回车键退出...")
            except:
                import time
                time.sleep(5)
        
        sys.exit(1)


def _main():
    """实际主入口函数"""
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(
        description='帕特智能油液位检测',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        'filename',
        nargs='?',
        help='图像或视频文件路径',
    )
    
    # 使用项目中的 default_config.yaml 而不是用户目录的 .detectionrc
    default_config_file = os.path.join(current_dir, "database", "config", "default_config.yaml")
    parser.add_argument(
        '--config',
        dest='config',
        help=f'配置文件路径 (默认: {default_config_file})',
        default=default_config_file,
    )
    
    parser.add_argument(
        '--version',
        action='store_true',
        help='显示版本信息',
    )
    
    parser.add_argument(
        '--logger-level',
        dest='logger_level',
        default='info',
        choices=['debug', 'info', 'warning', 'error'],
        help='日志级别',
    )
    
    parser.add_argument(
        '--auto-save',
        dest='auto_save',
        action='store_true',
        help='启用自动保存',
    )
    
    args = parser.parse_args()
    
    if args.version:
        return
    
    # 从args中提取配置
    config_from_args = args.__dict__
    filename = config_from_args.pop('filename')
    config_file_or_yaml = config_from_args.pop('config')
    version = config_from_args.pop('version')
    
    # 获取配置（三层级联）
    log_file_path = setup_logging(args.logger_level)
    logging.getLogger(__name__).debug("Logger level set to %s", args.logger_level)

    config = get_config(config_file_or_yaml, config_from_args)
    
    # 创建Qt应用
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Detection')
    app.setOrganizationName('Detection')
    
    # 应用全局字体配置
    FontManager.applyToApplication(app)
    
    # 创建主窗口
    win = MainWindow(
        config=config,
        filename=filename,
    )
    win.show()
    
    # 启动事件循环
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

