# -*- coding: utf-8 -*-
"""
SSH连接测试脚本
用于测试SSH免密连接功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ssh_connect.ssh_manager import SSHManager


def test_ssh_setup():
    """测试SSH设置"""
    print("="*60)
    print("SSH连接测试")
    print("="*60)
    
    ssh_manager = SSHManager()
    
    print("\n1. 检查SSH配置状态...")
    if ssh_manager.is_ssh_configured():
        print("   SSH配置文件已存在")
    else:
        print("   SSH未配置")
    
    print("\n2. 测试网络连接...")
    if ssh_manager.test_network_connection(ssh_manager.server_host):
        print("   网络连接正常")
    else:
        print("   网络连接失败")
        return False
    
    print("\n3. 检查必需命令...")
    if ssh_manager.check_required_commands():
        print("   所有必需命令都已安装")
    else:
        print("   缺少必需命令")
        return False
    
    print("\n4. 测试SSH连接...")
    if ssh_manager.test_ssh_connection():
        print("   SSH连接正常")
    else:
        print("   SSH连接失败，尝试设置...")
        
        print("\n5. 设置SSH免密连接...")
        if ssh_manager.setup_ssh_connection():
            print("   SSH设置成功")
        else:
            print("   SSH设置失败")
            return False
    
    print("\n6. 检查远程服务...")
    remote_status = ssh_manager.check_remote_services()
    
    if remote_status.get('go_api'):
        print("   Go API服务: 正在运行")
    else:
        print("   Go API服务: 未运行")
    
    if remote_status.get('python_inference'):
        print("   Python推理服务: 正在运行")
    else:
        print("   Python推理服务: 未运行")
    
    print("\n7. 测试远程命令执行...")
    result = ssh_manager.execute_remote_command('whoami')
    if result['success']:
        print(f"   远程用户: {result['stdout'].strip()}")
    else:
        print(f"   远程命令执行失败: {result['stderr']}")
    
    result = ssh_manager.execute_remote_command('pwd')
    if result['success']:
        print(f"   远程目录: {result['stdout'].strip()}")
    
    result = ssh_manager.execute_remote_command('ls -la /home/lqj/liquid')
    if result['success']:
        print("   远程项目目录内容:")
        for line in result['stdout'].strip().split('\n')[:5]:  # 只显示前5行
            print(f"     {line}")
    
    print("\n" + "="*60)
    print("SSH连接测试完成")
    print("="*60)
    
    return True


def test_remote_service_management():
    """测试远程服务管理"""
    print("\n" + "="*60)
    print("远程服务管理测试")
    print("="*60)
    
    ssh_manager = SSHManager()
    
    if not ssh_manager.test_ssh_connection():
        print("SSH连接不可用，跳过远程服务管理测试")
        return False
    
    print("\n1. 检查远程环境...")
    
    # 检查conda环境
    result = ssh_manager.execute_remote_command('conda info --envs | grep liquid')
    if result['success'] and 'liquid' in result['stdout']:
        print("   Conda环境 'liquid' 存在")
    else:
        print("   Conda环境 'liquid' 不存在或conda未安装")
    
    # 检查Go版本
    result = ssh_manager.execute_remote_command('source /home/lqj/anaconda3/etc/profile.d/conda.sh && conda activate liquid && go version')
    if result['success']:
        print(f"   Go版本: {result['stdout'].strip()}")
    else:
        print("   Go未安装或环境配置错误")
    
    # 检查Python版本
    result = ssh_manager.execute_remote_command('source /home/lqj/anaconda3/etc/profile.d/conda.sh && conda activate liquid && python --version')
    if result['success']:
        print(f"   Python版本: {result['stdout'].strip()}")
    
    # 检查项目文件
    result = ssh_manager.execute_remote_command('ls -la /home/lqj/liquid/api/liquid-api')
    if result['success']:
        print("   Go API可执行文件存在")
    else:
        print("   Go API可执行文件不存在")
    
    result = ssh_manager.execute_remote_command('ls -la /home/lqj/liquid/server/')
    if result['success']:
        print("   Python服务目录存在")
    
    # 检查海康SDK
    result = ssh_manager.execute_remote_command('ls -la /home/lqj/liquid/sdk/hikvision/lib/')
    if result['success']:
        print("   海康SDK库文件存在")
    else:
        print("   海康SDK库文件不存在")
    
    print("\n2. 检查当前运行的服务...")
    remote_status = ssh_manager.check_remote_services()
    
    print("\n" + "="*60)
    print("远程服务管理测试完成")
    print("="*60)
    
    return True


if __name__ == '__main__':
    print("开始SSH连接和远程服务管理测试...\n")
    
    # 测试SSH设置
    if test_ssh_setup():
        print("\nSSH连接测试通过")
        
        # 测试远程服务管理
        if test_remote_service_management():
            print("\n远程服务管理测试通过")
        else:
            print("\n远程服务管理测试失败")
    else:
        print("\nSSH连接测试失败")
    
    print("\n测试完成")