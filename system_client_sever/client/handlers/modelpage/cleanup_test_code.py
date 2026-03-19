# -*- coding: utf-8 -*-
"""
自动清理 model_training_handler.py 中已迁移的测试代码

此脚本会：
1. 备份原文件
2. 删除已迁移到 ModelTestHandler 的测试方法
3. 保留训练和标注相关代码
4. 生成清理报告
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

# 需要删除的方法列表（按在文件中出现的顺序）
METHODS_TO_DELETE = [
    '_handleStartTest',
    '_handleStopTest', 
    '_handleStartTestExecution',
    '_loadTestFrame',
    '_drawLiquidLinesOnFrame',
    '_updateRealtimeFrame',
    '_createRealtimeVideoPlayer',
    '_performVideoFrameDetection',
    '_saveVideoTestResults',
    '_showDetectionVideo',
    '_showDetectionComplete',
    '_performTestDetection',
    '_saveTestDetectionResult',
    '_showTestDetectionResult',
]

# 保留的方法（不要删除）
METHODS_TO_KEEP = [
    '_handleStartAnnotation',
    '_createAnnotationEngine',
    '_showAnnotationWidget',
    '_saveTestAnnotationResult',
    '_showAnnotationPreview',
    '_displayAnnotationPreview',
    'connectToTrainingPanel',
    '_initializeTrainingPanelDefaults',
    '_handleStartTraining',
    '_handleStopTraining',
    '_handleContinueTraining',
]

def backup_file(filepath):
    """备份文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    return backup_path

def find_method_range(lines, method_name):
    """
    找到方法的起始和结束行
    
    Returns:
        (start_line, end_line) 或 None
    """
    start_line = None
    indent_level = None
    
    # 查找方法定义
    for i, line in enumerate(lines):
        if f"def {method_name}(" in line:
            start_line = i
            # 计算缩进级别
            indent_level = len(line) - len(line.lstrip())
            break
    
    if start_line is None:
        return None
    
    # 查找方法结束（下一个相同或更小缩进级别的 def）
    end_line = len(lines)
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip():  # 非空行
            current_indent = len(line) - len(line.lstrip())
            # 如果遇到相同或更小缩进的 def，说明方法结束
            if current_indent <= indent_level and line.strip().startswith('def '):
                end_line = i
                break
    
    return (start_line, end_line)

def cleanup_test_code(filepath):
    """清理测试代码"""
    
    # 读取文件
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_line_count = len(lines)
    
    # 记录删除的方法
    deleted_methods = []
    deleted_lines = 0
    
    # 从后往前删除（避免行号变化）
    for method_name in reversed(METHODS_TO_DELETE):
        result = find_method_range(lines, method_name)
        if result:
            start, end = result
            method_lines = end - start
            
            # 删除方法
            del lines[start:end]
            deleted_methods.append({
                'name': method_name,
                'start': start + 1,
                'end': end,
                'lines': method_lines
            })
            deleted_lines += method_lines
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    new_line_count = len(lines)
    
    # 生成报告文件
    report_path = str(filepath).replace('.py', '_cleanup_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("测试代码清理报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"清理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"原文件: {filepath}\n")
        f.write(f"\n原文件行数: {original_line_count}\n")
        f.write(f"新文件行数: {new_line_count}\n")
        f.write(f"删除行数: {deleted_lines}\n")
        f.write(f"删除方法数: {len(deleted_methods)}\n")
        f.write("\n删除的方法:\n")
        for method in reversed(deleted_methods):
            f.write(f"  - {method['name']}: {method['lines']} 行 (第 {method['start']}-{method['end']} 行)\n")
        f.write("\n" + "=" * 60 + "\n")
    
    return deleted_methods

def verify_file(filepath):
    """验证文件语法"""
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, filepath, 'exec')
        return True
    except SyntaxError as e:
        return False

def main():
    """主函数"""
    script_dir = Path(__file__).parent
    filepath = script_dir / 'model_training_handler.py'
    
    if not filepath.exists():
        return False
    
    # 确认
    response = input("\n是否继续？(y/n): ")
    if response.lower() != 'y':
        return False
    
    # 备份
    backup_path = backup_file(filepath)
    
    # 清理
    try:
        deleted_methods = cleanup_test_code(filepath)
        
        # 验证
        if verify_file(filepath):
            return True
        else:
            shutil.copy2(backup_path, filepath)
            return False
            
    except Exception as e:
        shutil.copy2(backup_path, filepath)
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
