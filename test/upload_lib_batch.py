#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分批上传lib文件夹到服务端
"""

import os
import subprocess
import time

def upload_lib_files_batch():
    """分批上传lib文件"""
    print("=== 分批上传lib文件到服务端 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 本地lib文件夹路径
    local_lib_path = "server/lib"
    
    # 服务端目标路径
    remote_lib_path = "/home/lqj/liquid/server/lib"
    
    # 检查本地lib文件夹是否存在
    if not os.path.exists(local_lib_path):
        print(f"✗ 本地lib文件夹不存在: {local_lib_path}")
        return False
    
    try:
        # 1. 创建服务端lib目录
        print("创建服务端lib目录...")
        ssh_cmd = f'ssh {username}@{server_ip} "mkdir -p {remote_lib_path}"'
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ 服务端lib目录创建成功")
        else:
            print(f"创建目录失败: {result.stderr}")
        
        # 2. 上传Python文件
        print("上传Python文件...")
        python_files = [f for f in os.listdir(local_lib_path) if f.endswith('.py')]
        
        for py_file in python_files:
            local_file = os.path.join(local_lib_path, py_file)
            remote_file = f"{remote_lib_path}/{py_file}"
            
            scp_cmd = f'scp "{local_file}" {username}@{server_ip}:"{remote_file}"'
            print(f"上传: {py_file}")
            
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"  ✓ {py_file} 上传成功")
            else:
                print(f"  ✗ {py_file} 上传失败: {result.stderr}")
        
        # 3. 上传其他文件
        print("上传其他文件...")
        other_files = [f for f in os.listdir(local_lib_path) if not f.endswith('.py') and os.path.isfile(os.path.join(local_lib_path, f))]
        
        for other_file in other_files:
            local_file = os.path.join(local_lib_path, other_file)
            remote_file = f"{remote_lib_path}/{other_file}"
            
            scp_cmd = f'scp "{local_file}" {username}@{server_ip}:"{remote_file}"'
            print(f"上传: {other_file}")
            
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"  ✓ {other_file} 上传成功")
            else:
                print(f"  ✗ {other_file} 上传失败: {result.stderr}")
        
        # 4. 上传lib子目录
        lib_lib_path = os.path.join(local_lib_path, "lib")
        if os.path.exists(lib_lib_path):
            print("上传lib/lib目录...")
            
            # 创建远程lib/lib目录
            ssh_cmd = f'ssh {username}@{server_ip} "mkdir -p {remote_lib_path}/lib"'
            subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            # 上传.so文件
            so_files = [f for f in os.listdir(lib_lib_path) if f.endswith('.so')]
            print(f"找到 {len(so_files)} 个.so文件")
            
            for so_file in so_files:
                local_so = os.path.join(lib_lib_path, so_file)
                remote_so = f"{remote_lib_path}/lib/{so_file}"
                
                scp_cmd = f'scp "{local_so}" {username}@{server_ip}:"{remote_so}"'
                print(f"上传: {so_file}")
                
                result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print(f"  ✓ {so_file} 上传成功")
                else:
                    print(f"  ✗ {so_file} 上传失败: {result.stderr}")
            
            # 上传其他重要文件
            important_files = [f for f in os.listdir(lib_lib_path) 
                             if f.endswith(('.dll', '.lib', '.xml', '.dat', '.zip')) and os.path.isfile(os.path.join(lib_lib_path, f))]
            
            print(f"上传其他重要文件: {len(important_files)} 个")
            for imp_file in important_files:
                local_imp = os.path.join(lib_lib_path, imp_file)
                remote_imp = f"{remote_lib_path}/lib/{imp_file}"
                
                scp_cmd = f'scp "{local_imp}" {username}@{server_ip}:"{remote_imp}"'
                print(f"上传: {imp_file}")
                
                result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print(f"  ✓ {imp_file} 上传成功")
                else:
                    print(f"  ✗ {imp_file} 上传失败")
        
        return True
        
    except Exception as e:
        print(f"✗ 上传异常: {e}")
        return False

def verify_upload():
    """验证上传结果"""
    print("\n=== 验证上传结果 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    commands = [
        ("检查lib目录", "ls -la /home/lqj/liquid/server/lib/"),
        ("检查.so文件", "find /home/lqj/liquid/server/lib -name '*.so' -type f"),
        ("检查Python文件", "ls -la /home/lqj/liquid/server/lib/*.py"),
        ("检查lib/lib目录", "ls -la /home/lqj/liquid/server/lib/lib/ | head -20")
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
            print(f"验证异常: {e}")

def main():
    """主函数"""
    print("开始分批上传lib文件夹到服务端")
    
    try:
        # 1. 分批上传文件
        if upload_lib_files_batch():
            print("\n分批上传完成")
            
            # 2. 验证上传结果
            verify_upload()
        else:
            print("分批上传失败")
            
    except Exception as e:
        print(f"上传过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()