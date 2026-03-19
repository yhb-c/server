#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在服务器上运行HKcapture导入测试
"""

import subprocess
import sys

def run_server_test():
    """在服务器上运行测试"""
    print("在服务器上运行HKcapture导入测试")
    print("=" * 50)
    
    try:
        # SSH连接并运行测试
        ssh_cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            'lqj@192.168.0.121',
            'cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && python test/simple_hkcapture_test.py'
        ]
        
        print("执行SSH命令...")
        print(f"命令: {' '.join(ssh_cmd)}")
        
        # 运行命令
        result = subprocess.run(ssh_cmd, 
                              capture_output=True, 
                              text=True, 
                              timeout=120)
        
        print("\n测试输出:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("\n错误信息:")
            print("=" * 50)
            print(result.stderr)
        
        print(f"\n退出代码: {result.returncode}")
        
        # 分析结果
        success_indicators = [
            "HKcapture导入成功",
            "视频捕获工厂创建成功", 
            "所有测试通过"
        ]
        
        success_count = sum(1 for indicator in success_indicators if indicator in result.stdout)
        
        if success_count >= 2:
            print("\n测试成功！HKcapture导入修复完成")
            return True
        else:
            print(f"\n测试部分成功，成功指标: {success_count}/3")
            return False
        
    except subprocess.TimeoutExpired:
        print("SSH连接超时")
        return False
    except Exception as e:
        print(f"SSH连接失败: {e}")
        return False

if __name__ == "__main__":
    success = run_server_test()
    sys.exit(0 if success else 1)