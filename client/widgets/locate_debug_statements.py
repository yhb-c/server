#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试语句定位脚本
用于查找并记录 widgets 和 handlers 文件夹中的调试语句位置
"""

import os
import re
from pathlib import Path
from datetime import datetime


class DebugStatementLocator:
    """调试语句定位器"""
    
    def __init__(self, target_dirs):
        """
        初始化定位器
        
        Args:
            target_dirs: 要扫描的目标目录列表
        """
        self.target_dirs = target_dirs
        self.debug_patterns = [
            # print 语句
            (r'^\s*print\s*\(', 'print语句'),
            # logging.debug
            (r'^\s*logging\.debug\s*\(', 'logging.debug'),
            # logger.debug
            (r'^\s*logger\.debug\s*\(', 'logger.debug'),
            # self.logger.debug
            (r'^\s*self\.logger\.debug\s*\(', 'self.logger.debug'),
            # console.log (如果有JS代码)
            (r'^\s*console\.log\s*\(', 'console.log'),
            # 包含 DEBUG 或 debug 的注释
            (r'^\s*#.*(?:DEBUG|debug|调试|测试)', 'DEBUG注释'),
            # TODO/FIXME 注释
            (r'^\s*#.*(?:TODO|FIXME|XXX|HACK)', 'TODO/FIXME注释'),
        ]
        self.results = []
        
    def scan_file(self, file_path):
        """
        扫描单个文件
        
        Args:
            file_path: 文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line_num, line in enumerate(lines, 1):
                for pattern, pattern_name in self.debug_patterns:
                    if re.search(pattern, line):
                        self.results.append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': pattern_name,
                            'content': line.strip()
                        })
                        
        except Exception as e:
            print(f"扫描文件 {file_path} 时出错: {e}")
            
    def scan_directory(self, directory):
        """
        扫描目录
        
        Args:
            directory: 目录路径
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"目录不存在: {directory}")
            return
            
        # 遍历所有 Python 文件
        for py_file in dir_path.rglob('*.py'):
            # 跳过 __pycache__ 和本脚本自身
            if '__pycache__' in str(py_file) or py_file.name == 'locate_debug_statements.py':
                continue
            self.scan_file(py_file)
            
    def scan_all(self):
        """扫描所有目标目录"""
        for directory in self.target_dirs:
            print(f"正在扫描目录: {directory}")
            self.scan_directory(directory)
            
    def generate_report(self, output_file='debug_statements_report.txt'):
        """
        生成报告
        
        Args:
            output_file: 输出文件名
        """
        # 按文件分组
        files_dict = {}
        for item in self.results:
            file_path = item['file']
            if file_path not in files_dict:
                files_dict[file_path] = []
            files_dict[file_path].append(item)
            
        # 生成报告内容
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("调试语句定位报告")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"总计发现 {len(self.results)} 处调试语句")
        report_lines.append(f"涉及 {len(files_dict)} 个文件")
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # 按文件输出
        for file_path in sorted(files_dict.keys()):
            items = files_dict[file_path]
            report_lines.append(f"\n文件: {file_path}")
            report_lines.append(f"发现 {len(items)} 处调试语句:")
            report_lines.append("-" * 80)
            
            for item in sorted(items, key=lambda x: x['line']):
                report_lines.append(f"  行 {item['line']:4d} | {item['type']:20s} | {item['content']}")
                
            report_lines.append("")
            
        # 统计信息
        report_lines.append("=" * 80)
        report_lines.append("统计信息")
        report_lines.append("=" * 80)
        
        type_counts = {}
        for item in self.results:
            type_name = item['type']
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            
        for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"  {type_name:20s}: {count:4d} 处")
            
        report_lines.append("")
        report_lines.append("=" * 80)
        
        # 写入文件
        report_content = '\n'.join(report_lines)
        
        # 获取项目根目录
        script_dir = Path(__file__).parent.parent
        output_path = script_dir / output_file
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        print(f"\n报告已生成: {output_path}")
        print(f"总计发现 {len(self.results)} 处调试语句")
        
        return output_path


def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).parent.parent
    
    # 定义要扫描的目录
    target_dirs = [
        script_dir / 'widgets',
        script_dir / 'handlers'
    ]
    
    print("=" * 80)
    print("调试语句定位工具")
    print("=" * 80)
    print(f"项目根目录: {script_dir}")
    print(f"扫描目录: {', '.join([str(d) for d in target_dirs])}")
    print("=" * 80)
    print()
    
    # 创建定位器并扫描
    locator = DebugStatementLocator(target_dirs)
    locator.scan_all()
    
    # 生成报告
    report_path = locator.generate_report()
    
    print("\n扫描完成!")
    print(f"请查看报告文件: {report_path}")
    

if __name__ == '__main__':
    main()
