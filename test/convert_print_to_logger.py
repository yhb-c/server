#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将print语句转换为logger.debug
"""

import re
import sys

def convert_print_to_logger(file_path):
    """将文件中的print语句转换为logger.debug"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 匹配 print(f"[xxx] ...") 或 print("[xxx] ...")
        # 替换为 self.logger.debug(f"[xxx] ...") 或 logger.debug("[xxx] ...")

        # 模式1: print(f"[DEBUG] ...")
        content = re.sub(
            r'^(\s+)print\((f?"?\[.*?\].*?"?)\)(\s*)$',
            r'\1self.logger.debug(\2)\3',
            content,
            flags=re.MULTILINE
        )

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ 已转换: {file_path}")
            return True
        else:
            print(f"- 无需转换: {file_path}")
            return False

    except Exception as e:
        print(f"✗ 转换失败 {file_path}: {e}")
        return False

if __name__ == '__main__':
    files = [
        '/home/lqj/liquid/client/handlers/videopage/channelpanel_handler.py',
        '/home/lqj/liquid/client/handlers/videopage/general_set_handler.py',
        '/home/lqj/liquid/client/handlers/videopage/modelsetting_handler.py',
        '/home/lqj/liquid/client/widgets/videopage/channelpanel.py',
        '/home/lqj/liquid/client/widgets/videopage/general_set.py',
    ]

    for file_path in files:
        convert_print_to_logger(file_path)
