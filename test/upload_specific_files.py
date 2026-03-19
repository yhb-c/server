#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传特定修复文件的脚本
"""

import subprocess
import os

def upload_file(local_file, remote_file):
    """上传单个文件到服务器"""
    print(f"上传: {local_file} -> {remote_file}")
    
    # 使用scp命令上传文件
    scp_cmd = [
        'scp',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        local_file,
        f"lqj@192.168.0.121:{remote_file}"
    ]
    
    try:
        # 创建expect脚本
        expect_script = f'''#!/usr/bin/expect -f
set timeout 60
spawn {' '.join(scp_cmd)}
expect {{
    "*password*" {{ send "admin\\r"; exp_continue }}
    "*Password*" {{ send "admin\\r"; exp_continue }}
    "*(yes/no)*" {{ send "yes\\r"; exp_continue }}
    "*Are you sure*" {{ send "yes\\r"; exp_continue }}
    eof
}}
'''
        
        with open('temp_upload.exp', 'w') as f:
            f.write(expect_script)
        
        os.chmod('temp_upload.exp', 0o755)
        
        # 运行expect脚本
        result = subprocess.run(['expect', 'temp_upload.exp'], 
                              capture_output=True, text=True, timeout=60)
        
        # 清理临时文件
        os.remove('temp_upload.exp')
        
        if result.returncode == 0:
            print(f"  上传成功")
            return True
        else:
            print(f"  上传失败: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("  expect命令不可用，请手动上传文件")
        return False
    except Exception as e:
        print(f"  上传异常: {e}")
        return False

def run_remote_test():
    """在服务器上运行测试"""
    print("\n在服务器上运行测试...")
    
    ssh_cmd = [
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        'lqj@192.168.0.121',
        'cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && python test/simple_hkcapture_test.py'
    ]
    
    try:
        # 创建expect脚本
        expect_script = f'''#!/usr/bin/expect -f
set timeout 120
spawn {' '.join(ssh_cmd)}
expect {{
    "*password*" {{ send "admin\\r"; exp_continue }}
    "*Password*" {{ send "admin\\r"; exp_continue }}
    "*(yes/no)*" {{ send "yes\\r"; exp_continue }}
    "*Are you sure*" {{ send "yes\\r"; exp_continue }}
    eof
}}
'''
        
        with open('temp_test.exp', 'w') as f:
            f.write(expect_script)
        
        os.chmod('temp_test.exp', 0o755)
        
        # 运行expect脚本
        result = subprocess.run(['expect', 'temp_test.exp'], 
                              capture_output=True, text=True, timeout=120)
        
        # 清理临时文件
        os.remove('temp_test.exp')
        
        print("测试输出:")
        print(result.stdout)
        
        if result.stderr:
            print("错误信息:")
            print(result.stderr)
        
        return "所有测试通过" in result.stdout
        
    except Exception as e:
        print(f"远程测试异常: {e}")
        return False

if __name__ == "__main__":
    print("上传HKcapture修复文件")
    print("=" * 50)
    
    # 要上传的文件列表
    files_to_upload = [
        ('server/video/video_capture_factory.py', '/home/lqj/liquid/server/video/video_capture_factory.py'),
        ('test/simple_hkcapture_test.py', '/home/lqj/liquid/test/simple_hkcapture_test.py')
    ]
    
    success_count = 0
    
    for local_file, remote_file in files_to_upload:
        if os.path.exists(local_file):
            if upload_file(local_file, remote_file):
                success_count += 1
        else:
            print(f"本地文件不存在: {local_file}")
    
    print(f"\n上传完成: {success_count}/{len(files_to_upload)}")
    
    if success_count == len(files_to_upload):
        # 运行远程测试
        test_success = run_remote_test()
        
        if test_success:
            print("\n测试成功！HKcapture导入修复完成")
        else:
            print("\n测试失败，需要进一步调试")
    else:
        print("文件上传不完整，跳过测试")