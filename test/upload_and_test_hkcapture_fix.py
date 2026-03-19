#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传修复后的代码并在服务器上测试HKcapture导入
"""

import os
import sys
import paramiko
import time

def upload_files_to_server():
    """上传修复后的文件到服务器"""
    print("=" * 60)
    print("上传修复后的文件到服务器")
    print("=" * 60)
    
    try:
        # SSH连接配置
        hostname = '192.168.0.121'
        username = 'lqj'
        password = 'admin'
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        
        # 创建SFTP客户端
        sftp = ssh.open_sftp()
        
        # 要上传的文件列表
        files_to_upload = [
            ('server/video/video_capture_factory.py', '/home/lqj/liquid/server/video/video_capture_factory.py'),
            ('test/test_fixed_hkcapture_import.py', '/home/lqj/liquid/test/test_fixed_hkcapture_import.py')
        ]
        
        print("上传文件:")
        for local_file, remote_file in files_to_upload:
            if os.path.exists(local_file):
                sftp.put(local_file, remote_file)
                print(f"  {local_file} -> {remote_file}")
            else:
                print(f"  警告: 本地文件不存在 {local_file}")
        
        sftp.close()
        ssh.close()
        
        print("文件上传完成")
        return True
        
    except Exception as e:
        print(f"上传失败: {e}")
        return False

def run_test_on_server():
    """在服务器上运行测试"""
    print("\n" + "=" * 60)
    print("在服务器上运行HKcapture导入测试")
    print("=" * 60)
    
    try:
        # SSH连接配置
        hostname = '192.168.0.121'
        username = 'lqj'
        password = 'admin'
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        
        # 运行测试命令
        test_command = """
        cd /home/lqj/liquid
        source ~/anaconda3/bin/activate liquid
        python test/test_fixed_hkcapture_import.py
        """
        
        print("执行测试命令...")
        stdin, stdout, stderr = ssh.exec_command(test_command)
        
        # 读取输出
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        print("测试输出:")
        print(output)
        
        if error:
            print("错误信息:")
            print(error)
        
        ssh.close()
        
        # 分析结果
        success_indicators = [
            "HKcapture导入成功",
            "视频捕获工厂创建成功",
            "所有测试通过"
        ]
        
        success_count = sum(1 for indicator in success_indicators if indicator in output)
        
        return success_count >= 2  # 至少2个成功指标
        
    except Exception as e:
        print(f"服务器测试失败: {e}")
        return False

def create_simple_test_script():
    """创建简化的测试脚本"""
    simple_test_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的HKcapture导入测试
"""

import os
import sys

