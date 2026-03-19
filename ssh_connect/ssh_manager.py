# -*- coding: utf-8 -*-
"""
SSH连接管理器 - 用于管理到液位检测系统服务器的SSH免密连接
"""

import os
import sys
import subprocess
import platform
import time
import logging
from pathlib import Path


class SSHManager:
    """SSH连接管理器"""
    
    def __init__(self):
        self.server_host = "192.168.0.121"
        self.server_user = "lqj"
        self.ssh_config_host = "liquid"
        
        # SSH配置路径
        if platform.system().lower() == 'windows':
            self.ssh_dir = Path.home() / '.ssh'
        else:
            self.ssh_dir = Path.home() / '.ssh'
            
        self.private_key_path = self.ssh_dir / 'liquid_server_key'
        self.public_key_path = self.ssh_dir / 'liquid_server_key.pub'
        self.ssh_config_path = self.ssh_dir / 'config'
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def log_message(self, message, level="INFO"):
        """记录日志消息"""
        if level == "ERROR":
            self.logger.error(message)
            print(f"[SSH错误] {message}")
        elif level == "WARN":
            self.logger.warning(message)
            print(f"[SSH警告] {message}")
        elif level == "SUCCESS":
            self.logger.info(message)
            print(f"[SSH成功] {message}")
        else:
            self.logger.info(message)
            print(f"[SSH信息] {message}")
    
    def test_command_exists(self, command):
        """测试命令是否存在"""
        try:
            subprocess.run([command, '--version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(['which', command] if platform.system().lower() != 'windows' else ['where', command],
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, 
                             check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False
    
    def test_network_connection(self, host_ip, count=4):
        """测试网络连接"""
        self.log_message(f"测试到 {host_ip} 的网络连接...")
        
        try:
            # 根据操作系统选择ping命令参数
            if platform.system().lower() == 'windows':
                cmd = ['ping', '-n', str(count), host_ip]
            else:
                cmd = ['ping', '-c', str(count), host_ip]
            
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True, 
                                  timeout=30)
            
            if result.returncode == 0:
                self.log_message(f"到 {host_ip} 的网络连接成功", "SUCCESS")
                return True
            else:
                self.log_message(f"到 {host_ip} 的网络连接失败", "ERROR")
                self.log_message(f"Ping输出: {result.stdout}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_message(f"网络连接测试超时", "ERROR")
            return False
        except Exception as e:
            self.log_message(f"网络测试错误: {e}", "ERROR")
            return False
    
    def check_required_commands(self):
        """检查必需的命令"""
        self.log_message("检查必需的命令...")
        required_commands = ['ssh', 'ssh-keygen', 'scp']
        
        for cmd in required_commands:
            if not self.test_command_exists(cmd):
                self.log_message(f"缺少必需的命令: {cmd}", "ERROR")
                self.log_message("请安装OpenSSH客户端", "ERROR")
                return False
        
        self.log_message("所有必需命令都已安装", "SUCCESS")
        return True
    
    def create_ssh_directory(self):
        """创建SSH目录"""
        self.log_message("创建SSH目录...")
        
        try:
            self.ssh_dir.mkdir(mode=0o700, exist_ok=True)
            self.log_message("SSH目录创建成功", "SUCCESS")
            return True
        except Exception as e:
            self.log_message(f"创建SSH目录失败: {e}", "ERROR")
            return False
    
    def generate_ssh_key(self, force=False):
        """生成SSH密钥对"""
        self.log_message("生成SSH密钥对...")
        
        if self.private_key_path.exists() and not force:
            self.log_message("SSH密钥已存在", "WARN")
            return True
        
        try:
            cmd = [
                'ssh-keygen', 
                '-t', 'rsa', 
                '-b', '4096', 
                '-f', str(self.private_key_path), 
                '-N', '',  # 空密码
                '-C', 'liquid_client'
            ]
            
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
            
            if result.returncode == 0:
                self.log_message("SSH密钥对生成成功", "SUCCESS")
                # 设置密钥文件权限
                if platform.system().lower() != 'windows':
                    os.chmod(self.private_key_path, 0o600)
                    os.chmod(self.public_key_path, 0o644)
                return True
            else:
                self.log_message(f"生成SSH密钥对失败: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log_message(f"生成SSH密钥对异常: {e}", "ERROR")
            return False
    
    def copy_public_key_to_server(self):
        """复制公钥到服务器"""
        self.log_message("复制公钥到服务器（需要输入服务器密码）...")
        
        try:
            # 使用ssh-copy-id命令（如果可用）
            if self.test_command_exists('ssh-copy-id'):
                cmd = [
                    'ssh-copy-id', 
                    '-i', str(self.public_key_path),
                    '-o', 'StrictHostKeyChecking=no',
                    f'{self.server_user}@{self.server_host}'
                ]
            else:
                # 手动复制公钥
                cmd = [
                    'scp', 
                    '-o', 'StrictHostKeyChecking=no',
                    str(self.public_key_path),
                    f'{self.server_user}@{self.server_host}:~/.ssh/authorized_keys_temp'
                ]
            
            result = subprocess.run(cmd, text=True)
            
            if result.returncode == 0:
                self.log_message("公钥复制成功", "SUCCESS")
                
                # 如果使用手动复制，需要配置服务器端
                if not self.test_command_exists('ssh-copy-id'):
                    return self.configure_server_authorized_keys()
                return True
            else:
                self.log_message("复制公钥到服务器失败", "ERROR")
                return False
                
        except Exception as e:
            self.log_message(f"复制公钥异常: {e}", "ERROR")
            return False
    
    def configure_server_authorized_keys(self):
        """配置服务器端的authorized_keys"""
        self.log_message("配置服务器端authorized_keys...")
        
        try:
            ssh_command = (
                "mkdir -p ~/.ssh; "
                "cat ~/.ssh/authorized_keys_temp >> ~/.ssh/authorized_keys; "
                "rm ~/.ssh/authorized_keys_temp; "
                "chmod 700 ~/.ssh; "
                "chmod 600 ~/.ssh/authorized_keys"
            )
            
            cmd = [
                'ssh', 
                '-o', 'StrictHostKeyChecking=no',
                f'{self.server_user}@{self.server_host}',
                ssh_command
            ]
            
            result = subprocess.run(cmd, text=True)
            
            if result.returncode == 0:
                self.log_message("服务器配置完成", "SUCCESS")
                return True
            else:
                self.log_message("服务器配置失败", "ERROR")
                return False
                
        except Exception as e:
            self.log_message(f"配置服务器异常: {e}", "ERROR")
            return False
    
    def update_ssh_config(self):
        """更新SSH配置"""
        self.log_message("更新SSH配置...")
        
        config_content = f"""
Host {self.ssh_config_host}
    HostName {self.server_host}
    User {self.server_user}
    IdentityFile {self.private_key_path}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ServerAliveInterval 60
    ServerAliveCountMax 3

"""
        
        try:
            # 检查配置是否已存在
            if self.ssh_config_path.exists():
                with open(self.ssh_config_path, 'r', encoding='utf-8') as f:
                    existing_config = f.read()
                    if f"Host {self.ssh_config_host}" in existing_config:
                        self.log_message("SSH配置已存在", "WARN")
                        return True
                
                # 追加配置
                with open(self.ssh_config_path, 'a', encoding='utf-8') as f:
                    f.write(config_content)
            else:
                # 创建新配置
                with open(self.ssh_config_path, 'w', encoding='utf-8') as f:
                    f.write(config_content)
            
            # 设置配置文件权限
            if platform.system().lower() != 'windows':
                os.chmod(self.ssh_config_path, 0o600)
            
            self.log_message("SSH配置更新成功", "SUCCESS")
            return True
            
        except Exception as e:
            self.log_message(f"更新SSH配置失败: {e}", "ERROR")
            return False
    
    def test_ssh_connection(self):
        """测试SSH连接"""
        self.log_message("测试SSH连接...")
        
        try:
            cmd = [
                'ssh', 
                '-o', 'ConnectTimeout=10',
                '-o', 'BatchMode=yes',
                self.ssh_config_host,
                'echo "Connection test successful"'
            ]
            
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True, 
                                  timeout=15)
            
            if result.returncode == 0:
                self.log_message(f"SSH免密连接测试成功: {result.stdout.strip()}", "SUCCESS")
                self.log_message(f"配置完成！现在可以使用: ssh {self.ssh_config_host}", "SUCCESS")
                return True
            else:
                self.log_message("SSH连接测试失败", "ERROR")
                self.log_message(f"错误信息: {result.stderr}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_message("SSH连接测试超时", "ERROR")
            return False
        except Exception as e:
            self.log_message(f"SSH连接测试异常: {e}", "ERROR")
            return False
    
    def setup_ssh_connection(self, force=False):
        """设置SSH免密连接"""
        self.log_message("开始设置SSH免密连接...")
        
        # 1. 测试网络连接
        if not self.test_network_connection(self.server_host):
            self.log_message(f"无法连接到服务器 {self.server_host}，中止SSH配置", "ERROR")
            return False
        
        # 2. 检查必需命令
        if not self.check_required_commands():
            return False
        
        # 3. 创建SSH目录
        if not self.create_ssh_directory():
            return False
        
        # 4. 生成SSH密钥对
        if not self.generate_ssh_key(force):
            return False
        
        # 5. 复制公钥到服务器
        if not self.copy_public_key_to_server():
            return False
        
        # 6. 更新SSH配置
        if not self.update_ssh_config():
            return False
        
        # 7. 测试SSH连接
        if not self.test_ssh_connection():
            self.log_message("SSH配置完成但连接测试失败，请手动检查配置", "WARN")
            return False
        
        self.log_message("SSH免密连接设置完成", "SUCCESS")
        return True
    
    def is_ssh_configured(self):
        """检查SSH是否已配置"""
        return (self.private_key_path.exists() and 
                self.public_key_path.exists() and 
                self.ssh_config_path.exists())
    
    def execute_remote_command(self, command, timeout=30):
        """执行远程命令"""
        try:
            cmd = ['ssh', self.ssh_config_host, command]
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True, 
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=timeout)
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timeout',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def check_remote_services(self):
        """检查远程服务状态"""
        self.log_message("检查远程服务状态...")
        
        services = {
            'go_api': {
                'command': 'pgrep -f "liquid-api" || echo "not_running"',
                'port': 8084,
                'name': 'Go API服务'
            },
            'python_inference': {
                'command': 'pgrep -f "python.*8085" || echo "not_running"',
                'port': 8085,
                'name': 'Python推理服务'
            }
        }
        
        status = {}
        
        for service_key, service_info in services.items():
            result = self.execute_remote_command(service_info['command'])
            
            if result['success']:
                output = result['stdout'].strip()
                if output and output != 'not_running':
                    status[service_key] = True
                    self.log_message(f"{service_info['name']} 正在运行 (PID: {output})", "SUCCESS")
                else:
                    status[service_key] = False
                    self.log_message(f"{service_info['name']} 未运行", "WARN")
            else:
                status[service_key] = False
                self.log_message(f"检查 {service_info['name']} 失败: {result['stderr']}", "ERROR")
        
        return status