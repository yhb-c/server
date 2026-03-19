#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试海康SDK视频捕获功能
使用HKcapture.py专门的海康捕获类
"""

import os
import sys
import subprocess
import time
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_hikvision_test_script():
    """创建海康SDK测试脚本"""
    print("=== 创建海康SDK测试脚本 ===")
    
    test_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康SDK视频捕获测试
"""

import os
import sys
import time
import logging
import json

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_hikvision_environment():
    """设置海康SDK环境"""
    logger.info("=== 设置海康SDK环境 ===")
    
    # 设置库路径
    lib_path = "/home/lqj/liquid/server/lib/lib"
    
    # 检查库文件是否存在
    required_libs = [
        "libhcnetsdk.so",
        "libHCCore.so", 
        "libPlayCtrl.so"
    ]
    
    missing_libs = []
    for lib in required_libs:
        lib_file = os.path.join(lib_path, lib)
        if os.path.exists(lib_file):
            logger.info(f"找到库文件: {lib}")
        else:
            missing_libs.append(lib)
            logger.error(f"缺少库文件: {lib}")
    
    if missing_libs:
        logger.error(f"缺少必要的库文件: {missing_libs}")
        return False
    
    # 设置LD_LIBRARY_PATH
    current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
    if lib_path not in current_ld_path:
        os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{current_ld_path}"
        logger.info(f"设置LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
    
    # 添加lib目录到Python路径
    sys.path.insert(0, "/home/lqj/liquid/server/lib")
    
    return True

def test_hkcapture_import():
    """测试HKcapture导入"""
    logger.info("=== 测试HKcapture导入 ===")
    
    try:
        from HKcapture import HKcapture
        logger.info("HKcapture导入成功")
        return True
    except Exception as e:
        logger.error(f"HKcapture导入失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_hkcapture_basic():
    """测试HKcapture基本功能"""
    logger.info("=== 测试HKcapture基本功能 ===")
    
    try:
        from HKcapture import HKcapture
        
        # 相机参数
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        
        logger.info(f"创建HKcapture实例: {rtsp_url}")
        
        # 创建捕获器实例
        capture = HKcapture(
            source=rtsp_url,
            username="admin",
            password="cei345678",
            port=8000,
            channel=1,
            fps=25,
            debug=True
        )
        
        logger.info("HKcapture实例创建成功")
        
        # 打开连接
        logger.info("尝试打开连接...")
        if capture.open():
            logger.info("连接打开成功")
            
            # 启动捕获
            logger.info("尝试启动捕获...")
            if capture.start_capture():
                logger.info("捕获启动成功")
                
                # 启用YUV队列
                capture.enable_yuv_queue(enabled=True, interval=0.1)
                logger.info("YUV队列已启用")
                
                # 等待一段时间让数据流稳定
                time.sleep(3)
                
                # 尝试获取帧数据
                frame_count = 0
                success_count = 0
                
                for i in range(10):
                    try:
                        yuv_data = capture.get_yuv_data(timeout=1.0)
                        frame_count += 1
                        
                        if yuv_data:
                            success_count += 1
                            logger.info(f"成功获取第{frame_count}帧 YUV数据: {yuv_data['width']}x{yuv_data['height']}")
                        else:
                            logger.warning(f"第{frame_count}帧 YUV数据为空")
                            
                    except Exception as e:
                        logger.error(f"获取第{frame_count+1}帧失败: {e}")
                        frame_count += 1
                    
                    time.sleep(0.2)
                
                logger.info(f"帧获取测试完成 - 总帧数: {frame_count}, 成功: {success_count}")
                
                # 停止捕获
                capture.stop_capture()
                logger.info("捕获已停止")
                
                # 释放资源
                capture.release()
                logger.info("资源已释放")
                
                return success_count > 0
                
            else:
                logger.error("捕获启动失败")
                capture.release()
                return False
        else:
            logger.error("连接打开失败")
            return False
            
    except Exception as e:
        logger.error(f"HKcapture测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_hkcapture_read_method():
    """测试HKcapture的read方法"""
    logger.info("=== 测试HKcapture的read方法 ===")
    
    try:
        from HKcapture import HKcapture
        
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        
        capture = HKcapture(
            source=rtsp_url,
            username="admin", 
            password="cei345678",
            debug=True
        )
        
        if capture.open() and capture.start_capture():
            logger.info("HKcapture启动成功，测试read方法")
            
            # 等待数据流稳定
            time.sleep(2)
            
            success_count = 0
            for i in range(5):
                try:
                    frame = capture.read()
                    if frame is not None:
                        success_count += 1
                        logger.info(f"read方法成功获取第{i+1}帧: {frame.shape}")
                    else:
                        logger.warning(f"read方法第{i+1}帧返回None")
                except Exception as e:
                    logger.error(f"read方法第{i+1}帧异常: {e}")
                
                time.sleep(0.5)
            
            capture.stop_capture()
            capture.release()
            
            return success_count > 0
        else:
            logger.error("HKcapture启动失败")
            return False
            
    except Exception as e:
        logger.error(f"read方法测试异常: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始测试海康SDK视频捕获功能")
    
    results = {}
    
    # 1. 设置环境
    results['environment_setup'] = setup_hikvision_environment()
    
    if not results['environment_setup']:
        logger.error("环境设置失败，跳过后续测试")
        results['hkcapture_import'] = False
        results['hkcapture_basic'] = False
        results['hkcapture_read'] = False
    else:
        # 2. 测试导入
        results['hkcapture_import'] = test_hkcapture_import()
        
        if results['hkcapture_import']:
            # 3. 测试基本功能
            results['hkcapture_basic'] = test_hkcapture_basic()
            
            # 4. 测试read方法
            results['hkcapture_read'] = test_hkcapture_read_method()
        else:
            results['hkcapture_basic'] = False
            results['hkcapture_read'] = False
    
    # 输出测试结果
    logger.info("=== 海康SDK测试结果汇总 ===")
    for test_name, result in results.items():
        status = "成功" if result else "失败"
        logger.info(f"{test_name}: {status}")
    
    # 保存结果到文件
    result_file = "/home/lqj/liquid/hikvision_sdk_test_result.json"
    try:
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"测试结果已保存到: {result_file}")
    except Exception as e:
        logger.error(f"保存测试结果失败: {e}")

if __name__ == "__main__":
    main()
'''
    
    # 保存测试脚本
    script_path = "test/hikvision_sdk_test.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print(f"海康SDK测试脚本已创建: {script_path}")
    return script_path

def upload_and_run_hikvision_test():
    """上传并运行海康SDK测试"""
    print("\n=== 上传并运行海康SDK测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 创建测试脚本
    script_path = create_hikvision_test_script()
    
    # 上传测试脚本
    remote_script = "/home/lqj/liquid/hikvision_sdk_test.py"
    scp_cmd = f'scp "{script_path}" {username}@{server_ip}:"{remote_script}"'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✓ 海康SDK测试脚本上传成功")
        else:
            print(f"✗ 测试脚本上传失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 上传测试脚本异常: {e}")
        return False
    
    # 设置脚本权限并执行
    ssh_commands = [
        f"chmod +x {remote_script}",
        f"cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH && python {remote_script}"
    ]
    
    for i, cmd in enumerate(ssh_commands):
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        print(f"执行命令 {i+1}: {cmd}")
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=120, encoding='utf-8', errors='ignore')
            
            print(f"返回码: {result.returncode}")
            if result.stdout:
                print(f"输出:\n{result.stdout}")
            if result.stderr:
                print(f"错误:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("命令执行超时")
        except Exception as e:
            print(f"命令执行异常: {e}")
    
    return True

def check_hikvision_test_results():
    """检查海康SDK测试结果"""
    print("\n=== 检查海康SDK测试结果 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 检查结果文件
    check_cmd = "cat /home/lqj/liquid/hikvision_sdk_test_result.json 2>/dev/null || echo '结果文件不存在'"
    ssh_cmd = f'ssh {username}@{server_ip} "{check_cmd}"'
    
    try:
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        if result.stdout:
            print("海康SDK测试结果:")
            print(result.stdout)
        else:
            print("无法获取测试结果")
            
    except Exception as e:
        print(f"检查结果异常: {e}")

def main():
    """主函数"""
    print("开始测试海康SDK视频捕获功能")
    
    try:
        # 1. 上传并运行海康SDK测试
        if upload_and_run_hikvision_test():
            # 2. 等待测试完成
            print("\n等待测试完成...")
            time.sleep(10)
            
            # 3. 检查测试结果
            check_hikvision_test_results()
        else:
            print("海康SDK测试上传失败")
            
    except Exception as e:
        print(f"测试过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()