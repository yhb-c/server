# -*- coding: utf-8 -*-
"""
部署管理器 - 清空服务器项目路径并重新部署API和推理服务
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 添加ssh_connect模块路径
sys.path.append(str(Path(__file__).parent.parent / 'ssh_connect'))

from ssh_manager import SSHManager


class DeployManager:
    """部署管理器"""
    
    def __init__(self):
        self.ssh_manager = SSHManager()
        self.server_path = "/home/lqj/liquid"
        
    def log_message(self, message, level="INFO"):
        """记录日志消息"""
        if level == "ERROR":
            print(f"[部署错误] {message}")
        elif level == "SUCCESS":
            print(f"[部署成功] {message}")
        else:
            print(f"[部署信息] {message}")
    
    def stop_services(self):
        """停止现有服务"""
        self.log_message("停止现有服务...")
        
        # 停止API服务
        result = self.ssh_manager.execute_remote_command("pkill -f 'liquid-api' || true")
        if result['success']:
            self.log_message("API服务停止命令已执行")
        
        # 停止推理服务
        result = self.ssh_manager.execute_remote_command("pkill -f 'python.*8085' || true")
        if result['success']:
            self.log_message("推理服务停止命令已执行")
        
        time.sleep(3)
    
    def clean_server_directory(self):
        """清空服务器项目目录"""
        self.log_message("清空服务器项目目录...")
        
        # 清空目录
        result = self.ssh_manager.execute_remote_command(f"rm -rf {self.server_path}/*")
        if not result['success']:
            self.log_message(f"清空目录失败: {result['stderr']}", "ERROR")
            return False
        
        # 创建基础目录结构
        commands = [
            f"mkdir -p {self.server_path}",
            f"mkdir -p {self.server_path}/api",
            f"mkdir -p {self.server_path}/server", 
            f"mkdir -p {self.server_path}/logs"
        ]
        
        for cmd in commands:
            result = self.ssh_manager.execute_remote_command(cmd)
            if not result['success']:
                self.log_message(f"创建目录失败: {cmd} - {result['stderr']}", "ERROR")
                return False
        
        self.log_message("服务器目录清空完成", "SUCCESS")
        return True
    
    def upload_files(self):
        """上传文件到服务器"""
        self.log_message("上传文件到服务器...")
        
        try:
            # 上传API文件
            self.log_message("上传API服务文件...")
            api_cmd = f"scp -r ../api/* lqj@192.168.0.121:{self.server_path}/api/"
            result = subprocess.run(api_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                self.log_message(f"上传API文件失败: {result.stderr}", "ERROR")
                return False
            
            # 上传server文件
            self.log_message("上传推理服务文件...")
            server_cmd = f"scp -r ../server/* lqj@192.168.0.121:{self.server_path}/server/"
            result = subprocess.run(server_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                self.log_message(f"上传server文件失败: {result.stderr}", "ERROR")
                return False
            
            self.log_message("文件上传完成", "SUCCESS")
            return True
            
        except Exception as e:
            self.log_message(f"上传文件异常: {e}", "ERROR")
            return False
    
    def build_api_service(self):
        """构建API服务"""
        self.log_message("构建API服务...")
        
        build_cmd = (
            f"cd {self.server_path}/api && "
            "source /home/lqj/anaconda3/bin/activate liquid && "
            "go mod tidy && "
            "go build -o liquid-api main.go && "
            "chmod +x liquid-api"
        )
        
        result = self.ssh_manager.execute_remote_command(build_cmd, timeout=120)
        if not result['success']:
            self.log_message(f"构建API服务失败: {result['stderr']}", "ERROR")
            return False
        
        self.log_message("API服务构建完成", "SUCCESS")
        return True
    

    def deploy(self):
        """执行完整部署流程"""
        self.log_message("开始部署到远程服务器 192.168.0.121...")

        # 检查SSH连接
        if not self.ssh_manager.is_ssh_configured():
            self.log_message("SSH未配置，开始配置SSH连接...")
            if not self.ssh_manager.setup_ssh_connection():
                self.log_message("SSH配置失败，无法继续部署", "ERROR")
                return False

        # 测试SSH连接
        if not self.ssh_manager.test_ssh_connection():
            self.log_message("SSH连接测试失败，无法继续部署", "ERROR")
            return False

        # 执行部署步骤
        steps = [
            ("停止现有服务", self.stop_services),
            ("清空服务器目录", self.clean_server_directory),
            ("上传文件", self.upload_files),
            ("构建API服务", self.build_api_service)
        ]
        
        for step_name, step_func in steps:
            self.log_message(f"执行步骤: {step_name}")
            if not step_func():
                self.log_message(f"步骤失败: {step_name}", "ERROR")
                return False

        self.log_message("部署完成!", "SUCCESS")
        return True


def main():
    """主函数"""
    deploy_manager = DeployManager()
    success = deploy_manager.deploy()
    
    if success:
        print("\n部署成功完成!")
    else:
        print("\n部署失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()