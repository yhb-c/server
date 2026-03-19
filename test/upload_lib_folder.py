#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传lib文件夹到服务端
"""

import os
import subprocess
import time

def upload_lib_folder():
    """上传lib文件夹到服务端"""
    print("=== 上传lib文件夹到服务端 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 本地lib文件夹路径
    local_lib_path = "server/lib"
    
    # 服务端目标路径
    remote_server_path = "/home/lqj/liquid/server"
    
    # 检查本地lib文件夹是否存在
    if not os.path.exists(local_lib_path):
        print(f"✗ 本地lib文件夹不存在: {local_lib_path}")
        return False
    
    print(f"本地lib文件夹: {local_lib_path}")
    print(f"服务端目标路径: {remote_server_path}")
    
    try:
        # 先删除服务端的lib文件夹（如果存在）
        print("删除服务端现有的lib文件夹...")
        ssh_cmd = f'ssh {username}@{server_ip} "rm -rf {remote_server_path}/lib"'
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ 服务端lib文件夹已删除")
        else:
            print(f"删除服务端lib文件夹失败: {result.stderr}")
        
        # 使用scp上传整个lib文件夹
        print("开始上传lib文件夹...")
        scp_cmd = f'scp -r "{local_lib_path}" {username}@{server_ip}:"{remote_server_path}/"'
        
        print(f"执行命令: {scp_cmd}")
        
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✓ lib文件夹上传成功")
            
            # 验证上传结果
            print("验证上传结果...")
            verify_cmd = f'ssh {username}@{server_ip} "ls -la {remote_server_path}/lib/"'
            verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if verify_result.returncode == 0:
                print("上传验证结果:")
                print(verify_result.stdout)
            else:
                print(f"验证失败: {verify_result.stderr}")
            
            return True
        else:
            print(f"✗ lib文件夹上传失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 上传超时")
        return False
    except Exception as e:
        print(f"✗ 上传异常: {e}")
        return False

def check_so_files_after_upload():
    """检查上传后的.so文件"""
    print("\n=== 检查上传后的.so文件 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    commands = [
        ("检查lib/lib目录", "ls -la /home/lqj/liquid/server/lib/lib/"),
        ("查找所有.so文件", "find /home/lqj/liquid/server/lib -name '*.so' -type f"),
        ("检查关键.so文件", "ls -la /home/lqj/liquid/server/lib/lib/lib*.so"),
        ("检查文件权限", "ls -la /home/lqj/liquid/server/lib/lib/ | grep -E '\\.(so|dll)$'")
    ]
    
    for desc, cmd in commands:
        print(f"\n{desc}:")
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"错误: {result.stderr}")
                
        except Exception as e:
            print(f"检查异常: {e}")

def set_lib_permissions():
    """设置lib文件权限"""
    print("\n=== 设置lib文件权限 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    commands = [
        "chmod -R 755 /home/lqj/liquid/server/lib/",
        "chmod +x /home/lqj/liquid/server/lib/lib/*.so 2>/dev/null || true"
    ]
    
    for cmd in commands:
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        print(f"执行: {cmd}")
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print("✓ 权限设置成功")
            else:
                print(f"权限设置失败: {result.stderr}")
        except Exception as e:
            print(f"权限设置异常: {e}")

def main():
    """主函数"""
    print("开始上传lib文件夹到服务端")
    
    try:
        # 1. 上传lib文件夹
        if upload_lib_folder():
            # 2. 设置文件权限
            set_lib_permissions()
            
            # 3. 检查上传结果
            check_so_files_after_upload()
            
            print("\nlib文件夹上传完成")
        else:
            print("lib文件夹上传失败")
            
    except Exception as e:
        print(f"上传过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()