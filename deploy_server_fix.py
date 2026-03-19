#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
服务器部署修复脚本
解决WebSocket服务器端口占用问题，确保启动正确的增强服务器
"""

import paramiko
import time
import sys
from pathlib import Path

class ServerDeployFixer:
    """服务器部署修复工具"""
    
    def __init__(self):
        self.server_ip = '192.168.0.121'
        self.username = 'lqj'
        self.password = 'admin'
        self.server_path = '/home/lqj/liquid/server'
        
    def connect_server(self):
        """连接服务器"""
        try:
            print(f"连接服务器 {self.server_ip}...")
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=self.server_ip,
                username=self.username,
                password=self.password,
                timeout=10
            )
            print("✓ 服务器连接成功")
            return True
        except Exception as e:
            print(f"✗ 服务器连接失败: {e}")
            return False
    
    def execute_command(self, command, timeout=30):
        """执行服务器命令"""
        try:
            print(f"执行命令: {command}")
            stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
            
            # 读取输出
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            if output:
                print(f"输出: {output}")
            if error:
                print(f"错误: {error}")
                
            return exit_code == 0, output, error
            
        except Exception as e:
            print(f"命令执行异常: {e}")
            return False, "", str(e)
    
    def stop_old_websocket_server(self):
        """停止旧的WebSocket服务器"""
        print("\n=== 停止旧的WebSocket服务器 ===")
        
        # 查找占用8085端口的进程
        success, output, error = self.execute_command("lsof -ti:8085")
        
        if success and output.strip():
            pids = output.strip().split('\n')
            print(f"发现占用端口8085的进程: {pids}")
            
            for pid in pids:
                if pid:
                    print(f"停止进程 PID: {pid}")
                    self.execute_command(f"kill -9 {pid}")
            
            # 等待进程完全停止
            time.sleep(3)
            
            # 再次检查端口
            success, output, error = self.execute_command("lsof -ti:8085")
            if not output.strip():
                print("✓ 端口8085已释放")
                return True
            else:
                print("✗ 端口8085仍被占用")
                return False
        else:
            print("✓ 端口8085未被占用")
            return True
    
    def upload_fixed_files(self):
        """上传修复的文件"""
        print("\n=== 上传修复的文件 ===")
        
        try:
            # 创建SFTP连接
            sftp = self.ssh.open_sftp()
            
            # 上传修复的detection_service.py
            local_file = "server/websocket/detection_service.py"
            remote_file = f"{self.server_path}/websocket/detection_service.py"
            
            print(f"上传文件: {local_file} -> {remote_file}")
            sftp.put(local_file, remote_file)
            
            # 上传新的启动脚本
            local_file = "server/start_enhanced_server.py"
            remote_file = f"{self.server_path}/start_enhanced_server.py"
            
            print(f"上传文件: {local_file} -> {remote_file}")
            sftp.put(local_file, remote_file)
            
            # 设置执行权限
            self.execute_command(f"chmod +x {self.server_path}/start_enhanced_server.py")
            
            sftp.close()
            print("✓ 文件上传完成")
            return True
            
        except Exception as e:
            print(f"✗ 文件上传失败: {e}")
            return False
    
    def start_enhanced_server(self):
        """启动增强WebSocket服务器"""
        print("\n=== 启动增强WebSocket服务器 ===")
        
        # 激活conda环境并启动服务器
        command = f"""
        cd {self.server_path} && 
        source ~/anaconda3/bin/activate liquid && 
        python start_enhanced_server.py
        """
        
        print("启动增强WebSocket服务器...")
        print("注意: 服务器将在后台运行，请查看服务器控制台输出")
        
        # 使用nohup在后台启动
        bg_command = f"""
        cd {self.server_path} && 
        source ~/anaconda3/bin/activate liquid && 
        nohup python start_enhanced_server.py > websocket_server.log 2>&1 &
        """
        
        success, output, error = self.execute_command(bg_command)
        
        if success:
            print("✓ 增强WebSocket服务器启动命令已执行")
            
            # 等待服务器启动
            time.sleep(5)
            
            # 检查服务器是否启动成功
            success, output, error = self.execute_command("lsof -ti:8085")
            if output.strip():
                print("✓ WebSocket服务器启动成功，端口8085已监听")
                return True
            else:
                print("✗ WebSocket服务器可能启动失败，端口8085未监听")
                # 查看日志
                self.execute_command(f"tail -20 {self.server_path}/websocket_server.log")
                return False
        else:
            print(f"✗ 启动命令执行失败: {error}")
            return False
    
    def check_server_status(self):
        """检查服务器状态"""
        print("\n=== 检查服务器状态 ===")
        
        # 检查端口监听
        print("检查端口监听状态:")
        self.execute_command("netstat -tlnp | grep :8085")
        
        # 检查进程
        print("\n检查WebSocket进程:")
        self.execute_command("ps aux | grep websocket")
        
        # 查看最新日志
        print("\n查看服务器日志:")
        self.execute_command(f"tail -10 {self.server_path}/websocket_server.log")
    
    def run_fix(self):
        """执行修复流程"""
        print("开始服务器WebSocket修复流程...")
        
        if not self.connect_server():
            return False
        
        try:
            # 步骤1: 停止旧服务器
            if not self.stop_old_websocket_server():
                print("警告: 停止旧服务器失败，继续执行...")
            
            # 步骤2: 上传修复文件
            if not self.upload_fixed_files():
                print("✗ 文件上传失败，修复中止")
                return False
            
            # 步骤3: 启动新服务器
            if not self.start_enhanced_server():
                print("✗ 启动新服务器失败")
                return False
            
            # 步骤4: 检查状态
            self.check_server_status()
            
            print("\n=== 修复完成 ===")
            print("请运行客户端测试脚本验证WebSocket连接")
            return True
            
        finally:
            self.ssh.close()

def main():
    """主函数"""
    fixer = ServerDeployFixer()
    
    try:
        success = fixer.run_fix()
        if success:
            print("\n✓ 服务器WebSocket修复成功")
            print("现在可以运行测试脚本验证功能")
        else:
            print("\n✗ 服务器WebSocket修复失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n用户中断修复流程")
    except Exception as e:
        print(f"\n修复流程异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()