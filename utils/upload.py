#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件上传工具
用于将本地的api和server文件夹上传到远程服务器
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

class ServerUploader:
    def __init__(self):
        # 服务器配置
        self.server_ip = "192.168.0.121"
        self.username = "lqj"
        self.password = "admin"
        
        # 本地路径配置 - 基于当前工作目录
        self.project_root = Path.cwd()
        self.api_local_path = self.project_root / "api"
        self.server_local_path = self.project_root / "server"
        self.test_local_path = self.project_root / "test"
        
        # 远程路径配置
        self.api_remote_path = "/home/lqj/liquid/api"
        self.server_remote_path = "/home/lqj/liquid/server"
        self.test_remote_path = "/home/lqj/liquid/test"
        
    def check_local_paths(self):
        """检查本地路径是否存在"""
        print("检查本地路径...")
        
        if not self.api_local_path.exists():
            print(f"错误: API文件夹不存在: {self.api_local_path}")
            return False
            
        if not self.server_local_path.exists():
            print(f"错误: Server文件夹不存在: {self.server_local_path}")
            return False
            
        if not self.test_local_path.exists():
            print(f"错误: Test文件夹不存在: {self.test_local_path}")
            return False
            
        print(f"API文件夹: {self.api_local_path}")
        print(f"Server文件夹: {self.server_local_path}")
        print(f"Test文件夹: {self.test_local_path}")
        return True
        
    def check_rsync_available(self):
        """检查rsync命令是否可用"""
        try:
            result = subprocess.run(['rsync', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("错误: rsync命令不可用，请确保已安装rsync")
            print("Windows用户可以通过WSL或Git Bash使用rsync")
            return False
            
    def sync_folder(self, local_path, remote_path, folder_name):
        """同步文件夹到远程服务器（删除远程多余文件）"""
        print(f"\n开始同步{folder_name}文件夹...")
        print(f"本地路径: {local_path}")
        print(f"远程路径: {remote_path}")
        
        # 构建rsync命令 - 使用同步模式，删除远程多余文件
        rsync_cmd = [
            'rsync', '-avz', '--delete',
            '--exclude=__pycache__',
            '--exclude=*.pyc',
            '--exclude=.git',
            '-e', 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null',
            f"{local_path}/",
            f"{self.username}@{self.server_ip}:{remote_path}/"
        ]
        
        try:
            # 执行同步命令
            print(f"执行命令: {' '.join(rsync_cmd)}")
            print("请在提示时输入服务器密码...")
            
            result = subprocess.run(rsync_cmd, 
                                  text=True, 
                                  timeout=300)
            
            if result.returncode == 0:
                print(f"{folder_name}文件夹同步成功!")
                return True
            else:
                print(f"{folder_name}文件夹同步失败!")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"{folder_name}文件夹同步超时!")
            return False
        except Exception as e:
            print(f"{folder_name}文件夹同步异常: {str(e)}")
            return False
            
    def create_remote_directories(self):
        """在远程服务器创建目录"""
        print("\n创建远程目录...")
        
        ssh_cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f"{self.username}@{self.server_ip}",
            f"mkdir -p {self.api_remote_path} {self.server_remote_path} {self.test_remote_path}"
        ]
        
        try:
            print("请在提示时输入服务器密码...")
            result = subprocess.run(ssh_cmd,
                                  text=True,
                                  timeout=30)
            
            if result.returncode == 0:
                print("远程目录创建成功!")
                return True
            else:
                print("远程目录创建失败")
                return False
                
        except Exception as e:
            print(f"创建远程目录异常: {str(e)}")
            return False
            
    def sync_all(self):
        """同步所有文件夹"""
        print("=" * 50)
        print("液位检测系统文件同步工具")
        print("=" * 50)
        
        # 检查本地路径
        if not self.check_local_paths():
            return False
            
        # 检查rsync命令
        if not self.check_rsync_available():
            return False
            
        # 创建远程目录
        if not self.create_remote_directories():
            return False
            
        success_count = 0
        
        # 同步API文件夹
        if self.sync_folder(self.api_local_path, self.api_remote_path, "API"):
            success_count += 1
            
        # 同步Server文件夹  
        if self.sync_folder(self.server_local_path, self.server_remote_path, "Server"):
            success_count += 1
            
        # 同步Test文件夹
        if self.sync_folder(self.test_local_path, self.test_remote_path, "Test"):
            success_count += 1
            
        print("\n" + "=" * 50)
        if success_count == 3:
            print("所有文件夹同步完成!")
            print(f"API文件夹已同步到: {self.api_remote_path}")
            print(f"Server文件夹已同步到: {self.server_remote_path}")
            print(f"Test文件夹已同步到: {self.test_remote_path}")
            return True
        else:
            print(f"同步完成，成功: {success_count}/3")
            return False
            
    def sync_single(self, folder_type):
        """同步单个文件夹"""
        if not self.check_local_paths():
            return False
            
        if not self.check_rsync_available():
            return False
            
        if not self.create_remote_directories():
            return False
            
        if folder_type.lower() == "api":
            return self.sync_folder(self.api_local_path, self.api_remote_path, "API")
        elif folder_type.lower() == "server":
            return self.sync_folder(self.server_local_path, self.server_remote_path, "Server")
        elif folder_type.lower() == "test":
            return self.sync_folder(self.test_local_path, self.test_remote_path, "Test")
        else:
            print("错误: 无效的文件夹类型，请使用 'api'、'server' 或 'test'")
            return False

def main():
    parser = argparse.ArgumentParser(description='液位检测系统文件同步工具')
    parser.add_argument('--folder', '-f', 
                       choices=['api', 'server', 'test', 'all'], 
                       default='all',
                       help='指定要同步的文件夹 (api/server/test/all)')
    
    args = parser.parse_args()
    
    uploader = ServerUploader()
    
    try:
        if args.folder == 'all':
            success = uploader.sync_all()
        else:
            success = uploader.sync_single(args.folder)
            
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n同步被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"同步过程中发生异常: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()