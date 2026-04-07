#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量移除客户端代码中的print语句，改为使用logger
"""

import os
import re
from pathlib import Path

# 项目根目录
project_root = Path(__file__).parent.parent
client_dir = project_root / 'client'

# 需要处理的文件列表
files_to_process = [
    'main.py',
    'client/utils/config.py',
    'client/network/command_manager.py',
    'client/network/websocket_client.py',
    'client/widgets/system_window.py',
    'client/storage/detection_result_csv_writer.py',
    'client/handlers/videopage/curvepanel_handler.py',
]

def remove_print_statements(file_path):
    """移除文件中的print语句"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 注释掉所有print语句（保留代码以便需要时恢复）
        # 匹配 print(...) 语句
        content = re.sub(
            r'^(\s*)print\((.*?)\)\s*$',
            r'\1# print(\2)  # 已禁用终端输出',
            content,
            flags=re.MULTILINE
        )

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ 已处理: {file_path}")
            return True
        else:
            print(f"- 无需处理: {file_path}")
            return False

    except Exception as e:
        print(f"✗ 处理失败 {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("开始批量移除print语句...")
    print("=" * 60)

    processed_count = 0

    for file_rel_path in files_to_process:
        file_path = project_root / file_rel_path
        if file_path.exists():
            if remove_print_statements(file_path):
                processed_count += 1
        else:
            print(f"✗ 文件不存在: {file_path}")

    print("=" * 60)
    print(f"处理完成，共处理 {processed_count} 个文件")

if __name__ == '__main__':
    main()