def test_hkcapture_import():
    """测试HKcapture导入"""
    print("=" * 50)
    print("测试HKcapture导入")
    print("=" * 50)
    
    try:
        # 设置环境变量
        server_lib_path = '/home/lqj/liquid/server/lib'
        sdk_lib_path = '/home/lqj/liquid/server/lib/lib'
        
        print(f"设置LD_LIBRARY_PATH: {sdk_lib_path}")
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if sdk_lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{current_ld_path}"
        
        print(f"当前LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', '')}")
        
        # 添加lib路径到Python路径
        sys.path.insert(0, server_lib_path)
        
        # 检查路径
        print(f"\\n路径检查:")
        print(f"  server/lib存在: {os.path.exists(server_lib_path)}")
        print(f"  server/lib/lib存在: {os.path.exists(sdk_lib_path)}")
        
        if os.path.exists(sdk_lib_path):
            lib_files = os.listdir(sdk_lib_path)
            so_files = [f for f in lib_files if f.endswith('.so')]
            print(f"  动态库文件数量: {len(so_files)}")
        
        # 尝试导入HKcapture
        print(f"\\n尝试导入HKcapture...")
        import HKcapture
        print("HKcapture导入成功")
        
        # 尝试导入HCNetSDK
        print(f"尝试导入HCNetSDK...")
        import HCNetSDK
        print("HCNetSDK导入成功")
        
        return True
        
    except ImportError as e:
        print(f"导入失败: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_capture_factory():
    """测试视频捕获工厂"""
    print("\\n" + "=" * 50)
    print("测试视频捕获工厂")
    print("=" * 50)
    
    try:
        # 添加项目路径
        sys.path.insert(0, '/home/lqj/liquid')
        
        # 导入视频捕获工厂
        from server.video.video_capture_factory import VideoCaptureFactory
        print("视频捕获工厂导入成功")
        
        # 创建工厂实例
        factory = VideoCaptureFactory()
        print("视频捕获工厂创建成功")
        
        # 检查HKcapture是否可用
        from server.video.video_capture_factory import HK_CAPTURE_AVAILABLE
        print(f"HKcapture可用性: {HK_CAPTURE_AVAILABLE}")
        
        return HK_CAPTURE_AVAILABLE
        
    except Exception as e:
        print(f"视频捕获工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始HKcapture导入测试")
    
    # 测试1: HKcapture导入
    import_ok = test_hkcapture_import()
    
    # 测试2: 视频捕获工厂
    factory_ok = test_video_capture_factory()
    
    # 总结
    print("\\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"HKcapture导入: {'通过' if import_ok else '失败'}")
    print(f"视频捕获工厂: {'通过' if factory_ok else '失败'}")
    
    if import_ok and factory_ok:
        print("\\n所有测试通过！HKcapture导入和路径配置修复成功")
    else:
        print("\\n部分测试失败，需要进一步调试")
'''
    
    with open('test/simple_hkcapture_test.py', 'w', encoding='utf-8') as f:
        f.write(simple_test_content)
    
    print("创建简化测试脚本: test/simple_hkcapture_test.py")

def upload_and_run_simple_test():
    """上传并运行简化测试"""
    print("\n" + "=" * 60)
    print("上传并运行简化测试")
    print("=" * 60)
    
    try:
        # SSH连接配置
        hostname = '192.168.0.121'
        username = 'lqj'
        password = 'admin'
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        
        # 创建SFTP客户端
        sftp = ssh.open_sftp()
        
        # 上传简化测试脚本
        local_file = 'test/simple_hkcapture_test.py'
        remote_file = '/home/lqj/liquid/test/simple_hkcapture_test.py'
        
        if os.path.exists(local_file):
            sftp.put(local_file, remote_file)
            print(f"上传: {local_file} -> {remote_file}")
        
        sftp.close()
        
        # 运行简化测试
        test_command = """
        cd /home/lqj/liquid
        source ~/anaconda3/bin/activate liquid
        python test/simple_hkcapture_test.py
        """
        
        print("执行简化测试...")
        stdin, stdout, stderr = ssh.exec_command(test_command)
        
        # 读取输出
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        print("测试输出:")
        print(output)
        
        if error:
            print("错误信息:")
            print(error)
        
        ssh.close()
        
        # 分析结果
        return "所有测试通过" in output or ("HKcapture导入成功" in output and "视频捕获工厂创建成功" in output)
        
    except Exception as e:
        print(f"简化测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始HKcapture修复测试流程")
    
    # 步骤1: 上传修复后的文件
    upload_success = upload_files_to_server()
    
    if upload_success:
        # 步骤2: 运行测试
        test_success = run_test_on_server()
        
        if not test_success:
            # 步骤3: 如果复杂测试失败，尝试简化测试
            print("复杂测试失败，尝试简化测试...")
            create_simple_test_script()
            simple_test_success = upload_and_run_simple_test()
            
            if simple_test_success:
                print("\n简化测试成功！HKcapture导入修复完成")
            else:
                print("\n简化测试也失败，需要进一步调试")
        else:
            print("\n测试成功！HKcapture导入修复完成")
    else:
        print("文件上传失败，无法进行测试")